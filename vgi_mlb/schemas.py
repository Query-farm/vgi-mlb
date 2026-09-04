"""Arrow schema and flattening for MLB standings responses."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pyarrow as pa

from vgi_mlb.meta import field

PERCENTAGE = pa.decimal128(4, 3)
GAMES_BACK = pa.decimal128(6, 1)
TIMESTAMP = pa.timestamp("us", tz="UTC")

STANDINGS_SCHEMA = pa.schema(
    [
        field("season", pa.int32(), "MLB season year."),
        field("standings_type", pa.string(), "Requested standings view, such as regularSeason."),
        field("league_id", pa.int32(), "MLB league identifier: 103 for AL or 104 for NL."),
        field("league_name", pa.string(), "League name."),
        field("league_abbreviation", pa.string(), "League abbreviation, AL or NL."),
        field("division_id", pa.int32(), "MLB division identifier."),
        field("division_name", pa.string(), "Division name."),
        field("division_abbreviation", pa.string(), "Division abbreviation."),
        field("team_id", pa.int32(), "Stable MLB team identifier."),
        field("team_name", pa.string(), "Full team name."),
        field("team_abbreviation", pa.string(), "Team abbreviation."),
        field("division_rank", pa.int32(), "Rank within the team's division."),
        field("league_rank", pa.int32(), "Rank within the team's league."),
        field("sport_rank", pa.int32(), "Rank across Major League Baseball."),
        field("wild_card_rank", pa.int32(), "Wild-card rank when supplied by this standings view."),
        field("games_played", pa.int32(), "Games played."),
        field("wins", pa.int32(), "Wins."),
        field("losses", pa.int32(), "Losses."),
        field("ties", pa.int32(), "Ties, normally zero in regular-season MLB."),
        field("winning_percentage", PERCENTAGE, "Winning percentage as an exact decimal."),
        field("games_back", GAMES_BACK, "Division games back; a leader's '-' marker maps to 0.0."),
        field("games_back_display", pa.string(), "MLB's original games-back display value."),
        field("wild_card_games_back", GAMES_BACK, "Wild-card games back; '-' maps to 0.0."),
        field("wild_card_games_back_display", pa.string(), "Original wild-card games-back value."),
        field("runs_scored", pa.int32(), "Runs scored."),
        field("runs_allowed", pa.int32(), "Runs allowed."),
        field("run_differential", pa.int32(), "Runs scored minus runs allowed."),
        field("streak_code", pa.string(), "Compact streak label, for example W3 or L1."),
        field("streak_type", pa.string(), "Streak direction, wins or losses."),
        field("streak_number", pa.int32(), "Length of the current streak."),
        field("home_wins", pa.int32(), "Wins at home."),
        field("home_losses", pa.int32(), "Losses at home."),
        field("away_wins", pa.int32(), "Wins away."),
        field("away_losses", pa.int32(), "Losses away."),
        field("last_ten_wins", pa.int32(), "Wins in the team's last ten games."),
        field("last_ten_losses", pa.int32(), "Losses in the team's last ten games."),
        field("division_leader", pa.bool_(), "Whether the team currently leads its division."),
        field("division_champ", pa.bool_(), "Whether the team has clinched its division."),
        field("has_wildcard", pa.bool_(), "Whether the team holds a wild-card place."),
        field("clinched", pa.bool_(), "Whether the team has clinched a postseason place."),
        field("clinch_indicator", pa.string(), "MLB clinching marker, when present."),
        field("elimination_number", pa.string(), "MLB's division/playoff elimination marker."),
        field("wild_card_elimination_number", pa.string(), "MLB's wild-card elimination marker."),
        field("magic_number", pa.string(), "MLB's displayed magic number."),
        field("last_updated", TIMESTAMP, "Time MLB last updated this team's record."),
    ]
)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def to_int(value: Any) -> int | None:
    """Parse an integer-like API value without treating booleans as integers."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def to_decimal(value: Any) -> Decimal | None:
    """Parse a finite decimal value, returning null for display markers."""
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def to_games_back(value: Any) -> Decimal | None:
    """Parse games back, treating MLB's leader marker as zero games back."""
    if value == "-":
        return Decimal("0.0")
    return to_decimal(value)


