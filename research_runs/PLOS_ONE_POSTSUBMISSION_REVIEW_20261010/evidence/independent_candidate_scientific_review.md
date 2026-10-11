# Independent candidate scientific review

Candidate: `/workspace/plos-one-postsubmission-20261010/research_runs/PLOS_ONE_POSTSUBMISSION_REVIEW_20261010/revision_content.json`
Candidate SHA256: `6048c25d6e39f5f49100f5c80231b088dd0639f3131dcc7308186011aef0cfd6`

**Status:** NO SCIENTIFIC WORDING BLOCKER IN REVIEWED CANDIDATE; minor editorial fixes; further M1 evidence documentation remains required

This review examined the actual revised main/SI content. No repository writes, model loading/fitting/inference, raw EEG access or new physiological experiment/calculation occurred.

## SCI-01 — main Tables1–8

PASS: All cells compared with submitted manuscript. Tables4/6/7/8 are identical; other changes are semantic experiment names only. Original counts, trial/tensor dimensions, epoch durations, model means, p-values, confidence intervals, recalls and physiology values remain unchanged.

## SCI-02 — M1 Methods main74

PASS: Explicitly reads original frozen prediction tables/probability/identity/hash bindings; no loading/refitting/new inference/threshold/map updates. Primary equal-person BA distinguished from pooled proportions/medians.

## SCI-03 — M1 Results main118; SI94–95

PASS: Cho left92.07%, Lee83.21%; medians0.669/0.633 agree with independently audited saved outputs. TableS5 gives exact equal-person vs pooled BA. Pooled confusion matrices match original stored tables.

## SCI-04 — M1 scientific provenance main135; SI93/97

PASS: Source63.04%, newLOSO61.65%, targetcentering52.39/54.18 are not presented as verified results. Missing code/prediction/partition/centering/hash records stated. Report existence is acknowledged separately from artifact availability.

## SCI-05 — fit-count boundary main59/114; SI61/93/97

PASS: Original15 fits and migration0 remain primary historical counts. New source-held-out report evaluation is explicitly distinguished as requiring additional source fitting. Candidate audit itself does not claim to have performed those fits.

## SCI-06 — target-information boundary main30/60/74; SI97

PASS: No target fitting/adaptation in primary frozen evaluation. Target-input centering, even without labels, is explicitly a different target-adaptation budget, not equivalent zero-calibration follow-up.

## SCI-07 — binary complement SI96

PASS: BA complement values agree with exact original two-class arithmetic: Cho equal-person48.0096153846%, pooled48.0228136882%; Lee47.2314814815%. Report47.22 is identified as a discrepancy rather than replacing frozen values. No outcome-driven complement selected.

## SCI-08 — CSP mechanism main74/135/151; SI93/95/98

PASS: No claim to prove spatial-filter/device causal mechanism or exclude every implementation error. Numerical consistency is separated from physical acquisition truth.

## SCI-09 — source/target adapter boundaries main58/61/146; SI98

PASS: Cho diagram-based row order, physical voltage calibration, native reference and cue latency remain limitations. Neural scores are not used as proof that all label/channel errors are impossible.

## SCI-10 — complete-pipeline comparison main21/48/59/134/151

PASS: Broad/shared18/17Phys and14/19Cho/Lee remain exact. Views, BatchNorm/normalization exposure and computation confounds disclosed; no isolated parameter-sharing/band-decomposition attribution.

## SCI-11 — matched-duration availability main134

PASS: No frozen final all-source matched-duration neural pair claimed. Additional source fitting would be needed if new comparison pursued; none performed here.

## SCI-12 — development heterogeneity main1/98/128/129

PASS: Exploratory33.72→42.67 and S3/S8 87.57% retained. Fixed20 four improved/five worsened and negative median retained; no typical-person/generaloptimal20 inference.

## SCI-13 — robustness main105/106

PASS: No corrected improvement claimed; adverseGroupDRO and uncorrected interval vs Holmnull remain distinct. Runtime confounding retained.

## SCI-14 — external primary conclusions main109/115/116/131/138/151

PASS: Phys superiority not established; Cho corrected adverse−1.513pp retained; Lee+0.204uncertain/non-equivalence; no implied cohort interaction or universalzero-calibration/SOTA conclusion.

## SCI-15 — Q16 Methods main63–66/72

PASS: BNCIonly nine persons/native250Hz, post-decoder-outcome descriptive specification; one baseline vs three overlapping task segments; not unbiasedERD; no decoder feedback/physiology p-values/outcome-driven bands/models.

## SCI-16 — Q16 Results main122–125

PASS: Negative signed laterality separated from absolutecontralateral suppression; S2positiveabsolute components preserved; allsixcoefficients retained; rho+0.600 means larger/lessnegativeL, no causalbenefit.

## SCI-17 — Q16 Discussion/Conclusions main139/140/149/151

PASS: Sensor-level descriptive conclusions, no cortical source localization/decoderattribution/biomarker/clinicalmechanism; no externalphysiology replication; decoderwindowdifference retained.

## SCI-18 — Q16 Fig6 caption main124

PASS: ±6dB frozen scale, no clipping claim retained from frozen figureaudit, sensorgeometrynotcorticalsource. Onevs3Welch estimator precision caveat retained. Circle/trianglereadability statement is editorial, notnewdata.

## SCI-19 — source validation grouping main53/59/145

PASS: Unequal2/2/2/3 fixedgroups equalfold weighting and no prospective grouping sensitivity expressly stated.

## SCI-20 — reproducibility scope main55/61/76/77; SI65/84

PASS: PriorQ15raw-to-prediction replay and Q16rawspectral replay are historicalcompleted validation, not claimednew experiments in thisrevision. Savedoutputaudit remains checkpoint-free; no independentlabreplication claim.

## Minor editorial findings

* main22 caption; main27/48 notes; main31/144 paragraphs: Some sentence-initial lowercase "the" remains after semantic Q-number substitutions. Capitalize sentence starts while preserving technical variable names and frozen numbers.
* main73 heading: "Post-submission audit of archived CSP outputs" puts manuscript-process terminology in the scientific Methods. Prefer "Archived-output CSP diagnostic audit"; retain actual post-submission timing transparently in Methods prose or candidate README/SI.

## Outstanding scientific documentation

M1 remains partly addressed. This review does not clear all possible implementation errors or authenticate the report-described new evaluations.
* Authenticated source resubstitution prediction/score record for new report63.04% if author wants to include it.
* Nine newQ15LOSO fold predictions/model/partition/code/runtime/hash records for report61.65%,SD14.1,range49.3–94.4.
* Exact targetcentering rule/parameters/timing/input/outputhash records for report52.39%/54.18%, with explicitposthocadaptation scope.

Original main Tables1–8 retain all frozen scientific values. The new CSP diagnostic table reconstructs existing saved outputs; reported new fit/centering values are withheld from verified scientific results. No change to primary results is required or authorized.

Export/ZIP/publication/reference completeness and full frozen-file preservation are outside this narrow static review; the final delivery validation must check them.
