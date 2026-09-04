"""Arrow schemas and flattening for MLB season player statistics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

import pyarrow as pa

from vgi_mlb.meta import field
from vgi_mlb.schemas import to_decimal, to_int

RATE = pa.decimal128(5, 3)
RATE_2 = pa.decimal128(7, 2)


def _common_fields() -> list[pa.Field]:
    return [
        field("season", pa.int32(), "MLB season year."),
        field(
            "game_type", pa.string(), "MLB game-type code, such as R for regular season or P for postseason."
        ),
        field("player_id", pa.int32(), "Stable MLB player identifier."),
        field("player_name", pa.string(), "Player's full name."),
        field("age", pa.int32(), "Player age reported for this statistical season."),
        field("birth_date", pa.date32(), "Player birth date."),
        field("primary_number", pa.string(), "Uniform number, when available."),
        field("position_code", pa.string(), "MLB position code."),
        field("position_name", pa.string(), "Position name."),
        field("position_abbreviation", pa.string(), "Position abbreviation."),
        field("bats", pa.string(), "Batting side code: L, R, or S."),
        field("throws", pa.string(), "Throwing-hand code: L or R."),
        field(
            "team_id",
            pa.int32(),
            "Team represented by every statistic in this row; NULL for multi-team totals.",
        ),
        field("team_name", pa.string(), "Team represented by this row; NULL for multi-team totals."),
        field(
            "team_abbreviation",
            pa.string(),
            "Abbreviation of the represented team; NULL for multi-team totals.",
        ),
        field(
            "last_team_id",
            pa.int32(),
            "Last or current team MLB associates with the player, even for multi-team totals.",
        ),
        field("last_team_name", pa.string(), "Last or current team MLB associates with the player."),
        field("last_team_abbreviation", pa.string(), "Abbreviation of the player's last or current team."),
        field("league_id", pa.int32(), "MLB league identifier: 103 for AL or 104 for NL."),
        field("league_name", pa.string(), "League name."),
        field("league_abbreviation", pa.string(), "League abbreviation, AL or NL."),
        field("num_teams", pa.int32(), "Number of teams represented by this aggregate split."),
        field("num_leagues", pa.int32(), "Number of leagues represented by this aggregate split."),
    ]


BATTING_SCHEMA = pa.schema(
    [
        *_common_fields(),
        field("games_played", pa.int32(), "Games played."),
        field("plate_appearances", pa.int32(), "Plate appearances."),
        field("at_bats", pa.int32(), "Official at-bats."),
        field("runs", pa.int32(), "Runs scored."),
        field("hits", pa.int32(), "Hits."),
        field("doubles", pa.int32(), "Doubles."),
        field("triples", pa.int32(), "Triples."),
        field("home_runs", pa.int32(), "Home runs."),
        field("rbi", pa.int32(), "Runs batted in."),
        field("stolen_bases", pa.int32(), "Stolen bases."),
        field("caught_stealing", pa.int32(), "Times caught stealing."),
        field("walks", pa.int32(), "Bases on balls."),
        field("intentional_walks", pa.int32(), "Intentional bases on balls."),
        field("strikeouts", pa.int32(), "Strikeouts."),
        field("hit_by_pitch", pa.int32(), "Times hit by a pitch."),
        field("sacrifice_bunts", pa.int32(), "Sacrifice bunts."),
        field("sacrifice_flies", pa.int32(), "Sacrifice flies."),
        field("total_bases", pa.int32(), "Total bases."),
        field("grounded_into_double_play", pa.int32(), "Grounded-into-double-play count."),
        field("pitches_seen", pa.int32(), "Pitches seen."),
        field("left_on_base", pa.int32(), "Runners left on base in the player's plate appearances."),
        field("batting_average", RATE, "Batting average as an exact decimal."),
        field("on_base_percentage", RATE, "On-base percentage as an exact decimal."),
        field("slugging_percentage", RATE, "Slugging percentage as an exact decimal."),
        field("ops", RATE, "On-base plus slugging as an exact decimal."),
        field("babip", RATE, "Batting average on balls in play."),
    ]
)


PITCHING_SCHEMA = pa.schema(
    [
        *_common_fields(),
        field("games_played", pa.int32(), "Games played."),
        field("games_pitched", pa.int32(), "Games pitched."),
        field("games_started", pa.int32(), "Games started."),
        field("games_finished", pa.int32(), "Games finished."),
        field("wins", pa.int32(), "Pitching wins."),
        field("losses", pa.int32(), "Pitching losses."),
        field("saves", pa.int32(), "Saves."),
        field("save_opportunities", pa.int32(), "Save opportunities."),
        field("holds", pa.int32(), "Holds."),
        field("blown_saves", pa.int32(), "Blown saves."),
        field("complete_games", pa.int32(), "Complete games."),
        field("shutouts", pa.int32(), "Shutouts."),
        field(
            "innings_pitched",
            pa.string(),
            "Baseball innings notation from MLB; .1 and .2 mean one and two outs, not decimal fractions.",
        ),
        field("outs", pa.int32(), "Outs recorded; use this for exact innings arithmetic."),
        field("batters_faced", pa.int32(), "Batters faced."),
        field("hits", pa.int32(), "Hits allowed."),
        field("runs", pa.int32(), "Runs allowed."),
        field("earned_runs", pa.int32(), "Earned runs allowed."),
        field("home_runs", pa.int32(), "Home runs allowed."),
        field("walks", pa.int32(), "Bases on balls allowed."),
        field("intentional_walks", pa.int32(), "Intentional walks allowed."),
        field("strikeouts", pa.int32(), "Strikeouts."),
        field("hit_batters", pa.int32(), "Batters hit by a pitch."),
        field("wild_pitches", pa.int32(), "Wild pitches."),
        field("balks", pa.int32(), "Balks."),
        field("pickoffs", pa.int32(), "Pickoffs."),
        field("pitches", pa.int32(), "Pitches thrown."),
        field("strikes", pa.int32(), "Strikes thrown."),
        field("era", RATE_2, "Earned run average."),
        field("whip", RATE_2, "Walks plus hits per inning pitched."),
        field("opponent_average", RATE, "Opposing batting average."),
        field("opponent_obp", RATE, "Opposing on-base percentage."),
        field("opponent_slg", RATE, "Opposing slugging percentage."),
        field("opponent_ops", RATE, "Opposing on-base plus slugging."),
        field("strike_percentage", RATE, "Share of pitches recorded as strikes."),
        field("win_percentage", RATE, "Pitching win percentage."),
        field("strikeout_walk_ratio", RATE_2, "Strikeouts divided by walks."),
        field("strikeouts_per_nine", RATE_2, "Strikeouts per nine innings."),
        field("walks_per_nine", RATE_2, "Walks per nine innings."),
        field("hits_per_nine", RATE_2, "Hits per nine innings."),
        field("home_runs_per_nine", RATE_2, "Home runs per nine innings."),
        field("runs_per_nine", RATE_2, "Runs allowed per nine innings."),
    ]
)


FIELDING_SCHEMA = pa.schema(
    [
        *_common_fields(),
        field("games_played", pa.int32(), "Games in which the player appeared at this position."),
        field("games_started", pa.int32(), "Games started at this position."),
        field("innings", pa.string(), "Fielding innings in baseball notation; .1 and .2 represent outs."),
        field("outs", pa.int32(), "Fielding outs derived from MLB's innings notation."),
        field("putouts", pa.int32(), "Putouts credited to the fielder."),
        field("assists", pa.int32(), "Assists credited to the fielder."),
        field("errors", pa.int32(), "Errors charged to the fielder."),
        field("throwing_errors", pa.int32(), "Throwing errors charged to the fielder."),
        field("chances", pa.int32(), "Total fielding chances."),
        field("double_plays", pa.int32(), "Double plays involving the fielder."),
        field("triple_plays", pa.int32(), "Triple plays involving the fielder."),
        field("fielding_percentage", RATE, "Successful chances divided by total chances."),
        field("range_factor_per_game", RATE_2, "Putouts plus assists per game at the position."),
        field("range_factor_per_nine", RATE_2, "Putouts plus assists per nine defensive innings."),
    ]
)


ADVANCED_BATTING_SCHEMA = pa.schema(
    [
        *_common_fields(),
        field("plate_appearances", pa.int32(), "Plate appearances represented by the row."),
        field("total_bases", pa.int32(), "Bases produced by hits."),
        field("extra_base_hits", pa.int32(), "Doubles, triples, and home runs combined."),
        field("balls_in_play", pa.int32(), "Batted balls put into play."),
        field("total_swings", pa.int32(), "Recorded swings."),
        field("swing_and_misses", pa.int32(), "Swings that missed the pitch."),
        field("walk_offs", pa.int32(), "Walk-off hits."),
        field("reached_on_error", pa.int32(), "Times reaching base on an error."),
        field("gidp", pa.int32(), "Grounded-into-double-play count."),
        field("gidp_opportunities", pa.int32(), "Grounded-into-double-play opportunities."),
        field("babip", RATE, "Batting average on balls in play."),
        field("isolated_power", RATE, "Slugging percentage minus batting average."),
        field("pitches_per_plate_appearance", RATE, "Pitches seen per plate appearance."),
        field("walks_per_plate_appearance", RATE, "Walks divided by plate appearances."),
        field("strikeouts_per_plate_appearance", RATE, "Strikeouts divided by plate appearances."),
        field("home_runs_per_plate_appearance", RATE, "Home runs divided by plate appearances."),
        field("walks_per_strikeout", RATE, "Walks divided by strikeouts."),
    ]
)


ADVANCED_PITCHING_SCHEMA = pa.schema(
    [
        *_common_fields(),
        field("batters_faced", pa.int32(), "Batters faced."),
        field(
            "quality_starts", pa.int32(), "Starts with at least six innings and at most three earned runs."
        ),
        field("inherited_runners", pa.int32(), "Runners inherited on entry."),
        field("inherited_runners_scored", pa.int32(), "Inherited runners who scored."),
        field("bequeathed_runners", pa.int32(), "Runners left on base when the pitcher exited."),
        field("bequeathed_runners_scored", pa.int32(), "Bequeathed runners who later scored."),
        field("balls_in_play", pa.int32(), "Batted balls put into play against the pitcher."),
        field("total_swings", pa.int32(), "Recorded opposing swings."),
        field("swing_and_misses", pa.int32(), "Opposing swings that missed."),
        field("babip", RATE, "Opposing batting average on balls in play."),
        field("opponent_obp", RATE, "Opposing on-base percentage."),
        field("opponent_slg", RATE, "Opposing slugging percentage."),
        field("opponent_ops", RATE, "Opposing on-base plus slugging."),
        field("isolated_power", RATE, "Opposing isolated power."),
        field("strike_percentage", RATE, "Strikes divided by total pitches."),
        field("whiff_percentage", RATE, "Swinging misses divided by swings."),
        field("strikeouts_minus_walks_percentage", RATE, "Strikeout rate minus walk rate."),
        field("strikeouts_per_nine", RATE_2, "Strikeouts per nine innings."),
        field("walks_per_nine", RATE_2, "Walks per nine innings."),
        field("hits_per_nine", RATE_2, "Hits per nine innings."),
        field("home_runs_per_nine", RATE_2, "Home runs per nine innings."),
        field("runs_per_nine", RATE_2, "Runs allowed per nine innings."),
        field("pitches_per_inning", RATE_2, "Pitches per inning."),
        field("pitches_per_plate_appearance", RATE, "Pitches per batter faced."),
    ]
)


def _game_fields() -> list[pa.Field]:
    return [
        field("season", pa.int32(), "MLB season year."),
        field("game_pk", pa.int32(), "Stable MLB game identifier."),
        field("game_date", pa.date32(), "Date of the game."),
        field("game_type", pa.string(), "MLB game-type code."),
        field("player_id", pa.int32(), "Stable MLB player identifier."),
        field("player_name", pa.string(), "Player's full name."),
        field("team_id", pa.int32(), "Team represented by this game line."),
        field("team_name", pa.string(), "Team represented by this game line."),
        field("team_abbreviation", pa.string(), "Team abbreviation for this game."),
        field("opponent_id", pa.int32(), "Opponent's MLB team identifier."),
        field("opponent_name", pa.string(), "Opponent's team name."),
        field("opponent_abbreviation", pa.string(), "Opponent's team abbreviation."),
        field("is_home", pa.bool_(), "Whether the player's team was at home."),
        field("is_win", pa.bool_(), "Whether the player's team won."),
        field("summary", pa.string(), "MLB's compact summary of the player's game line."),
    ]


BATTING_GAME_LOG_SCHEMA = pa.schema(
    [
        *_game_fields(),
        field("plate_appearances", pa.int32(), "Plate appearances in the game."),
        field("at_bats", pa.int32(), "Official at-bats in the game."),
        field("runs", pa.int32(), "Runs scored in the game."),
        field("hits", pa.int32(), "Hits in the game."),
        field("doubles", pa.int32(), "Doubles in the game."),
        field("triples", pa.int32(), "Triples in the game."),
        field("home_runs", pa.int32(), "Home runs in the game."),
        field("rbi", pa.int32(), "Runs batted in during the game."),
        field("walks", pa.int32(), "Walks in the game."),
        field("strikeouts", pa.int32(), "Strikeouts in the game."),
        field("stolen_bases", pa.int32(), "Stolen bases in the game."),
        field("batting_average", RATE, "Batting average for the game line."),
        field("on_base_percentage", RATE, "On-base percentage for the game line."),
        field("slugging_percentage", RATE, "Slugging percentage for the game line."),
        field("ops", RATE, "On-base plus slugging for the game line."),
    ]
)


PITCHING_GAME_LOG_SCHEMA = pa.schema(
    [
        *_game_fields(),
        field("games_started", pa.int32(), "One when the player started this game, otherwise zero."),
        field("innings_pitched", pa.string(), "Innings in baseball notation; .1 and .2 represent outs."),
        field("outs", pa.int32(), "Outs recorded in the game."),
        field("hits", pa.int32(), "Hits allowed in the game."),
        field("runs", pa.int32(), "Runs allowed in the game."),
        field("earned_runs", pa.int32(), "Earned runs allowed in the game."),
        field("home_runs", pa.int32(), "Home runs allowed in the game."),
        field("walks", pa.int32(), "Walks allowed in the game."),
        field("strikeouts", pa.int32(), "Strikeouts in the game."),
        field("pitches", pa.int32(), "Pitches thrown in the game."),
        field("strikes", pa.int32(), "Strikes thrown in the game."),
        field("era", RATE_2, "Earned run average reported after the game line."),
        field("whip", RATE_2, "Walks plus hits per inning for the game line."),
    ]
)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def innings_to_outs(value: Any) -> int | None:
    """Convert baseball innings notation into an exact number of outs."""
    if not isinstance(value, str):
        return None
    whole, separator, partial = value.partition(".")
    if not separator or partial not in {"0", "1", "2"}:
        return None
    innings = to_int(whole)
    return innings * 3 + int(partial) if innings is not None else None


def _common(split: Mapping[str, Any]) -> tuple[dict[str, Any], Mapping[str, Any]]:
    stat = _mapping(split.get("stat"))
    player = _mapping(split.get("player"))
    team = _mapping(split.get("team"))
    position = _mapping(split.get("position")) or _mapping(player.get("primaryPosition"))
    league = _mapping(team.get("league")) or _mapping(split.get("league"))
    num_teams = to_int(split.get("numTeams"))
    represents_one_team = num_teams in {None, 1}
    row = {
        "season": to_int(split.get("season")),
        "game_type": split.get("gameType"),
        "player_id": to_int(player.get("id")),
        "player_name": player.get("fullName"),
        "age": to_int(stat.get("age")),
        "birth_date": _date(player.get("birthDate")),
        "primary_number": player.get("primaryNumber"),
        "position_code": position.get("code"),
        "position_name": position.get("name"),
        "position_abbreviation": position.get("abbreviation"),
        "bats": _mapping(player.get("batSide")).get("code"),
        "throws": _mapping(player.get("pitchHand")).get("code"),
        "team_id": to_int(team.get("id")) if represents_one_team else None,
        "team_name": team.get("name") if represents_one_team else None,
        "team_abbreviation": team.get("abbreviation") if represents_one_team else None,
        "last_team_id": to_int(team.get("id")),
        "last_team_name": team.get("name"),
        "last_team_abbreviation": team.get("abbreviation"),
        "league_id": to_int(league.get("id")),
        "league_name": league.get("name"),
        "league_abbreviation": league.get("abbreviation") or _mapping(split.get("league")).get("name"),
        "num_teams": num_teams,
        "num_leagues": to_int(split.get("numLeagues")),
    }
    return row, stat


def flatten_batting(splits: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten MLB hitting splits into one row per player."""
    rows: list[dict[str, Any]] = []
    for split in splits:
        row, stat = _common(split)
        row.update(
            {
                "games_played": to_int(stat.get("gamesPlayed")),
                "plate_appearances": to_int(stat.get("plateAppearances")),
                "at_bats": to_int(stat.get("atBats")),
                "runs": to_int(stat.get("runs")),
                "hits": to_int(stat.get("hits")),
                "doubles": to_int(stat.get("doubles")),
                "triples": to_int(stat.get("triples")),
                "home_runs": to_int(stat.get("homeRuns")),
                "rbi": to_int(stat.get("rbi")),
                "stolen_bases": to_int(stat.get("stolenBases")),
                "caught_stealing": to_int(stat.get("caughtStealing")),
                "walks": to_int(stat.get("baseOnBalls")),
                "intentional_walks": to_int(stat.get("intentionalWalks")),
                "strikeouts": to_int(stat.get("strikeOuts")),
                "hit_by_pitch": to_int(stat.get("hitByPitch")),
                "sacrifice_bunts": to_int(stat.get("sacBunts")),
                "sacrifice_flies": to_int(stat.get("sacFlies")),
                "total_bases": to_int(stat.get("totalBases")),
                "grounded_into_double_play": to_int(stat.get("groundIntoDoublePlay")),
                "pitches_seen": to_int(stat.get("numberOfPitches")),
                "left_on_base": to_int(stat.get("leftOnBase")),
                "batting_average": to_decimal(stat.get("avg")),
                "on_base_percentage": to_decimal(stat.get("obp")),
                "slugging_percentage": to_decimal(stat.get("slg")),
                "ops": to_decimal(stat.get("ops")),
                "babip": to_decimal(stat.get("babip")),
            }
        )
        rows.append(row)
    return rows