def to_timestamp(value: Any) -> datetime | None:
    """Parse MLB's RFC-3339 timestamp into UTC."""
    if not isinstance(value, str) or not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _split(team_record: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    records = _mapping(team_record.get("records"))
    splits = records.get("splitRecords")
    if not isinstance(splits, list):
        return {}
    return next(
        (value for value in splits if isinstance(value, Mapping) and value.get("type") == name),
        {},
    )


def flatten_records(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten nested league/division/team records into one row per team."""
    rows: list[dict[str, Any]] = []
    for grouping in records:
        league = _mapping(grouping.get("league"))
        division = _mapping(grouping.get("division"))
        team_records = grouping.get("teamRecords")
        if not isinstance(team_records, list):
            continue
        for raw_team_record in team_records:
            if not isinstance(raw_team_record, Mapping):
                continue
            team_record = raw_team_record
            team = _mapping(team_record.get("team"))
            team_league = _mapping(team.get("league"))
            team_division = _mapping(team.get("division"))
            resolved_league = league or team_league
            resolved_division = division or team_division
            league_record = _mapping(team_record.get("leagueRecord"))
            streak = _mapping(team_record.get("streak"))
            home = _split(team_record, "home")
            away = _split(team_record, "away")
            last_ten = _split(team_record, "lastTen")
            games_back_display = team_record.get("gamesBack")
            wild_card_games_back_display = team_record.get("wildCardGamesBack")
            rows.append(
                {
                    "season": to_int(team_record.get("season")),
                    "standings_type": grouping.get("standingsType"),
                    "league_id": to_int(resolved_league.get("id")),
                    "league_name": resolved_league.get("name"),
                    "league_abbreviation": resolved_league.get("abbreviation"),
                    "division_id": to_int(resolved_division.get("id")),
                    "division_name": resolved_division.get("name"),
                    "division_abbreviation": resolved_division.get("abbreviation"),
                    "team_id": to_int(team.get("id")),
                    "team_name": team.get("name"),
                    "team_abbreviation": team.get("abbreviation"),
                    "division_rank": to_int(team_record.get("divisionRank")),
                    "league_rank": to_int(team_record.get("leagueRank")),
                    "sport_rank": to_int(team_record.get("sportRank")),
                    "wild_card_rank": to_int(team_record.get("wildCardRank")),
                    "games_played": to_int(team_record.get("gamesPlayed")),
                    "wins": to_int(team_record.get("wins", league_record.get("wins"))),
                    "losses": to_int(team_record.get("losses", league_record.get("losses"))),
                    "ties": to_int(league_record.get("ties")),
                    "winning_percentage": to_decimal(
                        team_record.get("winningPercentage", league_record.get("pct"))
                    ),
                    "games_back": to_games_back(games_back_display),
                    "games_back_display": games_back_display,
                    "wild_card_games_back": to_games_back(wild_card_games_back_display),
                    "wild_card_games_back_display": wild_card_games_back_display,
                    "runs_scored": to_int(team_record.get("runsScored")),
                    "runs_allowed": to_int(team_record.get("runsAllowed")),
                    "run_differential": to_int(team_record.get("runDifferential")),
                    "streak_code": streak.get("streakCode"),
                    "streak_type": streak.get("streakType"),
                    "streak_number": to_int(streak.get("streakNumber")),
                    "home_wins": to_int(home.get("wins")),
                    "home_losses": to_int(home.get("losses")),
                    "away_wins": to_int(away.get("wins")),
                    "away_losses": to_int(away.get("losses")),
                    "last_ten_wins": to_int(last_ten.get("wins")),
                    "last_ten_losses": to_int(last_ten.get("losses")),
                    "division_leader": team_record.get("divisionLeader"),
                    "division_champ": team_record.get("divisionChamp"),
                    "has_wildcard": team_record.get("hasWildcard"),
                    "clinched": team_record.get("clinched"),
                    "clinch_indicator": team_record.get("clinchIndicator"),
                    "elimination_number": team_record.get("eliminationNumber"),
                    "wild_card_elimination_number": team_record.get("wildCardEliminationNumber"),
                    "magic_number": team_record.get("magicNumber"),
                    "last_updated": to_timestamp(team_record.get("lastUpdated")),
                }
            )
    return rows


def batch_from_records(records: Sequence[dict[str, Any]], schema: pa.Schema) -> pa.RecordBatch:
    """Build a record batch in the declared column order."""
    rows = flatten_records(records)
    return pa.RecordBatch.from_arrays(
        [pa.array([row.get(value.name) for row in rows], type=value.type) for value in schema],
        schema=schema,
    )
