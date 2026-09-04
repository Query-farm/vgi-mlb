"""Hermetic end-to-end coverage through Haybarn and the VGI transport."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class _MlbHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path.endswith("/standings"):
            payload = {
                "records": [
                    {
                        "standingsType": "regularSeason",
                        "league": {"id": 103, "name": "American League", "abbreviation": "AL"},
                        "division": {"id": 201, "name": "American League East", "abbreviation": "ALE"},
                        "teamRecords": [
                            {
                                "season": "2026",
                                "team": {"id": 147, "name": "New York Yankees", "abbreviation": "NYY"},
                                "divisionRank": "1",
                                "wins": 90,
                                "losses": 60,
                                "gamesPlayed": 150,
                                "gamesBack": "-",
                                "winningPercentage": ".600",
                            }
                        ],
                    }
                ]
            }
        elif parsed.path.endswith("/stats"):
            group = query.get("group", ["hitting"])[0]
            stat = {
                "hitting": {"gamesPlayed": 10, "atBats": 30, "hits": 10, "homeRuns": 2, "ops": ".900"},
                "pitching": {
                    "gamesPlayed": 5,
                    "gamesPitched": 5,
                    "inningsPitched": "10.0",
                    "outs": 30,
                    "strikeOuts": 12,
                    "era": "2.70",
                },
                "fielding": {
                    "gamesPlayed": 8,
                    "innings": "60.0",
                    "putOuts": 20,
                    "assists": 10,
                    "errors": 1,
                    "chances": 31,
                    "fielding": ".968",
                },
            }[group]
            payload = {
                "stats": [
                    {
                        "totalSplits": 1,
                        "splits": [
                            {
                                "season": "2026",
                                "numTeams": 1,
                                "player": {"id": 1, "fullName": "Test Player"},
                                "team": {"id": 147, "name": "New York Yankees", "abbreviation": "NYY"},
                                "league": {"id": 103, "name": "AL"},
                                "position": {"code": "6", "name": "Shortstop", "abbreviation": "SS"},
                                "stat": stat,
                            }
                        ],
                    }
                ]
            }
        else:
            self.send_error(404)
            return
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "max-age=60")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_haybarn_attaches_and_queries_every_current_table() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MlbHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    project = Path(__file__).resolve().parent.parent
    location = f"uv run --project {project} vgi-mlb"
    sql = (
        f"LOAD vgi; ATTACH 'mlb' (TYPE vgi, LOCATION '{location}'); "
        "SELECT "
        "(SELECT count(*) FROM mlb.main.current_standings) AS standings, "
        "(SELECT count(*) FROM mlb.main.current_batting) AS batting, "
        "(SELECT count(*) FROM mlb.main.current_pitching) AS pitching, "
        "(SELECT count(*) FROM mlb.main.current_fielding) AS fielding;"
    )
    env = {
        **os.environ,
        "MLB_API_BASE_URL": f"http://127.0.0.1:{server.server_port}/api/v1",
    }
    try:
        result = subprocess.run(
            ["uvx", "haybarn-cli", ":memory:", "-csv", "-c", sql],
            cwd=project,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "standings,batting,pitching,fielding" in result.stdout
    assert "1,1,1,1" in result.stdout
