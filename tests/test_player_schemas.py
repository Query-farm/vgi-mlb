"""Tests for player batting and pitching Arrow conversion."""

from datetime import date
from decimal import Decimal

import pyarrow as pa

from vgi_mlb.player_schemas import (
    BATTING_SCHEMA,
    FIELDING_SCHEMA,
    PITCHING_SCHEMA,
    batch_from_rows,
    batch_from_splits,
    flatten_batting,
    flatten_fielding,
    flatten_pitching,
    innings_to_outs,
)


def _split(stat: dict) -> dict:
    return {
        "season": "2025",
        "numTeams": 1,
        "player": {
            "id": 660271,
            "fullName": "Shohei Ohtani",
            "birthDate": "1994-07-05",
            "primaryNumber": "17",
            "batSide": {"code": "L"},
            "pitchHand": {"code": "R"},
        },
        "team": {
            "id": 119,
            "name": "Los Angeles Dodgers",
            "abbreviation": "LAD",
            "league": {"id": 104, "name": "National League", "abbreviation": "NL"},
        },
        "position": {"code": "Y", "name": "Two-Way Player", "abbreviation": "TWP"},
        "stat": {"age": 31, **stat},
    }


def test_batting_stats_are_typed_and_flattened() -> None:
    split = _split(
        {
            "gamesPlayed": 158,
            "plateAppearances": 727,
            "atBats": 611,
            "hits": 172,
            "homeRuns": 55,
            "baseOnBalls": 109,
            "strikeOuts": 187,
            "avg": ".282",
            "obp": ".392",
            "slg": ".622",
            "ops": "1.014",
        }
    )
    row = flatten_batting([split])[0]
    assert row["player_name"] == "Shohei Ohtani"
    assert row["birth_date"] == date(1994, 7, 5)
    assert row["league_abbreviation"] == "NL"
    assert row["home_runs"] == 55
    assert row["ops"] == Decimal("1.014")
    batch = batch_from_splits([split], BATTING_SCHEMA, pitching=False)
    assert batch.schema == BATTING_SCHEMA
    assert batch.column("ops").to_pylist() == [Decimal("1.014")]


def test_pitching_preserves_baseball_innings_notation() -> None:
    split = _split(
        {
            "gamesPitched": 14,
            "gamesStarted": 14,
            "inningsPitched": "47.2",
            "outs": 143,
            "strikeOuts": 62,
            "era": "2.45",
            "whip": "1.04",
            "strikeoutsPer9Inn": "11.71",
        }
    )
    row = flatten_pitching([split])[0]
    assert row["innings_pitched"] == "47.2"
    assert row["outs"] == 143
    assert row["era"] == Decimal("2.45")
    batch = batch_from_splits([split], PITCHING_SCHEMA, pitching=True)
    assert batch.schema == PITCHING_SCHEMA


def test_empty_player_result_retains_projected_schema() -> None:
    projected = pa.schema([BATTING_SCHEMA.field(name) for name in ("player_id", "home_runs", "ops")])
    batch = batch_from_splits([], projected, pitching=False)
    assert batch.num_rows == 0
    assert batch.schema == projected


def test_multi_team_total_does_not_claim_one_team() -> None:
    split = _split({"gamesPlayed": 100, "hits": 80})
    split["numTeams"] = 2
    row = flatten_batting([split])[0]
    assert row["team_id"] is None
    assert row["team_name"] is None
    assert row["last_team_id"] == 119
    assert row["last_team_name"] == "Los Angeles Dodgers"


def test_fielding_innings_have_exact_outs() -> None:
    split = _split({"gamesPlayed": 10, "innings": "39.2", "putOuts": 20, "fielding": ".990"})
    row = flatten_fielding([split])[0]
    assert innings_to_outs("39.2") == 119
    assert row["outs"] == 119
    batch = batch_from_rows([row], FIELDING_SCHEMA)
    assert batch.schema == FIELDING_SCHEMA
