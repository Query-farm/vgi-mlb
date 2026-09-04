"""VGI worker exposing MLB standings and player statistics as a SQL catalog."""

from __future__ import annotations

import json
import os
import sys

from vgi import Worker
from vgi.catalog import Catalog, Schema, Table

from vgi_mlb.advanced_stats import ADVANCED_FUNCTIONS
from vgi_mlb.meta import column_comments
from vgi_mlb.player_detail import DETAIL_FUNCTIONS
from vgi_mlb.player_schemas import BATTING_SCHEMA, FIELDING_SCHEMA, PITCHING_SCHEMA
from vgi_mlb.player_stats import (
    PLAYER_FUNCTIONS,
    CurrentBattingFunction,
    CurrentFieldingFunction,
    CurrentPitchingFunction,
)
from vgi_mlb.schemas import STANDINGS_SCHEMA
from vgi_mlb.standings import FUNCTIONS, CurrentStandingsFunction

SOURCE_URL = "https://github.com/Query-farm/vgi-mlb"

_CURRENT_TABLE_TAGS = {
    "provider": "mlb",
    "vgi.category": "standings",
    "vgi.title": "Current MLB Standings",
    "vgi.keywords": json.dumps(["standings", "records", "games back", "division race", "wild card"]),
    "vgi.doc_llm": (
        "Current AL and NL regular-season standings, one row per team. Start here for today's "
        "division races, records, games back, run differential, streaks, and clinching state. "
        "For another season or the wild-card view, call standings()."
    ),
    "vgi.doc_md": (
        "The current MLB regular-season standings as an ordinary read-only table. Results follow "
        "MLB's public Stats API cache policy. Use `standings()` for historical seasons and "
        "alternate standings views."
    ),
    "vgi.example_queries": json.dumps(
        [
            {
                "description": "Current division tables in official rank order.",
                "sql": (
                    "SELECT division_name, division_rank, team_name, wins, losses, games_back "
                    "FROM mlb.main.current_standings ORDER BY division_name, division_rank"
                ),
            },
            {
                "description": "Teams with the best run differential.",
                "sql": (
                    "SELECT team_name, wins, losses, run_differential "
                    "FROM mlb.main.current_standings ORDER BY run_differential DESC"
                ),
            },
        ]
    ),
}

_CURRENT_BATTING_TAGS = {
    "provider": "mlb",
    "vgi.category": "player-stats",
    "vgi.title": "Current MLB Batting Statistics",
    "vgi.keywords": json.dumps(["batting", "hitters", "home runs", "OPS", "batting average"]),
    "vgi.doc_llm": (
        "Current-season batting lines for every MLB player. Use for home runs, hits, RBI, steals, "
        "walks, strikeouts, AVG, OBP, SLG and OPS. Use batting_stats() for another season, one "
        "league, or qualified leaders only."
    ),
    "vgi.doc_md": "Complete current-season MLB batting statistics, one row per player.",
    "vgi.example_queries": json.dumps(
        [
            {
                "description": "Current MLB home-run leaders.",
                "sql": (
                    "SELECT player_name, last_team_abbreviation, home_runs, ops "
                    "FROM mlb.main.current_batting ORDER BY home_runs DESC LIMIT 20"
                ),
            }
        ]
    ),
}

_CURRENT_PITCHING_TAGS = {
    "provider": "mlb",
    "vgi.category": "player-stats",
    "vgi.title": "Current MLB Pitching Statistics",
    "vgi.keywords": json.dumps(["pitching", "pitchers", "ERA", "WHIP", "strikeouts", "saves"]),
    "vgi.doc_llm": (
        "Current-season pitching lines for every MLB player. Use for starts, wins, saves, innings, "
        "strikeouts, ERA, WHIP and per-nine rates. Use pitching_stats() for another season, one "
        "league, or qualified leaders only."
    ),
    "vgi.doc_md": "Complete current-season MLB pitching statistics, one row per player.",
    "vgi.example_queries": json.dumps(
        [
            {
                "description": "Current qualified ERA leaders with at least 300 outs.",
                "sql": (
                    "SELECT player_name, last_team_abbreviation, innings_pitched, strikeouts, era "
                    "FROM mlb.main.current_pitching WHERE outs >= 300 ORDER BY era LIMIT 20"
                ),
            }
        ]
    ),
}

