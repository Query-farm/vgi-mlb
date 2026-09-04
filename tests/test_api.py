"""Tests for the MLB HTTP boundary."""

from datetime import date

import httpx
import pytest

from vgi_mlb.api import MlbApiError, fetch_person_stats, fetch_player_stats, fetch_standings


def test_builds_expected_query_and_reads_cache_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MLB_API_BASE_URL", "https://example.test/api/v1")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/standings"
        assert request.url.params["season"] == "2025"
        assert request.url.params["leagueId"] == "103"
        assert request.url.params["standingsTypes"] == "wildCard"
        assert request.url.params["hydrate"] == "team,league,division"
        return httpx.Response(
            200,
            json={"records": [{"teamRecords": []}]},
            headers={"Cache-Control": "max-age=60, public, stale-while-revalidate=30, stale-if-error=86400"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_standings(
            season=2025,
            league_id=103,
            standings_type="wildCard",
            client=client,
        )

    assert len(result.records) == 1
    assert result.max_age == 60
    assert result.stale_while_revalidate == 30
    assert result.stale_if_error == 86400


def test_omitted_season_requests_both_leagues(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MLB_API_BASE_URL", "https://example.test/api/v1")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "season" not in request.url.params
        assert request.url.params["leagueId"] == "103,104"
        return httpx.Response(200, json={"records": []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        fetch_standings(client=client)


def test_api_failure_is_descriptive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MLB_API_BASE_URL", "https://example.test/api/v1")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad season")

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(MlbApiError, match="HTTP 400.*bad season"),
    ):
        fetch_standings(client=client)


def test_malformed_success_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MLB_API_BASE_URL", "https://example.test/api/v1")
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"teams": []}))
    with httpx.Client(transport=transport) as client, pytest.raises(ValueError, match="no records array"):
        fetch_standings(client=client)


def test_player_stats_follow_every_page(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MLB_API_BASE_URL", "https://example.test/api/v1")
    offsets: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/stats"
        assert request.url.params["group"] == "hitting"
        assert request.url.params["playerPool"] == "ALL"
        assert request.url.params["leagueIds"] == "104"
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        ids = [1, 2] if offset == 0 else [3]
        return httpx.Response(
            200,
            json={
                "stats": [
                    {
                        "totalSplits": 3,
                        "splits": [{"player": {"id": player_id}} for player_id in ids],
                    }
                ]
            },
            headers={"Cache-Control": "max-age=300, stale-if-error=86400"},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_player_stats(group="hitting", season=2025, league_id=104, client=client)

    assert offsets == [0, 2]
    assert [split["player"]["id"] for split in result.splits] == [1, 2, 3]
    assert result.max_age == 300
    assert result.stale_if_error == 86400


def test_empty_terminal_page_preserves_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stale totalSplits count must not erase pages already fetched."""
    monkeypatch.setenv("MLB_API_BASE_URL", "https://example.test/api/v1")

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        payload = (
            {"stats": [{"totalSplits": 2, "splits": [{"player": {"id": 1}}]}]}
            if offset == 0
            else {"stats": []}
        )
        return httpx.Response(200, json=payload, headers={"Cache-Control": "max-age=120"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_player_stats(group="hitting", client=client)

    assert [split["player"]["id"] for split in result.splits] == [1]
    assert result.max_age == 120


def test_retryable_response_honors_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MLB_API_BASE_URL", "https://example.test/api/v1")
    sleeps: list[float] = []
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"records": []})

    monkeypatch.setattr("vgi_mlb.api.time.sleep", sleeps.append)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_standings(client=client)

    assert result.records == []
    assert attempts == 2
    assert sleeps == [2.0]


def test_malformed_player_split_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MLB_API_BASE_URL", "https://example.test/api/v1")
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"stats": [{"totalSplits": 1, "splits": ["not-an-object"]}]},
        )
    )
    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(ValueError, match="malformed splits"),
    ):
        fetch_player_stats(group="hitting", client=client)


def test_player_stats_validate_group() -> None:
    with pytest.raises(ValueError, match="hitting.*pitching.*fielding"):
        fetch_player_stats(group="catching")


def test_person_game_log_passes_date_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MLB_API_BASE_URL", "https://example.test/api/v1")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/people/660271/stats"
        assert request.url.params["stats"] == "gameLog"
        assert request.url.params["startDate"] == "2025-06-01"
        assert request.url.params["endDate"] == "2025-06-30"
        return httpx.Response(200, json={"stats": [{"splits": [{"date": "2025-06-01"}]}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_person_stats(
            660271,
            group="hitting",
            stat_type="gameLog",
            season=2025,
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 30),
            client=client,
        )
    assert result.splits == [{"date": "2025-06-01"}]
