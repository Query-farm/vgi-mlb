<p align="center">
  <a href="https://query.farm/vgi/">
    <img src="https://raw.githubusercontent.com/Query-farm/vgi-kalshi/main/docs/vgi-logo.png" alt="Vector Gateway Interface logo" width="320">
  </a>
</p>

<h1 align="center">vgi-mlb</h1>

<p align="center">
  Major League Baseball standings and player statistics as ordinary DuckDB tables.<br>
  A <strong>read-only</strong> <a href="https://query.farm/vgi/">VGI</a> worker, built by <a href="https://query.farm">🚜 Query.Farm</a>
</p>

<p align="center">
  <a href="https://github.com/Query-farm/vgi-mlb/actions/workflows/ci.yml"><img src="https://github.com/Query-farm/vgi-mlb/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/python-3.13%2B-3776AB.svg" alt="Python 3.13+">
  <a href="https://query.farm/vgi/"><img src="https://img.shields.io/badge/VGI-read--only-6f42c1.svg" alt="Read-only VGI worker"></a>
</p>

---

`vgi-mlb` fetches data on demand from MLB's public Stats API and reformats the
responses as typed Arrow data for Haybarn SQL. It requires no credentials and
does not rehost or persist an MLB dataset.

## Quick start

The worker is not published to PyPI. `uvx` runs the tagged release straight from
GitHub and caches it after the first use:

```bash
uvx --from git+https://github.com/Query-farm/vgi-mlb@v0.4.0 vgi-mlb --help
```

Launch Haybarn with the catalog pre-attached:

```bash
uvx haybarn-cli \
  -cmd "INSTALL vgi FROM community; LOAD vgi; ATTACH 'mlb' (TYPE vgi, LOCATION 'uvx --from git+https://github.com/Query-farm/vgi-mlb@v0.4.0 vgi-mlb');" \
  :memory:
```

Or attach it in an existing Haybarn session:

```sql
INSTALL vgi FROM community;
LOAD vgi;
ATTACH 'mlb' (
  TYPE vgi,
  LOCATION 'uvx --from git+https://github.com/Query-farm/vgi-mlb@v0.4.0 vgi-mlb'
);
```

For source development, run `uv lock --check --no-sources`, then
`uv sync --no-sources` and `uv run --no-sources vgi-mlb`.
The lockfile resolves all dependencies from package registries and does not
require a sibling checkout.

## Catalog surface

The catalog exposes four convenient current-season tables and twelve
parameterized table functions:

| Kind | Objects |
| --- | --- |
| Current season | `current_standings`, `current_batting`, `current_pitching`, `current_fielding` |
| Season statistics | `standings()`, `batting_stats()`, `pitching_stats()`, `fielding_stats()` |
| Advanced statistics | `advanced_batting_stats()`, `advanced_pitching_stats()` |
| Player detail | `batting_career()`, `pitching_career()`, `batting_team_splits()`, `pitching_team_splits()`, `batting_game_log()`, `pitching_game_log()` |

## Usage

### Standings

The ordinary table is the shortest route to the live division races:

```sql
SELECT division_name, division_rank, team_name, wins, losses, games_back
FROM mlb.main.current_standings
ORDER BY division_name, division_rank;
```

Use `standings()` to choose a season, league, or alternate standings view. All
arguments are named and optional:

```sql
-- Final 2025 standings
SELECT division_name, division_rank, team_name, wins, losses
FROM mlb.main.standings(season := 2025)
ORDER BY division_name, division_rank;

-- Current American League wild-card race
SELECT wild_card_rank, team_name, wild_card_games_back
FROM mlb.main.standings(league := 'AL', standings_type := 'wildCard')
ORDER BY wild_card_rank;
```

`league` accepts `MLB`, `AL`, or `NL`. Supported `standings_type` values are
`regularSeason`, `wildCard`, `wildCardWithLeaders`, `divisionLeaders`,
`byDivision`, `byLeague`, `springTraining`, and `postseason`.

Numeric percentages are exact decimals. MLB's `-` leader marker becomes `0.0` in
the numeric games-back columns, while the untouched API values remain available in
`games_back_display` and `wild_card_games_back_display`.

### Player statistics

Current-season batting and pitching are ordinary tables containing every player:

```sql
SELECT player_name, last_team_abbreviation, home_runs, ops
FROM mlb.main.current_batting
ORDER BY home_runs DESC
LIMIT 20;

SELECT player_name, last_team_abbreviation, innings_pitched, strikeouts, era
FROM mlb.main.current_pitching
WHERE outs >= 300
ORDER BY era
LIMIT 20;
```

The parameterized functions support historical seasons, an `AL`/`NL` restriction,
MLB's official qualified-player pool, and `game_type`: `R` for regular season,
`S` for spring training, `P` for the whole postseason, or `F`, `D`, `L`, and `W`
for individual postseason rounds.

```sql
SELECT player_name, last_team_abbreviation, hits, batting_average, ops
FROM mlb.main.batting_stats(
  season := 2025,
  league := 'AL',
  qualified_only := true
)
ORDER BY ops DESC;

SELECT player_name, innings_pitched, strikeouts, era, whip
FROM mlb.main.pitching_stats(season := 2025, qualified_only := true)
ORDER BY era;
```

`innings_pitched` preserves baseball notation: `.1` and `.2` mean one and two
outs, not decimal fractions. Use the integer `outs` column for arithmetic.

