# Methods and original-reference audit

This audit describes completed repository work and supplies English manuscript wording with Chinese explanations. All Q15 data and prospective external cohorts are excluded. No training, preprocessing, checkpoint editing, or frozen-code changes occurred during this audit. The companion JSON contains source paths, function line numbers, SHA-256 values, configurations, and validation-receipt locations.

## Evaluated datasets and populations

**BNCI2014_001 / BCI Competition IV dataset 2a.** Nine participants completed two sessions on different days, each containing six runs of 48 trials: 12 trials each of left-hand, right-hand, feet, and tongue imagery. Twenty-two EEG electrodes and three EOG channels were sampled at 250 Hz. The official acquisition used a left-mastoid reference, right-mastoid ground, 0.5–100 Hz bandpass, and enabled 50 Hz notch. These acquisition settings are distinct from this project's additional offline filters. Primary models used the 22 EEG electrodes only.

The archived project metadata contain **5,184 trials, 576 per participant, 1,296 per class**, including **488 expert artifact-flagged trials**. The latter number comes from the local complete metadata audit, not the dataset-description PDF. The official competition evaluated artifact-free trials; the project's include-all primary population is therefore a different estimand. Source-clean sensitivity conditions remove flagged source-training examples while preserving target trials.

中文：主分析保留全部试次，不能写成复现官方比赛的无伪迹评分。两个session是采集日；`0train`、`1test`名称不意味着研究只用第一天训练或只用第二天测试。

