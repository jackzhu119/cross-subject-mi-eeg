# Q16-P001: BNCI sensor-level physiological characterization

Analysis date: 6 October 2026 (UTC). This executes the BNCI component of the earlier `PAPER_RELEASE_20260926/NEUROPHYSIOLOGY_PROTOCOL.md`. It is a descriptive analysis developed after decoder outcomes were available. The earlier document proposed windows and bands; it was not an independent prospective registration. The explicit estimator, aggregation, coverage, plotting, and association choices below are committed before any new raw power computation. There is no decoder fitting, adaptation, checkpoint inference, parameter selection, or feedback to the existing decoder results.

## Scientific scope and populations

Use all 18 original BNCI2014_001 MAT files, nine people, both sessions, six labeled runs per file, 48 trials per labeled run: 5,184 four-class trials. The left/right subset has 2,592 trials. Retain provider artifact flags as annotations, including 488 flagged four-class trials and 246 flagged hand trials; the primary analysis does not discard them. Separate unflagged summaries are a sensitivity description, not a replacement primary cohort or a basis for selecting decoders. Non-imagery run structs are not analyzed. Verify original bytes against the previously persisted official-source receipt before metadata inspection and computation. Metadata and event identities must match the archived Q8/Q15 source inventory.

External physiology is not computed in this component. The existing Cho mapping does not establish physical-run baseline continuity or the original acquisition reference, and Lee event indexing has a disclosed native-sample convention difference. External decoder outcomes remain separately evaluated frozen results. This BNCI component cannot establish an external neural mechanism, resolve acquisition calibration, or complete the entire proposed external physiology programme.

## Fixed event and signal conventions

Native sample rate is 250 Hz. Convert each MATLAB trial start to zero-based index by subtracting one; the imagery cue is 500 samples (2 s) later. Verify native class strings in code order: left hand, right hand, feet, tongue. Use the provider-ordered 22 EEG columns and skip its three EOG columns: Fz, FC3, FC1, FCz, FC2, FC4, C5, C3, C1, Cz, C2, C4, C6, CP3, CP1, CPz, CP2, CP4, P1, Pz, P2, POz. This is a documented montage mapping; the MAT file does not have per-column channel-name strings.

The half-open baseline is cue [−1.5,−0.5) s, equivalent to trial-start offsets [125,375). The half-open task interval is cue [0.5,2.5) s, offsets [625,1125). Both intervals must lie in the same labeled native run. Check the baseline against the previous trial's nominal cue+4-s imagery end (trial start +1,500 samples); report first trials without a prior within-run trial separately. These checks establish nominal timing feasibility, not observed neural recovery, behavioral compliance, or an independently recorded resting state.

Use native EEG amplitudes without additional digital filter, resampling, CAR, source scaler, learned spatial projection, or decoder transform. Provider acquisition filtering/reference remain part of the recordings. Baseline and task samples must be finite. Every channel/band pair requires finite, strictly positive integrated powers; report unavailable pairs and counts explicitly. Do not replace invalid powers with an arbitrary epsilon or allow data-dependent window changes.

## Fixed spectral estimator

Use Welch PSD with a one-second 250-sample **periodic Hann** window (`fftbins=True`), 125-sample overlap, 250-point FFT, linear detrending for every segment, one-sided density scaling, and arithmetic mean segment averaging. Baseline supplies one segment; the two-second task window supplies three overlapping segments. Integrate inclusive native-frequency bins 8–13 Hz for mu and 13–30 Hz for beta using the trapezoidal rule. The 13-Hz endpoint belongs to both declared band intervals. PSD units are native-numeric squared per Hz; integrated powers are native-numeric squared. No new absolute voltage calibration is asserted.

For each trial/channel/band calculate `10 log10(task_bandpower / baseline_bandpower)` in dB. Negative values denote lower estimated task power (ERD), positive values higher estimated power (ERS), relative to this baseline and estimator. Average **trial-level dB values**, not the logarithm of mean powers: within person × session × hand × channel × band, then weight the two sessions equally within person, then weight people equally for cohort summaries. Preserve per-trial power, eligibility and event identities, session means, person means and medians. Additional four-class summaries are descriptive and distinct from hand-specific primary panels.

Unequal baseline/task segment counts give unequal estimator variance. The concavity of the logarithm means that this fixed ratio can show a positive offset even for stationary signals; overlapping task segments are correlated. The metric is a window-specific descriptive estimate, not an unbiased power-change estimate or a mechanistic test. Do not redesign the baseline after seeing the result.

## Laterality and frozen-score associations

For each band/person form `0.5 × [(C3_right − C4_right) + (C4_left − C3_left)]`, with terms being the person-level dB values above. Negative indicates a relatively more negative contralateral than ipsilateral value; it does not by itself prove absolute contralateral suppression. Report the four constituent C3/C4 values, their absolute contra/ipsilateral averages, and Cz values alongside the descriptor.

The primary contextual association is Spearman correlation between this descriptor and the person's already saved three-seed-averaged **Q14 binary BNCI source LOSO Broad EEGNet balanced accuracy**. This is nine source-benchmark people, not external transfer scores. Report both bands and all Broad/Shared/CSP contexts (six correlations) without selecting the largest, without p-values or claims of confirmed association. Q14 decoder windows are cue [0.5,3.5), whereas Q16 uses [0.5,2.5); these are distinct representations. Reverify saved scoring populations and zero target fitting; seeds/sessions/trials do not increase n=9. No high/low-BA strata, decoder correctness conditioning, favorable-participant exclusion or tuning to correlation are permitted in this component.

## Predetermined figures and interpretation

Scalp figures use all 22 standard-1020 sensor positions, the geometry table frozen with this protocol, native montage orientation (anterior upward, left scalp on viewer left), a linear triangulated field only within the sensor convex hull, and the same symmetric color limits **−6 to +6 dB** for all mu/beta × hand maps. Outside-hull areas remain blank even within the illustrative head outline. Report actual clipping counts; do not change limits to accentuate results. Geometry is a schematic standard template, not digitized participant locations. No cortical source localization is implied. Include C3/Cz/C4 absolute person-level values, the two-band laterality distributions, and all nine-person Broad-score association points; Shared/CSP contexts remain visible in tables or supplement.

## Evidence and execution gate

A metadata-only audit is completed before this explicit preprocessing freeze. The committed manifest binds this protocol, raw receipt, metadata audit, event inventory, saved BA/validation files, analysis code, and figure geometry. Raw power execution requires verification against that immutable commit and the same local bytes. Preserve software versions, invocation, timestamps and output SHA-256 digests. A separate numerical reviewer must verify at least the full C3/Cz/C4 raw power calculation with an independently written periodogram and all aggregation/association calculations before the manuscript uses results.

This analysis is not a classifier experiment. New decoder fits = 0; new checkpoint inference = 0. Existing Q14/Q15 frozen pipelines, source-fit counts, evaluation populations, prediction tables, primary tests and result commits remain unchanged.
