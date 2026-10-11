# Verified PLOS ONE comparators — read-only literature audit

Checked UTC: 2026-10-10T12:48:46.744959+00:00

Read-only publisher full-text and Crossref review; no repository edits, experiments, fits, inference or new statistical analysis.

The three titles supplied for checking are shorthand. Publisher versions below are exact matches verified by DOI and metadata. They cannot be attributed to an unnamed reviewer, editor or missing scientific-review attachment.

LOSO alone does not establish a matched source-only information budget. Target-label eligibility/mapping, scoring, target-unlabelled normalization/alignment and validation-selection access must be specified separately. Absence of a reported detail is not evidence of leakage or of a restriction.

## accuracy_cost

Deep learning for EEG-based Motor Imagery classification: Accuracy-cost trade-off

Javier León; Juan José Escobar; Andrés Ortiz; Julio Ortega; Jesús González; Pedro Martín-Smith; John Q. Gan; Miguel Damas. 2020-06-11. PLOS ONE 15(6): e0234178. [DOI](https://doi.org/10.1371/journal.pone.0234178).

**dataset and task.** Three selected University of Essex participants (104, 107, 110) from a 12-person study; left hand, right hand and feet imagery. Fifteen channels, 256 Hz, 178 patterns and 3,600 wavelet-derived input features per participant dataset.

**evaluation.** Participant-specific experiments; 5-fold training-set cross-validation guides genetic feature/structure/training-hyperparameter searches, and test-set Kappa evaluates final models. Results average 15 executions. No held-out-person or external-dataset test is reported.

**target label budget.** Labels from each evaluated participant enter that participant dataset’s fitting/selection; this is not unseen-target source-only evaluation.

**target unlabelled statistics budget.** Patterns are normalized to [0,1]; fitted normalization scope is not sufficiently specified to certify a source-only contract. No source–target adaptation protocol is reported.

**selection and features.** Genetic feature selection and two-stage structural/learning search, including epochs; wavelet variance features and shallow CNN/FFNN/RNN.

**metrics and compute.** Training CV accuracy; test Kappa; measured training energy/time and architecture complexity.

**relevance.** Useful for a narrow statement that model selection and compute belong in evaluation. Low priority for main related work: selected-participant, within-dataset experiment differs substantially from this frozen external audit. Do not use as a numerical baseline.

**Evidence locations.** 10, 11, 13, 14, 15, 67, 79, 82, 86, 88, 89, 123, 128 in `accuracy_cost_publisher_paragraphs.json` (zero-based primary article body paragraph indexes). XML SHA-256: `6181156a89da653027c3db9d595107b0befa8c6bb70ce30f7c0f06ac9dc3639f`. Publisher XML and exact excerpts are retained in this QA directory. Crossref title/authors/publication date all agree.

## smmtm

SMMTM: Motor imagery EEG decoding algorithm using a hybrid multi-branch separable convolutional self-attention temporal convolutional network

DianGuo Cao; ZhenYuan Yu; Jinqiang Wang; Yuqiang Wu. 2025-10-23. PLOS ONE 20(10): e0333805. [DOI](https://doi.org/10.1371/journal.pone.0333805).

**dataset and task.** BCI Competition IV-2a (nine participants, four classes, 22 channels) and IV-2b (nine participants, binary hands, three channels), sampled at 250 Hz.

**evaluation.** Within-person evaluation and IV-2a LOSO: one held-out person and eight training people. It describes 5-fold validation and validation-set parameter selection/early stopping, but does not fully identify validation folds or every selection information boundary. Do not infer target-label leakage.

**target label budget.** LOSO testing labels support evaluation; remaining-person labels support training. Exact hyperparameter/early-stopping validation partition is not sufficiently documented to certify equivalence to the present source-only contract.

**target unlabelled statistics budget.** Z-score mean/variance are explicitly fitted on training data and applied to test data. No target distribution-matching procedure is reported.

**selection and features.** Serial spatiotemporal convolutions; three learned separable-convolution branches with kernel lengths 8/16/32; self-attention, TCN and feature/decision fusion. These are learned multiscale temporal filters, not fixed mu/beta input views.

**metrics and compute.** Accuracy, Kappa and Wilcoxon comparisons; architecture complexity is documented.

**relevance.** Direct recent architectural context, but no external-cohort replication or matched frozen source-selection protocol. A concise citation is justified; no SOTA ranking or isolated spectral-sharing comparison.

**Evidence locations.** 11, 12, 13, 31, 32, 33, 34, 35, 38, 40, 49, 51, 52 in `smmtm_publisher_paragraphs.json` (zero-based primary article body paragraph indexes). XML SHA-256: `1d66b41bc2e5c3c6bc75ffaebc81e20240179a350662bcc0ebfa727ab8465b32`. Publisher XML and exact excerpts are retained in this QA directory. Crossref title/authors/publication date all agree.

## rmetnet

RMETNet: A cross-subject motor imagery EEG signal classification model based on TSLANet and riemannian geometry features

Yun Zhao; Dongyi He; Fudai Ren; Qingling Xia; Linhao Xu; Guanghui Xie; Xiaoling Zhang; Renqiang Yang; Shuaidong Zou; Bin Jiang. 2026-04-22. PLOS ONE 21(4): e0347671. [DOI](https://doi.org/10.1371/journal.pone.0347671).

**dataset and task.** IV-2a (nine people, four classes, 22 channels) and IV-2b (nine people, binary hands, three channels; only three feedback sessions, 480 trials/person). Four-second 0.5–4.5-s post-cue windows.

**evaluation.** LOSO and within-person 8:1:1 splits; source participants supply training/validation. Source–target MMD and precomputed Riemannian alignment are expressly part of the method, which the paper calls session-level adaptation.

**target label budget.** Classification weighting uses source labels. Unlabelled target features enter distribution matching; no explicit ground-truth target supervision is described for MMD. Detailed target sample exposure/timing is not fully resolved; do not assume all-label access or source-only equivalence.

**target unlabelled statistics budget.** Training-fitted Z-score parameters; covariance/Riemannian features from source and target plus MMD alignment. This uses target distribution information, unlike the present no-target-adaptation contract.

**selection and features.** 500-epoch training budget; minimum-validation-loss checkpoint. TSLANet learned spectral gating, spatiotemporal convolutions and Riemannian branch.

**metrics and compute.** Accuracy, Kappa, Wilcoxon; parameters, FLOPs and latency with preprocessing distinguished from forward inference.

**relevance.** Highly relevant to distinguish cross-person transfer with unlabelled adaptation from strictly frozen source-only external evaluation. Cite for protocol distinction, not as a matched superiority comparator.

**Evidence locations.** 12, 13, 14, 15, 16, 34, 35, 47, 50, 51, 52, 56, 70, 76, 85 in `rmetnet_publisher_paragraphs.json` (zero-based primary article body paragraph indexes). XML SHA-256: `3ceffc7a6f6d0d08871fe50525f41fb83416837c466146ad3b5f0db2bbe18e3a`. Publisher XML and exact excerpts are retained in this QA directory. Crossref title/authors/publication date all agree.

## Scoped recommendation

Use SMMTM and RMETNet only if the revision needs recent architecture/adaptation context. They do not establish superiority, equivalence or a matched comparator for the present source-only pipeline audit. The 2020 accuracy-cost study is optional and lower priority; omit if the manuscript already supports compute/selection limitations.

Candidate prose: Recent multibranch architectures combine temporal convolutions and attention for within-dataset motor-imagery decoding, as in SMMTM. RMETNet adds learned spectral and Riemannian features together with source–target distribution alignment. These architecture and adaptation studies address a different evaluation question from the present audit of frozen source-selected external pipelines; their published accuracies do not provide matched estimates for our contrasts.

No experiment was rerun. No numerical between-paper leaderboard is justified. Published LOSO accuracy is not automatically comparable to external-cohort balanced accuracy. The SMMTM shorthand title and RMETNet preprint authors must not replace the formal publisher metadata.
