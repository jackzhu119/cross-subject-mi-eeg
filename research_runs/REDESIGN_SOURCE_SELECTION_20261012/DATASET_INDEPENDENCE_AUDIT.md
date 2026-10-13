# Dataset independence and acquisition audit

Initial audit date: 12 October 2026; bounded transport update: 13 October 2026. **Conditional data nomination, not completed independent validation.** Three authenticated EDF/BDF files from one person (48,295,882 bytes) were acquired solely for header, annotation and precue format-scale checks; no target decoder output, score or task feature was computed. This dataset audit started no model fits. Existing BNCI, PhysioNet, Cho2017 and Lee2019 results remain historical evidence; reusing them is not an untouched confirmatory cohort.

## Selection rules established before target decoder evaluation

The primary cohort must provide real left/right-hand imagery, a traceable original recording source, usable real common electrode locations, explicit legal data terms, enough people for participant-level inference, and feasible storage. Nominal sample count, task, raw availability and objective technical quality determine priority; decoder accuracy and favorable physiology must not determine inclusion. Cohort, cue window, event mapping, montage, QC and exclusion rules must be committed before model output is inspected. Provider descriptor pages include historical online performance: during protocol/QC reading those results were encountered incidentally **after conditional nomination**, but are not a selection criterion. No proposed target-model result exists.

| Priority | Original collection | Nominal people | Task / source and licensing | Decision before outcomes |
|---|---|---:|---|---|
| 1 | Dreyer2023 A/B/C | 87 (60/21/6) | Real two-hand imagery; original GDF; Zenodo CC BY 4.0 | Nominated, conditional on all raw gates. Two published montage-corruption participants excluded before model evaluation; upper bound 85, not an observed completed sample. |
| 2 | Stieger2021 | 62 | Two-hand cursor task separable from both-hands/rest; original MATLAB; Figshare CC BY 4.0 | Secondary candidate: closed-loop and response-dependent trial duration require an independently frozen adapter. |
| 3 | Shin2017A | 29 | Real two-hand imagery; original EEG MATLAB; provider GNU terms | Not a direct common-montage replication: actual half-position electrodes do not include C3/C4. |
| 4 | Weibo2014 | 10 | Single-hand tasks within six MI tasks/rest; original Harvard Dataverse | Small secondary candidate only; original licensing/read access not directly established in this environment. |
| 5 | GrosseWentrup2009 | 10 | Two-hand MI; original EEGLAB set/fdt; Zenodo CC BY 4.0 | Small secondary candidate; provider records missing names of channels 65–128. |

No algorithm score determined this ordering. A smaller/easier participant subset must not replace the declared cohort after target outcomes become available.

## Preferred cohort: Dreyer2023

