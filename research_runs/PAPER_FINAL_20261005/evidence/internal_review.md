# Independent review of Q1–Q14 for the completed manuscript

Source snapshot: `7af1a137e2676a018e1e880ab076de6cae4ce30b` in `jackzhu119/cross-subject-mi-eeg`. The previous English draft was read in full. This review rescored existing predictions only: **38 arms and 809,434 prediction rows**. Every selected all-trial evaluation cell reproduced its saved balanced accuracy within an absolute tolerance of 10⁻¹²; no duplicate prediction identities were found. Q8, all six Q12 contrasts, all eleven Q13 contrasts, and the Q14 primary bootstrap/sign test were recomputed at participant level. No raw EEG was processed, no checkpoint executed, and no model fitted.

The companion JSON records actual current byte hashes. **314 previously reviewed controlling inputs were byte-identical to their prior recorded hashes**, with no missing or unresolved inputs. Other earlier Q1–Q11 details are retained from the previous independent review only with that custody. Historical Q10/Q14 records also contain Windows CRLF-versus-Git-LF notes; the current match to the previous paper review does not erase those earlier custody distinctions.

## Consequential findings for the manuscript

| Comparison | Verified result | Required interpretation |
| --- | --- | --- |
| Q5 mean-loss versus Q8 mean-rank selection | Mean BA 33.7191% versus 42.6698%; paired change +8.9506 pp, median +1.8519 pp | Exploratory comparison in the same previously examined nine-person cohort. S3 and S8 contribute 87.57% of the summed gain. |
| Q8 participant signs | Seven improvements, no decrements, two ties | The archive reports p = 0.1796875 using all nine in the binomial denominator. The conventional exact sign test excluding ties gives p = 0.015625. Both definitions must be disclosed; do not silently substitute the favorable calculation. |
| Q8 original bootstrap | +8.9506 pp; 95% percentile interval [1.0481, 19.9588] pp, 20,000 draws, seed 20260923 | Reproduced exactly to numerical tolerance. This is an unadjusted exploratory interval, not prospective confirmation. Paired t-test p = 0.110964. |
| Fixed20 versus historical duration schedule under matched runtime | 43.9879% versus 33.9249%; +10.0630 pp; exact sign-flip p = 0.125 | Only four participants improve and five worsen; median change is −0.1736 pp. The positive mean is driven by large rescues. The historical Q5 source-selected schedule was replayed rather than reselected under the new runtime. |
| Q9 shared mu/beta versus Q8 broad rank model | 42.1875% versus 42.6698%; −0.4823 pp | A constrained representation, not an established improvement. The 8–30 Hz arm has higher descriptive mean (44.5538%), but post hoc ordering does not define a confirmatory winner. |
| Q12 robustness | No contrast survives its declared within-family Holm correction | Retain every negative and positive participant difference and the correctly matched GroupDRO control. |
| Q13 source-count series | Broad 32.9572%, 38.8905%, 43.1552%, 43.9879% at k = 2, 4, 6, 8; shared 34.7431%, 38.8889%, 42.4849%, 43.9751% | Nine target participants remain the inference units. Four source subsets and three seeds are repeated measurements; larger source counts also change trial count and optimizer update exposure. |
| Q14 PhysioNet primary | Broad 61.8146%, shared 62.3879%, CSP4–LDA 54.4617%; shared minus broad +0.5733 pp, 95% interval [−0.0967, 1.2416] pp | 109 participants; the interval spans zero, so superiority is not established. |
| Q14 frozen exact-zero sign convention | 63 positive, 43 negative, three ties; p = 0.0644636 | S10 has an approximately −1.11 × 10⁻¹⁶ stored difference. A disclosed 10⁻¹⁴ tolerance sensitivity gives 63/42/four ties and p = 0.0504422; the primary rule remains unchanged. |

## Robustness is heterogeneous, including adverse effects

