"""Example queries that combine several MLB catalog objects in one statement.

Each example is defined once here and referenced from the schema-level example list
and from the example list of the object that drives the query.
"""

from __future__ import annotations

from typing import NamedTuple

from vgi.metadata import FunctionExample


class ComposedExample(NamedTuple):
    """A described SQL statement combining two or more catalog objects."""

    description: str
    sql: str

    def query(self) -> dict[str, str]:
        """Return the ``vgi.example_queries`` entry for this example."""
        return {"description": self.description, "sql": self.sql}

    def function_example(self) -> FunctionExample:
        """Return the function-metadata example for this example."""
        return FunctionExample(sql=self.sql, description=self.description.removesuffix("."))


DIVISION_WINNER_ACES = ComposedExample(
    description=(
        "Each 2025 division winner's lowest-ERA qualified pitcher, joining standings() to "
        "pitching_stats() on team_id (pitchers traded mid-season have no team_id and are excluded)."
    ),
    sql=(
        "SELECT s.division_name, s.team_name, s.wins, p.player_name, p.innings_pitched, "
        "p.strikeouts, p.era "
        "FROM mlb.main.standings(season := 2025) s "
        "JOIN mlb.main.pitching_stats(season := 2025, qualified_only := true) p "
        "ON p.team_id = s.team_id "
        "WHERE s.division_rank = 1 "
        "QUALIFY row_number() OVER (PARTITION BY s.team_id ORDER BY p.era, p.player_id) = 1 "
        "ORDER BY s.division_name"
    ),
)

POSITION_PLAYERS_WHO_PITCHED = ComposedExample(
    description=(
        "2025 hitters with at least 50 plate appearances who also pitched, joining "
        "batting_stats() to pitching_stats() on player_id; mostly position players in mop-up "
        "relief, led by two-way Shohei Ohtani."
    ),
    sql=(
        "SELECT b.player_name, b.position_abbreviation, b.plate_appearances, b.ops, "
        "p.games_pitched, p.innings_pitched, p.era "
        "FROM mlb.main.batting_stats(season := 2025) b "
        "JOIN mlb.main.pitching_stats(season := 2025) p USING (player_id) "
        "WHERE b.plate_appearances >= 50 "
        "ORDER BY p.games_pitched DESC, b.player_name LIMIT 20"
    ),
)

SHORTSTOP_BAT_AND_GLOVE = ComposedExample(
    description=(
        "2025 shortstops with at least 2,400 defensive outs (800 innings) at the position, "
        "ranked by OPS alongside their errors and fielding percentage there."
    ),
    sql=(
        "SELECT f.player_name, f.last_team_abbreviation, f.outs, f.errors, "
        "f.fielding_percentage, b.plate_appearances, b.ops "
        "FROM mlb.main.fielding_stats(season := 2025) f "
        "JOIN mlb.main.batting_stats(season := 2025) b USING (player_id) "
        "WHERE f.position_abbreviation = 'SS' AND f.outs >= 2400 "
        "ORDER BY b.ops DESC, f.player_id LIMIT 10"
    ),
)

GAME_LOG_VS_OPPONENT_RECORD = ComposedExample(
    description=(
        "Shohei Ohtani's 2025 batting split by whether the opponent finished at .500 or "
        "better, joining his batting_game_log() to the final standings() on opponent_id."
    ),
    sql=(
        "SELECT s.winning_percentage >= 0.500 AS opponent_500_or_better, "
        "count(*) AS games, sum(g.at_bats) AS at_bats, sum(g.hits) AS hits, "
        "sum(g.home_runs) AS home_runs, "
        "round(sum(g.hits) / sum(g.at_bats), 3) AS batting_average "
        "FROM mlb.main.batting_game_log(660271, season := 2025) g "
        "JOIN mlb.main.standings(season := 2025) s ON s.team_id = g.opponent_id "
        "GROUP BY ALL ORDER BY opponent_500_or_better"
    ),
)

COMPOSED_EXAMPLES = (
    DIVISION_WINNER_ACES,
    POSITION_PLAYERS_WHO_PITCHED,
    SHORTSTOP_BAT_AND_GLOVE,
    GAME_LOG_VS_OPPONENT_RECORD,
)