_CURRENT_FIELDING_TAGS = {
    "provider": "mlb",
    "vgi.category": "player-stats",
    "vgi.title": "Current MLB Fielding Statistics",
    "vgi.keywords": json.dumps(["fielding", "defense", "errors", "putouts", "assists"]),
    "vgi.doc_llm": (
        "Current regular-season fielding lines at player-position grain. Use for defensive "
        "innings, putouts, assists, errors, chances, double plays, fielding percentage and range "
        "factors. A player can appear in multiple rows for multiple positions."
    ),
    "vgi.doc_md": (
        "Current regular-season fielding statistics, one row per player-position combination. "
        "Use `outs` for exact defensive-inning arithmetic."
    ),
    "vgi.example_queries": json.dumps(
        [
            {
                "description": "Current shortstops with substantial defensive playing time.",
                "sql": (
                    "SELECT player_name, last_team_abbreviation, outs, errors, fielding_percentage "
                    "FROM mlb.main.current_fielding "
                    "WHERE position_abbreviation = 'SS' AND outs >= 600 "
                    "ORDER BY fielding_percentage DESC"
                ),
            }
        ]
    ),
}

_EXECUTABLE_EXAMPLES = json.dumps(
    [
        {
            "name": "current_standings_are_populated",
            "description": "MLB regular-season standings contain team rows.",
            "sql": "SELECT count(*) > 0 AS populated FROM mlb.main.current_standings",
            "expected_result": [{"populated": True}],
        },
        {
            "name": "current_batting_has_players",
            "description": "The complete current batting pool has stable player identifiers.",
            "sql": (
                "SELECT count(*) > 0 AND count(player_id) = count(*) AS populated "
                "FROM mlb.main.current_batting"
            ),
            "expected_result": [{"populated": True}],
        },
        {
            "name": "baseball_innings_are_exact",
            "description": "Every displayed pitching inning count agrees with the exact outs count.",
            "sql": (
                "SELECT bool_and(outs >= 0) AS valid_outs FROM mlb.main.current_pitching "
                "WHERE innings_pitched IS NOT NULL"
            ),
            "expected_result": [{"valid_outs": True}],
        },
    ]
)

_AGENT_TEST_TASKS = json.dumps(
    [
        {
            "name": "division_races",
            "prompt": (
                "Show the current MLB division leaders and how many games back each second-place team is."
            ),
        },
        {
            "name": "qualified_ops_leaders",
            "prompt": "Who were the top ten qualified MLB hitters by OPS in 2025?",
        },
        {
            "name": "traded_pitcher_team_lines",
            "prompt": "Break Jhoan Duran's 2025 pitching results out by team; his MLB player ID is 661395.",
        },
        {
            "name": "player_game_log",
            "prompt": "List Shohei Ohtani's June 2025 batting game log; his MLB player ID is 660271.",
        },
        {
            "name": "current_player_leaders",
            "prompt": "Who currently leads MLB in home runs, and who currently leads in strikeouts?",
        },
        {
            "name": "historical_standings",
            "prompt": "Return the final 2025 MLB division standings in division-rank order.",
        },
        {
            "name": "historical_pitching",
            "prompt": "List the ten qualified 2025 MLB pitchers with the lowest ERA.",
        },
        {
            "name": "shortstop_fielding",
            "prompt": (
                "Compare current MLB shortstops by fielding percentage after requiring 600 defensive outs."
            ),
        },
        {
            "name": "historical_fielding",
            "prompt": (
                "List 2025 MLB center fielders with at least 600 defensive outs, "
                "ordered by fielding percentage."
            ),
        },
        {
            "name": "advanced_batting",
            "prompt": "Who led qualified MLB hitters in isolated power in 2025? Return the top ten.",
        },
        {
            "name": "advanced_pitching",
            "prompt": "Who led qualified MLB pitchers in strikeout-minus-walk percentage in 2025?",
        },
        {
            "name": "two_way_career",
            "prompt": (
                "Show Shohei Ohtani's career regular-season batting and pitching totals; his ID is 660271."
            ),
        },
        {
            "name": "traded_hitter_team_lines",
            "prompt": "Split Josh Naylor's 2025 batting line by team; his MLB player ID is 647304.",
        },
        {
            "name": "pitching_game_log",
            "prompt": (
                "List Shohei Ohtani's 2025 pitching appearances with opponent, innings, and strikeouts."
            ),
        },
    ]
)

