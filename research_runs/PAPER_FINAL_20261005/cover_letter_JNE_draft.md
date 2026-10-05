# Cover letter — unsent draft

5 October 2026

Editorial Office

Journal of Neural Engineering

Dear Editors,

Please consider our manuscript, "Source-only model selection and limits of shared spectral representations in cross-subject motor-imagery EEG decoding," for publication as an original research paper.

The study examines how source-only duration selection and a fixed shared μ/β input representation behave in cross-subject motor-imagery EEG decoding. It combines a documented development programme on BNCI2014_001 with separate frozen binary evaluations on PhysioNet, Cho2017, and Lee2019_MI. The paper distinguishes these protocols and reports participant-level uncertainty rather than treating repeated training seeds or trials as independent samples.

The completed Q15 evaluation adds 52 Cho2017 participants and 54 Lee2019_MI participants under a prespecified common 21-channel adapter. It provides a useful boundary on the shared representation: relative to broad EEGNet, shared μ/β reduced balanced accuracy on Cho2017 by 1.51 percentage points (95% paired-person bootstrap interval −2.25 to −0.80), whereas the Lee2019_MI difference was small and uncertain (+0.20 points, interval −0.52 to +0.97). We therefore do not claim a general shared-band advantage. The manuscript also states that physical export voltage calibration, the original Cho hardware reference, and hardware cue latency were not independently established.

Code, saved predictions, preprocessing and inference freezes, file-level provenance, and validation receipts accompany the paper. Q15 independent validation reconstructs the raw-to-epoch pipeline, frozen-checkpoint predictions, participant statistics, and the two-cohort multiplicity correction without target fitting. The historical fit counts and failed/superseded attempts remain visible in the supplementary inventory.

Journal of Neural Engineering provides a directly relevant audience for questions of reliable BCI evaluation. The manuscript addresses how a decoder can appear to improve through concentrated duration effects and how a plausible compact spectral representation can fail under frozen cross-dataset transfer. These findings inform the design and interpretation of future neural-engineering experiments; the study makes no claim of online assistive-control or patient benefit.

[Insert author-confirmed declarations concerning originality, overlap/preprints, exclusive submission, all-author approval, ethics, funding, competing interests, and any journal-required AI-assistance disclosure. These declarations have not yet been supplied.]

Thank you for considering the manuscript.

Sincerely,

Ziyuan Zhu (朱子元)

College of Artificial Intelligence Medicine, Chongqing Medical University, Chongqing, China

zzy2630816871@gmail.com

This is a preparation document. It has not been submitted or sent to a journal.
