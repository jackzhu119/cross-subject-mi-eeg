# Literature and novelty review: source-only selection reliability in MI EEG

**Review cutoff:** 12 October 2026 (Asia/Shanghai). **Status:** research-design review; independent new-cohort validation has not been completed. No EEG fitting or inference was performed for this document.

## Assessment

The strongest defensible direction is an empirical reliability study of source-only duration decisions under participant heterogeneity and acquisition-cohort shift. It is not a new mean-rank algorithm, a new spectral-sharing mechanism, or the first reproducibility benchmark. The revised study needs to show whether a pre-fixed decision made without target feedback succeeds, fails, or concentrates benefit in particular participants on genuinely unused target cohorts. Historical BNCI, PhysioNet, Cho2017 and Lee2019 results are development/retrospective evidence once their outcomes have been inspected. Re-splitting them does not restore a blind test.

The search does not establish that no previous study has evaluated this exact question. Several formal articles could not be read in full. Novelty should therefore be stated as the specific experiment and evidence delivered, not as a first-ever assertion.

## Search and verification

This focused update used new Crossref searches, Europe PMC original abstracts/full-text XML, publisher pages, author manuscripts and official author code. Formal version-of-record titles, authors, years and DOI records were checked when available. The existing 36-reference bibliography and three saved primary-protocol audits were reused with explicit provenance. It is not a PRISMA review or an exhaustive absence search. Broad early-stopping searches were noisy; one cross-dataset query failed with HTTP 429. Several publisher full texts were blocked. A 200 response containing HTML at an IOP PDF endpoint was classified as unsuccessful PDF retrieval. See `evidence/literature_redesign.json` for hashes, coverage and unresolved fields.

## Direct precedents and their implications

Cawley and Talbot (2010) already argued that finite-sample selection criteria can be overfit and that learning algorithm/model-selector combinations should be evaluated together. Gulrajani and Lopez-Paz (ICLR 2021) explicitly treated DG model selection as part of the learning problem and separated training-domain validation, leave-one-domain-out selection and target-domain oracle selection. These principles cannot be presented as inventions of the present project.

Borra, Paissan and Ravanelli (2024) introduced SpeechBrain-MOABB with whole-pipeline hyperparameter search and multi-seed evaluation. Borra, Magosso and Ravanelli's formal Neural Networks article (2025, online 2024) directly studies participant subsets for hyperparameter search, search strategy and seed variability. A claim that this project first audits EEG reproducibility, random initialization or validation-participant composition would conflict with these precedents. Their full formal articles were not retrieved here; original abstracts and official author code were inspected. That coverage does not prove the absence of an external stopping-rule study in their full text.

Eder, Xu and Grosse-Wentrup (JNE 2024) compare established Riemannian methods and CNNs across within-session, cross-session and cross-subject MOABB settings. Merely adding a Riemannian baseline or comparing more model scores is insufficient novelty. Barachant et al. (2012) provide the original covariance-geometry methods: the source-only implementation must fit class/reference statistics on source data. Label-free Euclidean or Riemannian target alignment is an adaptation condition when target statistics update the transformation; it does not satisfy the stricter primary information contract just because target labels are absent.

Recent formal DG papers establish an active algorithmic field. Zheng et al. (2025) use source spectral distillation, source-source alignment, validation-loss early stopping and two-stage training. Their within-dataset LOSO experiments are distinct from transporting one unchanged, pre-frozen source model into an unused acquisition cohort. Zhong et al. (2025) and Zhi et al. (2025) present source DG methods; their exact selection/normalization budgets remain unresolved because full texts were unavailable. These papers should not be accused of leakage, and unknown details should not be assumed identical to the proposed strict protocol.

Miao et al. (2026) explicitly describe pretraining followed by meta-learning with all subjects in the target dataset except the unseen test subject. This is zero calibration for that individual, with target-cohort training permitted; it differs from the proposed source-only no-target-cohort-update evaluation. RMETNet likewise uses target alignment/MMD in the inspected publisher full text. Consequently, headline calibration-free labels or absolute accuracies cannot establish comparable data permissions.

## Focused protocol difference matrix

