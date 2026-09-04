"""Per-player career totals, team splits, and game logs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Annotated, ClassVar

import pyarrow as pa
from vgi.arguments import Arg
from vgi.metadata import FunctionExample
from vgi.table_function import (
    ProcessParams,
    TableCardinality,
    TableFunctionGenerator,
    bind_fixed_schema,
    init_single_worker,
)
from vgi_rpc.rpc import OutputCollector

from vgi_mlb import api
from vgi_mlb.meta import result_columns_schema
from vgi_mlb.player_schemas import (
    BATTING_GAME_LOG_SCHEMA,
    BATTING_SCHEMA,
    PITCHING_GAME_LOG_SCHEMA,
    PITCHING_SCHEMA,
    batch_from_rows,
    flatten_batting,
    flatten_batting_game_log,
    flatten_pitching,
    flatten_pitching_game_log,
)
from vgi_mlb.player_stats import GAME_TYPES, _cache_control

_PLAYER_ID = Arg(0, arrow_type=pa.int32(), ge=1, doc="Stable MLB player identifier.")
_GAME_TYPE = Arg(
    "game_type",
    default="R",
    arrow_type=pa.string(),
    choices=tuple(GAME_TYPES),
    doc="R regular season, S spring training, P postseason, or a specific postseason round.",
)


@dataclass(kw_only=True)
class CareerArgs:
    """Arguments for one player's career totals."""

    player_id: Annotated[int, _PLAYER_ID]
    game_type: Annotated[str, _GAME_TYPE]


@dataclass(kw_only=True)
class TeamSplitArgs:
    """Arguments for one player's team-by-team season lines."""

    player_id: Annotated[int, _PLAYER_ID]
    season: Annotated[int, Arg(1, arrow_type=pa.int32(), ge=1876, doc="Season year to split by team.")]
    game_type: Annotated[str, _GAME_TYPE]


@dataclass(kw_only=True)
class GameLogArgs:
    """Arguments for one player's per-game log."""

    player_id: Annotated[int, _PLAYER_ID]
    season: Annotated[
        int | None,
        Arg(
            "season",
            default=None,
            arrow_type=pa.int32(),
            ge=1876,
            doc="Season year; NULL selects the current season.",
        ),
    ]
    game_type: Annotated[str, _GAME_TYPE]
    start_date: Annotated[
        date | None,
        Arg("start_date", default=None, arrow_type=pa.date32(), doc="Optional inclusive lower bound."),
    ]
    end_date: Annotated[
        date | None,
        Arg("end_date", default=None, arrow_type=pa.date32(), doc="Optional inclusive upper bound."),
    ]


def _stamp(splits: list[dict], player_id: int, game_type: str) -> list[dict]:
    """Fill context the person endpoint occasionally omits from each split."""
    result: list[dict] = []
    for value in splits:
        stamped = dict(value)
        stamped.setdefault("gameType", game_type)
        player = dict(stamped.get("player") or {})
        player.setdefault("id", player_id)
        stamped["player"] = player
        result.append(stamped)
    return result


def _emit_basic(
    *,
    group: str,
    player_id: int,
    stat_type: str,
    game_type: str,
    output_schema: pa.Schema,
    out: OutputCollector,
    season: int | None = None,
    team_rows_only: bool = False,
) -> None:
    response = api.fetch_person_stats(
        player_id,
        group=group,
        stat_type=stat_type,
        season=season,
        game_type=game_type,
    )
    splits = _stamp(response.splits, player_id, game_type)
    if team_rows_only:
        splits = [value for value in splits if str(value.get("season")) == str(season) and value.get("team")]
    rows = flatten_pitching(splits) if group == "pitching" else flatten_batting(splits)
    out.emit(batch_from_rows(rows, output_schema), cache_control=_cache_control(response))
    out.finish()