Evidence: [official Brunner2008 dataset description](https://www.bbci.de/competition/iv/desc_2a.pdf), [archived trial metadata](/workspace/cross-subject-mi-eeg/research_runs/Q8-E001/results/trial_metadata.csv), [channel/run audit](/workspace/cross-subject-mi-eeg/research_runs/Q8-E001/results/data_audit.csv), and [raw-file provenance](/workspace/cross-subject-mi-eeg/research_runs/Q8-E001/results/source_files.json).

**PhysioNet EEG Motor Movement/Imagery Database v1.0.0.** The completed binary transfer evaluation used all 109 subjects and only imagery runs 4, 8, and 12. `T1` denotes left-fist imagery and `T2` right-fist imagery; rest, executed-movement runs, and bilateral tasks were excluded. The amended complete inventory contains 327 checksum-verified EDFs and **4,918 unique trials**. Seven prediction rows per trial arise from two neural models × three seeds plus one CSP+LDA model; 34,426 rows are not 34,426 independent observations. No target fitting occurred.

中文：这是已完成的独立二分类外部任务；不能把它的平衡准确率直接与四分类BNCI数值混成同一任务平均。Q14-R2对采样率异常的元数据修订及后续验证移植必须保留。

Evidence: [official dataset](https://physionet.org/content/eegmmidb/1.0.0/), [source freeze](/workspace/cross-subject-mi-eeg/results/Q14-E002/freeze_receipt.json), [complete inference receipt](/workspace/cross-subject-mi-eeg/results/Q14-E002R2/external/completion_receipt.json), [independent V1 validation](/workspace/cross-subject-mi-eeg/results/Q14-E002R2V1/validation_report.json). V1 reports `passed=true`; it records a different validation host/runtime from the historical inference runtime.

**Munich High-Gamma / Schirrmeister2017 is not an evaluated cohort in this repository.** No executed configuration or result artifact was found. Its original task contains executed hand/feet movements and rest, rather than the left/right/feet/tongue imagery task. Schirrmeister2017 may be cited for CNN context; it must not appear in the paper's experimental dataset or result tables.

## Preprocessing, partitions, and duration selection

For four-class BNCI analyses, fixed fourth-order Butterworth IIR filters were applied in zero-phase mode separately to each native recording run before epoch extraction. Trials cover **[2.5,5.5) s after MAT trial start**, equivalent to **[0.5,3.5) s after cue onset**. The right endpoint is excluded by setting MNE `tmax=5.5−1/250`, yielding **750 samples**. There is no baseline subtraction, additional notch, or additional re-reference in the primary neural pipeline. MNE-loaded volt values are multiplied by 10^6 for microvolt network inputs. Zero-phase filtering is offline and noncausal.

Q5/Q8 use 4–40 Hz broadband input. Q9's restricted broad condition uses 8–30 Hz; its two fixed views use μ=8–13 Hz and β=13–30 Hz. These bands are fixed experimental choices, not estimates of each person's physiological optimum. Learned projections and normalization use only the corresponding source-training partition.

All primary four-class LOSO folds hold out both sessions of one participant: **eight source subjects / 4,608 trials**, versus **one target subject / 576 trials**. Sort the eight source IDs and split them into four consecutive two-person validation groups. Each inner fit uses **six source-training subjects / 3,456 trials**, with **two source-validation subjects / 1,152 trials**. This is nested subject-level validation, not random trial-wise cross-validation.

Q5 selects the earliest epoch minimizing the equal-inner-fold mean raw validation cross-entropy. Q8 selects the earliest minimum of the equal-fold mean **within-fold validation-CE rank**, with average ranks for ties, over epochs 1–40. Q8 reuses the original 36 Q5 inner trajectories and trains 27 new final models. Main representation-specific Q9/Q10/Q11/Q12 conditions recompute their source-only inner trajectories. Final fits use three fixed seeds: 20260924, 20260925, and 20260926. Seed results are averaged within subject before equal-subject aggregation. No target normalization, covariance fitting, early stopping, seed choice, or hyperparameter selection occurs.

中文：source-only是每个拟合/选epoch环节不使用目标被试；它不能消除整个研究路线已看过BNCI目标结果的探索性。不能把同一被试的三个seed或多个source子集当成独立样本。

Code: [BNCI loader](/workspace/cross-subject-mi-eeg/src/mi_eeg/data/bnci_epochs.py:21), [Q5 inner/final splits and CE selection](/workspace/cross-subject-mi-eeg/scripts/run_eegnet.py:263), [Q8 selection freeze](/workspace/cross-subject-mi-eeg/research_runs/Q8-E001/code/freeze_q8_selection.py:32), [Q9 rank selection](/workspace/cross-subject-mi-eeg/scripts/q9_neural.py:231), [Q9 source partitions](/workspace/cross-subject-mi-eeg/scripts/q9_neural.py:296).

## EEGNet and shared μ/β mechanism

The project uses Braindecode 1.5.1 EEGNet: **F1=8, D=2, F2=16, temporal kernel=64 samples, dropout=0.25**, with 22 channels, 750 time samples, and four output classes in the primary BNCI model. This configuration has **2,932 trainable parameters**. The implementation contains temporal convolution; depthwise spatial convolution spanning the channel dimension; BatchNorm/ELU/average pooling/dropout; depthwise temporal and pointwise separable convolutions; and an auto-length convolution classifier. Defaults retained by this project include 16-sample separable temporal kernels, pooling widths 4 and 8, spatial max-norm 1, and BatchNorm momentum .01 / epsilon .001. The 64-sample temporal kernel spans 256 ms at 250 Hz and 400 ms at the binary model's 160 Hz common rate.

Training uses Adam, learning rate .001, batch size 64, weight decay 0, cross-entropy, no scheduler, and no default augmentation. Evaluation uses `model.eval()` and inference mode, so target examples do not update BatchNorm statistics. This is a configured EEGNet study, not an exact replication of Lawhern2018's preprocessing or splits.

Recommended English description:

> We applied fixed mu (8–13 Hz) and beta (13–30 Hz) filters and passed both views through the same EEGNet. The two class-logit vectors were averaged before cross-entropy during training and before softmax at inference. Both bands therefore used the same network parameters, without learned band-specific fusion weights.

Implementation detail: band views are reshaped into a single `2 × batch` mini-batch. **BatchNorm is also shared across the two band views**, and dropout acts per view during training. This matters when interpreting the intervention. The model has the same trainable parameter count as one branch, while processing two inputs; it is not two independent networks, learned attention, or mean-probability ensembling.

中文：固定频段提供两个输入视图，共用参数并等权平均logits。这是一种结构约束/归纳偏置；不能仅凭架构写成生理特征解耦、节律源定位、因果机制或普遍有效的域不变特征。频段分解、共享BatchNorm以及前向计算量共同改变了流水线。

Code: [EEGNet builder](/workspace/cross-subject-mi-eeg/src/mi_eeg/models/eegnet_training.py:23), [training/evaluation helpers](/workspace/cross-subject-mi-eeg/src/mi_eeg/models/eegnet_training.py:37), [shared-band forward](/workspace/cross-subject-mi-eeg/scripts/q9_neural.py:186), [binary shared-band implementation](/workspace/cross-subject-mi-eeg/scripts/q14_source.py:194). The companion JSON also records the installed EEGNet source path and defaults.

## Completed controls that should retain their exact labels

| Experiment | Implemented contrast | Interpretation limit |
|---|---|---|
| Q4 | Broadband CSP8 and nine fixed 4-Hz bands from 4–40 Hz; MNE multiclass CSP with OAS, log power, scaler, shrinkage LDA / linear SVM / source-fitted MI8 | FBCSP-inspired approximation, not literal Ang2012 replication |
| Q9-A001 | Fixed 44-feature μ/β Welch PSD: Hamming250, overlap125, nfft250, density/mean windows, log10 integrated band power; source-only scaler plus LDA/SVM | Spectral feature control, not Fourier artifact removal |
| Q9-E002 | MID8–30 and shared μ/β retrained at frozen Q8 per-target epoch numbers | Fixed-duration representation sensitivity; no representation-specific inner reselection |
| Q6 / Q9-E005 | Source-fitted per-channel z-score; separately per band in Q9-E005 | Source-only moments; no target adaptation |
| Q9-E004 | Exclude artifact-flagged source-training trials | Every target trial stays in the primary denominator |
| Q10-E001 | Eight CSP or PCA projections per band; 16 stacked channels, source-only projected-channel standardization | CSP/PCA width match each other; they do not match the 22-channel shared-logit model |
| Q10-A001 | Per-trial shrinkage covariance and fixed matrix-log features; source-only shallow classifiers | Log-Euclidean features, not target-pooled Euclidean alignment or affine-invariant tangent adaptation |
| Q11 | Four-band shared, two independent branches, 44-channel early stacking, and broadband capacity comparator | Independent2=5,864 parameters; comparator F1=15/F2=30 has 5,914, a 0.853% mismatch |
| Q12-E001 | Equal-source-subject pooled whitening with 5% mean-eigenvalue ridge; matched balanced ERM versus GroupDRO | Source whitening is not target EA; GroupDRO vs pooled ERM also changes batching |
| Q12-E002 | Training-only channel dropout p=.1, gain U[.8,1.2], and gain then dropout | Validation/target inputs are not augmented |
| Q13-E001 | Raw CE versus rank versus fixed20 duration | Historical Q5 runtime differs; matched-runtime duration comparator is Q13-E006 |
| Q13-E004 | Fixed20; k=2/4/6 source circular windows, four source-identity subsets; k=8 anchor | Source count also changes examples and optimizer updates; not isolated causal subject-count effect |
| Q13-E005 | One source session versus the other, with all eight source subjects; 2,304 training trials | Both target sessions evaluated; one versus both source sessions also changes training budget |
| Q13-E006 | Twenty-seven matched-runtime finals using historical Q5 source-selected epoch schedule | No new inner selection; does not establish which epochs a newer-runtime reselection would choose |

## Completed binary transfer protocol

Q14 builds **separate binary models**, using BNCI left/right trials only: **2,592 total source trials, 288 per person**. Native 250 Hz run filtering and 750-sample epochs precede deterministic polyphase resampling 16/25 to 160 Hz / **480 samples**. Both neural conditions use the same 22×480 binary architecture, with 8–30 Hz broad input or shared μ/β views. The all-nine-source duration groups are `[1,2]`, `[3,4]`, `[5,6]`, `[7,8,9]`, so inner-training complements contain 7/7/7/6 people. Equal-fold weighting is retained despite differing validation-group sizes. The frozen selected durations are broad=18 and shared=17 epochs. Two conditions require 14 source deep fits total (4 inner +3 final per condition); CSP adds one source fit.

The external adapter selects the same 22 electrode names in the same order and uses the same cue-relative [0.5,3.5) window. One hundred six subjects are native 160 Hz. S88/S92/S100 are native 128 Hz; the metadata-driven R2 amendment filters/epochs natively to 384 samples, then resamples 5/4 to 480. It does not choose a preprocessing branch by accuracy. No extra reference, learned denoising, artifact rejection, or target normalization is introduced.

Q14 `CSP4_LDA` uses CSP4 with `reg=None`, log power, `cov_est=concat`, no trace normalization, full rank, mutual-info component order; source-only StandardScaler and **LDA solver=svd**. Do not copy Q4's OAS/shrinkage-LDA settings into this comparator's description. Acquisition reference and hardware differ between cohorts; transfer is not a controlled test of one acquisition mechanism.

Code: [binary source loading/resampling](/workspace/cross-subject-mi-eeg/scripts/q14_source.py:109), [source groups/rank rule](/workspace/cross-subject-mi-eeg/scripts/q14_source.py:163), [binary CSP pipeline](/workspace/cross-subject-mi-eeg/scripts/q14_source.py:312), [external cue epochs](/workspace/cross-subject-mi-eeg/scripts/q14_external.py:136), [128-Hz amendment](/workspace/cross-subject-mi-eeg/scripts/q14_r2_external.py:110).

## Verified original references

1. Brunner, C., Leeb, R., Müller-Putz, G. R., Schlögl, A., and Pfurtscheller, G. (2008). *BCI Competition 2008 – Graz data set A*. Official dataset description. [Original PDF](https://www.bbci.de/competition/iv/desc_2a.pdf). **No DOI is asserted.**
2. Tangermann, M., et al. (2012). *Review of the BCI Competition IV*. Frontiers in Neuroscience. [DOI: 10.3389/fnins.2012.00055](https://doi.org/10.3389/fnins.2012.00055).
3. Lawhern, V. J., Solon, A. J., Waytowich, N. R., Gordon, S. M., Hung, C. P., and Lance, B. J. (2018). *EEGNet: a compact convolutional neural network for EEG-based brain–computer interfaces*. Journal of Neural Engineering 15(5), 056013. [DOI: 10.1088/1741-2552/aace8c](https://doi.org/10.1088/1741-2552/aace8c).
4. Ramoser, H., Müller-Gerking, J., and Pfurtscheller, G. (2000). *Optimal spatial filtering of single trial EEG during imagined hand movement*. IEEE Transactions on Rehabilitation Engineering 8(4), 441–446. [DOI: 10.1109/86.895946](https://doi.org/10.1109/86.895946).
5. Ang, K. K., Chin, Z. Y., Zhang, H., and Guan, C. (2008). *Filter Bank Common Spatial Pattern (FBCSP) in Brain-Computer Interface*. IJCNN, 2390–2397. [DOI: 10.1109/IJCNN.2008.4634130](https://doi.org/10.1109/IJCNN.2008.4634130).
6. Ang, K. K., Chin, Z. Y., Wang, C., Guan, C., and Zhang, H. (2012). *Filter Bank Common Spatial Pattern Algorithm on BCI Competition IV Datasets 2a and 2b*. Frontiers in Neuroscience 6. [DOI: 10.3389/fnins.2012.00039](https://doi.org/10.3389/fnins.2012.00039).
7. Schalk, G. (2009). *EEG Motor Movement/Imagery Dataset*, version 1.0.0. PhysioNet. [DOI: 10.13026/C28G6P](https://doi.org/10.13026/C28G6P). This dataset citation is requested by the official resource page.
8. Schalk, G., McFarland, D. J., Hinterberger, T., Birbaumer, N., and Wolpaw, J. R. (2004). *BCI2000: A General-Purpose Brain-Computer Interface (BCI) System*. IEEE Transactions on Biomedical Engineering 51(6), 1034–1043. [DOI: 10.1109/TBME.2004.827072](https://doi.org/10.1109/TBME.2004.827072). Original publication requested by the PhysioNet resource page.
9. Schirrmeister, R. T., et al. (2017). *Deep learning with convolutional neural networks for EEG decoding and visualization*. Human Brain Mapping 38(11), 5391–5420. [DOI: 10.1002/hbm.23730](https://doi.org/10.1002/hbm.23730). CNN background only; not a project evaluated-cohort citation.
10. Goldberger, A. L., et al. (2000). *PhysioBank, PhysioToolkit, and PhysioNet: Components of a New Research Resource for Complex Physiologic Signals*. Circulation 101(23). [DOI: 10.1161/01.CIR.101.23.e215](https://doi.org/10.1161/01.CIR.101.23.e215). Optional original-platform background; do not call it the current resource page's requested standard platform citation.
11. Sagawa, S., Koh, P. W., Hashimoto, T. B., and Liang, P. (2020). *Distributionally Robust Neural Networks for Group Shifts: On the Importance of Regularization for Worst-Case Generalization*. ICLR. [OpenReview](https://openreview.net/forum?id=ryxGuJrFvS), [official ICLR page](https://iclr.cc/virtual_2020/poster_ryxGuJrFvS.html), [original preprint](https://arxiv.org/abs/1911.08731). No conference DOI is asserted; **10.48550/arXiv.1911.08731** is specifically the arXiv-issued preprint DOI. OpenReview returned HTTP403 during verification; official ICLR and arXiv confirm the metadata.

DOIs and publication metadata were independently checked through Crossref and, where applicable, official dataset pages and PMC. Full verified author lists and verification URLs are in the companion JSON. He/Wu target Euclidean alignment is excluded from the implemented-method references because that target-adaptation algorithm was not performed.