#### Correct team attribution

A season total can combine a player's work for multiple clubs. In that case,
`num_teams` is greater than one and `team_id`, `team_name`, and
`team_abbreviation` are `NULL`; the row is not falsely assigned to the last club.
The API's associated club remains available as `last_team_id`, `last_team_name`,
and `last_team_abbreviation` for display only.

Use the team-split functions when attribution matters:

```sql
SELECT team_name, games_pitched, innings_pitched, strikeouts, era
FROM mlb.main.pitching_team_splits(661395, 2025)
ORDER BY team_name;
```

#### Fielding and advanced statistics

`current_fielding` and `fielding_stats()` return one row per player and position.
Defensive innings have the same baseball notation caveat, so an exact `outs`
column is included.

```sql
SELECT player_name, last_team_abbreviation, position_abbreviation,
       outs, errors, fielding_percentage
FROM mlb.main.current_fielding
WHERE position_abbreviation = 'SS' AND outs >= 600
ORDER BY fielding_percentage DESC;

SELECT player_name, isolated_power, strikeouts_per_plate_appearance
FROM mlb.main.advanced_batting_stats(
  season := 2025,
  qualified_only := true
)
ORDER BY isolated_power DESC;
```

Advanced pitching is available through `advanced_pitching_stats()`.

#### Career totals and game logs

Career totals and team splits are keyed by MLB player ID:

```sql
SELECT player_name, games_played, hits, home_runs, batting_average, ops
FROM mlb.main.batting_career(660271);

SELECT player_name, games_started, innings_pitched, strikeouts, era, whip
FROM mlb.main.pitching_career(660271);
```

Game logs return one row per game and support inclusive date bounds:

```sql
SELECT game_date, opponent_abbreviation, hits, home_runs, summary
FROM mlb.main.batting_game_log(
  660271,
  season := 2025,
  start_date := DATE '2025-06-01',
  end_date := DATE '2025-06-30'
)
ORDER BY game_date;
```

The pitching equivalent is `pitching_game_log()`.

## Production HTTP deployment

Stdio is the recommended transport when Haybarn can launch the worker locally.
Use HTTP when the worker must be shared across hosts. The production HTTP entry
point fails closed unless it has a stable signing key and either authentication
or an explicit anonymous-access decision:

```bash
export VGI_SIGNING_KEY='a-long-random-secret-shared-by-every-replica'
export VGI_BEARER_TOKENS='replace-with-a-random-token=haybarn'

uvx --from git+https://github.com/Query-farm/vgi-mlb@v0.4.0 vgi-mlb-http \
  --host 0.0.0.0 \
  --port 8000 \
  --cors-origins 'https://sql.example.com' \
  --log-format json
```

`vgi-mlb-http` disables the description pages and cross-origin access unless
they are explicitly configured. Terminate TLS at a trusted proxy or load
balancer. All replicas must receive the same `VGI_SIGNING_KEY`; rotate it as a
coordinated deployment because outstanding state tokens are signed with it.

Supported authentication options are:

- `VGI_BEARER_TOKENS`: comma-separated `token=principal` pairs.
- `VGI_JWT_ISSUER` and `VGI_JWT_AUDIENCE`: JWT/JWKS authentication.
- `VGI_PROXY_PROOF_MODE=require` with the corresponding VGI proxy-proof
  settings when a trusted proxy authenticates users.

Because this connector exposes read-only public data, an intentionally public
service can set `VGI_ALLOW_ANONYMOUS=1`. It should still be protected by gateway
rate limits. The health probe is `GET /health`.

### Container

```bash
docker build -t vgi-mlb .
docker run --rm -p 8000:8000 \
  -e VGI_SIGNING_KEY='replace-with-a-stable-random-secret' \
  -e VGI_BEARER_TOKENS='replace-with-a-random-token=haybarn' \
  vgi-mlb
```

The image runs as an unprivileged user, emits JSON logs, disables interactive
description pages, and includes a health check.

## Reliability and operations

The connector forwards MLB's `Cache-Control` freshness policy to VGI clients.
Upstream calls use a 30-second request timeout, a 120-second total query
deadline, at most four attempts, and at most four simultaneous MLB requests per
process. HTTP 429 and transient 5xx responses are retried; `Retry-After` is
honored with a 30-second per-retry cap. Success timings are available at debug
log level, while retries and transport failures are warnings.

`MLB_API_BASE_URL` may point to an alternate `/api/v1` root for hermetic tests.
Do not set it from untrusted user input.

## Development and release checks

```bash
uv lock --check --no-sources
uv sync --no-sources
uv run --no-sources ruff check .
uv run --no-sources ruff format --check .
uv run --no-sources pytest
uv build
uvx twine check dist/*
uvx --no-sources --from vgi-lint-check==2.5.0 vgi-lint lint \
  'uv run --no-sources mlb_worker.py' \
  --no-execute --no-check-links --audit-waivers --fail-on warning
```

Live upstream smoke tests are opt-in with `uv run pytest -m live` and also run
in a serialized scheduled workflow alongside executable VGI catalog examples.
Publishing is driven by releases. Create a GitHub release named `vX.Y.Z` that
matches the version in `pyproject.toml`. CI then builds, validates and attests
the wheel and sdist, attaches them to the release, and publishes a
multi-platform container image to `ghcr.io/query-farm/vgi-mlb`. The package is
not published to PyPI; install it from the release tag as shown in the quick
start.
