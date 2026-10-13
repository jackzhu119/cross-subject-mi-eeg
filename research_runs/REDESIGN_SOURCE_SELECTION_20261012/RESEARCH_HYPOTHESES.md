# Research hypotheses and contribution boundaries

Version1, prepared13October2026. Core question: **How reliable are source-only model-selection decisions for cross-subject motor-imagery EEG decoding under participant heterogeneity and cross-dataset distribution shifts?**

## Unified scientific contribution

Reliability is defined through a locked selection-rule contrast, participant-level benefit and failure distributions, and a task-matched first-use acquisition cohort. The potential contribution is empirical: whether developmental stopping-rule gains survive this information budget and acquisition shift. Model selection, nested evaluation, multi-seed analysis and robust EEG benchmarking already have direct precedents (Cawley/Talbot, DomainBed, SpeechBrain-MOABB, Borra2025); none is claimed invented here. A null or adverse new-target estimate is a valid answer. Until the new-cohort gates and models run, the independent contribution is a planned test, not an established finding.

### H1: primary independent-cohort duration-selection contrast

For the common19-channel Broad EEGNet, test the two-sided zero mean of participant-balanced-accuracy differences mean-rank minus mean-loss. All three final seeds are averaged within person. The nine historical BNCI people and observed PhysioNet/Cho/Lee cohorts do not supply independent confirmation. New target labels/statistics cannot pick schedules, seed, grouping, band, crop or preprocessing.

### H2: simple versus selected schedules

Fixed20 minus mean-loss and fixed20 minus mean-rank are prespecified secondary differences. Fixed20 is a pragmatic source-development benchmark, not an optimum inferred from new targets. No noninferiority/equivalence margin is scientifically justified; nonsignificance cannot establish either.

### H3: duration-matched complete-pipeline contrast

Shared μ/β fixed20 minus Broad fixed20 is the third secondary contrast. It controls epoch count, source persons, native trial processing, channel set, crop, final-seed strategy and target scoring. It does not isolate parameter sharing: band inputs, two-view computation, pooled BatchNorm exposure and representation differ. Source-selected architecture contrasts and interaction contrasts remain descriptive.

### H4: secondary reliability diagnostics

Record participant prediction dominance, class recalls, tail BA and source grouping/compute sensitivity. The fresh21-channel CPU CSP source audit is retrospective diagnostic evidence, not an H1 replication or new biological mechanism. No posthoc target mean-centering/threshold/label flip changes primary outputs. If later explored, it must be declared target adaptation and kept separate.

## Confirmatory gate and falsifiability

H1 is the sole primary endpoint/test. Only its rejection opens the three-test Holm secondary family; all estimates/uncertainties/adverse results are reported irrespective of the gate. Closed data/identity/prior-use/code/checkpoint gates prevent confirmatory labelling even if p<.05. No outcome authorizes favourable participant removal, model retuning or replacement of the primary cohort. One acquisition programme is one target-cohort evaluation, not three A/B/C replications or a population of datasets.

Q16 addresses measured-signal description rather than model-selection reliability and is moved chiefly to Supporting Information. Its existing negative/variable laterality and six no-p-value associations remain in the historical record. No physiology-driven extra training is planned.
