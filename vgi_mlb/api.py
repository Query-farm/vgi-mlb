"""Small, read-only client for MLB's public Stats API."""

from __future__ import annotations

import logging
import os
import random
import re
import threading
import time
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from vgi_mlb import __version__

DEFAULT_BASE_URL = "https://statsapi.mlb.com/api/v1"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 4
PAGE_SIZE = 1_000
MAX_PAGES = 10
MAX_RETRY_DELAY = 30.0
QUERY_TIMEOUT = 120.0
MAX_CONCURRENT_REQUESTS = 4

logger = logging.getLogger(__name__)
_request_slots = threading.BoundedSemaphore(MAX_CONCURRENT_REQUESTS)

_MAX_AGE = re.compile(r"(?:^|[,\s])max-age=(\d+)", re.IGNORECASE)
_STALE_WHILE_REVALIDATE = re.compile(r"(?:^|[,\s])stale-while-revalidate=(\d+)", re.IGNORECASE)
_STALE_IF_ERROR = re.compile(r"(?:^|[,\s])stale-if-error=(\d+)", re.IGNORECASE)


class MlbApiError(RuntimeError):
    """A failed response from the MLB Stats API."""

    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"MLB Stats API returned HTTP {status}: {body[:400]}")
        self.status = status


@dataclass(frozen=True, slots=True)
class StandingsResponse:
    """Decoded standings plus the origin's cache policy."""

    records: list[dict[str, Any]]
    max_age: int | None = None
    stale_while_revalidate: int | None = None
    stale_if_error: int | None = None


@dataclass(frozen=True, slots=True)
class PlayerStatsResponse:
    """Decoded player-stat splits plus the origin's cache policy."""

    splits: list[dict[str, Any]]
    max_age: int | None = None
    stale_while_revalidate: int | None = None
    stale_if_error: int | None = None


def base_url() -> str:
    """Return the API root, optionally overridden for testing."""
    return os.environ.get("MLB_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _directive(pattern: re.Pattern[str], header: str) -> int | None:
    match = pattern.search(header)
    return int(match.group(1)) if match else None


@contextmanager
def _client(client: httpx.Client | None):
    """Reuse one connection pool for every request in a logical API fetch."""
    if client is not None:
        yield client
        return
    with httpx.Client(timeout=TIMEOUT) as owned:
        yield owned


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    """Return a bounded Retry-After delay or exponential backoff with jitter."""
    if response is not None:
        raw = response.headers.get("retry-after")
        if raw:
            try:
                delay = float(raw)
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(raw)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=UTC)
                    delay = (retry_at - datetime.now(UTC)).total_seconds()
                except (TypeError, ValueError, OverflowError):
                    delay = -1.0
            if delay >= 0:
                return min(delay, MAX_RETRY_DELAY)
    base = min(0.25 * 2**attempt, MAX_RETRY_DELAY)
    return min(base + random.uniform(0, base * 0.25), MAX_RETRY_DELAY)


