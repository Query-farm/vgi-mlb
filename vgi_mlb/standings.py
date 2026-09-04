"""VGI table functions for current and historical MLB standings."""

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
from vgi_mlb.meta import result_columns_schema
from vgi_mlb.schemas import STANDINGS_SCHEMA, batch_from_records

LEAGUE_IDS = {"MLB": None, "AL": 103, "NL": 104}
STANDINGS_TYPES = (
    "regularSeason",
    "wildCard",
    "wildCardWithLeaders",
    "divisionLeaders",
    "byDivision",
    "byLeague",
    "springTraining",
    "postseason",
)


def _cache_control(response: api.StandingsResponse) -> CacheControl | None:
    if response.max_age is None:
        return None
    return CacheControl(
        ttl=response.max_age,
        stale_while_revalidate=response.stale_while_revalidate,
        stale_if_error=response.stale_if_error,
    )


def _emit(
    *,
    season: int | None,
    league: str,
    standings_type: str,
    output_schema: pa.Schema,
    out: OutputCollector,
) -> None:
    response = api.fetch_standings(
        season=season,
        league_id=LEAGUE_IDS[league],
        standings_type=standings_type,
    )
    out.emit(
        batch_from_records(response.records, output_schema),
        cache_control=_cache_control(response),
    )
    out.finish()


@dataclass(kw_only=True)
class StandingsArgs:
    """Arguments accepted by ``standings``."""

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
    standings_type: Annotated[
        str,
        Arg(
            "standings_type",
            default="regularSeason",
            arrow_type=pa.string(),
            choices=STANDINGS_TYPES,
            doc="MLB standings view to request.",
        ),
    ]


_RESULT_TAG = result_columns_schema(STANDINGS_SCHEMA)


@init_single_worker
@bind_fixed_schema
class StandingsFunction(TableFunctionGenerator[StandingsArgs]):
    """MLB standings for a selected season, league, and standings view."""

    FIXED_SCHEMA: ClassVar[pa.Schema] = STANDINGS_SCHEMA

    class Meta:
        """Function discovery metadata."""

        name = "standings"
        description = "MLB standings by season, league, and standings view"
        categories = ["baseball", "standings"]
        projection_pushdown = True
        tags = {
            "provider": "mlb",
            "vgi.category": "standings",
            "vgi.result_columns_schema": _RESULT_TAG,
            "vgi.doc_llm": (
                "One row per MLB team with rankings, wins and losses, games back, run "
                "differential, streak, home/away and last-ten records, and clinching state. "
                "Use season for historical standings, league => 'AL' or 'NL' to narrow, and "
                "standings_type => 'wildCard' for the wild-card race. With no arguments it "
                "returns the current regular-season standings for both leagues."
            ),
            "vgi.doc_md": (
                "MLB standings flattened to one row per team. All arguments are named and "
                "optional. `games_back` is numeric for sorting and arithmetic; the original "
                "MLB marker remains in `games_back_display`. The same applies to wild-card "
                "games back. Percentages use exact `DECIMAL` values rather than binary floats."
            ),
            "vgi.example_queries": json.dumps(
                [
                    {
                        "description": "The 2025 final division standings.",
                        "sql": (
                            "SELECT division_name, division_rank, team_name, wins, losses "
                            "FROM mlb.main.standings(season := 2025) "
                            "ORDER BY division_name, division_rank"
                        ),
                    },
                    {
                        "description": "The current American League wild-card race.",
                        "sql": (
                            "SELECT wild_card_rank, team_name, wild_card_games_back "
                            "FROM mlb.main.standings(league := 'AL', "
                            "standings_type := 'wildCard') ORDER BY wild_card_rank"
                        ),
                    },
                ]
            ),
        }
        examples = [
            FunctionExample(
                sql=(
                    "SELECT division_name, division_rank, team_name, wins, losses "
                    "FROM mlb.main.standings(season := 2025) "
                    "ORDER BY division_name, division_rank"
                ),
                description="The 2025 final division standings",
            )
        ]

    @classmethod
    def cardinality(cls, params: object) -> TableCardinality:
        """MLB currently has 30 teams; some views return a subset."""
        return TableCardinality(estimate=30, max=64)

    @classmethod
    def process(cls, params: ProcessParams[StandingsArgs], state: None, out: OutputCollector) -> None:
        """Fetch and emit the requested standings."""
        args = params.args
        _emit(
            season=args.season,
            league=args.league,
            standings_type=args.standings_type,
            output_schema=params.output_schema,
            out=out,
        )


@init_single_worker
@bind_fixed_schema
class CurrentStandingsFunction(TableFunctionGenerator[None]):
    """Current regular-season standings backing the ``current_standings`` table."""

    FIXED_SCHEMA: ClassVar[pa.Schema] = STANDINGS_SCHEMA

    class Meta:
        """Function discovery metadata."""

        name = "all_current_standings"
        description = "Current MLB regular-season standings (scan behind current_standings)"
        categories = ["baseball", "standings"]
        projection_pushdown = True
        tags = {
            "provider": "mlb",
            "vgi.category": "standings",
            "vgi.result_columns_schema": _RESULT_TAG,
            "vgi.doc_llm": (
                "The scan behind the current_standings table. Prefer the table for ordinary "
                "queries; use standings() when you need a historical season, one league, or "
                "a different standings view."
            ),
            "vgi.doc_md": (
                "Returns the current regular-season AL and NL standings. This function exists "
                "as the scan behind `current_standings`; selecting the table is normally clearer."
            ),
            "vgi.example_queries": json.dumps(
                [
                    {
                        "description": "Read the table's backing scan directly.",
                        "sql": (
                            "SELECT division_name, team_name, wins, losses "
                            "FROM mlb.main.all_current_standings() WHERE division_rank = 1 "
                            "ORDER BY division_name"
                        ),
                    }
                ]
            ),
        }
        examples = [
            FunctionExample(
                sql=(
                    "SELECT division_name, team_name, wins, losses "
                    "FROM mlb.main.all_current_standings() WHERE division_rank = 1 "
                    "ORDER BY division_name"
                ),
                description="Read current division leaders directly from the backing scan",
            )
        ]

    @classmethod
    def cardinality(cls, params: object) -> TableCardinality:
        """Return a planner estimate for the current 30-team league."""
        return TableCardinality(estimate=30, max=64)

    @classmethod
    def process(cls, params: ProcessParams[None], state: None, out: OutputCollector) -> None:
        """Fetch and emit current regular-season standings."""
        _emit(
            season=None,
            league="MLB",
            standings_type="regularSeason",
            output_schema=params.output_schema,
            out=out,
        )


FUNCTIONS = [StandingsFunction, CurrentStandingsFunction]
