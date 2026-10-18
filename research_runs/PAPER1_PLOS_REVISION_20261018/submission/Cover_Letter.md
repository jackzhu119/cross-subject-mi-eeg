18 October 2026

Dear Editors of PLOS ONE,

Please consider the Research Article entitled **“Source-cohort expansion and weaker-class coverage in cross-subject motor-imagery EEG decoding”** by Ziyuan Zhu.

This study asks whether a broader source cohort improves the coverage of both motor-imagery classes when model architecture and maximum optimization budget are held fixed. The completed experiment compares 9, 29 and 60 source participants using a common 18-channel, dimensionless processing pipeline and participant-held-out source validation. It evaluates the resulting models on 85 participants from a separate acquisition programme. Each neural trajectory received the same maximum of 5,120 optimizer updates; the comparison therefore makes the computational allocation explicit alongside the changing source composition and available trials.

For the primary BROAD/tail-minimum-recall comparison, expansion from S9 to S60 increased mean weaker-class recall from 27.31% to 48.48%, a paired difference of 21.17 percentage points (95% CI 17.12–25.21). Balanced accuracy increased by 5.85 percentage points in the corresponding secondary comparison. The full prespecified comparison set is reported: S60 was not demonstrably better than S29 on weaker-class recall, and tail-minimum-recall selection did not outperform mean-balanced-accuracy selection within S60. These findings distinguish the supported source-cohort contrast from a claim of a generally superior checkpoint-selection algorithm.

The contribution is a controlled empirical evaluation of source-cohort expansion, participant-level class coverage and source-only checkpoint selection, supported by an inspectable evidence chain. The release includes frozen configuration and code, source-selection records, participant-level predictions and numerical checks. Independent saved-prediction auditing passed 1,179 checks; separate integrity and source-selection auditing checked the recorded training trajectories and selector calculations. The external analysis is identified as exploratory because first-use independence of the evaluation cohort cannot be established from the historical records.

The work uses secondary public EEG data and recruited no new participants. The manuscript reports the author's assessment of secondary-use ethics requirements, the available original collection provenance, funding and competing interests, data/code availability, author contributions and substantive AI assistance. Third-party raw recordings remain with their providers. The manuscript and research materials have been publicly available on GitHub.

Thank you for considering this work.

Sincerely,

Ziyuan Zhu, sole and corresponding author  
College of Artificial Intelligence Medicine, Chongqing Medical University  
Jinyun Campus, No. 61 Daxuecheng Middle Road, Shapingba District, Chongqing 401331, China  
zzy2630816871@gmail.com  
ORCID: 0009-0005-1153-4926