def _request(
    path: str,
    params: Mapping[str, str | int],
    *,
    client: httpx.Client,
    deadline: float,
) -> httpx.Response:
    """Issue the connector's only outbound request, retrying transient failures."""
    url = f"{base_url()}/{path.lstrip('/')}"
    for attempt in range(MAX_ATTEMPTS):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"MLB Stats API query exceeded {QUERY_TIMEOUT:g} seconds")
        started = time.monotonic()
        try:
            if not _request_slots.acquire(timeout=remaining):
                raise TimeoutError(f"MLB Stats API query exceeded {QUERY_TIMEOUT:g} seconds")
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"MLB Stats API query exceeded {QUERY_TIMEOUT:g} seconds")
                response = client.get(
                    url,
                    params=params,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": f"vgi-mlb/{__version__}",
                    },
                    timeout=httpx.Timeout(min(30.0, remaining), connect=min(10.0, remaining)),
                )
            finally:
                _request_slots.release()
        except httpx.TransportError:
            logger.warning(
                "mlb_api_transport_error path=%s attempt=%d duration_ms=%d",
                path,
                attempt + 1,
                round((time.monotonic() - started) * 1_000),
            )
            if attempt + 1 == MAX_ATTEMPTS:
                raise
            time.sleep(min(_retry_delay(None, attempt), max(0.0, deadline - time.monotonic())))
            continue
        duration_ms = round((time.monotonic() - started) * 1_000)
        logger.debug(
            "mlb_api_response path=%s status=%d attempt=%d duration_ms=%d",
            path,
            response.status_code,
            attempt + 1,
            duration_ms,
        )
        if response.status_code not in RETRYABLE_STATUSES or attempt + 1 == MAX_ATTEMPTS:
            return response
        delay = min(_retry_delay(response, attempt), max(0.0, deadline - time.monotonic()))
        logger.warning(
            "mlb_api_retry path=%s status=%d attempt=%d delay_seconds=%.3f",
            path,
            response.status_code,
            attempt + 1,
            delay,
        )
        time.sleep(delay)
    raise AssertionError("retry loop exited without a response")


def fetch_standings(
    *,
    season: int | None = None,
    league_id: int | None = None,
    standings_type: str = "regularSeason",
    client: httpx.Client | None = None,
) -> StandingsResponse:
    """Fetch AL, NL, or combined standings.

    Omitting ``season`` lets MLB choose its current season. Omitting
    ``league_id`` requests both the American and National Leagues.
    """
    params: dict[str, str | int] = {
        "leagueId": league_id if league_id is not None else "103,104",
        "standingsTypes": standings_type,
        "hydrate": "team,league,division",
    }
    if season is not None:
        params["season"] = season

    deadline = time.monotonic() + QUERY_TIMEOUT
    with _client(client) as http:
        response = _request("standings", params, client=http, deadline=deadline)
    if not response.is_success:
        raise MlbApiError(response.status_code, response.text)
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError("MLB Stats API standings response has no records array")

    cache_control = response.headers.get("cache-control", "")
    return StandingsResponse(
        records=payload["records"],
        max_age=_directive(_MAX_AGE, cache_control),
        stale_while_revalidate=_directive(_STALE_WHILE_REVALIDATE, cache_control),
        stale_if_error=_directive(_STALE_IF_ERROR, cache_control),
    )


def _minimum_directive(values: list[int | None]) -> int | None:
    """Return the shortest directive only when every page supplied one."""
    return (
        min(value for value in values if value is not None)
        if all(value is not None for value in values)
        else None
    )