“Independent external” below means a frozen source-trained decision tested on a genuinely unused acquisition cohort; within-dataset held-out-subject performance is a different valuable evaluation. “Unknown” records a verification boundary, not an allegation. Raw EEG licence permission is audited separately; an open-access article licence does not authorize every underlying dataset.

| Study | Data/task and models | Target labels / unlabelled target statistics | Selection and stopping budget | External boundary and scientific question | Difference relevant to this redesign | Coverage |
|---|---|---|---|---|---|---|
| Cawley & Talbot 2010 | Non-EEG ML; selector/classifier combinations | Not a target EEG protocol | Finite-sample selection variance; nested evaluation | Selection bias, not first-use MI external validation | Foundational precedent; no new principle claim | Official full text |
| Gulrajani & Lopez-Paz 2021 | DomainBed vision; ERM/DG | Source vs target-oracle access explicit | Source-domain and leave-domain-out criteria; oracle 20-query limit | Held-out domains; importance of selector contract | No first source-only selection claim | Formal conference identity + author full text |
| Varoquaux 2017 | MRI/MEG/simulations; brain decoders | Nested tuning/evaluation | CV uncertainty and sane defaults | Reliability of decoder assessment | Supports uncertainty, not new MI result | Formal identity + author full text |
| Schirrmeister 2017 | IV2a MI / High-Gamma ME; CNN/FBCSP | Subject-specific supervision | Validation-based early stopping; SI details not all recovered | Subject-specific EEG decoding | Early stopping is established; not matched strict transfer | Original full article XML |
| Barachant 2012 | IV2a four-class; MDM/TSLDA/CSP | Labelled subject calibration | Subject-specific 30-fold CV | Covariance geometry baseline | New source-only baseline needs source-only centres | Author full text + formal DOI |
| He & Wu 2020 | MI/ERP alignment | No new-subject labels; target-statistics details require full text | Exact budget unknown | Transfer through alignment | No-label ≠ no target transformation update | Formal identity + original abstract |
| Jayaram 2018 | Public BCI datasets; MOABB | Protocol-specific, not automatically target-free | Standardized evaluation/meta-analysis | Reproducible cross-dataset benchmarking | Not a new benchmarking infrastructure contribution | Existing formal identity; full text not reread |
| Eder 2024 | MOABB MI/P300/SSVEP; CNN/Riemannian | Full tuning/statistics permissions unknown | Exact selection budget unknown | Within/cross-session and cross-subject benchmark | Model-score comparisons alone are not novelty | Formal identity + original abstract |
| Borra 2024 | Nine MOABB datasets; neural toolkit | Protocol-specific; cohort-first-use unknown | Whole-pipeline HPO and multi-seed | Robust benchmark toolkit | Not first reliable complete neural pipeline | Original abstract + author code |
| Borra 2025 | Nine datasets / 204 people; deep models | Complete target-permission path unknown without full text | HPO participant subsets, multi-step/search algorithms, 10 final seeds | Protocol reliability and compute trade-off | Strong prior for subject/seed sensitivity; need distinct locked-cohort duration question | Original abstract + author code; formal 2025 issue |
| Zhong 2025 | IV2a/2b/OpenBMI; EEG-DG | Abstract: unseen target excluded from training; details unknown | Checkpoint and tuning budget unknown | Source invariance algorithm; cohort-independent status unverified | Fixed existing decoders, selector reliability rather than new DG algorithm | Fresh formal metadata + primary abstract |
| Zheng 2025 | IV2a four-class / OpenBMI hands; spectral distillation/CORAL | Method: no target training/validation; source-source alignment | 80/20 source split; fivefold stage 1; 1000/400 maxima; grouping sensitivity | Two within-dataset LOSO tests | Not unchanged source-to-new-cohort transfer; spectral/duration controls remain necessary | Publisher/PMC full text |
| Zhi 2025 | Six MI/ME datasets; contrastive DG | Abstract: unavailable target; full permissions unknown | Exact stopping and meta-selection unknown | Algorithmic DG | MI/ME task differences must be respected | Formal metadata + primary abstract |
| Miao 2026 | ME/MI pretrain; CBCIC/own cohort/IV2b; meta-learning | Target-cohort labels used except unseen individual | Meta fine-tuning; exact stopping unknown | Adaptation to target cohort, then held-out person | Subject zero calibration ≠ no target-cohort update | Formal metadata + primary abstract |
| Cao 2025 | IV2a/2b; temporal multibranch/attention/TCN | LOSO test person excluded; source Z-score described | Full nested early-stopping budget not reconstructed | Within-dataset architecture comparison | Temporal kernels are not fixed μ/β sharing | Saved publisher full-text audit |
| Zhao 2026 | Cross-subject MI; temporal/Riemannian model | Target MMD + Riemannian/session alignment | Adaptation, not strict source-only contract | Architecture + target alignment | Keep optional adaptation arm separate | Saved publisher full-text audit |
| Smedemark-Margulies 2024 | RSVP, 64 people; divergence network | Subject splits; best-λ mean-test comparison in postprint | 100 main epochs; ≤30 appendix | Subject transfer in a different EEG task | Not MI; meta-selection boundary differs | Saved formal identity + author postprint |
| Wei 2022 | Cross-dataset EEG transfer competition | Task 2 labelled target calibration | Competition-specific | Transfer learning with supplied calibration | No first cross-dataset claim; permissions differ | Saved formal PMLR full text |
| Roots 2020 | Pooled MI windows; fusion CNN | Random windows, not participant-disjoint guarantee | 70/10/20 window split | Pooled classification | Not matched cross-subject outcome | Saved publisher full-text audit |
| Luo 2023 | IV2a/High-Gamma/OpenBMI; overlap banks/CNNs | Same-participant/session setting | Separate band networks | Multisubject multiclass performance | Band decomposition ≠ shared parameters; MI ≠ ME | Saved publisher full-text audit |
| Zhang 2021 | MI; pretrained CNN | Target-subject fine-tuning | Calibration amount unknown | Adaptive transfer | Not strict source-only comparator | Saved formal identity + primary abstract |
| Sonntag 2025 | 26-person unilateral elbow MI; power/correlation | Within-person supervised training | Fivefold 80/20; exploratory correlations | Physiology-performance association | Q16 auxiliary, not external mechanism validation | Saved primary full-text audit |
| Chen 2026 | Recent MI-DGHCL DG formal article | Unknown | Unknown | No detailed protocol claim | Recent screened work; no title-based superiority claim | Formal metadata only |
| Zhao 2026 | IV2a/2b MI / High-Gamma ME, abstract | Complete permissions unknown | Unknown | Two-stage distillation DG | MI/ME separated; exact target-first-use unknown | Formal metadata + abstract only |

