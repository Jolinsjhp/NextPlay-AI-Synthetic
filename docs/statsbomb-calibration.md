# StatsBomb statistical calibration: prepared, not activated

## Release status

The 30 bundled matches, 20 fictional clubs and 360 invented players remain
independently generated. The bundled generator frequency profile still uses
engineering defaults. No StatsBomb-fitted profile, raw event sequences, real
identities or StatsBomb-derived validation result is included in this release.
The optional tool below is implemented and tested using invented fixtures only.
It has not been run against StatsBomb data for this release.

## Why activation is pending

The [StatsBomb Public Data User Agreement](https://github.com/hudl/open-data/blob/master/LICENSE.pdf)
(reviewed 28 October 2026, document dated 8 September 2023) permits research and
sharing analysis subject to conditions. Section 1.2 restricts redistribution of
data and commercial exploitation of the data or derived analysis. Section 1.4
requires the StatsBomb brand logo on published analysis. The
[repository README](https://github.com/hudl/open-data/blob/master/README.md)
also requests attribution and the logo.

We have no project-specific written authorization recorded for prize entry,
public derived statistics and public product demonstration. We therefore do not
assert that the public research terms cover all intended project uses. Changing
names or publishing only aggregates does not establish permission.

The [hackathon rules](https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md)
require authorized third-party integrations (4.3), synthetic football-realistic
data and rights to sourced materials (4.7). They do not explicitly certify
external statistical calibration as eligible. Section 5 also restricts
post-deadline submission changes. This repository update is a development
update, not evidence that a modified entry has been accepted by the organizer.

## Retained interface and authorization scope

The retained interface is the local command
`python3 -m research.statsbomb_calibration --manifest PATH`. There is no new
public HTTP calibration endpoint. The command writes only under `.local/` and
does not download data, alter the release profile, regenerate matches, retrain
Q2, publish derived artifacts or deploy Azure automatically.

Before enabling real-data calibration, record what the applicable permission
actually covers:

| Intended use | What needs clarification |
| --- | --- |
| Local research and fitting | Applicable dataset/version, authorized users, permitted processing and retention. |
| Prize-bearing hackathon participation | Whether this project's contest and demonstration purposes are covered; do not presume that a prize alone establishes or rules out commercial use. |
| Public GitHub publication | Whether aggregate tables, fitted parameters and any derived synthetic dataset may be redistributed, and under which conditions. Raw events are not published by this tool. |
| Hosted demonstrations on Azure | Whether use of derived results in the public application is covered, including the allowed audience and duration. |
| Later paid or commercial use | Separate commercial rights must be established; public research access alone is not treated as commercial authorization. |
| Attribution and branding | Follow the applicable credit/logo requirements and any approved publication wording; do not imply endorsement. |

The rights holder determines the data license scope. The hackathon organizer
determines eligibility and whether post-deadline changes are accepted. Neither
approval substitutes for the other. A local authorization manifest records the
team's review; it does not verify rights or grant permission.

Until that scope is established, keep the bundled engineering-default profile,
fictional player attributes and independently generated matches. Merely renaming
real players or perturbing their attributes is not our synthesis method. The
four-action tendency baseline and existing Q2 ranking do not load StatsBomb
calibration through this interface.

## Reproducible workflow after authorization

1. Obtain permission covering the actual uses, including the public release of
   aggregate results and their incorporation into a synthetic generator. Record
   only a non-sensitive reference locally; do not publish private correspondence.
2. Store authorized event JSON files and a manifest under `.local/`. Declare
   disjoint train/test matches before fitting, with SHA-256 per source file.
3. Run `python3 -m research.statsbomb_calibration --manifest .local/statsbomb/manifest.json`.
4. Inspect `.local/statsbomb-calibration/profile.json` and `validation.json`.
   They remain private and are never activated or published automatically.
5. Review permission, attribution/logo and scope before activating a profile.
   Independently regenerate matches, re-extract snapshots, refit Q2 folds and
   validate model/source hashes. Existing matches cannot be retrospectively
   described as statistically calibrated by changing a profile file.
6. Compare generated statistics with a disjoint real reference sample. Report
   discrepancies; do not equate matching averages with tactical realism.

Manifest structure (the reference below is a placeholder, not permission):

```json
{
  "authorization": {
    "reviewed": false,
    "reference": "REPLACE_ONLY_AFTER_PROJECT_SPECIFIC_RIGHTS_REVIEW",
    "uses": ["research", "hackathon", "public_derived_statistics", "public_demo"]
  },
  "sources": [
    {"path": "train-events.json", "split": "train", "sha256": "ACTUAL_SHA256"},
    {"path": "test-events.json", "split": "test", "sha256": "ACTUAL_SHA256"}
  ]
}
```

The manifest is an audit aid, not a rights-verification service. Setting
`reviewed` to true does not grant a license or prove organizer approval.

## Method and limits

Only regular-play events in periods 1–2 are used: footed ground passes, footed
shots and carries. Coordinates are rescaled from 120x80 to 105x68 metres.
Training produces distance/pressure pass-completion bins, shot-distance goal
frequency bins, pass-length/backward shares by pitch quarter, and event-type
frequencies. Outcome bins use a 20-observation training-prior smoothing strength;
geometry/action bins use additive smoothing. Sparse cells retain uncertainty.
Event-type frequencies are not frequencies of choices at equivalent decision
opportunities and must not be treated as an optimal policy.

Held-out Brier scores are compared with a constant training-prior baseline;
missing held-out bins fall back to that training prior. A weaker result remains
visible rather than being described as improved. No event IDs, player attributes,
real match sequences or original coordinates are written into the aggregate
profile. Input source hashes are kept for reproducibility.

This validates selected event frequencies only. It cannot validate defensive
trajectories, unchosen actions, counterfactual rollouts or the real-world accuracy
of the Q2 ranking. More realistic generation does not establish calibrated
real-match decision probabilities.
