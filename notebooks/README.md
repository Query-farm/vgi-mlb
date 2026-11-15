# Major League Baseball Data notebooks

Three focused SQL stories use the real **vgi-mlb v0.4.1** worker to reconcile counts before interpreting rates. Saved defaults replay unchanged public MLB response bodies; each notebook also supports bounded public live reads without credentials or replay fallback.

| Notebook | Question | Experiment |
| --- | --- | --- |
| [01 · Count outs correctly, then choose the comparison pool](01_outs_before_rates_before_rankings.ipynb) | Why does decimal-parsing baseball innings distort ERA, and how does a workload rule change the displayed players? The advanced K−BB fraction introduces a separate batters-faced denominator. | `MIN_OUTS=450`, compared with 150. Raw observations and the notation-error figure remain fixed. |
| [02 · Separate hits from extra bases](02_separate_hits_from_extra_bases.ipynb) | Which part of slugging comes from first bases and which from extra bases? Reconstruct isolated power from counts, reconcile the advanced report, and show the selected population. | `MIN_PA=500`, compared with 250. Individual rate coordinates remain fixed. `750` tests an empty selection. |
| [03 · Keep player, team and career scopes separate](03_keep_player_team_and_career_scopes_separate.ipynb) | Do game logs reconcile with each traded player's club totals, and how does pooling exposures change a rate? Compare Josh Naylor's batting and Jhoan Duran's pitching, with career totals explicitly kept in their larger time window. | `RATE_SCOPE="season"`, compared with `"team"`. Four club rows become two pooled player-season rows; the source audit stays fixed. |

## Run from this directory