def fetch_player_stats(
    *,
    group: str,
    stat_type: str = "season",
    season: int | None = None,
    league_id: int | None = None,
    team_id: int | None = None,
    game_type: str = "R",
    qualified_only: bool = False,
    client: httpx.Client | None = None,
) -> PlayerStatsResponse:
    """Fetch all season-stat splits for hitters or pitchers.

    The endpoint pages full player pools. Every page is consumed so callers
    receive complete season results rather than an unexplained prefix.
    """
    if group not in {"hitting", "pitching", "fielding"}:
        raise ValueError("player stats group must be 'hitting', 'pitching', or 'fielding'")

    base_params: dict[str, str | int] = {
        "stats": stat_type,
        "group": group,
        "playerPool": "QUALIFIED" if qualified_only else "ALL",
        "sportIds": 1,
        "hydrate": "person,team",
        "limit": PAGE_SIZE,
        "gameType": game_type,
    }
    if season is not None:
        base_params["season"] = season
    if league_id is not None:
        base_params["leagueIds"] = league_id
    if team_id is not None:
        base_params["teamId"] = team_id

    splits: list[dict[str, Any]] = []
    max_ages: list[int | None] = []
    stale_while_revalidates: list[int | None] = []
    stale_if_errors: list[int | None] = []
    offset = 0

    deadline = time.monotonic() + QUERY_TIMEOUT
    with _client(client) as http:
        for _page in range(MAX_PAGES):
            response = _request("stats", {**base_params, "offset": offset}, client=http, deadline=deadline)
            if not response.is_success:
                raise MlbApiError(response.status_code, response.text)
            payload = response.json()
            stats = payload.get("stats") if isinstance(payload, dict) else None
            if not isinstance(stats, list):
                raise ValueError("MLB Stats API player stats response has no stats array")

            cache_control = response.headers.get("cache-control", "")
            max_ages.append(_directive(_MAX_AGE, cache_control))
            stale_while_revalidates.append(_directive(_STALE_WHILE_REVALIDATE, cache_control))
            stale_if_errors.append(_directive(_STALE_IF_ERROR, cache_control))

            if not stats:
                return PlayerStatsResponse(
                    splits=splits,
                    max_age=_minimum_directive(max_ages),
                    stale_while_revalidate=_minimum_directive(stale_while_revalidates),
                    stale_if_error=_minimum_directive(stale_if_errors),
                )
            if not isinstance(stats[0], dict):
                raise ValueError("MLB Stats API player stats response has malformed stats")
            block = stats[0]
            page_splits = block.get("splits")
            if not isinstance(page_splits, list):
                raise ValueError("MLB Stats API player stats response has no splits array")
            if any(not isinstance(value, dict) for value in page_splits):
                raise ValueError("MLB Stats API player stats response has malformed splits")
            splits.extend(page_splits)

            total = block.get("totalSplits")
            total_splits = total if isinstance(total, int) else len(splits)
            if not page_splits or len(splits) >= total_splits:
                return PlayerStatsResponse(
                    splits=splits,
                    max_age=_minimum_directive(max_ages),
                    stale_while_revalidate=_minimum_directive(stale_while_revalidates),
                    stale_if_error=_minimum_directive(stale_if_errors),
                )
            offset += len(page_splits)

    raise RuntimeError(f"MLB Stats API pagination exceeded {MAX_PAGES} pages after {len(splits)} splits")


def fetch_person_stats(
    player_id: int,
    *,
    group: str,
    stat_type: str,
    season: int | None = None,
    game_type: str = "R",
    start_date: date | None = None,
    end_date: date | None = None,
    client: httpx.Client | None = None,
) -> PlayerStatsResponse:
    """Fetch one player's career, team splits, date range, or game log."""
    if player_id <= 0:
        raise ValueError("player_id must be positive")
    if group not in {"hitting", "pitching", "fielding"}:
        raise ValueError("player stats group must be 'hitting', 'pitching', or 'fielding'")
    params: dict[str, str | int] = {
        "stats": stat_type,
        "group": group,
        "gameType": game_type,
        "hydrate": "team,opponent",
    }
    if season is not None:
        params["season"] = season
    if start_date is not None:
        params["startDate"] = start_date.isoformat()
    if end_date is not None:
        params["endDate"] = end_date.isoformat()

    deadline = time.monotonic() + QUERY_TIMEOUT
    with _client(client) as http:
        response = _request(f"people/{player_id}/stats", params, client=http, deadline=deadline)
    if not response.is_success:
        raise MlbApiError(response.status_code, response.text)
    payload = response.json()
    stats = payload.get("stats") if isinstance(payload, dict) else None
    if not isinstance(stats, list):
        raise ValueError("MLB Stats API person stats response has no stats array")
    if not stats:
        return PlayerStatsResponse(splits=[])
    if not isinstance(stats[0], dict) or not isinstance(stats[0].get("splits"), list):
        raise ValueError("MLB Stats API person stats response has no splits array")

    cache_control = response.headers.get("cache-control", "")
    return PlayerStatsResponse(
        splits=[value for value in stats[0]["splits"] if isinstance(value, dict)],
        max_age=_directive(_MAX_AGE, cache_control),
        stale_while_revalidate=_directive(_STALE_WHILE_REVALIDATE, cache_control),
        stale_if_error=_directive(_STALE_IF_ERROR, cache_control),
    )
