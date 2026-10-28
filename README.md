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
tool calls. This export does not claim to run Microsoft Agent Framework or YOLO.
It is not a video-to-tracking accuracy benchmark. Optional proposal JSONL files
can be imported, but still require manual identity and observation confirmation.

## Submission data

All bundled data is newly generated with seed **20261028**. No old roster,
birth dates, nationalities, external player IDs, downloaded footage, inherited
event-fitted models, Git history or private uploads are included. See [SOURCE.md](SOURCE.md).
The original development repository is separate; replacing its main branch
would not erase its previous history or forks.

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
