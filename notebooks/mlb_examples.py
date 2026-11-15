"""Hash-verified public response replay; all analytical work remains visible SQL."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse


class MLBExample:
    """Own one bounded public-response scenario and its endpoint override."""

    def __init__(self, mode: str, scenario: str):
        if mode not in {"replay", "live"}:
            raise ValueError("DATA_MODE must be replay or live")
        if scenario not in {"pitching", "batting", "trades"}:
            raise ValueError("Unknown MLB notebook scenario")
        self.mode = mode
        self.requests: list[str] = []
        self.unexpected: list[str] = []
        self.server = None
        self.thread = None
        self.root = Path(__file__).resolve().parent
        self.previous = os.environ.pop("MLB_API_BASE_URL", None)
        if mode == "live":
            return
        manifest = json.loads((self.root / "recordings/provenance.json").read_text())
        items = [
            dict(item, folder="recordings") for item in manifest["files"] if item["scenario"] == scenario
        ]
        if scenario == "pitching":
            original = json.loads((self.root / "fixtures/manifest.json").read_text())
            for item in original["entries"]:
                route = urlparse(item["url"])
                query = parse_qs(route.query)
                items.append(
                    dict(
                        item,
                        folder="fixtures",
                        file=item["filename"],
                        request_path=route.path,
                        params={key: value[0] for key, value in query.items()},
                    )
                )
        self.expected = [item["file"] for item in items]
        responses = {}
        for item in items:
            body = (self.root / item["folder"] / item["file"]).read_bytes()
            if hashlib.sha256(body).hexdigest() != item["sha256"]:
                raise ValueError("Recorded response hash mismatch: " + item["file"])
            key = (item["request_path"], tuple(sorted((k, str(v)) for k, v in item["params"].items())))
            if key in responses:
                raise ValueError("Duplicate recorded request")
            responses[key] = (item["file"], body, item.get("cache_control") or "no-store")
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                route = urlparse(self.path)
                query = parse_qs(route.query, keep_blank_values=True)
                if any(len(values) != 1 for values in query.values()):
                    owner.unexpected.append("duplicate query values")
                    self.send_error(400)
                    return
                key = (route.path, tuple(sorted((k, v[0]) for k, v in query.items())))
                if key not in responses:
                    owner.unexpected.append(self.path)
                    self.send_error(404, "Outside recorded coverage; no forwarding")
                    return
                name, body, cache_control = responses[key]
                owner.requests.append(name)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", cache_control)
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        os.environ["MLB_API_BASE_URL"] = f"http://127.0.0.1:{self.server.server_port}/api/v1"

    def audit(self) -> str:
        """Confirm the exact bounded request set, without claiming live instrumentation."""
        if self.mode == "live":
            return "Live public reads used the default MLB endpoint; no replay fallback. Retries are not instrumented."
        assert not self.unexpected, self.unexpected
        assert Counter(self.requests) == Counter(self.expected), (self.requests, self.expected)
        return f"Exactly {len(self.expected)} recorded responses requested once each; no unexpected requests."

    def close(self):
        """Stop replay and restore the inherited endpoint."""
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=5)
        if self.previous is None:
            os.environ.pop("MLB_API_BASE_URL", None)
        else:
            os.environ["MLB_API_BASE_URL"] = self.previous
