"""Serve canned MLB Stats API responses over HTTP for the SQL tests.

``ci/run-integration.sh`` starts this server, points ``MLB_API_BASE_URL`` at
it, and runs ``test/sql`` through DuckDB, so the suite is hermetic. Prints
``PORT:<n>`` once listening.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


def main() -> None:
    """Serve until killed."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MlbHandler)
    print(f"PORT:{server.server_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