## What could constitute a stronger, falsifiable contribution?

1. **A locked selector transport test.** Compare fixed-duration, mean-loss and mean-rank source-only choices on a documented first-use hand-MI cohort under one frozen source set, processing contract, checkpoint candidate set and seed policy. Report participant-level differences and uncertainty, including failure to reproduce historical gains. This is not yet completed.
2. **A clear separation of decision and architecture contrasts.** A pre-specified architecture × duration-rule design can distinguish schedule-associated complete-pipeline differences from matched-duration broad/shared contrasts. Matched epoch count still leaves two-view compute, filtering, shared BatchNorm exposure and model structure; it does not identify the isolated causal effect of parameter sharing.
3. **Reliability beyond a cohort mean.** Quantify predeclared participant gains/losses, benefit concentration, lower-tail behavior, prediction-class concentration, group/seed stability and compute. Retrospective analyses can describe these risks; only a locked new test can establish reproducibility of an effect. Seeds are repeated training realizations, not additional independent people.
4. **An auditable failure taxonomy.** Distinguish implementation/data-mapping uncertainty, source-trained model behavior and distribution-dependent degradation. Archive CSP left-prediction diagnostics do not prove that device shift caused failure or that all bugs have been excluded. A lightweight source-only Riemannian baseline can help characterize model-family sensitivity without being claimed as a new method.

The primary scientific question should remain duration-selection reliability. A large DG algorithm leaderboard, target-calibrated alignment or new Q16 physiology experiments would dilute that question and inflate comparisons. Q16 should be moved chiefly to supporting material with its historical BNCI-only, sensor-level, post-outcome and descriptive limitations unchanged.

## Claims to prohibit and evidence that could change the assessment