MLB_CATALOG = Catalog(
    name="mlb",
    default_schema="main",
    source_url=SOURCE_URL,
    comment="Read-only Major League Baseball standings and player statistics from MLB's Stats API",
    tags={
        "provider": "mlb",
        "domain": "sports",
        "vgi.title": "Major League Baseball Data",
        "vgi.source_url": SOURCE_URL,
        "vgi.author": "Query Farm LLC <hello@query.farm>",
        "vgi.copyright": (
            "Worker (c) 2026 Query Farm LLC. MLB data (c) MLB Advanced Media, L.P.; "
            "use is subject to MLB's data terms."
        ),
        "vgi.license": "MIT",
        "vgi.support_contact": "https://github.com/Query-farm/vgi-mlb/issues",
        "vgi.support_policy_url": "https://github.com/Query-farm/vgi-mlb/blob/main/README.md",
        "vgi.keywords": json.dumps(["MLB", "baseball", "standings", "American League", "National League"]),
        "vgi.executable_examples": _EXECUTABLE_EXAMPLES,
        "vgi.agent_test_tasks": _AGENT_TEST_TASKS,
        "vgi.doc_llm": (
            "Read-only Major League Baseball standings and player statistics from MLB's Stats API. "
            "Use the current tables for regular-season standings plus complete batting, pitching, "
            "and player-position fielding lines. Parameterized functions cover historical seasons, "
            "AL or NL restriction, spring training and postseason game types, official qualified "
            "leaderboards, advanced metrics, career totals, team-specific lines for traded players, "
            "and per-game logs with optional date bounds. Player statistics use exact decimal rate "
            "columns; pitching and fielding expose integer outs for correct innings arithmetic."
        ),
        "vgi.doc_md": (
            "# MLB standings and player statistics\n\n"
            "Query current and historical Major League Baseball data directly from SQL. The catalog "
            "contains team standings and complete batting, pitching, and fielding season lines, plus "
            "advanced metrics, career totals, team splits, and per-game logs.\n\n"
            "## Data model\n\n"
            "Current tables are the quickest entry point. Parameterized functions select seasons, "
            "leagues, game types, qualified pools, or individual players. Multi-team season totals "
            "never claim to belong to one club: use the team-split functions when attribution matters.\n\n"
            "All access is read-only and requires no credential. Rate statistics are exact decimals; "
            "baseball innings remain display strings alongside exact integer outs."
        ),
    },
    schemas=[
        Schema(
            name="main",
            comment="Current and historical MLB standings",
            tags={
                "provider": "mlb",
                "domain": "sports",
                "vgi.title": "MLB Standings",
                "vgi.keywords": json.dumps(
                    ["MLB", "baseball", "standings", "batting", "pitching", "fielding", "game logs"]
                ),
                "vgi.categories": json.dumps(
                    [
                        {
                            "name": "standings",
                            "title": "Standings",
                            "description": "Team records, ranks, games back, and playoff position.",
                            "keywords": ["standings", "records", "rank", "wild card"],
                        },
                        {
                            "name": "player-stats",
                            "title": "Player Statistics",
                            "description": (
                                "Season batting, pitching, fielding, and advanced statistical lines."
                            ),
                            "keywords": [
                                "players",
                                "batting",
                                "pitching",
                                "fielding",
                                "advanced",
                                "leaders",
                            ],
                        },
                        {
                            "name": "player-detail",
                            "title": "Player Detail",
                            "description": "Career totals, team splits, and per-game logs for one player.",
                            "keywords": ["career", "game log", "team splits", "trades"],
                        },
                    ]
                ),
                "vgi.doc_llm": (
                    "Use current_standings for today's division tables, current_batting for hitter "
                    "lines, current_pitching for pitcher lines, and current_fielding for defense. "
                    "Parameterized functions support seasons, AL/NL, game type, qualified-player "
                    "selection, advanced metrics, career totals, team splits, and game logs."
                ),
                "vgi.doc_md": (
                    "## MLB analytical data\n\n"
                    "Current and historical standings plus batting, pitching, and fielding lines. "
                    "Rows are explicitly team-, player-, player-position-, or player-game-grain.\n\n"
                    "Use current tables for live regular-season analysis and parameterized functions "
                    "for historical seasons, alternate game types, career totals, advanced metrics, "
                    "team attribution, and date-bounded game logs."
                ),
                "vgi.example_queries": _CURRENT_TABLE_TAGS["vgi.example_queries"],
            },
            functions=[*FUNCTIONS, *PLAYER_FUNCTIONS, *ADVANCED_FUNCTIONS, *DETAIL_FUNCTIONS],
            tables=[
                Table(
                    name="current_standings",
                    function=CurrentStandingsFunction,
                    comment="Current AL and NL regular-season standings, one row per team",
                    tags=_CURRENT_TABLE_TAGS,
                    column_comments=column_comments(STANDINGS_SCHEMA),
                    primary_key=(("team_id",),),
                    not_null=("team_id",),
                    cardinality_estimate=30,
                ),
                Table(
                    name="current_batting",
                    function=CurrentBattingFunction,
                    comment="Current-season batting statistics, one row per MLB player",
                    tags=_CURRENT_BATTING_TAGS,
                    column_comments=column_comments(BATTING_SCHEMA),
                    primary_key=(("player_id",),),
                    not_null=("player_id",),
                    cardinality_estimate=800,
                ),
                Table(
                    name="current_pitching",
                    function=CurrentPitchingFunction,
                    comment="Current-season pitching statistics, one row per MLB player",
                    tags=_CURRENT_PITCHING_TAGS,
                    column_comments=column_comments(PITCHING_SCHEMA),
                    primary_key=(("player_id",),),
                    not_null=("player_id",),
                    cardinality_estimate=900,
                ),
                Table(
                    name="current_fielding",
                    function=CurrentFieldingFunction,
                    comment="Current-season fielding statistics at player-position grain",
                    tags=_CURRENT_FIELDING_TAGS,
                    column_comments=column_comments(FIELDING_SCHEMA),
                    primary_key=(("player_id", "position_code"),),
                    not_null=("player_id", "position_code"),
                    cardinality_estimate=2_700,
                ),
            ],
        )
    ],
)


