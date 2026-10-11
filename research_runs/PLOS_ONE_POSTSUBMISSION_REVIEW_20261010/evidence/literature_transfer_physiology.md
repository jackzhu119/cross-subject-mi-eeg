# Transfer-learning and physiology literature verification

Verified read-only on 2026-10-10T12:50:25.310196+00:00. No fits, inference or experiment changes.

## Zhang2021AdaptiveTransfer

**Adaptive transfer learning for EEG motor imagery classification with deep Convolutional Neural Network** (2021).
Kaishuo Zhang, Neethu Robinson, Seong-Whan Lee, Cuntai Guan.
Neural Networks, 136: 1-10. DOI: 10.1016/j.neunet.2020.12.013.
Canonical source: https://doi.org/10.1016/j.neunet.2020.12.013

Identity: Likely candidate because first author and title theme match; user shorthand is not the exact formal title. No alternate Zhang paper should be silently substituted.
Full text verified: False; metadata verified: True.

Protocol distinctions:
- The indexed authors' abstract states five schemes for adaptation of a deep CNN EEG-BCI system for hand MI.
- Each scheme fine-tunes an extensively trained, pre-trained model and adapts it for a target subject.

Safe manuscript use: Adaptive transfer-learning work has studied target-subject fine-tuning of pretrained CNNs; this differs from evaluating an already frozen source-only pipeline with no target fitting. This statement relies on the verified original abstract and does not specify unverified calibration amounts.

Recommendation: Candidate citation may support only the abstract-level target-adaptation distinction. Do not call full protocol audited; exact requested-paper identity should be confirmed against supplied review when available.

Inspectible short excerpts:
- Europe PMC indexed original abstract, PMID33401114: “Each scheme fine-tunes an extensively trained, pre-trained model and adapt it to enhance the evaluation performance on a target subject.”

Access limits:
- Elsevier publisher and text-mining routes returned network403.
- DR-NTU handle10356/160766 returned HTTP405.
- OpenAlex/SemanticScholar secondary records used only to locate potential fulltext, not to establish protocol.

Do not assert:
- Exact train/test/calibration split and target-label counts
- Which source-target datasets and settings correspond to reported84.19%
- No-target-fitting arm details versus adapted arms

Evidence hashes:
- https://api.crossref.org/works/10.1016%2Fj.neunet.2020.12.013 — SHA256 `2dfcc187be5a7cfc06e664511d0cfd4c4d2ecfe48b8aff17ff693e97e0862f5d` (Formal bibliographic registry metadata).
- https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:10.1016/j.neunet.2020.12.013&resultType=core&format=json — SHA256 `b805b1d54e9c2533bc5ab8b52ec8d5effe7b9f46656c4934a2bb767437fac772` (Original abstract indexed by EuropePMC; fulltext explicitly subscription required).

## Sonntag2025Neurophysiological

**Neurophysiological predictors of deep learning based unilateral upper limb motor imagery classification** (2025).
Justin Sonntag, Lin Yu, Xilu Wang, Thomas Schack.
Frontiers in Human Neuroscience, 19: 1617748. DOI: 10.3389/fnhum.2025.1617748.
Canonical source: https://doi.org/10.3389/fnhum.2025.1617748

Identity: Exact formal paper found and authors/title/DOI verified against publisher and registry.
Full text verified: True; metadata verified: True.

Protocol distinctions:
- 26 right-handed participants; unilateral right elbow flexion/extension plus non-task state, a three-class paradigm.
- Models trained for each participant;80%training/20%validation and mean fivefold accuracy; three deep models EEGNet/FBCNet/NFEEG and CSP-based SVM/LDA.
- Prior eyes-open and eyes-closed180s resting recordings; absolute and relative alpha8–13Hz/beta13–30Hz power.
- Pearson associations between resting features and model accuracy, with explicitly exploratory treatment and no FDR correction.

Safe manuscript use: Sonntag et al. related resting-state alpha/beta features to participant-specific classification performance in a distinct unilateral elbow-imagery task. Our BNCI-only nine-person analysis instead describes baseline-relative sensor-level task power after decoder outcomes are fixed, without decoder feedback, confirmatory p-values or mechanistic attribution.

Recommendation: Suitable concise physiology-context citation; retain different paradigm/resting metric and exploratory boundaries.

Inspectible short excerpts:
- 2.1 Participants: “Twenty-six participants ... were recruited in the experiment.”
- 2.5 Data analysis: “Three different neural networks were chosen to be trained for each participant.”
- 2.5 Data analysis: “Each model was trained on 80% of the dataset and the other 20% were used for validation. The final reported accuracy of each model will be the average of a fivefold cross validation.”
- 2.5 Data analysis: “Given the exploratory nature of this study ... we chose not to apply False Discovery Rate (FDR) correction at this initial stage.”