def flatten_pitching(splits: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten MLB pitching splits into one row per player."""
    rows: list[dict[str, Any]] = []
    for split in splits:
        row, stat = _common(split)
        row.update(
            {
                "games_played": to_int(stat.get("gamesPlayed")),
                "games_pitched": to_int(stat.get("gamesPitched")),
                "games_started": to_int(stat.get("gamesStarted")),
                "games_finished": to_int(stat.get("gamesFinished")),
                "wins": to_int(stat.get("wins")),
                "losses": to_int(stat.get("losses")),
                "saves": to_int(stat.get("saves")),
                "save_opportunities": to_int(stat.get("saveOpportunities")),
                "holds": to_int(stat.get("holds")),
                "blown_saves": to_int(stat.get("blownSaves")),
                "complete_games": to_int(stat.get("completeGames")),
                "shutouts": to_int(stat.get("shutouts")),
                "innings_pitched": stat.get("inningsPitched"),
                "outs": to_int(stat.get("outs")),
                "batters_faced": to_int(stat.get("battersFaced")),
                "hits": to_int(stat.get("hits")),
                "runs": to_int(stat.get("runs")),
                "earned_runs": to_int(stat.get("earnedRuns")),
                "home_runs": to_int(stat.get("homeRuns")),
                "walks": to_int(stat.get("baseOnBalls")),
                "intentional_walks": to_int(stat.get("intentionalWalks")),
                "strikeouts": to_int(stat.get("strikeOuts")),
                "hit_batters": to_int(stat.get("hitBatsmen")),
                "wild_pitches": to_int(stat.get("wildPitches")),
                "balks": to_int(stat.get("balks")),
                "pickoffs": to_int(stat.get("pickoffs")),
                "pitches": to_int(stat.get("numberOfPitches")),
                "strikes": to_int(stat.get("strikes")),
                "era": to_decimal(stat.get("era")),
                "whip": to_decimal(stat.get("whip")),
                "opponent_average": to_decimal(stat.get("avg")),
                "opponent_obp": to_decimal(stat.get("obp")),
                "opponent_slg": to_decimal(stat.get("slg")),
                "opponent_ops": to_decimal(stat.get("ops")),
                "strike_percentage": to_decimal(stat.get("strikePercentage")),
                "win_percentage": to_decimal(stat.get("winPercentage")),
                "strikeout_walk_ratio": to_decimal(stat.get("strikeoutWalkRatio")),
                "strikeouts_per_nine": to_decimal(stat.get("strikeoutsPer9Inn")),
                "walks_per_nine": to_decimal(stat.get("walksPer9Inn")),
                "hits_per_nine": to_decimal(stat.get("hitsPer9Inn")),
                "home_runs_per_nine": to_decimal(stat.get("homeRunsPer9")),
                "runs_per_nine": to_decimal(stat.get("runsScoredPer9")),
            }
        )
        rows.append(row)
    return rows


def flatten_fielding(splits: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten MLB fielding splits at player-position grain."""
    rows: list[dict[str, Any]] = []
    for split in splits:
        row, stat = _common(split)
        row.update(
            {
                "games_played": to_int(stat.get("gamesPlayed")),
                "games_started": to_int(stat.get("gamesStarted")),
                "innings": stat.get("innings"),
                "outs": innings_to_outs(stat.get("innings")),
                "putouts": to_int(stat.get("putOuts")),
                "assists": to_int(stat.get("assists")),
                "errors": to_int(stat.get("errors")),
                "throwing_errors": to_int(stat.get("throwingErrors")),
                "chances": to_int(stat.get("chances")),
                "double_plays": to_int(stat.get("doublePlays")),
                "triple_plays": to_int(stat.get("triplePlays")),
                "fielding_percentage": to_decimal(stat.get("fielding")),
                "range_factor_per_game": to_decimal(stat.get("rangeFactorPerGame")),
                "range_factor_per_nine": to_decimal(stat.get("rangeFactorPer9Inn")),
            }
        )
        rows.append(row)
    return rows


def flatten_advanced_batting(splits: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten MLB advanced batting splits."""
    rows: list[dict[str, Any]] = []
    for split in splits:
        row, stat = _common(split)
        row.update(
            {
                "plate_appearances": to_int(stat.get("plateAppearances")),
                "total_bases": to_int(stat.get("totalBases")),
                "extra_base_hits": to_int(stat.get("extraBaseHits")),
                "balls_in_play": to_int(stat.get("ballsInPlay")),
                "total_swings": to_int(stat.get("totalSwings")),
                "swing_and_misses": to_int(stat.get("swingAndMisses")),
                "walk_offs": to_int(stat.get("walkOffs")),
                "reached_on_error": to_int(stat.get("reachedOnError")),
                "gidp": to_int(stat.get("gidp")),
                "gidp_opportunities": to_int(stat.get("gidpOpp")),
                "babip": to_decimal(stat.get("babip")),
                "isolated_power": to_decimal(stat.get("iso")),
                "pitches_per_plate_appearance": to_decimal(stat.get("pitchesPerPlateAppearance")),
                "walks_per_plate_appearance": to_decimal(stat.get("walksPerPlateAppearance")),
                "strikeouts_per_plate_appearance": to_decimal(stat.get("strikeoutsPerPlateAppearance")),
                "home_runs_per_plate_appearance": to_decimal(stat.get("homeRunsPerPlateAppearance")),
                "walks_per_strikeout": to_decimal(stat.get("walksPerStrikeout")),
            }
        )
        rows.append(row)
    return rows


def flatten_advanced_pitching(splits: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten MLB advanced pitching splits."""
    rows: list[dict[str, Any]] = []
    for split in splits:
        row, stat = _common(split)
        row.update(
            {
                "batters_faced": to_int(stat.get("battersFaced")),
                "quality_starts": to_int(stat.get("qualityStarts")),
                "inherited_runners": to_int(stat.get("inheritedRunners")),
                "inherited_runners_scored": to_int(stat.get("inheritedRunnersScored")),
                "bequeathed_runners": to_int(stat.get("bequeathedRunners")),
                "bequeathed_runners_scored": to_int(stat.get("bequeathedRunnersScored")),
                "balls_in_play": to_int(stat.get("ballsInPlay")),
                "total_swings": to_int(stat.get("totalSwings")),
                "swing_and_misses": to_int(stat.get("swingAndMisses")),
                "babip": to_decimal(stat.get("babip")),
                "opponent_obp": to_decimal(stat.get("obp")),
                "opponent_slg": to_decimal(stat.get("slg")),
                "opponent_ops": to_decimal(stat.get("ops")),
                "isolated_power": to_decimal(stat.get("iso")),
                "strike_percentage": to_decimal(stat.get("strikePercentage")),
                "whiff_percentage": to_decimal(stat.get("whiffPercentage")),
                "strikeouts_minus_walks_percentage": to_decimal(stat.get("strikeoutsMinusWalksPercentage")),
                "strikeouts_per_nine": to_decimal(stat.get("strikeoutsPer9")),
                "walks_per_nine": to_decimal(stat.get("baseOnBallsPer9")),
                "hits_per_nine": to_decimal(stat.get("hitsPer9")),
                "home_runs_per_nine": to_decimal(stat.get("homeRunsPer9")),
                "runs_per_nine": to_decimal(stat.get("runsScoredPer9")),
                "pitches_per_inning": to_decimal(stat.get("pitchesPerInning")),
                "pitches_per_plate_appearance": to_decimal(stat.get("pitchesPerPlateAppearance")),
            }
        )
        rows.append(row)
    return rows


def _game_common(split: Mapping[str, Any]) -> tuple[dict[str, Any], Mapping[str, Any]]:
    stat = _mapping(split.get("stat"))
    player = _mapping(split.get("player"))
    team = _mapping(split.get("team"))
    opponent = _mapping(split.get("opponent"))
    game = _mapping(split.get("game"))
    row = {
        "season": to_int(split.get("season")),
        "game_pk": to_int(game.get("gamePk")),
        "game_date": _date(split.get("date")),
        "game_type": split.get("gameType"),
        "player_id": to_int(player.get("id")),
        "player_name": player.get("fullName"),
        "team_id": to_int(team.get("id")),
        "team_name": team.get("name"),
        "team_abbreviation": team.get("abbreviation"),
        "opponent_id": to_int(opponent.get("id")),
        "opponent_name": opponent.get("name"),
        "opponent_abbreviation": opponent.get("abbreviation"),
        "is_home": split.get("isHome"),
        "is_win": split.get("isWin"),
        "summary": stat.get("summary"),
    }
    return row, stat


def flatten_batting_game_log(splits: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten one row per hitter game."""
    rows: list[dict[str, Any]] = []
    for split in splits:
        row, stat = _game_common(split)
        row.update(
            {
                "plate_appearances": to_int(stat.get("plateAppearances")),
                "at_bats": to_int(stat.get("atBats")),
                "runs": to_int(stat.get("runs")),
                "hits": to_int(stat.get("hits")),
                "doubles": to_int(stat.get("doubles")),
                "triples": to_int(stat.get("triples")),
                "home_runs": to_int(stat.get("homeRuns")),
                "rbi": to_int(stat.get("rbi")),
                "walks": to_int(stat.get("baseOnBalls")),
                "strikeouts": to_int(stat.get("strikeOuts")),
                "stolen_bases": to_int(stat.get("stolenBases")),
                "batting_average": to_decimal(stat.get("avg")),
                "on_base_percentage": to_decimal(stat.get("obp")),
                "slugging_percentage": to_decimal(stat.get("slg")),
                "ops": to_decimal(stat.get("ops")),
            }
        )
        rows.append(row)
    return rows


def flatten_pitching_game_log(splits: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten one row per pitcher game."""
    rows: list[dict[str, Any]] = []
    for split in splits:
        row, stat = _game_common(split)
        row.update(
            {
                "games_started": to_int(stat.get("gamesStarted")),
                "innings_pitched": stat.get("inningsPitched"),
                "outs": to_int(stat.get("outs")),
                "hits": to_int(stat.get("hits")),
                "runs": to_int(stat.get("runs")),
                "earned_runs": to_int(stat.get("earnedRuns")),
                "home_runs": to_int(stat.get("homeRuns")),
                "walks": to_int(stat.get("baseOnBalls")),
                "strikeouts": to_int(stat.get("strikeOuts")),
                "pitches": to_int(stat.get("numberOfPitches")),
                "strikes": to_int(stat.get("strikes")),
                "era": to_decimal(stat.get("era")),
                "whip": to_decimal(stat.get("whip")),
            }
        )
        rows.append(row)
    return rows


def batch_from_rows(rows: Sequence[dict[str, Any]], schema: pa.Schema) -> pa.RecordBatch:
    """Build a projected player-stat batch in schema order."""
    return pa.RecordBatch.from_arrays(
        [pa.array([row.get(value.name) for row in rows], type=value.type) for value in schema],
        schema=schema,
    )


def batch_from_splits(
    splits: Sequence[dict[str, Any]], schema: pa.Schema, *, pitching: bool
) -> pa.RecordBatch:
    """Build a player-stat batch in the requested projection order."""
    rows = flatten_pitching(splits) if pitching else flatten_batting(splits)
    return batch_from_rows(rows, schema)