class MlbWorker(Worker):
    """Worker process hosting the read-only MLB catalog."""

    catalog = MLB_CATALOG


def main() -> None:
    """Run over stdio by default, or HTTP when VGI's ``--http`` flag is supplied."""
    MlbWorker.main()


def main_http() -> None:
    """Run HTTP with production-safe configuration requirements."""
    if not os.environ.get("VGI_SIGNING_KEY"):
        raise SystemExit(
            "VGI_SIGNING_KEY is required for HTTP mode so state remains valid across restarts and replicas"
        )
    auth_configured = bool(os.environ.get("VGI_BEARER_TOKENS") or os.environ.get("VGI_JWT_ISSUER"))
    auth_configured = auth_configured or os.environ.get("VGI_PROXY_PROOF_MODE", "").lower() == "require"
    if not auth_configured and os.environ.get("VGI_ALLOW_ANONYMOUS") != "1":
        raise SystemExit(
            "HTTP authentication is required; configure bearer/JWT/proxy proof, or explicitly set "
            "VGI_ALLOW_ANONYMOUS=1 for an intentionally public deployment"
        )
    argv = sys.argv[1:]
    if "--http" not in argv:
        argv = ["--http", *argv]
    if "--describe" not in argv and "--no-describe" not in argv:
        argv = ["--no-describe", *argv]
    if not any(value == "--cors-origins" or value.startswith("--cors-origins=") for value in argv):
        argv = ["--cors-origins", "", *argv]
    sys.argv = [sys.argv[0], *argv]
    MlbWorker.main()
