# Research log — 2026-09-27

- **Current question:** What do the completed Q12 source-only domain-generalization
  and Q14 external-transfer experiments actually support, and what should be
  frozen before Q13 heterogeneity and Q15 independent-cohort work?
- **Evidence examined:** GitHub `main` snapshot `e70a076`; Q12 batch/scientific
  validation, six subject-level paired contrasts and saved predictions; Q14
  R2 completion, historic failed validator, amended portable independent
  validation, 109-person subject table and 34,426 trial predictions. Historical
  results and checkpoint files were not edited.
- **Methods of this audit:** Recomputed subject-level BA from saved predictions
  and checked against validators; kept subjects as inferential units, seeds
  within subjects, and the predeclared Q14 primary contrast separate from
  exploratory Q12 and deep-versus-CSP findings. Generated a fixed-order Q12
  all-subject heatmap without excluding difficult participants.
- **Result:** Q12's 12 jobs, 216 inner and 162 final fits are complete and
  scientifically validated. None of the six tested conditions establishes a
  multiplicity-corrected improvement over its declared control. Q14's
  109-subject external binary prediction set passed the versioned independent
  validation; shared μ/β minus broad BA is +0.005733 with subject-bootstrap
  95% CI [−0.000967, +0.012416], so superiority is not established. Preserve
  the negative results, class-collapse cases, rate amendment, and failed
  validator history. See `Q12_Q14_EVIDENCE.md` for exact figures and paths.
- **Problem found:** Q13's original Q5 reuse could confound a historical
  PyTorch/CUDA runtime with the epoch schedule. A separate Q13-E006 27-fit
  matched-runtime sensitivity protocol/runner/validator was prepared locally;
  it has not been trained. The MOABB v1.7.2 Lee channel catalogue omits
  Q14's required FCz, so old 22-channel Lee transfer is blocked pending raw
  metadata confirmation. A conditional Q15-E005 21-channel source protocol
  and E006/E007 external arms were specified before new cohort outcomes.
- **Local implementation and verification:** Added Q13-E006 post-run
  subject-level statistics (blocked until both independent Q13/E006 validators
  pass), Q15 metadata-only audit scaffold, and Q15-E005 source-only runner.
  Current real Lee/Cho MAT files deliberately cannot pass the auditor without
  a reviewed provider adapter and authenticated complete inventory. The Q15
  source dry run returned `blocked_metadata_or_freeze_pending`, `fits_started:0`;
  Q15 static contract still returns `external_prediction_authorized=false`.
  Six targeted Q13/Q15 test modules passed **76/76**; the complete repository
  suite passed **190/190** and Ruff passed. These
  are structural/synthetic checks, not GPU fits or external validation.
  Real Q13 GPU fits, Lee/Cho raw audits, Q15 source fitting, external
  inference, and future publication were not performed. The cloud remained off.
- **Next step:** Independently review the new Q13/Q15 code. Only after an
  explicit later release instruction should a new cloud queue be
  committed/published, host/data hashes rechecked, and Q13 training started.
  Q15 needs real data adapters/inventory, a source validator, and further
  pre-fit/source-checkpoint freezes before external scoring; its current
  source-runner implementation is not a cloud training release.