| Proposed claim | Current verdict | Required boundary |
|---|---|---|
| First source-only model selection or first complete-pipeline evaluation | Not defensible | Cawley & Talbot and DomainBed explicitly establish selection/evaluation and algorithm-selector combinations. |
| First reliable EEG HPO/multi-seed/participant-subset audit | Not defensible | Borra 2024 and formal 2025 protocol directly address these topics. |
| First cross-dataset MI generalization | Not defensible | Formal transfer competition and adaptation/meta-learning literature already exists; information permissions differ. |
| Matched epochs isolate causal benefit of parameter sharing | Not defensible without additional single-factor/capacity/compute controls | Views, filtering, BN exposure and architecture/compute still differ. |
| New locked first-use cohort gives confirmatory evidence | Conditional, not achieved | Requires documented dataset-first-use audit, frozen source-only selectors, QC and inference contract, completed locked test and independent numerical validation. |
| Negative mean plus concentrated person-level gains/failed selectors is useful methodological evidence | Potentially defensible if prespecified and independently replicated | Requires effect/uncertainty, tail outcomes, multiplicity and cohort/domain boundaries; archive evidence alone remains retrospective. |

A suitable new public cohort is not automatically independent. Verify this research team's prior accesses, participant/file overlap, labels, first performance exposure and selection history. Prospective locking of analysis on an old public dataset is not prospective data collection. If no eligible untouched cohort can be acquired, label the extension retrospective and do not use “independent validation” as an achieved-result title.

## Journal fit: preliminary, not a ranking or submission decision

| Venue | Current verification | Practical assessment |
|---|---|---|
| Journal of Neural Engineering | Official scope page checked on 12 October 2026: BCI and neural signal processing in scope | Scope fits, but a convincing new empirical methodological contribution and independent cohort validation are needed. This review cannot predict reversal of the prior desk decision. |
| Journal of Neuroscience Methods | Official current aims/scope retrieval blocked; a directly relevant 2026 formal methods paper was verified | Plausible methods audience if the redesign yields a concrete validated protocol insight; verify current scope/instructions before selecting. |
| Biomedical Signal Processing and Control | Current official aims/scope retrieval blocked | Provisional applied-signal-processing alternative; no impact-factor or acceptance claim. |
| Brain-Computer Interfaces | Current official about page blocked | Provisional specialist BCI audience; current instructions and scope require verification. |
| PLOS ONE | Official page checked: methodologically sound replication and negative/null work in scope | Scientific scope does not resolve eligibility after the author-reported duplicate-submission decision. No permission to resubmit has been established, and no inquiry was sent. |

The JNE desk decision about editorial research standards and the PLOS ONE duplicate-submission decision, as reported by the author, are different decisions. They are not two independent adverse scientific peer reviews. Do not infer journal ranking from a current scope page, a prior rejection or an unverified impact factor. Submit to one journal at a time only after a completed scientific evidence gate.

At present, a higher-tier claim is premature: the deliverable is a research working draft and design, not an independently confirmed new effect. Specialist methodological review becomes more plausible if the new cohort, controlled schedule comparisons, person-level endpoints and negative/null retention pass independent validation. Merely extending the narrative or adding baselines is unlikely to overcome a limited evidence contribution.

## Bibliography identities and recommended use

Keep a small set of directly relevant references in the main narrative. Cawley–Talbot, DomainBed, Borra's formal 2025 protocol and Eder's 2024 benchmark are essential to avoid overstating novelty. Zheng/Zhong give MI DG context; Barachant justifies the independent-family baseline. Miao clarifies the distinction between unseen-person calibration and target-cohort adaptation. Other audited architecture/physiology articles can remain in supporting context. No pairwise numerical ranking is justified across these task/access/selection protocols.

The new metadata below supplements the existing 36 verified bibliography records; it does not silently renumber or modify historical references. Full-text limitations above apply to protocol claims even when DOI identity is verified.