def _emit_game_log(
    *,
    group: str,
    args: GameLogArgs,
    output_schema: pa.Schema,
    out: OutputCollector,
) -> None:
    if args.start_date and args.end_date and args.start_date > args.end_date:
        raise ValueError("start_date must be on or before end_date")
    response = api.fetch_person_stats(
        args.player_id,
        group=group,
        stat_type="gameLog",
        season=args.season,
        game_type=args.game_type,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    splits = _stamp(response.splits, args.player_id, args.game_type)
    rows = flatten_pitching_game_log(splits) if group == "pitching" else flatten_batting_game_log(splits)
    out.emit(batch_from_rows(rows, output_schema), cache_control=_cache_control(response))
    out.finish()


def _tags(*, title: str, llm: str, schema: pa.Schema, example: str, description: str) -> dict[str, str]:
    return {
        "provider": "mlb",
        "vgi.category": "player-detail",
        "vgi.title": title,
        "vgi.result_columns_schema": result_columns_schema(schema),
        "vgi.doc_llm": llm,
        "vgi.doc_md": llm,
        "vgi.example_queries": json.dumps([{"description": description, "sql": example}]),
    }


_CAREER_BATTING_SQL = (
    "SELECT player_name, games_played, hits, home_runs, batting_average, ops "
    "FROM mlb.main.batting_career(660271)"
)
_CAREER_PITCHING_SQL = (
    "SELECT player_name, games_started, innings_pitched, strikeouts, era, whip "
    "FROM mlb.main.pitching_career(660271)"
)
_TEAM_BATTING_SQL = (
    "SELECT team_name, games_played, hits, home_runs, ops "
    "FROM mlb.main.batting_team_splits(647304, 2025) ORDER BY team_name"
)
_TEAM_PITCHING_SQL = (
    "SELECT team_name, games_pitched, innings_pitched, strikeouts, era "
    "FROM mlb.main.pitching_team_splits(661395, 2025) ORDER BY team_name"
)
_BATTING_LOG_SQL = (
    "SELECT game_date, opponent_abbreviation, summary "
    "FROM mlb.main.batting_game_log(660271, season := 2025, "
    "start_date := DATE '2025-06-01', end_date := DATE '2025-06-30') ORDER BY game_date"
)
_PITCHING_LOG_SQL = (
    "SELECT game_date, opponent_abbreviation, innings_pitched, strikeouts, summary "
    "FROM mlb.main.pitching_game_log(660271, season := 2025) ORDER BY game_date"
)


class _CareerBase:
    GROUP: ClassVar[str]

    @classmethod
    def cardinality(cls, params: object) -> TableCardinality:
        return TableCardinality(estimate=1, max=1)

    @classmethod
    def process(cls, params: ProcessParams[CareerArgs], state: None, out: OutputCollector) -> None:
        _emit_basic(
            group=cls.GROUP,
            player_id=params.args.player_id,
            stat_type="career",
            game_type=params.args.game_type,
            output_schema=params.output_schema,
            out=out,
        )


@init_single_worker
@bind_fixed_schema
class BattingCareerFunction(_CareerBase, TableFunctionGenerator[CareerArgs]):
    """Career batting totals for one player."""

    GROUP = "hitting"
    FIXED_SCHEMA = BATTING_SCHEMA

    class Meta:
        name = "batting_career"
        description = "Career batting totals for one MLB player"
        categories = ["baseball", "player-detail", "career"]
        projection_pushdown = True
        tags = _tags(
            title="Player Career Batting",
            llm="Career batting totals for one player ID and game type, usually regular season.",
            schema=BATTING_SCHEMA,
            example=_CAREER_BATTING_SQL,
            description="Shohei Ohtani's regular-season career batting totals.",
        )
        examples = [FunctionExample(sql=_CAREER_BATTING_SQL, description="Player career batting totals")]


@init_single_worker
@bind_fixed_schema
class PitchingCareerFunction(_CareerBase, TableFunctionGenerator[CareerArgs]):
    """Career pitching totals for one player."""

    GROUP = "pitching"
    FIXED_SCHEMA = PITCHING_SCHEMA

    class Meta:
        name = "pitching_career"
        description = "Career pitching totals for one MLB player"
        categories = ["baseball", "player-detail", "career"]
        projection_pushdown = True
        tags = _tags(
            title="Player Career Pitching",
            llm="Career pitching totals for one player ID and game type, usually regular season.",
            schema=PITCHING_SCHEMA,
            example=_CAREER_PITCHING_SQL,
            description="Shohei Ohtani's regular-season career pitching totals.",
        )
        examples = [FunctionExample(sql=_CAREER_PITCHING_SQL, description="Player career pitching totals")]


class _TeamSplitsBase:
    GROUP: ClassVar[str]

    @classmethod
    def cardinality(cls, params: object) -> TableCardinality:
        return TableCardinality(estimate=1, max=32)

    @classmethod
    def process(cls, params: ProcessParams[TeamSplitArgs], state: None, out: OutputCollector) -> None:
        args = params.args
        _emit_basic(
            group=cls.GROUP,
            player_id=args.player_id,
            stat_type="yearByYear",
            season=args.season,
            game_type=args.game_type,
            output_schema=params.output_schema,
            out=out,
            team_rows_only=True,
        )


@init_single_worker
@bind_fixed_schema
class BattingTeamSplitsFunction(_TeamSplitsBase, TableFunctionGenerator[TeamSplitArgs]):
    """One player's season batting line split by team."""

    GROUP = "hitting"
    FIXED_SCHEMA = BATTING_SCHEMA

    class Meta:
        name = "batting_team_splits"
        description = "One MLB player's season batting totals split by team"
        categories = ["baseball", "player-detail", "team-splits"]
        projection_pushdown = True
        tags = _tags(
            title="Player Batting By Team",
            llm="Team-specific season batting lines for a player who may have been traded.",
            schema=BATTING_SCHEMA,
            example=_TEAM_BATTING_SQL,
            description="Josh Naylor's 2025 batting totals separated by team.",
        )
        examples = [FunctionExample(sql=_TEAM_BATTING_SQL, description="Player batting totals by team")]


@init_single_worker
@bind_fixed_schema
class PitchingTeamSplitsFunction(_TeamSplitsBase, TableFunctionGenerator[TeamSplitArgs]):
    """One player's season pitching line split by team."""

    GROUP = "pitching"
    FIXED_SCHEMA = PITCHING_SCHEMA

    class Meta:
        name = "pitching_team_splits"
        description = "One MLB player's season pitching totals split by team"
        categories = ["baseball", "player-detail", "team-splits"]
        projection_pushdown = True
        tags = _tags(
            title="Player Pitching By Team",
            llm="Team-specific season pitching lines for a player who may have been traded.",
            schema=PITCHING_SCHEMA,
            example=_TEAM_PITCHING_SQL,
            description="Jhoan Duran's 2025 pitching totals separated by team.",
        )
        examples = [FunctionExample(sql=_TEAM_PITCHING_SQL, description="Player pitching totals by team")]


class _GameLogBase:
    GROUP: ClassVar[str]

    @classmethod
    def cardinality(cls, params: object) -> TableCardinality:
        return TableCardinality(estimate=100, max=200)

    @classmethod
    def process(cls, params: ProcessParams[GameLogArgs], state: None, out: OutputCollector) -> None:
        _emit_game_log(group=cls.GROUP, args=params.args, output_schema=params.output_schema, out=out)


@init_single_worker
@bind_fixed_schema
class BattingGameLogFunction(_GameLogBase, TableFunctionGenerator[GameLogArgs]):
    """Per-game batting lines for one player and optional date range."""

    GROUP = "hitting"
    FIXED_SCHEMA = BATTING_GAME_LOG_SCHEMA

    class Meta:
        name = "batting_game_log"
        description = "Per-game batting lines for one MLB player"
        categories = ["baseball", "player-detail", "game-log"]
        projection_pushdown = True
        tags = _tags(
            title="Player Batting Game Log",
            llm="One batting line per game for a player, optionally bounded to an inclusive date range.",
            schema=BATTING_GAME_LOG_SCHEMA,
            example=_BATTING_LOG_SQL,
            description="Shohei Ohtani's June 2025 batting game log.",
        )
        examples = [FunctionExample(sql=_BATTING_LOG_SQL, description="Player batting log by date")]


@init_single_worker
@bind_fixed_schema
class PitchingGameLogFunction(_GameLogBase, TableFunctionGenerator[GameLogArgs]):
    """Per-game pitching lines for one player and optional date range."""

    GROUP = "pitching"
    FIXED_SCHEMA = PITCHING_GAME_LOG_SCHEMA

    class Meta:
        name = "pitching_game_log"
        description = "Per-game pitching lines for one MLB player"
        categories = ["baseball", "player-detail", "game-log"]
        projection_pushdown = True
        tags = _tags(
            title="Player Pitching Game Log",
            llm="One pitching line per game for a player, optionally bounded to an inclusive date range.",
            schema=PITCHING_GAME_LOG_SCHEMA,
            example=_PITCHING_LOG_SQL,
            description="Shohei Ohtani's 2025 pitching game log.",
        )
        examples = [FunctionExample(sql=_PITCHING_LOG_SQL, description="Player pitching log by date")]


DETAIL_FUNCTIONS = [
    BattingCareerFunction,
    PitchingCareerFunction,
    BattingTeamSplitsFunction,
    PitchingTeamSplitsFunction,
    BattingGameLogFunction,
    PitchingGameLogFunction,
]
