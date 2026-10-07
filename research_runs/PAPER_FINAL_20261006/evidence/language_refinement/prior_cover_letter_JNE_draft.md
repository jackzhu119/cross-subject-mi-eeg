# Cover letter — prepared for submission, unsent

7 October 2026

Editorial Office

Journal of Neural Engineering

Dear Editors,

Please consider my manuscript, "Source-only model selection and limits of fixed spectral-sharing pipelines in cross-subject motor-imagery EEG decoding," for publication as an original research paper.

The study examines source-only model selection and fixed spectral sharing in cross-subject motor-imagery EEG. It combines a documented BNCI development programme with separately frozen binary evaluations on PhysioNet, Cho2017 and Lee2019_MI. Zero calibration is defined as absence of target-dependent parameter fitting or target-based model selection. Target labels used for metadata and scoring are distinguished from learning; participant-level uncertainty is retained throughout.

The completed Q15 evaluation covers 52 Cho2017 and 54 Lee2019_MI participants under a prespecified common 21-channel adapter. The shared-input pipeline had 1.513 percentage points lower balanced accuracy on Cho2017 (95% paired-person bootstrap interval −2.249 to −0.804), while the Lee2019_MI difference was small and uncertain (+0.204 points, interval −0.515 to +0.969). The adverse result is reported directly. Comparisons reflect complete frozen pipelines, including their selected training durations.

The revision adds a separately frozen BNCI sensor-level physiological characterization, with fixed baseline/task intervals and participant-level μ/β descriptors. It examines these descriptions alongside saved source-LOSO performance without feeding them back into model selection. The manuscript distinguishes physiological signal description from evidence about what a decoder learned. This component covers nine BNCI participants and does not assert external physiological replication.

Code, saved predictions, contracts, event/file provenance and validation receipts accompany the manuscript. Q15 validation reconstructs original-data processing, frozen-checkpoint outputs and prescribed statistics without target fitting. The BNCI power analysis has its own pre-power committed recipe and executed manifest; independent numerical verification passed, including full central-sensor periodogram replay and complete saved-table aggregation checks. Physical export voltage calibration, original Cho acquisition reference and hardware cue latency remain explicit limitations.

Journal of Neural Engineering provides a relevant audience for reliable BCI evaluation and physiological interpretation. The manuscript shows how source-only duration decisions can produce concentrated gains and how a fixed spectral-sharing pipeline can have lower balanced accuracy under frozen transfer. Its separate sensor-level analysis provides physiological context while retaining the limits of retrospective association. The study does not evaluate online assistive control, patients or rehabilitation outcomes.

This research received no funding. I declare no competing interests. I confirm that neither ethics approval nor an exemption was required for this secondary analysis of publicly available EEG recordings; no new participants were recruited.

I confirm that I am the sole author, have reviewed and approved the final manuscript, and that this work is not under consideration elsewhere. It has not been published in a journal or deposited on a preprint server; a candidate manuscript and reproducibility materials are publicly available on GitHub. AI-assisted work is disclosed in the manuscript Acknowledgements and Methods, including the author-reported use of ChatGPT (GPT-6) and the established OpenAI Codex assistance. No other human assistance is reported.

Thank you for considering the manuscript.

Sincerely,

Ziyuan Zhu (朱子元)

College of Artificial Intelligence Medicine, Chongqing Medical University, Chongqing, China

zzy2630816871@gmail.com

Jinyun Campus, Chongqing Medical University, No. 61, Daxuecheng Middle Road, Shapingba District, Chongqing 401331, China

This letter has not been submitted or sent. Repository publication does not submit the manuscript to JNE.