| Frozen contrast | Mean change (pp) | Participant range (pp) | Exact sign-flip p | Holm p |
| --- | ---: | ---: | ---: | ---: |
| Source-pooled whitening minus Q8 | +1.6654 | −4.4560 to +7.4074 | 0.1797 | 0.3594 |
| Balanced ERM minus Q8 | +0.5144 | −2.8935 to +4.2824 | 0.4766 | 0.4766 |
| GroupDRO minus balanced ERM | −6.4493 | −19.7917 to +4.2245 | 0.0469 | 0.1406 |
| Channel dropout minus Q8 | −1.6654 | −11.1111 to +4.3981 | 0.3008 | 0.7617 |
| Gain perturbation minus Q8 | +0.7523 | −1.9097 to +3.8194 | 0.2539 | 0.7617 |
| Dropout plus gain minus Q8 | −1.7490 | −12.0370 to +4.2824 | 0.3516 | 0.7617 |

Intervals are unadjusted participant bootstrap intervals; the p-values above are corrected within the separately declared domain-generalization and augmentation families. Most Q12 comparisons use historical Q8 outcomes across runtime, whereas GroupDRO uses the contemporaneous balanced-ERM control. Neither unadjusted GroupDRO p nor a confidence interval excluding zero overrides the Holm-null outcome.

## Scope and earlier evidence

Q4–Q13 four-class BNCI comparisons evaluate all 5,184 trials (576 per participant; 144 per class), with both target sessions excluded from source fitting. Q7 is a three-seed diagnostic case for S3: cells A and D reuse Q5/Q6, and only B/C were newly fitted. It is not a nine-person experiment. Q4-A001 reuses CSP caches while refitting the scaler/LDA, and duplicated k8/k72 endpoints are not independent replications. Q9's top-level batch pass is orchestration only; the later Q10-V001 artifact validation does not constitute raw EEG/checkpoint replay. The internal log-Euclidean geometry should not be called affine-invariant tangent-space decoding. The Q11 broad capacity control has 5,914 parameters versus 5,864 for independent branches, a 50-parameter (0.853%) approximate match.

Earlier P2/P3/P4 results are binary and use different target populations. Within-session and cross-session P2 evaluations use labeled target-person calibration, whereas cross-subject LOSO does not. P3/P4 use expert-clean target trials; all/flagged target strata remain secondary. The EOG regression retry requires three synchronous EOG sensors and does not establish decoding benefit or selective ocular removal. P1 is an acquisition audit, and technical smokes/failures receive no population replication claim. They belong in the complete research inventory or supplement rather than a pooled decoder leaderboard.

Q13-E002/E003 and Q14-E003 are unrun and must receive no invented outcomes. Three source seeds, subsets, sessions, trials, and overlapping LOSO training sets do not create independent participant replicates. The repeated internal research program also does not become prospectively confirmatory merely because later external Q15 completed.

## Q14 amendment and validation provenance

The 109-person PhysioNet endpoint comprises 4,918 unique trials, 34,426 model/seed prediction rows, and 327 official EDF files. Metadata identified native 128 Hz for participants 88, 92, and 100; those signals were resampled to 160 Hz following a failure after partial external execution. The completed R2 cohort includes 87 retained prediction copies and 22 additional participants. The R2 amendment therefore must not be described as an unchanged original protocol. A later validation-only portability amendment reconstructed official event identities and rescored immutable predictions on a different host/runtime, with no new fitting or inference. Cite `results/Q14-E002R2V1/validation_report.json` as the passing scientific validation and retain the original failed R2 batch as history; do not substitute the failed batch state for the completed endpoint.

## Editorial consequence of completed Q15

The old abstract was appropriately cautious, but it is now incomplete because it described only one external cohort. Add Q15's separately verified frozen external endpoint, its model-specific dataset effects and pooling rules. Preserve a distinction between internal duration diagnostics and externally tested representations: Q15 does not externally test mean-loss versus mean-rank selection. Use the actual favorable, adverse, and uncertain contrasts without selecting the best model or dataset after inspecting outcomes. Claims about invariant rhythms, causal mechanisms, clinical utility, universal calibration-free transfer, or superiority of all spatial-spectral representations are unsupported.

The companion `internal_review.json` gives cell-level coverage, participant values, source selections, statistical conventions, and actual source hashes. `paper_internal_numbers.json` preserves the previous paper's numeric interface while adding the independent checks above. Numerical recomputation supports the saved outcomes; historical scientific receipts support raw/checkpoint validation only within their recorded scopes.
