# NextPlay AI

**Pause a football moment. Compare the available actions. See the evidence behind the explanation.**

NextPlay AI combines a 2D synthetic match replay, numerical action comparison,
short hypothetical rollouts and a four-role assistant. A separate local video
workspace turns manually confirmed observations into an auditable 2D snapshot.

## Team product demo

- **Hosted team product:** https://nextplay-ai.azurewebsites.net/index.html?view=replay
- **Hosted question-and-answer cases:** https://nextplay-ai.azurewebsites.net/cases.html

The hosted team version returned a four-role answer during our live check on
28 October. It is a separate deployment and has **not yet been updated to this
new synthetic dataset or local video workspace**. The links demonstrate the
team product; they do not prove deployment of this repository revision.

## Challenge alignment

Built for the **Synthetic Match Insights Engine** challenge: help a viewer
understand *why a football moment matters*, with inspectable numerical evidence.

| Challenge stage | Implemented experience |
| --- | --- |
| Ingest | Load generated match events, metadata and player positions from 30 fictional matches. Replay consumes recorded synthetic events; this is not a live broadcast ingestion claim. |
| Interpret | Summarize match events and compare available actions using the numerical decision engine. |
| Explain | Attack and defence roles examine the same evidence; coordination produces an explanation and review checks its support. |
| Render | Show synchronized 2D replay, candidate routes, numerical comparisons and short hypothetical continuations. |
| Personalize | Provide club/player views, English/Chinese assistant controls and a training-oriented decision workspace. |

The core submission uses **20 fictional clubs and 360 independently generated
player profiles**. The video workspace is an additional human-confirmed input
path; the bundled demonstration can use a generated synthetic clip without
third-party match footage. It does not claim automatic video-to-tracking accuracy.

## Judge walkthrough

1. Run the project locally and choose a synthetic match in Replay.
2. Pause an active-play moment with a clear ball holder; open decision analysis.
3. Compare available actions and inspect a hypothetical continuation. These are
   model-based comparisons, not predictions of what certainly would happen.
4. With a configured model service, ask the assistant about that moment and
   inspect its evidence and review outcome. Without a model, numerical analysis
   remains available and the unavailable status is explicit.
5. Optionally open the video workspace, generate a synthetic clip, confirm the
   observations and create a 2D snapshot before requesting analysis.

## Run locally

```sh
python3 server.py
```

Open `http://127.0.0.1:5173/` for synthetic match replay and
`http://127.0.0.1:5173/coach.html` for decision analysis.
`http://127.0.0.1:5173/video-review.html` provides local video review, including a
generated synthetic clip. Public deployments disable uploads by default.

## What is calculated

The generator produces fictional players, matches, events and tracking. Q2
compares candidate ground passes using a short simulated continuation and a
position-value model fitted only to generated matches. The auxiliary four-action
comparison exposes pass, carry, shot and wait assumptions. Its weights are
engineering assumptions, not measured real-world scoring probabilities.

The assistant uses attack, defence, coordination and review roles. They share
the same numerical candidates and evidence; they cannot replace computed scores.
The evidence layer binds observations to an immutable confirmed revision.
Claims require matching evidence, and hypothetical claims require a rollout.
Rule checks and final review can withhold unsupported answers. These checks
reduce specific errors; they do not guarantee a hallucination-free explanation.

## Model configuration

Set `NEXTPLAY_MODEL_BASE_URL`, `NEXTPLAY_MODEL` and `NEXTPLAY_MODEL_API_KEY` in
the server environment, using a service supporting the Responses tools used by
this project. See `.env.example`; the server does not automatically load it.
Never put keys in Git or browser code. Azure Foundry deployments can be connected
through their compatible endpoint. Without configuration the numerical tools
remain usable and the assistant reports that the model is unavailable.

The production four-role orchestration is implemented in Python using Responses
tool calls. The optional Microsoft Agent Framework workflow runs the decision
kernel; it does not replace the four-role Responses orchestration. YOLO is not
automatically enabled by this integration.
It is not a video-to-tracking accuracy benchmark. Optional proposal JSONL files
can be imported, but still require manual identity and observation confirmation.

## Submission data

All bundled data is newly generated with seed **20261028**. No old roster,
birth dates, nationalities, external player IDs, downloaded footage, inherited
event-fitted models, Git history or private uploads are included. See [SOURCE.md](SOURCE.md).
The original development repository is separate; replacing its main branch
would not erase its previous history or forks.

## Integrated decision kernel