Install [uv](https://docs.astral.sh/uv/) and Git, then run:

```bash
uv sync --frozen
uv run --frozen vgi-notebooks
```

The notebook environment locks Haybarn 2.0.0rc11 and the shared publication runner at **v0.3.51**. The worker uses its own Python 3.13 environment, launched by visible SQL:

```sql
INSTALL vgi FROM community;
LOAD vgi;
ATTACH 'mlb' (TYPE vgi, LOCATION 'uvx --python 3.13 --from git+https://github.com/Query-farm/vgi-mlb@v0.4.1 vgi-mlb');
```

No transitive `--with` overrides or worker checkout are needed. The public release tag resolves to `64cf449971b10b221f1730b6c6b16c2a0e045f2e`. First use needs network access for dependencies, the VGI extension, managed Python and public companions; replay then serves only the recorded responses over loopback.

Each **Open in Colab** link opens the notebook directly. Its bootstrap installs only the shared base package, preserves compatible preloaded kernel libraries, and fetches SHA-verified companions. The local environment uses the `[runner]` extra. Shared connection setup establishes UTC, an empty temporary SQL-secret directory and disabled persistent secrets.

For an interactive local kernel:

```bash
uv run --frozen python -m ipykernel install --user --name vgi-mlb-notebooks --display-name 'Python (vgi-mlb notebooks)'
```

Run each story in a fresh kernel so its worker owns the intended endpoint. Restart and run all after changing a parameter. Cleanup closes the connection and replay server and restores any inherited `MLB_API_BASE_URL`.

## Change one parameter

The runner only saves successful results. Overrides require a separate destination, protecting the published defaults:

```bash
uv run --frozen vgi-notebooks 01_outs_before_rates_before_rankings.ipynb --parameters '{"MIN_OUTS":450}' --output-dir validation/outs-450
uv run --frozen vgi-notebooks 02_separate_hits_from_extra_bases.ipynb --parameters '{"MIN_PA":500}' --output-dir validation/pa-500
uv run --frozen vgi-notebooks 03_keep_player_team_and_career_scopes_separate.ipynb --parameters '{"RATE_SCOPE":"season"}' --output-dir validation/season-scope
```

All three accept `DATA_MODE="live"`. They retain the same historical season/player parameters, clear inherited endpoint overrides, and use the public MLB API. Failures remain errors; live retries are not instrumented by the replay helper.

```bash
uv run --frozen vgi-notebooks 03_keep_player_team_and_career_scopes_separate.ipynb --parameters '{"DATA_MODE":"live"}' --output-dir validation/live-trades --timeout 600
```

## Exact response provenance

The original [pitching fixture manifest](fixtures/manifest.json) is preserved unchanged. Its complete 2,687,589-byte response was captured on **2026-11-14 at 08:19:55.942457 UTC**, with 873 rows and `totalSplits=873`, for the 2025 regular season, both leagues and `playerPool=ALL`. The notebook still checks every raw player-ID/outs/earned-runs tuple against worker output.

The new [recording manifest](recordings/provenance.json) describes **nine complete, unchanged public JSON responses acquired independently on 2026-11-15 UTC**: advanced pitching, basic/advanced batting, and career/team/game-log responses for Naylor and Duran. Each record preserves the exact URL/query, request interval, status, byte count, row counts and SHA256. Basic and advanced pools contain 873 pitchers and 765 hitters. These are real public observations, not synthetic data or one atomic snapshot.

`mlb_examples.py` verifies hashes and serves only exact scenario requests through the released worker's supported alternate-base setting. Unexpected paths, parameters or duplicate values fail without forwarding. Replay audits require exactly **2 / 2 / 6** response requests in the three stories. Full player pools are materialized once before local workload filters and display limits; the worker's upstream pagination is distinct from a SQL limit. All analytical joins, arithmetic and aggregation remain visible SQL.

Career totals reflect their acquisition time and may contain seasons after 2025. Historical team splits and game logs retain the explicit 2025 regular-season scope. A last-associated club is not an attribution rule for a multi-team aggregate.

## Interpretation limits

Baseball `.1` and `.2` innings notation means one or two outs. ERA is reconstructed as `27 × earned_runs / outs`; zero denominators remain unavailable. K−BB uses batters faced instead, and the released advanced percentage column stores a fraction before conversion to display percent. Reported rounded values are checked with explicit tolerances.

For batting, `total_bases = hits + doubles + 2×triples + 3×home_runs`, so unrounded ISO is `(total_bases − hits) / at_bats`. A high hit rate and high isolated power are different descriptive properties. The local workload thresholds do not reproduce official qualification rules or establish statistical reliability.

Game-log counts reconcile to team-season exposures before rates are pooled. Summing numerators and denominators gives an exposure-weighted rate; a simple mean of club rates answers another question. Career reference lines use a larger time window. No example estimates player ability, trade effects, uncertainty, park adjustment or future performance.

## Coverage and publication evidence

[coverage.json](coverage.json) maps **10 of 20** distinct public SQL names to visible executed SQL, results and interpretations. Actual complete function/table/view exports reconcile the released v0.4.1 catalog and public source `db4a4d894c1ca21f8d676b1a559e853f4abd0d75`. Same-name aliases count once; differently named `all_current_*` functions remain in the denominator. The other ten names remain explicitly uncovered. Analytical execution uses the release; current-interface correspondence does not claim an exact-current analytical run.

Saved defaults contain native SVG and links to committed chart assets for GitHub. Experiment copies retain native SVG; runtime logs, extracted PNG previews and temporary copies are ignored under `validation/` and `artifacts/`. The unchanged worker's [green source CI](https://github.com/Query-farm/vgi-mlb/actions/runs/43575726527) is reused without rebuilding or dispatching source/container CI. The repository README documents MLB data terms and affiliation; the worker's MIT code license does not license MLB data.


All three defaults, three detached notebook-only experiments and the 750-PA empty boundary passed **38 SQL invariants**, exact replay-request audits and cross-run comparisons. The pitching pool changes **339→70**, the batting pool **309→146→0**, and team scope changes **4→2** rate rows. Basic/advanced pitching fingerprints, all hitter rate coordinates, career totals and team counts remain fixed where required; the two fixed audit figures are byte-identical across their experiments.

All three bounded live runs on **2026-11-15 UTC** reproduced the default analytical tables and checks. Seven runner/parameter guards preserved the defaults. A fresh notebook-only Python 3.12 setup with pandas, Matplotlib, IPython, ipykernel and Jupyter client already imported passed the complete third notebook using only base shared dependencies, preserving their versions and reproducing all analytical rows and replay requests. This validates local preloaded-kernel compatibility; hosted Colab was not manually executed. Ruff, formatting, presentation and catalog/receipt validation passed; every changed figure was reviewed.
