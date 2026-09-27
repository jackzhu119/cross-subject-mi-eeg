# Paper-stage local continuation, 2026-09-27

This folder is a **new versioned preparation packet** built after reviewing
GitHub `main` at `e70a07690646561135aa4b22d0bd9335a44c7412`. It does not
rewrite `PAPER_RELEASE_20260926`, any frozen Q5--Q14 result, or a prior
failed-attempt receipt. The cloud is off; nothing in this packet launches or
authorizes GPU work or an external prediction.

## Read in order

1. `Q12_Q14_EVIDENCE.md`: audited Q12 and Q14 results and scientific limits.
2. `CURRENT_STATUS_AND_GATES.md`: which evidence gates are green, pending, or
   blocked and what the next cloud release would need to verify.
3. `research_runs/Q13-E006/AMENDMENT.md`: additive, matched-runtime 27-fit
   control for Q13's historical source-only epoch schedule. The original
   837-fit Q13 matrix/runner remain unchanged and unrun.
4. `Q15_AMENDMENT.md` and `Q15_CONTRACT.json`: prospective 21-channel,
   two-second external-cohort design, **conditional** on real Lee/Cho metadata
   audits and a new BNCI source freeze. The old 22-channel Lee arm is blocked
   by the current MOABB channel catalogue until raw-file review.
5. `Q15_METADATA_AUDIT_RUNBOOK.md` and `Q15_E005_SOURCE_RUNBOOK.md`: exact
   fail-closed gates for real-data metadata review and the conditional BNCI
   source-only runner. Both remain **non-authorizing** today: no reviewed real
   Lee/Cho adapter/provider inventory or independent Q15 source validator
   exists. `research_runs/Q13-E006/POSTRUN_STATS.md` describes the separate
   subject-level statistics to run only after Q13 and E006 scientific passes.

The Q12 descriptive per-person heatmap is
`figures/q12_subject_delta_heatmap.png`; its generation is reproducible via
`scripts/paper_q12_heterogeneity_figure.py`. It is not an inferential test.

## Scientific boundary

Q12 and Q14 are already validated but do not establish that the tested
source-only method or shared μ/β representation universally improves unseen
people. Q13 has no results yet. Q15 has neither raw metadata receipt nor
classifier results. A passing plan/synthetic test is not a scientific pass.
The unit for confidence intervals is a held-out person, not a trial, seed,
session, or source subset. No method, seed, channel subset, or cohort may be
selected from external target balanced accuracy.

## Local verification

Use the project's Python environment; the Windows system Python may not
contain MNE/Braindecode. The non-executing checks are:

```text
python -m pytest tests/test_q13.py tests/test_q13_e006.py tests/test_q13_e006_postrun_stats.py tests/test_q15_prospective_contract.py tests/test_q15_metadata_audit.py tests/test_q15_source_preflight.py -q
python scripts/q13_batch.py
python scripts/q13_e006.py
python research_runs/PAPER_RELEASE_20260927/q15_validate_contract.py
python scripts/q15_source.py
python scripts/paper_q12_heterogeneity_figure.py
```

These verify plans, historical selections, fail-closed conditions and a
figure. `q15_source.py` must currently report blocked with zero fits. They do
not validate CUDA, raw Lee/Cho compatibility, future Q13
checkpoints, live publication, or server persistence. Before a later cloud
release, freeze and commit the new code, rerun tests, check every raw file
hash and the host runtime, then use the independent scientific validators.
Do not restart the old `Q12-PAPERQUEUE2` orchestration; its historic frozen
manifest no longer matches the current code and its failure record belongs
in the audit trail.