Evidence hashes:
- https://api.crossref.org/works/10.3389%2Ffnhum.2025.1617748 — SHA256 `22834392bad2ba77ab3b768be0ae2302612e67a51199140ac527b9d67fa2fc82` (Registry metadata).
- https://www.frontiersin.org/journals/human-neuroscience/articles/10.3389/fnhum.2025.1617748/full — SHA256 `a2d34c3ffe1a051f197187cb40ee97ac82bea9f52acbf7da74b11b10409b7495` (Official version-of-record fulltext).
- https://www.frontiersin.org/journals/human-neuroscience/articles/10.3389/fnhum.2025.1617748/pdf — SHA256 `ef2e585cb8ba97b2f8d258fcdbf6e54eca4dfd84021b03a8ad659283021563b1` (Official version-of-record PDF).

## Wei2022BEETL

**2021 BEETL Competition: Advancing Transfer Learning for Subject Independence and Heterogenous EEG Data Sets** (2022).
Xiaoxi Wei, A. Aldo Faisal, Moritz Grosse-Wentrup, Alexandre Gramfort, Sylvain Chevallier, Vinay Jayaram, Camille Jeunet, Stylianos Bakas, Siegfried Ludwig, Konstantinos Barmpas, Mehdi Bahri, Yannis Panagakis, Nikolaos Laskaris, Dimitrios A. Adamos, Stefanos Zafeiriou, William C. Duong, Stephen M. Gordon, Vernon J. Lawhern, Maciej Śliwowski, Vincent Rouanne, Piotr Tempczyk.
Proceedings of Machine Learning Research, 176: 205–219. DOI: not displayed by formal publisher.
Canonical source: https://proceedings.mlr.press/v176/wei22a.html

Identity: Formal published competition paper, not a proposed challenge/preprint.
Full text verified: True; metadata verified: True.

Protocol distinctions:
- Task2three-wayMI(left-hand,right-hand,reject); labelled source data Cho2017,BNCI2014,PhysioNetMI.
- Target data Weibo2014/CybathlonIC, with some labelled data provided per test subject. Hence target calibration/adaptation permitted, not zero-calibration source-only.
- Leaderboardphase and finalrankingphase use different target-subject subsets.
- Reported winning schemes include training simultaneously on source and calibration data and domain/label adaptation.

Safe manuscript use: BEETL extended evaluation across subjects and heterogeneous MI datasets while providing labelled target-subject calibration examples. Its protocol therefore illustrates cross-dataset transfer under target adaptation and is not a matched source-only comparator for our frozen external evaluation.

Recommendation: Suitable benchmark/protocol-context citation; never present its calibration-assisted accuracy as directly comparable to our no-target-fit balanced accuracy or assert superiority.

Inspectible short excerpts:
- §2 competitiondesign, PDFpage3: “new users that need to be up and running with only minutes worth of calibration data”
- §3 Training, validation and test set, PDFpage5: “In both the Weibo2014 and CybathlonIC data sets, we provide some data with labels per test subject.”
- §4.1 First-place method, PDFpage6: “The models are trained on the source and calibration data simultaneously”

Evidence hashes:
- https://proceedings.mlr.press/v176/wei22a.html — SHA256 `3b5af81fc48e45bdfaeb03d9b36bb1e309a242dd74c4991a83f9c4031f48e00a` (Formal proceedings metadata and BibTeX).
- https://proceedings.mlr.press/v176/wei22a/wei22a.pdf — SHA256 `7e5c264358e4f8a9ea812bf1c6da926e048ca9466b58d01acac4ed12a80f72a1` (Formal proceedings PDF fulltext).

## Optional concise manuscript language

Transfer-learning studies often permit adaptation using target-subject data. Zhang et al. proposed target-subject fine-tuning of pretrained CNNs [candidate identity: Zhang2021AdaptiveTransfer], and the BEETL motor-imagery challenge supplied labelled calibration examples for its target participants [Wei2022BEETL]. These protocols differ from the present frozen source-only evaluation, which prohibits target fitting and target-driven model selection. The present contribution is an audit of source-only selection, participant-level heterogeneity and complete-pipeline transfer, rather than a new domain-generalization algorithm or a claim of superiority over adaptation methods.

Resting-state alpha/beta associations with participant-specific decoding have also been investigated in unilateral elbow imagery [Sonntag2025Neurophysiological]. Our BNCI-only nine-person characterization uses baseline-relative sensor-level task power after decoder outcomes are fixed; it is neither a prospective predictor nor evidence of a learned decoder mechanism.

Zhang identity remains conditional because the review attachment is unavailable. Use the exact verified bibliographic record only when this candidate is confirmed; no exact target split or calibration-count claim is supported by the accessible abstract. No DOI is invented for the PMLR article.
