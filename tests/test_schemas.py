"""Tests for MLB payload flattening and exact numeric conversion."""

from datetime import UTC, datetime
from decimal import Decimal

from vgi_mlb.schemas import STANDINGS_SCHEMA, batch_from_records, flatten_records


def sample_payload() -> list[dict]:
    """Return a representative, deliberately small standings response."""
    return [
        {
            "standingsType": "regularSeason",
            "league": {"id": 103, "name": "American League", "abbreviation": "AL"},
            "division": {"id": 201, "name": "American League East", "abbreviation": "ALE"},
            "teamRecords": [
                {
                    "team": {"id": 147, "name": "New York Yankees", "abbreviation": "NYY"},
                    "season": "2025",
                    "divisionRank": "1",
                    "leagueRank": "2",
                    "sportRank": "3",
                    "gamesPlayed": 162,
                    "gamesBack": "-",
                    "wildCardGamesBack": "-",
                    "leagueRecord": {"wins": 94, "losses": 68, "ties": 0, "pct": ".580"},
                    "wins": 94,
                    "losses": 68,
                    "winningPercentage": ".580",
                    "runsScored": 815,
                    "runsAllowed": 668,
                    "runDifferential": 147,
                    "streak": {"streakCode": "W1", "streakType": "wins", "streakNumber": 1},
                    "records": {
                        "splitRecords": [
                            {"type": "home", "wins": 50, "losses": 31},
                            {"type": "away", "wins": 44, "losses": 37},
                            {"type": "lastTen", "wins": 7, "losses": 3},
                        ]
                    },
                    "divisionLeader": True,
                    "divisionChamp": True,
                    "hasWildcard": True,
                    "clinched": True,
                    "clinchIndicator": "z",
                    "lastUpdated": "2025-09-28T22:01:02Z",
                }
            ],
        }
    ]


def test_flattens_one_team_row() -> None:
    row = flatten_records(sample_payload())[0]
    assert row["team_id"] == 147
    assert row["league_abbreviation"] == "AL"
    assert row["division_rank"] == 1
    assert row["winning_percentage"] == Decimal(".580")
    assert row["games_back"] == Decimal("0.0")
    assert row["games_back_display"] == "-"
    assert (row["home_wins"], row["away_wins"], row["last_ten_wins"]) == (50, 44, 7)
    assert row["last_updated"] == datetime(2025, 9, 28, 22, 1, 2, tzinfo=UTC)


def test_batch_has_the_declared_schema() -> None:
    batch = batch_from_records(sample_payload(), STANDINGS_SCHEMA)
    assert batch.schema == STANDINGS_SCHEMA
    assert batch.num_rows == 1
    assert batch.column("winning_percentage").to_pylist() == [Decimal("0.580")]


def test_missing_optional_data_becomes_null() -> None:
    payload = [{"teamRecords": [{"team": {"id": 1, "name": "A"}}]}]
    batch = batch_from_records(payload, STANDINGS_SCHEMA)
    assert batch.num_rows == 1
    assert batch.column("home_wins").to_pylist() == [None]
    assert batch.column("last_updated").to_pylist() == [None]


def test_empty_response_retains_schema() -> None:
    batch = batch_from_records([], STANDINGS_SCHEMA)
    assert batch.num_rows == 0
    assert batch.schema == STANDINGS_SCHEMA
