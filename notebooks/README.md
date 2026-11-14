# MLB pitching notebooks

[01 · Count outs correctly, then choose the comparison pool](01_outs_before_rates_before_rankings.ipynb) reconstructs earned-run rates from integer outs, measures the error from decimal-parsing baseball innings, and changes a custom workload threshold. It uses the complete 2025 regular-season player pool, both leagues. It does not forecast performance or reproduce MLB's official qualified-player rules.

## Run from this directory

Requires Python 3.13–3.14, [uv](https://docs.astral.sh/uv/), Git, and internet for initial packages, pinned worker checkout and VGI extension. Replay itself only reads the committed response through a loopback HTTP server.

```sh
cd notebooks
uv sync --locked
uv run --locked python execute.py
uv run --locked python -m ipykernel install --user --name vgi-mlb-notebooks --display-name 'Python (vgi-mlb notebooks)'
```

Select that kernel and Restart Kernel → Run All. The runner creates its own fresh temporary kernel and sets this directory as cwd; global kernel installation is optional. The complete notebooks directory runs independently of the worker checkout. The visible literal `uvx --from git+https://github.com/Query-farm/vgi-mlb@v0.4.1 ... vgi-mlb` pins remote tag `64cf449971b10b221f1730b6c6b16c2a0e045f2e`. Explicit runtime pins include SDK 0.51.0, RPC 0.53.1, httpx 0.28.1, httpx2 2.13.1 and Arrow 25.0.1. Notebook Haybarn is locked to 2.0.0rc11. No PyPI worker package is claimed. Rerun defaults, experiment and live checks before upgrading pins.

## Experiment and live check

```sh
uv run --locked python execute.py --parameters '{"MIN_OUTS":450}' --output-dir validation/outs-450
uv run --locked python execute.py --parameters '{"DATA_MODE":"live"}' --output-dir validation/live
```

Defaults: `DATA_MODE="replay"`, `MIN_OUTS=150`. The experiment changes only the inclusive local workload minimum from 50 to 150 innings. Both modes always request the historical 2025 regular season, all players, both leagues. Live has no fixture fallback, and reports its retrieval interval; upstream corrections can change historical values. The notebook overrides inherited `MLB_API_BASE_URL` in both modes and restores it on cleanup.

Overrides require a separate destination; unknown parameters are rejected. Default files are replaced atomically only after successful execution. Experiment copies include response fixtures, helper, branding, documentation, runner and locked environment. Runtime audits, extracted charts and experiments are ignored; the main notebook retains embedded successful outputs.

## Recorded public data

`fixtures/pitching-page-0.json` is the **complete, unmodified** 2,687,589-byte MLB Stats API response captured from `https://statsapi.mlb.com/api/v1/stats` on **2026-11-14 at 08:19:55.942457 UTC**. The request selected `stats=season`, `group=pitching`, `playerPool=ALL`, `sportIds=1`, `hydrate=person,team`, `limit=1000`, `gameType=R`, `season=2025`, `offset=0`. It contains 873 rows and upstream `totalSplits=873`, so one page covers this pool. These are public player statistics, not synthetic data or a present-day snapshot.

`fixtures/manifest.json` preserves URL, exact query, status, capture interval, SHA-256, byte count and pagination totals. `replay_source.py` verifies hashes and serves only exact path/query matches through the worker's existing alternate-base seam; unmatched requests fail with no forwarding/fallback. The notebook verifies row count, player uniqueness and every raw outs/earned-runs pair. The replay request audit is saved under `artifacts/`. Live attempts are not instrumented; the worker can retry transient failures.

No retrieval SQL LIMIT is used. The worker pages the full bounded season pool (1,000 per page, ten-page cap); all workload filters and top-eight/top-ten presentation limits operate on one materialized local table. The replay capture clock and the current execution clock are labeled separately. A season is the API's competition-season label, not an invented UTC date interval.

## Interpretation limits

Baseball `.1` and `.2` innings notation means one or two outs. The calculation uses `27 * earned_runs / outs`, leaving zero/unknown denominators unavailable. The comparison to reported ERA allows its two-decimal rounding. The deliberately incorrect decimal calculation is labeled as an error illustration.

The minimum-outs rule is custom and combines roles. Rankings have no uncertainty, park/role adjustment or predictive claim. Multi-team totals remain at player grain and are not credited to the API's last associated club. Weighted and equal-player mean rates describe different summaries of the selected subset, not official league totals.

[MLB innings glossary](https://www.mlb.com/glossary/standard-stats/innings-pitched) · [MLB ERA glossary](https://www.mlb.com/glossary/standard-stats/earned-run-average) · [Notebook standard](STANDARD.md) · [Query.Farm](https://query.farm/)
