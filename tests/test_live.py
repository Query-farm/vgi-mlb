"""Opt-in smoke test against MLB's public Stats API."""

from datetime import date

import pytest

from vgi_mlb.api import fetch_person_stats, fetch_player_stats, fetch_standings
from vgi_mlb.player_schemas import (
    BATTING_SCHEMA,
    FIELDING_SCHEMA,
    PITCHING_SCHEMA,
    batch_from_rows,
    batch_from_splits,
    flatten_batting,
    flatten_batting_game_log,
    flatten_fielding,
    flatten_pitching,
)
from vgi_mlb.schemas import flatten_records


@pytest.mark.live
def test_current_major_league_standings() -> None:
    rows = flatten_records(fetch_standings().records)
    assert len(rows) >= 30
    assert {row["league_id"] for row in rows} == {103, 104}
    assert all(row["team_id"] is not None for row in rows)


@pytest.mark.live
@pytest.mark.parametrize(
    ("group", "schema", "pitching"),
    [("hitting", BATTING_SCHEMA, False), ("pitching", PITCHING_SCHEMA, True)],
)
def test_current_player_stats(group, schema, pitching: bool) -> None:
    response = fetch_player_stats(group=group)
    batch = batch_from_splits(response.splits, schema, pitching=pitching)
    player_ids = batch.column("player_id").to_pylist()
    assert batch.num_rows >= 500
    assert None not in player_ids
    assert len(player_ids) == len(set(player_ids))


@pytest.mark.live
def test_current_fielding_stats() -> None:
    response = fetch_player_stats(group="fielding")
    batch = batch_from_rows(flatten_fielding(response.splits), FIELDING_SCHEMA)
    assert batch.num_rows >= 2_000
    assert None not in batch.column("player_id").to_pylist()


@pytest.mark.live
def test_multi_team_aggregate_and_team_splits() -> None:
    aggregate = flatten_pitching(fetch_player_stats(group="pitching", season=2025).splits)
    duran = next(row for row in aggregate if row["player_id"] == 661395)
    assert duran["num_teams"] == 2
    assert duran["team_id"] is None
    assert duran["last_team_id"] == 143

    response = fetch_person_stats(661395, group="pitching", stat_type="yearByYear", season=2025)
    splits = [value for value in response.splits if value.get("season") == "2025" and value.get("team")]
    rows = flatten_pitching(splits)
    assert {row["team_id"] for row in rows} == {142, 143}


@pytest.mark.live
def test_batting_game_log_date_range() -> None:
    response = fetch_person_stats(
        660271,
        group="hitting",
        stat_type="gameLog",
        season=2025,
        start_date=date(2025, 6, 1),
        end_date=date(2025, 6, 30),
    )
    rows = flatten_batting_game_log(response.splits)
    assert rows
    assert min(row["game_date"] for row in rows) >= date(2025, 6, 1)
    assert max(row["game_date"] for row in rows) <= date(2025, 6, 30)


@pytest.mark.live
def test_career_batting() -> None:
    response = fetch_person_stats(660271, group="hitting", stat_type="career")
    rows = flatten_batting(response.splits)
    assert len(rows) == 1
    assert rows[0]["home_runs"] >= 300