- Gavin C. Cawley; Nicola L. C. Talbot. 2010. On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation. Journal of Machine Learning Research, 11: 2079–2107. https://www.jmlr.org/papers/v11/cawley10a.html
- Gaël Varoquaux; Pradeep Reddy Raamana; Denis A. Engemann; Andrés Hoyos-Idrobo; Yannick Schwartz; Bertrand Thirion. 2017. Assessing and tuning brain decoders: Cross-validation, caveats, and guidelines. NeuroImage, 145: 166-179. https://doi.org/10.1016/j.neuroimage.2016.10.038
- A. Barachant; S. Bonnet; M. Congedo; C. Jutten. 2012. Multiclass Brain–Computer Interface Classification by Riemannian Geometry. IEEE Transactions on Biomedical Engineering, 59(4): 920-928. https://doi.org/10.1109/tbme.2011.2172210
- He He; Dongrui Wu. 2020. Transfer Learning for Brain–Computer Interfaces: A Euclidean Space Data Alignment Approach. IEEE Transactions on Biomedical Engineering, 67(2): 399-410. https://doi.org/10.1109/tbme.2019.2913914
- Manuel Eder; Jiachen Xu; Moritz Grosse-Wentrup. 2024. Benchmarking brain–computer interface algorithms: Riemannian approaches vs convolutional neural networks. Journal of Neural Engineering, 21(4): 044002. https://doi.org/10.1088/1741-2552/ad6793
- Davide Borra; Francesco Paissan; Mirco Ravanelli. 2024. SpeechBrain-MOABB: An open-source Python library for benchmarking deep neural networks applied to EEG signals. Computers in Biology and Medicine, 182: 109097. https://doi.org/10.1016/j.compbiomed.2024.109097
- Davide Borra; Elisa Magosso; Mirco Ravanelli. 2025. A protocol for trustworthy EEG decoding with neural networks. Neural Networks, 182: 106847. https://doi.org/10.1016/j.neunet.2024.106847
- Minmin Miao; Wenliang Fu; Hong Zeng; Baoguo Xu; Wenbin Zhang; Wenjun Hu. 2026. Meta-Learning Enhanced Multi-Source Domain Adaptation for zero-calibration motor imagery EEG decoding. Journal of Neuroscience Methods, 431: 110742. https://doi.org/10.1016/j.jneumeth.2026.110742
- Junfu Chen; Dechang Pi; Feng Gao; Cheng Ma; Yang Chen. 2026. MI-DGHCL: Motor imagery EEG domain generalization via hyperbolic contrastive learning. Expert Systems with Applications, 312: 131477. https://doi.org/10.1016/j.eswa.2026.131477
- Hongyi Zhi; Tianyou Yu; Zhenghui Gu; Zhuobin Lin; Le Che; Yuanqing Li; Zhuliang Yu. 2025. Supervised Contrastive Learning-Based Domain Generalization Network for Cross-Subject Motor Decoding. IEEE Transactions on Biomedical Engineering, 72(1): 401-412. https://doi.org/10.1109/tbme.2024.3432934
- Yuhang Zhao; Wanfeng Xu; Xiaoqi Luo; Yunyuan Gao. 2026. Tsmd-net: two-stage multi-domain distillation network for cross-subject MI-EEG domain generalization. Cognitive Neurodynamics, 20(1): 192. https://doi.org/10.1007/s11571-026-10564-7

**Year notes:** Borra's trustworthy-protocol article is formal issue year 2025 (online 2024); He–Wu alignment is formal issue year 2020 (DOI/online 2019). DOI strings do not determine citation year. TSMD-Net is online 30 September 2026, formal Cognitive Neurodynamics 20, article 192; the case of the deposited title is retained.

## Completion and unresolved scope

This review documents new real literature retrieval, metadata checks, full-text/abstract boundaries and an explicit novelty critique. It has not established a new model advantage, a clinical endpoint, a neurophysiological mechanism or independent experimental confirmation. Missing full protocols for several new papers prevent categorical assertions that no prior work has tested a similar selector design. Those limits should remain visible through final submission readiness review.

## Execution-date extension: 13 October 2026

Two bounded Crossref date-filtered metadata queries extended the12October focused review through13October (`evidence/literature_date_extension_20261013.json`). Their14 and129 total matches were broad keyword matches; all14 and the top20 returned titles, respectively, were screened. The returned set did not supply another directly relevant formal source-only MI duration-selection study, so no manuscript citation was added on that basis. The second query was capped at20 rows and many results were unrelated. This is not an exhaustive same-day literature search, proof that no additional study exists, or authentication of future issue/index dates. The existing contribution boundaries and fulltext-access limitations remain unchanged.
