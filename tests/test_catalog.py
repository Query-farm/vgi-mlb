"""Tests for the SQL-facing catalog shape."""

import json

from vgi_mlb.player_stats import CurrentBattingFunction, CurrentFieldingFunction, CurrentPitchingFunction
from vgi_mlb.standings import CurrentStandingsFunction, StandingsFunction
from vgi_mlb.worker import MLB_CATALOG


def test_catalog_surface() -> None:
    schema = MLB_CATALOG.schemas[0]
    assert MLB_CATALOG.name == "mlb"
    assert schema.path == ["main"]
    assert {function.Meta.name for function in schema.functions} == {
        "standings",
        "all_current_standings",
        "batting_stats",
        "pitching_stats",
        "all_current_batting",
        "all_current_pitching",
        "fielding_stats",
        "all_current_fielding",
        "advanced_batting_stats",
        "advanced_pitching_stats",
        "batting_career",
        "pitching_career",
        "batting_team_splits",
        "pitching_team_splits",
        "batting_game_log",
        "pitching_game_log",
    }
    assert {table.name: table.function for table in schema.tables} == {
        "current_standings": CurrentStandingsFunction,
        "current_batting": CurrentBattingFunction,
        "current_pitching": CurrentPitchingFunction,
        "current_fielding": CurrentFieldingFunction,
    }


def test_standings_arguments_are_named_and_optional() -> None:
    metadata = StandingsFunction.get_metadata()
    parameters = {parameter.name: parameter for parameter in metadata.parameters}
    assert set(parameters) == {"season", "league", "standings_type"}
    assert all(not parameter.required for parameter in parameters.values())


def _key_of(table, kind: str) -> list[tuple[str, ...]]:
    return [
        tuple(name for path in record.definition.column_paths for name in path)
        for record in table.constraints
        if record.definition.kind == kind
    ]


def test_table_primary_key_is_team_id() -> None:
    table = MLB_CATALOG.schemas[0].tables[0]
    assert _key_of(table, "PRIMARY_KEY") == [("team_id",)]
    assert _key_of(table, "NOT_NULL") == [("team_id",)]


def test_player_tables_use_player_id_as_primary_key() -> None:
    for table in MLB_CATALOG.schemas[0].tables[1:3]:
        assert _key_of(table, "PRIMARY_KEY") == [("player_id",)]
        assert _key_of(table, "NOT_NULL") == [("player_id",)]
    fielding = MLB_CATALOG.schemas[0].tables[3]
    assert _key_of(fielding, "PRIMARY_KEY") == [("player_id", "position_code")]
    assert _key_of(fielding, "NOT_NULL") == [("player_id",), ("position_code",)]


def test_catalog_discovery_contract_is_public_and_machine_readable() -> None:
    examples = json.loads(MLB_CATALOG.tags["vgi.executable_examples"])
    tasks = json.loads(MLB_CATALOG.tags["vgi.agent_test_tasks"])

    assert examples
    assert all({"name", "description", "sql", "expected_result"} <= example.keys() for example in examples)
    assert tasks
    assert all(set(task) == {"name", "prompt"} for task in tasks)
    assert len({task["name"] for task in tasks}) == len(tasks)
