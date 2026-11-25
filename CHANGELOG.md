# Changelog

All notable changes to this project are documented here.

## 0.5.0 (2026-11-25)

- Speaks VGI protocol 3.4: require vgi-python `>=0.55.1,<0.56`; uv.lock re-locked. This release
  needs Haybarn 2.0.1 (or stock DuckDB 2.0 with `INSTALL vgi FROM query_farm`): Haybarn 2.0.0
  loads a 3.3 `vgi` extension that cannot attach it.
- SQL tests run on haybarn-unittest 2.0.1rc3 (CI and Makefile).
- `serve` extra includes `vgi-python[http,oauth]`; the Docker image installs it, so the image runs in
  Orchard hosted mode (`VGI_ORCHARD_HOSTED=1` with VGI_JWT_ISSUER, VGI_JWT_AUDIENCE,
  VGI_JWT_JWKS_URI and VGI_SIGNING_KEY). The Docker HEALTHCHECK uses `HEAD /health`, which
  stays anonymous in hosted mode.

## 0.4.3 (2026-11-16)

- Bump vgi-python to 0.52.2.
- Move to Python 3.14: `requires-python >=3.14`, CI, the Docker image and lint tooling target 3.14.
- CI runs the SQL tests through the starter's `ci/run-integration.sh` over stdio, launch and HTTP.

## [Unreleased]

## [0.4.2]

- Docs link to the MLB Stats API, MLB.com Stats and MLB's data copyright notice:
  the catalog's documentation gains a Sources and references section (vgi-lint
  VGI183).

## [0.4.0]

- Port to VGI protocol 3.3 (vgi-python `>=0.51.0,<0.52`). The vgi extension
  matches the protocol's major and minor version exactly, so the current
  extension refuses 3.2 workers; the SQL surface is unchanged (the current_*
  table scans are also schema functions, so they stay callable).
- The README lints with vgi-lint-check 2.5.0 and runs the worker from `@v0.4.0`.

## [0.3.1]

- Stop publishing to PyPI. Releases attach the wheel and sdist to the GitHub
  release and publish the container image; the README now runs the worker from
  the release tag with `uvx --from git+https://github.com/Query-farm/vgi-mlb@v0.3.1`.
- Report the real package version (`__version__` and the User-Agent said 0.2.0).

## [0.3.0]

- Port to VGI protocol 3.2 (vgi-python 0.50); declare table keys as canonical
  constraint records and update vgi-lint to 2.2.0.
- Preserve earlier player-stat pages when MLB returns an empty terminal page.
- Reuse HTTP connections, bound concurrent upstream requests, honor
  `Retry-After`, and enforce a total query deadline.
- Require explicit signing and authentication policy for HTTP deployments.
- Add portable installation, container, CI, and trusted-publishing support.
- Add dependency compatibility bounds and production regression tests.

## [0.2.0]

- Add batting, pitching, fielding, advanced statistics, career totals, team
  splits, and game logs.
- Add typed Arrow schemas, cache-policy forwarding, agent metadata, and Haybarn
  end-to-end coverage.
