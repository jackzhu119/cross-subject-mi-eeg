# Original-method literature audit for postsubmission revision preparation

Three specifically requested original papers; bibliographic metadata verified against formal publisher DOI records. Protocol facts checked in publisher fulltext or explicitly identified institutional author postprint. No scores or target-label budgets inferred from title/abstract alone.

All work was read-only. No fits, predictions or scientific experiments were run. Existing submitted files were not edited.

| Original paper | Task / cohort | Evaluation and label-use boundary | Model selection | Architecture / metric |
|---|---|---|---|---|
| Karel Roots et al. (2020), [DOI 10.3390/computers9030072](https://doi.org/10.3390/computers9030072) | PhysioNet EEG Motor Movement/Imagery dataset; separate binary left/right executed-movement and imagined-movement subsets; 103 of 109 participants after excluding 38, 88, 89, 92, 100 and 104. | Published §2.5 randomly assigns 70% / 10% / 20% of 37,080 pooled labelled samples/windows to train / validation / test with fixed seed. This is not a documented participant-disjoint held-out-subject evaluation, despite the title. No cross-dataset transfer experiment is reported. Labels are used for the pooled training and validation samples. There is no designated unseen target cohort or zero-target-participant-label calibration budget in this protocol; therefore classify this budget as not applicable / not established, not as zero. Test labels are used for scoring. | Best validation-accuracy checkpoint retained/loaded (§2.5). The paper evaluates branch hyperparameter choices but does not provide a prospectively frozen participant-disjoint source-only selection and target-inference evidence chain. | Three separately parameterized EEGNet-style branches with temporal kernel lengths64/128/256 and differing filter counts; learned branch features are concatenated before classification. All branches receive the same bandpass-preprocessed input. This is multiscale/multibranch fusion, not fixed μ/β views sharing one backbone parameter set. Ordinary classification accuracy (correct labels / total), precision, recall, F1 and runtime per sample. Original4-second trials are divided into eight nonoverlapping0.5-second windows, each with the trial label; no participant-level BA estimand in §2.5. |
| Niklas Smedemark-Margulies et al. (2024), [DOI 10.1088/1741-2552/ad9777](https://doi.org/10.1088/1741-2552/ad9777) | RSVP binary target/non-target stimulus classification, not motor imagery; just over1million trials,64participants with two sessions. Data recorded1000Hz and provided250Hz; non-target trials subsampled to10:1 relative to target trials. | Within-dataset zero-shot subject transfer. Main experiments use28training and4test participants for100epochs. Ten partially overlapping subject splits ×10random seeds; within each split subject sets are disjoint. No cross-dataset MI transfer experiment. §2.1 describes training on source participants and at test time receiving only X from unseen test participants to infer Y. No target-subject fitting is described in these zero-shot experiments. Test labels nevertheless support performance evaluation; optimal λ/peak comparisons are selected from test performance (§§3.2 and6.2.2). Thus zero-shot target fitting does not imply fully source-only selection of reported optimal configurations. | Main fixed100epoch hyperparameter sweep; optimal-λ peak comparisons pooled across censor modes/projection choices. Appendix6.2 uses24training/4validation/4test participants, best validation-performance checkpoint, max30epochs. Appendix6.2.2 explicitly selects λ giving best mean test performance; distinguish this peak analysis from prospectively source-only frozen model selection. | 1D CNN encoder, MLP task classifier, optional MLP projector and auxiliary censor network. Density-ratio mutual-information or Wasserstein critic censoring with marginal/conditional/complementary modes. Not a fixed overlapping-filter-bank or shared μ/β branch architecture. Balanced accuracy and test/train balanced-accuracy generalization ratio; variability across seeds/splits/hyperparameters. Quantitative results are not comparable to current MI cross-dataset cohorts/tasks. |
| Jing Luo et al. (2023), [DOI 10.1186/s13040-023-00336-y](https://doi.org/10.1186/s13040-023-00336-y) | BCIIV2a/BNCI2014_001:9participants/four MIclasses; High-Gamma:14participants/four motor-execution/rest classes (not MI); OpenBMI:21selected of54participants/binary left-right MI after excluding33 designated MI-blind subjects. | Pooled multisubject within-dataset recognition. All9BNCI participants contribute training and test-session data; all14High-Gamma participants contribute earlier-run training and later-run testing. OpenBMI uses selected21participants and recordedtrain/test sets. No participant-disjoint unseen-target design or cross-dataset frozen transfer is described. Dataset participants contribute labelled training data; future test-session participants are represented in the training cohort. Therefore not zero-target-participant-label fitting. No distinct unseen target-participant calibration budget is defined; mark not applicable rather than zero. | BNCI/High-Gamma maximum500epochs; OpenBMI300epochs; average test accuracy/F1/AUC over final100epochs reported. Frequency-step sensitivity study selects4Hz as an empirical choice based on reported test results(Table4/Fig5,p13), not a prospectively source-only locked validation selection. No separate validation-fold checkpoint selection described in reviewed Experimentalsetup. | Multiple independent CNN models, one per overlapping bandpass-filtered view, trained separately with cross-entropy; output probabilities summed beforeargmax(Eqs2–4). Backbones shallow/deepConvNet,EEGNet,ATCNet. Table1 fixed low-cut examples0–8,0–12,…0–36Hz and4–12,4–16,…4–36Hz; sliding examples0–12,4–16,…24–36Hz. Explicitly separate models, not parameter-sharing μ/β backbone. Ordinary accuracy(%),F1,AUC and test-accuracy variance averaged over the last100training epochs. No participant-level BA matched to current zero-calibration transfer estimand. |

## Bibliographic records and primary-text evidence

### Roots2020

**Formal reference:** Karel Roots, Yar Muhammad, Naveed Muhammad. Fusion Convolutional Neural Network for Cross-Subject EEG Motor Imagery Classification. Computers. 2020;9(3):72. doi:10.3390/computers9030072.

**Fulltext:** [publisher_version_of_record_retrieved](https://mdpi-res.com/d_attachment/computers/computers-09-00072/article_deploy/computers-09-00072.pdf). 

**Evidence locators:** Publisher PDF §§2.1–2.2 (pp3–4), §2.3 (pp4–5), §2.5 (p5).

**Unlabelled-target statistics:** Paper reports notch60Hz and bandpass2–60Hz preprocessing and learned BatchNorm layers. No explicit target-domain distribution adaptation stage is described; no independently inspected code or normalization-statistics provenance audit was performed, so do not assert target-statistics exclusion.

**Interpretation boundary:** Do not quantitatively compare its headline ordinary sample/window accuracy with the current participant-level balanced-accuracy transfer estimates. Cite as architecture precedent while stating protocol non-equivalence. Pooled-window random splitting also gives no guarantee of trial-level or participant-level disjointness.

**Local excerpts:** `literature_sources/primary_excerpts/roots_cohort_preprocessing.txt`, `literature_sources/primary_excerpts/roots_branches.txt`, `literature_sources/primary_excerpts/roots_split_selection_metrics.txt`

### SmedemarkMargulies2024

**Formal reference:** Niklas Smedemark-Margulies, Ye Wang, Toshiaki Koike-Akino, Jing Liu, Kieran Parsons, Yunus Bicer, Deniz Erdoğmuş. Improving subject transfer in EEG classification with divergence estimation. Journal of Neural Engineering. 2024;21(6):066031. doi:10.1088/1741-2552/ad9777.

**Fulltext:** [formal_metadata_verified_institutional_author_postprint_retrieved_publisher_pdf_challenge_blocked](https://www.merl.com/publications/docs/TR2025-044.pdf). MERL TR2025-044 institutional cover is dated2April2025 and says JNE2025, but publisher-deposited DOI metadata and PubMed39591745 identify the formal article as JNE21(6):066031 (2024), online16December2024. Use formal2024 bibliography, not technical-report/preprint year. The institutional postprint abstract matches publisher-deposited formal abstract; direct publisher PDF returned an anti-bot challenge, so the VoR fulltext itself was not independently recovered.

**Evidence locators:** Institutional postprint §2.1 (printedp4), §2.9 (pp10–11), §3.2 (p12), Appendix6.2/6.2.2 (pp19–20); formal metadata Crossref +PubMed39591745.

**Unlabelled-target statistics:** Censoring penalties estimate dependence between source latent features and subject/session IDs, with optional task-label conditioning, using training batches. No explicit test-subject adaptation/distribution alignment stage is described. Preprocessing and empirical exclusion of all target-derived normalization statistics are not established by the inspected Methods; mark that narrower detail unverified.

**Interpretation boundary:** Cite as general EEG zero-shot subject-transfer and selection-sensitivity precedent, explicitly RSVP rather than MI. Do not label its ideal-parameter results a source-only frozen selection benchmark. Do not cite2023 arXiv title Stabilizing Subject Transfer in EEG Classification with Divergence Estimation as the final formal title/year.

**Local excerpts:** `literature_sources/primary_excerpts/smed_problem_statement.txt`, `literature_sources/primary_excerpts/smed_rsvp_cohort_training_and_metric.txt`, `literature_sources/primary_excerpts/smed_peak_selection.txt`, `literature_sources/primary_excerpts/smed_early_stopping_and_test_peak_selection.txt`

### Luo2023

**Formal reference:** Jing Luo, Jundong Li, Qi Mao, Zhenghao Shi, Haiqin Liu, Xiaoyong Ren, Xinhong Hei. Overlapping filter bank convolutional neural network for multisubject multicategory motor imagery brain-computer interface. BioData Mining. 2023;16(1):19. doi:10.1186/s13040-023-00336-y.

**Fulltext:** [publisher_version_of_record_retrieved](https://link.springer.com/content/pdf/10.1186/s13040-023-00336-y.pdf). 

**Evidence locators:** PublisherPDF Table1/Eqs2–4(pp5–6); Experimentaldata(pp7–8); Experimentalsetup(p8); performancecomparison(p9); sensitivitystudy(Table4/Fig5,p13).

**Unlabelled-target statistics:** Exponential running channel standardization is applied to filtered EEG (Experimentalsetup,p8). This is input-dependent preprocessing, not evidence of a source-only fixed normalization-statistics contract. The paper does not document a separate target adaptation stage; exact training-versus-test running-statistics reset/fit provenance was not verified from execution.

**Interpretation boundary:** Relevant overlapping-filter-bank/ensemble precedent, not a direct unseen-subject or cross-dataset source-only comparator. Do not imply superiority or numerical equivalence across unequal class counts, tasks, cohort exclusions, metrics, split and epoch-selection rules. Formal2023 paper has7authors, includingJundongLi andHaiqinLiu; ResearchSquare preprints have different authorlists/name spelling and must not supply final citation metadata.

**Local excerpts:** `literature_sources/primary_excerpts/luo_bands_and_separate_models.txt`, `literature_sources/primary_excerpts/luo_cohorts_split_and_normalization.txt`, `literature_sources/primary_excerpts/luo_epoch_reporting.txt`, `literature_sources/primary_excerpts/luo_frequency_step_selection.txt`

## Safe manuscript synthesis

Multibranch fusion and overlapping-filter-bank ensembles are established EEG approaches, and dependence-censoring has been studied for zero-shot EEG subject transfer. The current study should therefore frame its contribution as a source-only model-selection audit with participant heterogeneity, frozen cross-dataset evaluation, retention of adverse/null results, and a reproducible evidence chain, not as the first multibranch representation or a new state-of-the-art domain-generalization algorithm. The three precedents do not provide a protocol-matched performance ranking: Roots uses a pooled-window random split; Luo uses same-cohort multisubject train/test sessions; Smedemark-Margulies studies RSVP with test-based optimal-λ peak analyses.

## Remaining verification boundaries

- DirectSmedemark-Margulies publisherVoR fulltext unavailable duechallenge; institutional postprint used with formalmetadata.
- Noauthorcodeexecuted ortraining-statistics provenance empirically audited for anypriorpaper.
- No cross-study numerical performancecomparison warranted.
- No newmethods citationsare added to already-submitted files automatically.

All primary files and excerpts have SHA-256 provenance in the JSON companion. Keep downloaded third-party PDFs local; they are verification sources, not author-owned CC BY release assets.
