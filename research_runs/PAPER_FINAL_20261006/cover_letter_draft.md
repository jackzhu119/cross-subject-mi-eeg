# Cover letter — prepared for submission, unsent

7 October 2026

[Editor name or Editorial Office]

[Journal]

Dear [Editor name / Editor],

Please consider my manuscript, "Source-only model selection and limits of fixed spectral-sharing pipelines in cross-subject motor-imagery EEG decoding," for publication as [journal-appropriate article type].

The study examines source-only model selection and the transfer limits of fixed spectral-sharing pipelines. BNCI development analyses are followed by separately frozen binary evaluations on PhysioNet, Cho2017 and Lee2019_MI. Zero calibration means no target-dependent fitting or model selection; label use for metadata and scoring is distinguished from learning. Results and uncertainty are reported at participant level.

The frozen Q15 evaluation includes 52 Cho2017 and 54 Lee2019_MI participants under a prespecified common 21-channel adapter. The shared-input pipeline had 1.513 percentage points lower balanced accuracy on Cho2017 (95% paired-person bootstrap interval −2.249 to −0.804); the Lee2019_MI difference was small and uncertain (+0.204 points, interval −0.515 to +0.969). These adverse and uncertain results are retained. The contrasts compare complete pipelines, including their source-selected training durations.

A separate BNCI sensor analysis uses fixed baseline/task intervals and participant-level μ/β descriptors, specified after decoder outcomes were known and before the power calculation. Its associations with saved source-LOSO scores are descriptive and do not feed back into model selection. The analysis distinguishes recorded physiology from evidence about decoder mechanisms. It includes nine BNCI participants and has no external physiological replication.

The accompanying code, saved predictions, frozen contracts and validation records make the evaluation traceable. Q15 validation reconstructs raw-data processing, frozen-checkpoint outputs and prescribed statistics without target fitting. Independent verification of the BNCI analysis includes full central-sensor periodogram replay and all saved-table aggregations, checked against its committed pre-power recipe and execution manifest. Physical export voltage calibration, the original Cho acquisition reference and hardware cue latency remain unresolved.

[Add a paragraph addressing the chosen journal's readership and specific scientific contribution.]

This research received no funding. I declare no competing interests. I confirm that neither ethics approval nor an exemption was required for this secondary analysis of publicly available EEG recordings; no new participants were recruited.

I confirm that I am the sole author, have reviewed and approved the final manuscript, and that this work is not under consideration elsewhere. It has not been published in a journal or deposited on a preprint server; a candidate manuscript and reproducibility materials are publicly available on GitHub. AI-assisted work is disclosed in the manuscript Acknowledgements and Methods, including the author-reported use of ChatGPT (GPT-6) and the established OpenAI Codex assistance. No other human assistance is reported.

Thank you for considering the manuscript.

Sincerely,

Ziyuan Zhu (朱子元)

College of Artificial Intelligence Medicine, Chongqing Medical University, Chongqing, China

zzy2630816871@gmail.com

Jinyun Campus, Chongqing Medical University, No. 61, Daxuecheng Middle Road, Shapingba District, Chongqing 401331, China

This letter has not been submitted or sent. Repository publication does not submit the manuscript to JNE.
