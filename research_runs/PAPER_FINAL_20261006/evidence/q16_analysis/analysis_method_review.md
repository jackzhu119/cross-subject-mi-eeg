# Q16 BNCI pre-execution method review

**Approved before raw power computation.** The reviewed three-script numerical pipeline, protocol, sensor geometry, plot recipe, passed metadata receipt and prepared freeze have no unresolved blocking scientific issue. All bound file sizes and SHA-256 digests match the prepared freeze. Actual execution must use the committed immutable freeze.

The reviewer did not open current original EEG, calculate original physiological power, fit a decoder or produce new decoder predictions. Synthetic spectral calculations and existing saved-Q14 prediction checks were performed independently.

The prior binary endpoint audit checked all 63 saved prediction hashes and all 63 complete final manifests, confirmed that each outer target was excluded from training, matched 2,592 binary identities to Q8, and reproduced 63 balanced-accuracy cells from 18,144 saved prediction rows. Q14 neural seeds are averaged within person; CSP retains its `deterministic` seed identifier.

Independent synthetic checks passed for the fixed periodic-Hann Welch estimator, inclusive trapezoid bands, amplitude doubling/halving, uniform voltage-gain invariance, nonpositive/nonfinite power guards, and the laterality sign. Aggregation checks excluded an unpaired extreme C3 value, reproduced the equal-session/equal-hand −1 dB descriptor with absolute contralateral −2.5 dB and ipsilateral −1.5 dB components, retained a person with an unavailable hand/session descriptor, validated the actual Q14 performance schema, and reproduced exactly six signed nine-person Spearman contexts without p-values.

Review fixes were made before freezing: the CSP seed text is preserved; native trial starts are bounded before offset arithmetic; raw class strings and simplified loader shape are retained; metadata states that amplitude-finite guards occur in the analysis windows; and all 6,336 artifact-stratum cells are represented, including empty cells.

The actual geometry contains all 22 declared sensors in montage order. The frozen orthographic projection reproduces from the source coordinates, places C3 on viewer left and C4 on viewer right, and has anterior upward. The standard template is schematic rather than digitized participant geometry. Linear Delaunay interpolation is restricted to the sensor convex hull; outside areas stay blank. Color limits stay −6 to +6 dB. The 161 × 161 figure grid and 41 × 41 TeX display approximation are both fixed before power; clipping counts must be reported without altering numerical values. Cohort maps use equal-person means.

The companion JSON records exact reviewed file hashes and the passed metadata counts: 18 files, 108 labeled runs, nine people, 18 person-sessions, 5,184 four-class trials and 2,592 hand trials, with 488 and 246 native artifact flags. The nominal prior-task separation gate passes without a window-bound or overlap failure. This establishes timing feasibility, not neural recovery or behavioral compliance.

A separate post-execution reviewer must still independently recompute raw C3/Cz/C4 power using an independent periodogram implementation and verify saved aggregation and all six associations before manuscript use. This approval is a pre-execution method review, not that raw numerical validation.

Keep the declared interpretation limits in the paper: BNCI-only physiology; post hoc descriptive nine-person associations; no p-values, tertiles or biomarker validation; relative signed laterality with absolute components visible; unequal baseline/task Welch precision and possible stationary log-ratio offset; no newly verified physical voltage calibration; no cortical source or decoder-mechanism attribution; and distinct Q14 decoder versus Q16 physiology windows.