The [formal descriptor](https://doi.org/10.1038/s41597-023-02445-z) and [original versioned Zenodo record](https://zenodo.org/records/8089820) identify 87 people in A/B/C origin strata. These are one shared-protocol collection, not three independent cross-dataset replications. Original recordings contain 27 EEG electrodes at 512 Hz, left-ear reference, two EMG and three EOG channels. Original collection consent/approval is documented in the descriptor; that does not establish institutional approval or exemption for this secondary study.

The exact ordered BNCI–Dreyer intersection has **19 actual sites**:

`Fz, FC3, FC1, FCz, FC2, FC4, C5, C3, C1, Cz, C2, C4, C6, CP3, CP1, CPz, CP2, CP4, Pz`.

Legacy Q15 includes P1/P2/POz and omits FCz. Dreyer does not record those three posterior sites. Therefore legacy 21-channel checkpoints cannot be relabelled, filled or directly presented as this new matched-montage evaluation. New source models must be fitted on the common 19-site input, with all source/target ordering verified. Exact labels, digital-to-physical scales and cue events were checked for the bounded one-person subset described in [DREYER_TRANSPORT_PREFLIGHT.md](DREYER_TRANSPORT_PREFLIGHT.md). Full-cohort labels, actual acquisition ordering, original GDF equivalence and physical device calibration remain unverified; a prefix format-scale check does not establish those facts.

Primary candidates are the **first two acquisition runs**, expected 80 trials/person (40/class), with sham feedback; four later runs use real feedback from each participant's individually calibrated decoder and are not silently mixed into this primary population. OpenViBE codes are 769=left cue, 770=right cue, 768=trial start, 781=feedback start, 800=feedback/trial end. The proposed fixed cue-relative [0.5, 2.5) s crop intersects side-specific sham visual feedback beginning +1.25 s. It matches the source two-second budget but is **not a feedback-free, pure physiological epoch**. This protocol difference must be disclosed, not eliminated by choosing a window after seeing accuracy.

### Prespecified objective quality handling

| Provider person | Published technical issue | Common19 affected | Primary rule before results |
|---|---|---|---|
| A04 | Large artifacts from FC5 technical fault | FC5 is not retained | Retain unless fixed signal-only QC fails; quality-flag sensitivity. |
| A09 | Large artifacts from FC5 technical fault | FC5 is not retained | Same rule. |
| A17 | Two-amplifier recording order causes incorrect electrode arrangement and disturbed signal | Entire ordering cannot be authenticated | Exclude. No verified inverse permutation/repair record is available. |
| A29 | Possible FC5/CP5 disconnection or excessive impedance | Neither site retained | Retain unless fixed signal-only QC fails; do not remove a whole person solely from outside-montage flags. |
| A41 | Same recording-order problem as A17 | Entire ordering cannot be authenticated | Exclude under the same rule. |
| B78 | Major artifacts on P4/C3/FC3 in different runs | C3/FC3 retained | Retain flagged person, then apply frozen raw QC per run/trial. R1/R2-specific involvement remains unchecked. |
| B79 | C2 dysfunction | C2 retained | Retain flagged person, then apply frozen raw QC; exact first-run involvement remains unchecked. |

These flags come from the provider's technical review, not our target decoder scores. Other flagged people must not be removed based on low online performance, successful cursor control, visible MI responses or difficulty. Primary upper bound after the two montage exclusions is **85 people / 6,800 expected acquisition trials**, not a verified final sample. A predeclared sensitivity excluding all seven provider quality flags has an upper bound of 80 people. It must never replace the primary analysis because its score is more favorable. Once actual signal-only QC is complete, every retained/excluded trial and person requires a logged reason shared across all model conditions.

### Acquisition and storage

The original record exposes one `BCI Database.zip`, **27,475,466,178 bytes**, MD5 **c8c6f5f09f1882666eec10e29155fdcb**. [Canonical content URL](https://zenodo.org/api/records/8089820/files/BCI%20Database.zip/content). The provider API metadata was retrieved successfully. Two original archive HEAD requests timed out, so raw endpoint accessibility and Range support must not be claimed from metadata API success. A bounded tail-only Range probe has a separate receipt; no full archive is downloaded here. The original API does not expose per-person GDF URLs. Original archive access and GDF authentication remain unresolved. A separately versioned NEMAR upstream-EDF mirror now exposes an individually addressable R1/R2 route, authenticated for a bounded subset; this establishes transport of the mirror rather than equivalence to original GDF bytes.

An approximately 28 GB free workspace cannot safely accommodate this 27.5 GB compressed archive plus expanded signals and training cache. Do not start a blind full original archive download or claim R2 contains the new collection. The NEMAR v1.0.5 mirror declares 174 acquisition EDFs totaling 2,515,343,396 bytes (about 2.343 GiB). Its 520/522 all-run discrepancy is localized to sub-59 R5/R6 online files; all 174 acquisition paths are declared. Only the fixed 48.3 MB subset has been acquired and checked here. EDF/BDF annotations and precue physical-scale agreement were checked on that subset; original GDF equivalence and original device calibration were not.

## Other candidates and task exclusions

[Stieger's formal descriptor](https://doi.org/10.1038/s41597-021-00883-1) specifies 62 people, 7–11 sessions, 62 EEG leads and 1000 Hz. For two-hand MI use tasknumber=1 and presented targetnumber=1(right)/2(left), never hit target, success or cursor outcome as ground truth. Session 1 predates the eight-week intervention. It contains online feedback and variable feedback length: a fixed epoch rule must not condition eligibility on success. The released cohort also reflects provider selection from a larger study, including ceiling-performance/noncompliance criteria; it does not represent an unselected population. Original Figshare lists **598 MATLAB files + README**: 376,894,144,767 bytes total; session-1 files alone are 38,395,648,006 bytes. Provider API says CC BY 4.0, current MOABB documentation CC BY-NC 4.0: retain this conflict and use the versioned original provider terms. A common19 label map remains a raw-file gate.

[Shin's original provider](https://doc.ml.tu-berlin.de/hBCI/contactthanks.html) documents 29 people, MI sessions 1/3/5 and 60 trials/person. EEG was acquired at 1000 Hz and distributed at 200 Hz with linked-mastoid reference. Actual 10-5 sites include FCC3h/CCP3h rather than C3 and C4; only Cz/Pz overlap with common19. They cannot be renamed as nominal equivalent sites. The provider describes only downsampling/re-reference before distribution, whereas current adapter metadata lists additional analysis processing. Provider documentation takes precedence. GNU terms and actual archive license must be retained on future acquisition. [Formal citation](https://doi.org/10.1109/TNSRE.2016.2628057).

[Weibo's original paper](https://doi.org/10.1371/journal.pone.0114853) describes 10 people performing six simple/compound MI tasks and rest; left/right-hand trials can be isolated. The original acquisition is 1000 Hz, nose reference; paper analysis resamples to 200 Hz. Original Dataverse API access returned 403, so its exact data terms and actual raw fields are unverified. A derived mirror's CC0 label must not be used to infer original rights. N=10 is insufficient as the primary validation cohort in this design.

[Grosse-Wentrup's original deposit](https://zenodo.org/records/1217449) verifies 10 people and CC BY 4.0, 20 set/fdt files totaling 7,813,315,168 bytes. It explicitly warns that channel names 65–128 are missing and the head model is poorly specified. Canonical labels require original header audit; current adapter 500 Hz/Cz metadata is supporting information, not a completed primary raw check. [Formal paper](https://doi.org/10.1109/TBME.2008.2009768).

Schirrmeister High-Gamma is an executed-movement collection, not a matched hand-imagery-only cohort. NETBCI's reported right-hand-versus-rest task differs from left-versus-right MI. Neither can be silently combined into the binary cohort mean. The second-paper repository was not accessed, altered or automatically incorporated.

## What remains unproved

Anonymized subject IDs, distinct institutions/countries or acquisition dates do not prove no repeated person across datasets. Before a confirmatory claim, reconcile provider origins, author prior exposure and second-paper reuse, authenticate original/converted provenance, acquire and verify the whole selected cohort rather than extrapolating from one person, check all file hashes and units and whole-file/trial duplicates, authenticate every channel/event axis, freeze signal-only QC and run inclusion, and independently replay saved predictions/statistics. Perfect real-world identity reconciliation may remain impossible with anonymized public collections; report that limit.

No independent target decoder validation has been completed. This audit establishes a plausible, pre-outcome candidate and explicit stop gates, not the success of mean-rank, fixed training, spectral sharing or a physiological explanation. Machine-readable findings and fetch receipts are in `evidence/dataset_candidate_audit.json` and `evidence/dataset_sources/`.

## Future acquisition gate

`DREYER_DATA_ACCESS_PLAN.json` binds the proposed source-EDF mirror, provider version, manifest SHA-256, two acquisition runs, exact shared-channel order and event map. `scripts/acquire_dreyer_runs.py` defaults to a metadata-only dry-run; it does not download absent signals or start training. Explicit `--download` or `--audit-cache` requires a genuine author prior-use declaration plus a Git-committed access plan. The declaration template remains unresolved, and provider metadata cannot supply the author's answer. Passing this access gate permits only transport/hash/header/event audit, not confirmatory model inference. All signal-only QC, original GDF provenance, independence and scientific preanalysis gates remain separate.