The lightweight System 1 code from [the teammate repository](https://github.com/tigerguoyi/Microsoft_Hackthon)
is included under `inside_the_game/`, with source hashes in
[`UPSTREAM.json`](inside_the_game/UPSTREAM.json). The adapter normalizes both teams
to their actual attacking direction and uses only decision-time ball position,
opponent proximity, clock and score from the same synthetic or human-confirmed
video snapshot.

**Snapshot → four-class tendency → existing candidate comparison → hypothetical
rollout → evidence-bound agent explanation and review.** The tendency is a
separate diagnostic, not a filter or multiplier on Q2. Existing candidate IDs,
values, ranks and registered evidence stay unchanged.

The integrated baseline uses **hand-set upstream softmax coefficients**, explicitly
labelled `hand_set_stub`. No upstream trained weight files or datasets were
imported. Its pass/shoot/dribble/hold shares sum to one, but are not action-success
rates, goal probabilities or proof that a specific action is eligible. The model
has not been trained on this release's 30 matches. Agent context receives the
separate diagnostic with instructions not to override Q2 or invent evidence.
The decision-analysis and confirmed-video comparison views display it separately.

Run with `python3 server.py`, or optionally install the included packages into a
virtual environment with `python -m pip install -e .`. Python 3.12 is recommended.
This integration now also includes the teammate analytic route kernel and an
optional Microsoft Agent Framework execution path. It does not enable YOLO,
cloud deployment or real-model provider validation.

## Microsoft Agent Framework and the route kernel

Install the tested framework extra in a Python 3.12 virtual environment:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[agent]"
python server.py
```

The pinned `agent-framework-core==1.23.0` runtime executes the imported workflow:
**read-frame → decide → score-completion → narrate**. It reads only the bound
snapshot and eligible Q2 candidate targets, computes the teammate kernel's
analytic pitch-control × static-position-value route diagnostics, and builds an
offline narration request. Without an injected narrator, `sent` stays false.
This is an actual framework execution path, not a renamed Python chain.

Both synthetic analysis and confirmed-video analysis expose `kernel_workflow`
and its real tool trace. The agent context receives the diagnostics too. The
existing Q2 model still owns the displayed candidate ranking and registered
evidence; analytic kernel route scores do not replace it. The separate category
panel uses the same six-feature softmax baseline as the workflow.

The default kernel backend is `framework`. With dependencies missing it reports
`unavailable` and Q2 remains usable; it does not silently claim a framework run.
`NEXTPLAY_KERNEL_BACKEND=direct` explicitly selects the teammate in-process
reference path. Four-role attack/defence/coordinator/reviewer calls still use our
Responses orchestration; this release does not claim they have been migrated to
Agent Framework.

Local validation: the installation command succeeded, 92 Python tests passed
with the actual framework installed (including five framework integration tests,
none skipped), and six JavaScript tests passed. Tested failure paths include
scoring and narration failures and rejecting a future frame. No live provider
request or Azure redeployment was performed for this integration.

## Statistical calibration status

An optional, offline StatsBomb-format calibration tool is available in
`research/statsbomb_calibration.py`. It checks source hashes and disjoint splits,
fits aggregate frequency tables and reports held-out errors. It was tested with
invented fixtures; **StatsBomb calibration is not activated in the bundled data**.
The public license restricts commercial exploitation and requires attribution
and a logo; project-specific authorization for the intended contest/public-demo
uses has not been established. See [method, rights review and activation steps](docs/statsbomb-calibration.md).
The release remains synthetic and uses engineering-default frequency assumptions.
The calibration interface is retained as an **offline, opt-in research tool**,
not a public upload/inference API. Keeping the interface does not authorize
using external data. Before activation, confirm rights for contest participation,
public GitHub publication of derived tables/models, hosted demos and any later
commercial use; these are separate uses and cannot be inferred from research
access alone. Organizer approval concerns contest rules and does not grant
StatsBomb data rights. No additional permission is needed to run our invented
calibration test fixtures.
No compliance or real-match predictive accuracy is certified by these checks.

## Validation

```sh
npm ci
npm test
python3 scripts/audit_submission_sources.py data
```

Training the Q2 models requires NumPy, scikit-learn, joblib and threadpoolctl;
the fitted release models are bundled so runtime replay needs only Python.
See [release validation](docs/release-validation.md) for the actual check results.

## Repository and submission status

**Source repository:** https://github.com/Jolinsjhp/NextPlay-AI-Synthetic

This repository contains the application source, synthetic match data, fitted
release artifacts, tests and setup instructions. The hosted team demo uses Azure
App Service; this code supports server-side Azure Foundry-compatible model
configuration. Publishing this source does not redeploy that service.

A public English demonstration video under two minutes must also be linked in
the contest form. Its public hosting URL is not recorded here. The team must
verify this synthetic build online, provider calls, judging-period availability
and account limits. See [submission checklist](docs/submission-checklist.md).

This README maps the implemented features to the
[official challenge and submission requirements](https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md).
It does not certify eligibility or completion of the external submission steps.

C/D is jointly owned by two teammates: evidence confirmation, assistant tools,
review, video workspace and integration. A/B owns generator and scoring contracts;
the Azure account owner assists with deployment and quotas.
