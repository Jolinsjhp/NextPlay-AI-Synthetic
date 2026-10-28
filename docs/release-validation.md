# Synthetic release validation — 28 October 2026

## Data boundary

This export starts without the old data directory, fitted models, Git history,
private uploads, downloaded clips or source-identifying contract examples.
Seed 20261028 independently generates 20 clubs and 360 fictional players, then
30 matches across three matchweeks. Birth dates, nationalities and external IDs
are not copied from an upstream roster. Match metadata may contain null nationality
placeholders for compatibility; they carry no real nationality value.

The auxiliary position-value grid was fitted from 26,937 generated first-week
actions. Q2 uses three rotating folds with 10 fitting, 10 calibration and 10 test
matches; no match occupies more than one role in its fold. Generator frequencies
use explicit engineering defaults. No original event-fitted frequency tables or
real-player radar values are included. These are synthetic-only estimates.

## Completed checks

- 79 Python tests passed, including HTTP upload, manual confirmation, annotation
  invalidation, action analysis, missing-model fallback, evidence checks and
  mocked Azure configuration/authentication. No paid provider calls were made.
- 6 JavaScript tests passed for video conversation state and stale responses.
- Python source compilation passed.
- Roster regeneration reproduced all 360 fictional players byte for byte.
- JSON Schema validation passed for 30 matches, 30 previews, 141,587 events,
  180,030 states, 170,069 tracking records and 80,066 decision snapshots.
- Decision-analysis schema compilation and the synthetic video annotation fixture passed.
- Known-source-field scans passed for newly generated data, retained synthetic
  test fixtures and contracts. Scans detect known fields; they are not an
  independent legal, ownership or re-identification certification.
- Full derivative validation is recorded in
  `data/decision-analysis/validation/result.json`; source hashes and model IDs
  are rebuilt from the current source, not patched to conceal changed data.

The release suite targets this synthetic build. It does not reproduce the older
review's 206-test count or import tests for removed real-data collection paths.
Node schema dependencies were installed with pnpm locally; CI explicitly runs
`npm ci` before `npm test`.

## Remaining external validation

There is no verified live Azure model configuration in the inspected local
service. Real Responses/tool-call compatibility, deployed access and budget
must be verified with the resource owner. The Settings form supports reusing an
existing deployment; see [Azure configuration](azure-existing-deployment.md).

The 5184 preview remains a separate development build. This export has not been
deployed over it or the existing Azure website. A requested restart of the
separate 5185 preview was not approved, so that preview is currently stopped.
HTTP regression checks exercised temporary local test servers instead.

The team still needs public repository, deployed build and public captioned
demo-video URLs. A source/data ZIP is not itself a completed contest entry.

## Reproduce models

Install NumPy, scikit-learn, joblib and threadpoolctl in an isolated Python
environment, then run from a fresh export:

```sh
python3 scripts/generate_rosters.py --check
python3 generate.py --weeks 3 --tracking featured --seed 20261028
python3 scripts/fit_synthetic_value.py
python3 -m decision_analysis.pipeline all --source data/league
```

If changing source metadata or seeds, use a new derivative output directory
with `--output data/NEW_NAME`; do not manually edit existing source hashes.

## Decision kernel integration

87 Python tests and 6 JavaScript tests passed locally after the integration.
The four new integration checks cover normalized class shares and provenance,
rotation invariance, unavailable non-live snapshots, and unchanged candidates
after adding diagnostics. HTTP tests run against local servers; these are not
Azure deployment or provider validation. All bundled data is unchanged.

## Microsoft Agent Framework integration

A clean Python 3.12 environment installed the project with `pip install -e ".[agent]"`.
Tested agent-framework-core 1.23.0 and NumPy 2.5.4. All 92 Python tests passed,
including five actual framework tests with no skips. They verify tool order and
parity with the direct route kernel, immutable inputs/Q2 candidates, scoring and
narration degradation, and rejecting future frames. Six JavaScript tests passed.
The narration stage constructs a request but does not send it. Four-role
Responses orchestration remains separate. No Azure/provider validation claimed.
