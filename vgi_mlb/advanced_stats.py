"""Advanced MLB batting and pitching season statistics."""

from __future__ import annotations

import json
from typing import ClassVar

import pyarrow as pa
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
    ADVANCED_BATTING_SCHEMA,
    ADVANCED_PITCHING_SCHEMA,
    batch_from_rows,
    flatten_advanced_batting,
    flatten_advanced_pitching,
)
from vgi_mlb.player_stats import PlayerStatsArgs, _cache_control
from vgi_mlb.standings import LEAGUE_IDS


def _emit_advanced(
    *,
    group: str,
    args: PlayerStatsArgs,
    output_schema: pa.Schema,
    out: OutputCollector,
) -> None:
    response = api.fetch_player_stats(
        group=group,
        stat_type="seasonAdvanced",
        season=args.season,
        league_id=LEAGUE_IDS[args.league],
        game_type=args.game_type,
        qualified_only=args.qualified_only,
    )
    splits = [
        value if value.get("gameType") else {**value, "gameType": args.game_type} for value in response.splits
    ]
    rows = flatten_advanced_pitching(splits) if group == "pitching" else flatten_advanced_batting(splits)
    out.emit(batch_from_rows(rows, output_schema), cache_control=_cache_control(response))
    out.finish()


@init_single_worker
@bind_fixed_schema
class AdvancedBattingStatsFunction(TableFunctionGenerator[PlayerStatsArgs]):
    """Advanced MLB batting rates and batted-ball counts."""

    FIXED_SCHEMA: ClassVar[pa.Schema] = ADVANCED_BATTING_SCHEMA

    class Meta:
        """Function discovery metadata."""

        name = "advanced_batting_stats"
        description = "Advanced MLB batting statistics by season, league, and game type"
        categories = ["baseball", "player-stats", "advanced"]
        projection_pushdown = True
        tags = {
            "provider": "mlb",
            "vgi.category": "player-stats",
            "vgi.result_columns_schema": result_columns_schema(ADVANCED_BATTING_SCHEMA),
            "vgi.doc_llm": (
                "Advanced season hitting metrics: isolated power, BABIP, plate-discipline rates, "
                "swing-and-miss counts, batted-ball counts, extra-base hits and double-play "
                "opportunities. Use qualified_only for a comparable leaderboard population."
            ),
            "vgi.doc_md": (
                "Advanced batting statistics from MLB's `seasonAdvanced` view. Rate values are "
                "exact `DECIMAL` columns and counts retain their integer form."
            ),
            "vgi.example_queries": json.dumps(
                [
                    {
                        "description": "Qualified 2025 isolated-power leaders.",
                        "sql": (
                            "SELECT player_name, plate_appearances, isolated_power, "
                            "strikeouts_per_plate_appearance FROM mlb.main.advanced_batting_stats("
                            "season := 2025, qualified_only := true) "
                            "ORDER BY isolated_power DESC LIMIT 20"
                        ),
                    }
                ]
            ),
        }
        examples = [
            FunctionExample(
                sql=(
                    "SELECT player_name, plate_appearances, isolated_power, "
                    "strikeouts_per_plate_appearance "
                    "FROM mlb.main.advanced_batting_stats("
                    "season := 2025, qualified_only := true) "
                    "ORDER BY isolated_power DESC LIMIT 20"
                ),
                description="Qualified 2025 isolated-power leaders",
            )
        ]

    @classmethod
    def cardinality(cls, params: object) -> TableCardinality:
        """Estimate a full season player pool."""
        return TableCardinality(estimate=800, max=2_000)

    @classmethod
    def process(cls, params: ProcessParams[PlayerStatsArgs], state: None, out: OutputCollector) -> None:
        """Fetch and emit advanced batting statistics."""
        _emit_advanced(group="hitting", args=params.args, output_schema=params.output_schema, out=out)


@init_single_worker
@bind_fixed_schema
class AdvancedPitchingStatsFunction(TableFunctionGenerator[PlayerStatsArgs]):
    """Advanced MLB pitching rates and contact-quality counts."""

    FIXED_SCHEMA: ClassVar[pa.Schema] = ADVANCED_PITCHING_SCHEMA

    class Meta:
        """Function discovery metadata."""

        name = "advanced_pitching_stats"
        description = "Advanced MLB pitching statistics by season, league, and game type"
        categories = ["baseball", "player-stats", "advanced"]
        projection_pushdown = True
        tags = {
            "provider": "mlb",
            "vgi.category": "player-stats",
            "vgi.result_columns_schema": result_columns_schema(ADVANCED_PITCHING_SCHEMA),
            "vgi.doc_llm": (
                "Advanced season pitching metrics: K-minus-BB rate, whiff and strike rates, "
                "per-nine rates, opponent slash line, quality starts, inherited runners and "
                "batted-ball counts. Use qualified_only for starter leaderboard comparisons."
            ),
            "vgi.doc_md": (
                "Advanced pitching statistics from MLB's `seasonAdvanced` view. Rate values are "
                "exact `DECIMAL` columns and counts retain their integer form."
            ),
            "vgi.example_queries": json.dumps(
                [
                    {
                        "description": "Qualified 2025 pitchers by K-minus-BB percentage.",
                        "sql": (
                            "SELECT player_name, strikeouts_minus_walks_percentage, whiff_percentage "
                            "FROM mlb.main.advanced_pitching_stats("
                            "season := 2025, qualified_only := true) "
                            "ORDER BY strikeouts_minus_walks_percentage DESC LIMIT 20"
                        ),
                    }
                ]
            ),
        }
        examples = [
            FunctionExample(
                sql=(
                    "SELECT player_name, strikeouts_minus_walks_percentage, whiff_percentage "
                    "FROM mlb.main.advanced_pitching_stats("
                    "season := 2025, qualified_only := true) "
                    "ORDER BY strikeouts_minus_walks_percentage DESC LIMIT 20"
                ),
                description="Qualified 2025 pitchers by K-minus-BB percentage",
            )
        ]

    @classmethod
    def cardinality(cls, params: object) -> TableCardinality:
        """Estimate a full season pitcher pool."""
        return TableCardinality(estimate=900, max=2_000)

    @classmethod
    def process(cls, params: ProcessParams[PlayerStatsArgs], state: None, out: OutputCollector) -> None:
        """Fetch and emit advanced pitching statistics."""
        _emit_advanced(group="pitching", args=params.args, output_schema=params.output_schema, out=out)


ADVANCED_FUNCTIONS = [AdvancedBattingStatsFunction, AdvancedPitchingStatsFunction]
