"""VGI functions exposing MLB season batting and pitching statistics."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Annotated, ClassVar

import pyarrow as pa
from vgi.arguments import Arg
from vgi.cache_control import CacheControl
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
from vgi_mlb.composed import POSITION_PLAYERS_WHO_PITCHED, SHORTSTOP_BAT_AND_GLOVE
from vgi_mlb.meta import result_columns_schema
from vgi_mlb.player_schemas import (
    BATTING_SCHEMA,
    FIELDING_SCHEMA,
    PITCHING_SCHEMA,
    batch_from_rows,
    batch_from_splits,
    flatten_fielding,
)
from vgi_mlb.standings import LEAGUE_IDS

GAME_TYPES = {
    "R": "Regular Season",
    "S": "Spring Training",
    "P": "Postseason",
    "F": "Wild Card",
    "D": "Division Series",
    "L": "League Championship Series",
    "W": "World Series",
}


@dataclass(kw_only=True)
class PlayerStatsArgs:
    """Arguments shared by batting and pitching season-stat functions."""

    season: Annotated[
        int | None,
        Arg(
            "season",
            default=None,
            arrow_type=pa.int32(),
            ge=1876,
            doc="Season year. NULL asks MLB for its current season.",
        ),
    ]
    league: Annotated[
        str,
        Arg(
            "league",
            default="MLB",
            arrow_type=pa.string(),
            choices=tuple(LEAGUE_IDS),
            doc="MLB for both leagues, AL for American League, or NL for National League.",
        ),
    ]
    qualified_only: Annotated[
        bool,
        Arg(
            "qualified_only",
            default=False,
            arrow_type=pa.bool_(),
            doc="Return only players who qualify for the official rate-stat leaderboards.",
        ),
    ]
    game_type: Annotated[
        str,
        Arg(
            "game_type",
            default="R",
            arrow_type=pa.string(),
            choices=tuple(GAME_TYPES),
            doc="R regular season, S spring training, P postseason, or a specific postseason round.",
        ),
    ]


def _cache_control(response: api.PlayerStatsResponse) -> CacheControl | None:
    if response.max_age is None:
        return None
    return CacheControl(
        ttl=response.max_age,
        stale_while_revalidate=response.stale_while_revalidate,
        stale_if_error=response.stale_if_error,
    )


def _emit(
    *,
    group: str,
    season: int | None,
    league: str,
    qualified_only: bool,
    game_type: str,
    output_schema: pa.Schema,
    out: OutputCollector,
) -> None:
    response = api.fetch_player_stats(
        group=group,
        season=season,
        league_id=LEAGUE_IDS[league],
        qualified_only=qualified_only,
        game_type=game_type,
    )
    splits = [
        value if value.get("gameType") else {**value, "gameType": game_type} for value in response.splits
    ]
    out.emit(
        batch_from_splits(splits, output_schema, pitching=group == "pitching"),
        cache_control=_cache_control(response),
    )
    out.finish()


@init_single_worker
@bind_fixed_schema
class BattingStatsFunction(TableFunctionGenerator[PlayerStatsArgs]):
    """MLB player batting statistics for a selected season and league."""

    FIXED_SCHEMA: ClassVar[pa.Schema] = BATTING_SCHEMA

    class Meta:
        """Function discovery metadata."""

        name = "batting_stats"
        description = "MLB player batting statistics by season and league"
        categories = ["baseball", "player-stats", "batting"]
        projection_pushdown = True
        tags = {
            "provider": "mlb",
            "vgi.category": "player-stats",
            "vgi.result_columns_schema": result_columns_schema(BATTING_SCHEMA),
            "vgi.doc_llm": (
                "Season batting lines at player grain: games, plate appearances, hits, extra-base "
                "hits, home runs, RBI, steals, walks, strikeouts, AVG, OBP, SLG, OPS and BABIP. "
                "Defaults to all players in MLB's current season. Set qualified_only => true for "
                "the official rate-stat leaderboard pool, or pass a season and AL/NL league."
            ),
            "vgi.doc_md": (
                "One aggregate season batting line per player. Rate statistics are exact `DECIMAL` "
                "columns. The full player pool is returned and completely paged by default; "
                "`qualified_only := true` narrows to official qualifiers."
            ),
            "vgi.example_queries": json.dumps(
                [
                    {
                        "description": "Qualified 2025 MLB OPS leaders.",
                        "sql": (
                            "SELECT player_name, last_team_abbreviation, home_runs, ops "
                            "FROM mlb.main.batting_stats(season := 2025, qualified_only := true) "
                            "ORDER BY ops DESC LIMIT 20"
                        ),
                    }
                ]
            ),
        }
        examples = [
            FunctionExample(
                sql=(
                    "SELECT player_name, last_team_abbreviation, home_runs, ops "
                    "FROM mlb.main.batting_stats(season := 2025, qualified_only := true) "
                    "ORDER BY ops DESC LIMIT 20"
                ),
                description="Qualified 2025 MLB OPS leaders",
            )
        ]

    @classmethod
    def cardinality(cls, params: object) -> TableCardinality:
        """Return a planner estimate for a complete MLB player pool."""
        return TableCardinality(estimate=800, max=2_000)

    @classmethod
    def process(cls, params: ProcessParams[PlayerStatsArgs], state: None, out: OutputCollector) -> None:
        """Fetch and emit batting statistics."""
        args = params.args
        _emit(
            group="hitting",
            season=args.season,
            league=args.league,
            qualified_only=args.qualified_only,
            game_type=args.game_type,
            output_schema=params.output_schema,
            out=out,
        )


@init_single_worker
@bind_fixed_schema
class PitchingStatsFunction(TableFunctionGenerator[PlayerStatsArgs]):
    """MLB player pitching statistics for a selected season and league."""

    FIXED_SCHEMA: ClassVar[pa.Schema] = PITCHING_SCHEMA

    class Meta:
        """Function discovery metadata."""

        name = "pitching_stats"
        description = "MLB player pitching statistics by season and league"
        categories = ["baseball", "player-stats", "pitching"]
        projection_pushdown = True
        tags = {
            "provider": "mlb",
            "vgi.category": "player-stats",
            "vgi.result_columns_schema": result_columns_schema(PITCHING_SCHEMA),
            "vgi.doc_llm": (
                "Season pitching lines at player grain: appearances, starts, wins, saves, innings, "
                "outs, strikeouts, walks, ERA, WHIP, opponent slash line, K/BB and per-nine rates. "
                "Defaults to all players in MLB's current season. Set qualified_only => true for "
                "qualified leaders, or pass a season and AL/NL league. Use outs—not the display "
                "innings_pitched string—for exact innings arithmetic."
            ),
            "vgi.doc_md": (
                "One aggregate season pitching line per player. `innings_pitched` preserves "
                "baseball notation, where .1 and .2 mean one and two outs; divide `outs` by three "
                "for arithmetic. Rate statistics are exact `DECIMAL` columns."
            ),
            "vgi.example_queries": json.dumps(
                [
                    {
                        "description": "Qualified 2025 pitchers ordered by ERA.",
                        "sql": (
                            "SELECT player_name, last_team_abbreviation, innings_pitched, strikeouts, era "
                            "FROM mlb.main.pitching_stats(season := 2025, qualified_only := true) "
                            "ORDER BY era LIMIT 20"
                        ),
                    },
                    POSITION_PLAYERS_WHO_PITCHED.query(),
                ]
            ),
        }
        examples = [
            FunctionExample(
                sql=(
                    "SELECT player_name, last_team_abbreviation, innings_pitched, strikeouts, era "
                    "FROM mlb.main.pitching_stats(season := 2025, qualified_only := true) "
                    "ORDER BY era LIMIT 20"
                ),
                description="Qualified 2025 pitchers ordered by ERA",
            ),
            POSITION_PLAYERS_WHO_PITCHED.function_example(),
        ]

    @classmethod
    def cardinality(cls, params: object) -> TableCardinality:
        """Return a planner estimate for a complete MLB pitcher pool."""
        return TableCardinality(estimate=900, max=2_000)

    @classmethod
    def process(cls, params: ProcessParams[PlayerStatsArgs], state: None, out: OutputCollector) -> None:
        """Fetch and emit pitching statistics."""
        args = params.args
        _emit(
            group="pitching",
            season=args.season,
            league=args.league,
            qualified_only=args.qualified_only,
            game_type=args.game_type,
            output_schema=params.output_schema,
            out=out,
        )


@dataclass(kw_only=True)
class FieldingStatsArgs:
    """Arguments for season fielding statistics."""

    season: Annotated[
        int | None,
        Arg(
            "season",
            default=None,
            arrow_type=pa.int32(),
            ge=1876,
            doc="Season year; NULL selects MLB's current season.",
        ),
    ]
    league: Annotated[
        str,
        Arg(
            "league",
            default="MLB",
            arrow_type=pa.string(),
            choices=tuple(LEAGUE_IDS),
            doc="MLB for both leagues, AL for American League, or NL for National League.",
        ),
    ]
    game_type: Annotated[
        str,
        Arg(
            "game_type",
            default="R",
            arrow_type=pa.string(),
            choices=tuple(GAME_TYPES),
            doc="R regular season, S spring training, P postseason, or a specific postseason round.",
        ),
    ]


def _emit_fielding(
    *,
    season: int | None,
    league: str,
    game_type: str,
    output_schema: pa.Schema,
    out: OutputCollector,
) -> None:
    response = api.fetch_player_stats(
        group="fielding",
        season=season,
        league_id=LEAGUE_IDS[league],
        game_type=game_type,
    )
    splits = [
        value if value.get("gameType") else {**value, "gameType": game_type} for value in response.splits
    ]
    out.emit(
        batch_from_rows(flatten_fielding(splits), output_schema),
        cache_control=_cache_control(response),
    )
    out.finish()


@init_single_worker
@bind_fixed_schema
class FieldingStatsFunction(TableFunctionGenerator[FieldingStatsArgs]):
    """MLB player fielding statistics at player-position grain."""

    FIXED_SCHEMA: ClassVar[pa.Schema] = FIELDING_SCHEMA

    class Meta:
        """Function discovery metadata."""

        name = "fielding_stats"
        description = "MLB player fielding statistics by season, league, and game type"
        categories = ["baseball", "player-stats", "fielding"]
        projection_pushdown = True
        tags = {
            "provider": "mlb",
            "vgi.category": "player-stats",
            "vgi.result_columns_schema": result_columns_schema(FIELDING_SCHEMA),
            "vgi.doc_llm": (
                "Season fielding lines at player-position grain, including defensive innings, "
                "putouts, assists, errors, chances, double plays, fielding percentage and range "
                "factors. A player can have several rows when he appeared at several positions."
            ),
            "vgi.doc_md": (
                "One row per player and position. `innings` preserves baseball notation; use the "
                "derived integer `outs` for exact defensive-inning arithmetic."
            ),
            "vgi.example_queries": json.dumps(
                [
                    {
                        "description": "2025 shortstops with at least 900 defensive outs.",
                        "sql": (
                            "SELECT player_name, last_team_abbreviation, outs, errors, fielding_percentage "
                            "FROM mlb.main.fielding_stats(season := 2025) "
                            "WHERE position_abbreviation = 'SS' AND outs >= 900 "
                            "ORDER BY fielding_percentage DESC"
                        ),
                    },
                    SHORTSTOP_BAT_AND_GLOVE.query(),
                ]
            ),
        }
        examples = [
            FunctionExample(
                sql=(
                    "SELECT player_name, last_team_abbreviation, outs, errors, fielding_percentage "
                    "FROM mlb.main.fielding_stats(season := 2025) "
                    "WHERE position_abbreviation = 'SS' AND outs >= 900 "
                    "ORDER BY fielding_percentage DESC"
                ),
                description="2025 shortstops with substantial defensive playing time",
            ),
            SHORTSTOP_BAT_AND_GLOVE.function_example(),
        ]

    @classmethod
    def cardinality(cls, params: object) -> TableCardinality:
        """Estimate player-position rows in one MLB season."""
        return TableCardinality(estimate=2_700, max=6_000)

    @classmethod
    def process(cls, params: ProcessParams[FieldingStatsArgs], state: None, out: OutputCollector) -> None:
        """Fetch and emit fielding statistics."""
        args = params.args
        _emit_fielding(
            season=args.season,
            league=args.league,
            game_type=args.game_type,
            output_schema=params.output_schema,
            out=out,
        )


class _CurrentPlayerStatsBase:
    """Shared implementation for current all-player scan functions."""

    GROUP: ClassVar[str]
    FIXED_SCHEMA: ClassVar[pa.Schema]

    @classmethod
    def cardinality(cls, params: object) -> TableCardinality:
        """Return a planner estimate for a complete MLB player pool."""
        return TableCardinality(estimate=800, max=2_000)

    @classmethod
    def process(cls, params: ProcessParams[None], state: None, out: OutputCollector) -> None:
        """Fetch and emit current all-player statistics."""
        _emit(
            group=cls.GROUP,
            season=None,
            league="MLB",
            qualified_only=False,
            game_type="R",
            output_schema=params.output_schema,
            out=out,
        )


@init_single_worker
@bind_fixed_schema
class CurrentBattingFunction(_CurrentPlayerStatsBase, TableFunctionGenerator[None]):
    """Current batting stats backing the ``current_batting`` table."""

    GROUP = "hitting"
    FIXED_SCHEMA = BATTING_SCHEMA

    class Meta:
        """Function discovery metadata."""

        name = "all_current_batting"
        description = "Current MLB batting lines (scan behind current_batting)"
        categories = ["baseball", "player-stats", "batting"]
        projection_pushdown = True
        tags = {
            "provider": "mlb",
            "vgi.category": "player-stats",
            "vgi.result_columns_schema": result_columns_schema(BATTING_SCHEMA),
            "vgi.doc_llm": "The scan behind current_batting. Prefer that table for normal queries.",
            "vgi.doc_md": "Current-season batting lines for the complete MLB player pool.",
            "vgi.example_queries": json.dumps(
                [
                    {
                        "description": "Current home-run leaders from the backing scan.",
                        "sql": (
                            "SELECT player_name, home_runs FROM mlb.main.all_current_batting() "
                            "ORDER BY home_runs DESC LIMIT 10"
                        ),
                    }
                ]
            ),
        }


@init_single_worker
@bind_fixed_schema
class CurrentPitchingFunction(_CurrentPlayerStatsBase, TableFunctionGenerator[None]):
    """Current pitching stats backing the ``current_pitching`` table."""

    GROUP = "pitching"
    FIXED_SCHEMA = PITCHING_SCHEMA

    class Meta:
        """Function discovery metadata."""

        name = "all_current_pitching"
        description = "Current MLB pitching lines (scan behind current_pitching)"
        categories = ["baseball", "player-stats", "pitching"]
        projection_pushdown = True
        tags = {
            "provider": "mlb",
            "vgi.category": "player-stats",
            "vgi.result_columns_schema": result_columns_schema(PITCHING_SCHEMA),
            "vgi.doc_llm": "The scan behind current_pitching. Prefer that table for normal queries.",
            "vgi.doc_md": "Current-season pitching lines for the complete MLB player pool.",
            "vgi.example_queries": json.dumps(
                [
                    {
                        "description": "Current strikeout leaders from the backing scan.",
                        "sql": (
                            "SELECT player_name, strikeouts FROM mlb.main.all_current_pitching() "
                            "ORDER BY strikeouts DESC LIMIT 10"
                        ),
                    }
                ]
            ),
        }


@init_single_worker
@bind_fixed_schema
class CurrentFieldingFunction(TableFunctionGenerator[None]):
    """Current fielding stats backing the ``current_fielding`` table."""

    FIXED_SCHEMA: ClassVar[pa.Schema] = FIELDING_SCHEMA

    class Meta:
        """Function discovery metadata."""

        name = "all_current_fielding"
        description = "Current MLB fielding lines (scan behind current_fielding)"
        categories = ["baseball", "player-stats", "fielding"]
        projection_pushdown = True
        tags = {
            "provider": "mlb",
            "vgi.category": "player-stats",
            "vgi.result_columns_schema": result_columns_schema(FIELDING_SCHEMA),
            "vgi.doc_llm": "The scan behind current_fielding. Prefer that table for normal queries.",
            "vgi.doc_md": "Current regular-season fielding lines at player-position grain.",
            "vgi.example_queries": json.dumps(
                [
                    {
                        "description": "Current shortstop fielding lines from the backing scan.",
                        "sql": (
                            "SELECT player_name, outs, errors FROM mlb.main.all_current_fielding() "
                            "WHERE position_abbreviation = 'SS' ORDER BY outs DESC LIMIT 10"
                        ),
                    }
                ]
            ),
        }

    @classmethod
    def cardinality(cls, params: object) -> TableCardinality:
        """Estimate player-position rows in the current MLB season."""
        return TableCardinality(estimate=2_700, max=6_000)

    @classmethod
    def process(cls, params: ProcessParams[None], state: None, out: OutputCollector) -> None:
        """Fetch and emit current regular-season fielding statistics."""
        _emit_fielding(
            season=None,
            league="MLB",
            game_type="R",
            output_schema=params.output_schema,
            out=out,
        )


PLAYER_FUNCTIONS = [
    BattingStatsFunction,
    PitchingStatsFunction,
    CurrentBattingFunction,
    CurrentPitchingFunction,
    FieldingStatsFunction,
    CurrentFieldingFunction,
]
