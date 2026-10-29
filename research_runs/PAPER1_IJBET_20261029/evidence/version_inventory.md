# Paper 1: version and evidence inventory (29 October 2026)

Scope: read-only source inspection and extraction of saved tables/JSON from previously audited exports. No original EEG, model weights, new fitting/inference or resampling were used. Local research checkout was clean at `c40a5daaf57228be8741486e20c0da1b3c4be822` at inspection.

## Which versions exist?

There are **three currently relevant scientific experiment families**, plus the **legacy Q1–Q16/archive family**. Manuscript snapshots, operation repairs, input identities and experiments are different kinds of version; they must not be counted as independent studies.

1. **Completed source-expansion eligible-v3, 18 October.** BNCI9, BNCI9+Yang20 (S29), BNCI9+Yang51 (S60); 108 neural trajectories (90 source-validation+18 final), nine CSP/LDA fits. Source trials 2,592/14,590/33,183; external Dreyer85×80=6,800 trials. Original Figshare-v5 identity, 18-channel dimensionless arrays, Braindecode1.5.1 EEGNet, batch64. Fixed results handoff `040956085499ed788948de0d5a09cddd9eabca56`.
2. **Completed school-HPC source-risk-v1, exported 27 October.** Five objectives ERM/GroupDRO/TAIL/consistency/TAIL+consistency on the fixed60-person source pool; 75 development+15 final=90 neural fits, 105 selected held-out evaluations, 9,015 prediction shards. Complete results commit `2afb6c3eddbe2c3c82664b683f01970f95d4db39`, branch `hpc-results/paper1-risk-v1`, path `research_runs/PAPER1_HPC_RESULTS_20261027/b96a3fcaacf91017/`. The archive was fully verified previously; independent saved-prediction arithmetic passed833,310checks, zero failures. The later audit did **not** rerun stored bootstrap/permutation p/CI.
3. **Composition-by-objective-v2, frozen27October, unfinished.** Planned540neural+90deterministicCSP/RLDA=630tasks. The29October09:17:34CST GitHub snapshot records189complete/441remaining and no complete analysis/export. Its controller timestamp is08:06:15CST, so the fresh upload time must not be interpreted as a fresh optimizer observation. This unfinished experiment is not an additional completed Results section.
4. **Legacy Q1–Q16 and early submissions.** `research_runs/PAPER_FINAL_20261006/`, `research_runs/PLOS_ONE_SUBMISSION/`, oldJNE/9OctPLOS materials, and prior19-channel recovery/protocol records remain historical. They contain other external data and preprocessing contracts. They cannot be numerically mixed with18-channel eligible-v3.

The17October source-expansion package initially anticipated33,192trials. That is a planned inventory, not the completed eligible-v3 total33,183. Native missing/unknown labels account for explicit eligibility handling; do not copy the initial number into the new Results.

## Current manuscript and reusable assets

- Current main source: `research_runs/PAPER1_REVIEW_20261020/manuscript_en.md`.
- Current mainWord/PDF: same directory, `main_manuscript.docx` / `main_manuscript.pdf`.
- Currentsupplement: same directory `supplementary_en.md`, `S1_Appendix.docx/pdf`.
- RevisedFigure1: same directory `figures/Fig1_workflow.*`.
- UnchangedFigures2–7: `research_runs/PAPER1_PLOS_FINAL_20261018/figures/`.
- Exacttable/figureCSV: `research_runs/PAPER1_PLOS_FINAL_20261018/tables/` and `figure_data/`.
- Originalcomplete numerical audit: `research_runs/ELIGIBLE_V3_RESULTS_20261018/audits/`.

The current20October manuscript already foregrounds the principal positive effects, participant-level joint benefit and common-duration controls. A meaningful new rewrite should sharpen the research question and contribution map, rather than imply that none of these results had been written before.

## Strongest completed source-expansion evidence

All effects below are percentage points. External statistical unit is85people; each person's metric is computed perfinalseed then averaged over3seeds. Seeds,folds,trials and checkpoint aliases are not extra independent people.

| Evidence | Effect | Interval / test | Status and source |
|---|---:|---|---|
| S60−S9, BROAD/tail-min-recall, W | +21.1667 | t95%CI[17.1226,25.2107];p8.8841e−17;bootstrapCI[17.1468,24.9512] | Frozenprimary; `tables/Table2_frozen_comparisons.csv` |
| Samecontrast,BA | +5.8529 | t95%CI[4.1288,7.5771];Holmp5.3414e−9 | FrozenHolm3secondary; sametable |
| S29−S9,W | +21.7157 | t95%CI[17.7228,25.7086];Holmp5.52999e−17 | PosthocHolm4family; `tables/review2_posthoc_comparisons.csv` |
| S29−S9,BA | +5.7892 | t95%CI[4.1233,7.4551];Holmp2.61106e−9 | Sameposthocfamily |
| CSP/LDA S60−S9,W | +13.8235 | t95%CI[9.1980,18.4490];Holmp6.32762e−8 | Sameposthocfamily |
| CSP/LDA S60−S9,BA | +5.2451 | t95%CI[3.5345,6.9557];Holmp6.32762e−8 | Sameposthocfamily |
| Fixed20S60−S9,W,BROAD | +17.0686 | Descriptive, no newtest | Same2560updates; `tables/source_expansion_inventory.csv` |
| Fixed20S60−S9,W,sharedmu/beta | +24.8725 | Descriptive, no newtest | Same2560updates; sameinventory |

Further transparent descriptions: Wimproved72/85(10declined,3ties), BAimproved71/85; bothendpoints improved in the same66/85people. Meanabsoluteclass-recallgap fell62.0098→31.3824points (−30.6275points;49.39%relative reduction). Stronger-classrecall concurrently changed89.3235→79.8627%, so the gap reduction should not be represented as improvement of both class recalls. Weaker-command coverage and balanced accuracy increased together.

The24existing fixed20per-seed comparisons (2sourceincrements×2pipelines×2metrics×3seeds) all have positive point differences. These are a complete descriptive control inventory, not24independentconfirmatory tests.

Two frozen comparisons remain central to interpretation: S60−S29W=−0.5490points(tCI−2.1604to1.0624;Holm.999859), and S60tailselector−meanBAselectorW=−0.8725points(CI−3.4935to1.7484;Holm.999859). The supported claim is expansion versus the BNCI-only configuration, not monotonic benefit from source count or selector superiority.

## What the complete90-fit HPC extension supports

The three saved domains are nestedsourceouter(n60,equalcohort then equalperson), externalfixed40(n85,equalperson), and externalsource-selected(n85,equalperson). Source-selectedmedianepochs: ERM14,GroupDRO21,TAIL18,consistency11,combined18.

| Contrast, W | Effect(pp) | Savedbootstrap95%CI | Savedp / adjustedp |
|---|---:|---|---|
| Combined−ERM,sourceouter | +1.3505 | [−0.4620,3.3858] | p.192078 |
| Combined−ERM,externalfixed40 | +1.2843 | [−0.3137,2.8824] | p.123719 |
| Combined−ERM,externalselected | +0.0784 | [−1.6078,1.7941] | p.937411 |
| Combined−GroupDRO,externalfixed40 | +8.7549 | [6.5586,10.9414] | Holmp3.99996e−5 |
| Combined−GroupDRO,externalselected | +7.0686 | [4.4507,9.6081] | Holmp3.99996e−5 |

Source-selectedcombined versus ERM BA difference is−1.3431points(CI−2.0539to−0.6324;Holm.00146999). TAIL-alone has slightlyhigherWthancombined in allthree domains; combined is not established as a synergistic advance. Its advantage versus the implementedGroupDRObaseline can be reported with that specific comparator and scope; it does not establish general superiority.

## Can the experiment versions be combined?

They may appear as separately labeled experiments in one paper, with distinct Methods, tables and provenance. They cannot be pooled as one run or treated as independent external-cohort replications.

SchoolHPC uses officialNEMARnm000348v1.0.5privacy-correctednativefiles. All306fileancestryrecords are pinned; provider policy changesBDFidentificationfields[8,168). Independent checks verified onefullsignal/eventpair outsidechangedheaders, all306correctedheaders, and all153eventfiles. This does not establish an independent fullsamplepayload comparison for all153signalfiles.

NewCPUpreparation NumPy2.2.6/SciPy1.15.3 regenerates arrays with newfingerprint `115eb0e80294031a7f47b9f7908aa918092a41a9a2e3396ffdc95d84a4c8adb2`. The protocol explicitly rejects an assumed bitwise match to oldarrays. HPC uses directPyTorch EEGNet-style (notBraindecodecheckpoint-equivalent), batch128=8people×2classes×8trials, matchedthree-viewBNexposure and broadinference, plusnestedvalidation. Eligible-v3 usedBraindecode1.5.1,batch64,differentparticipant/trialsamplingandselection. Consequently, differences between old and new scores cannot be assigned solely to a new objective.

The ongoingcompositionversion uses the schoolpreparedregistry but newwhitelists,4personbatches and fixed40endpoints. Its540newneuralfits are not replacements/relabels ofold90weights.

## Small table discrepancy to avoid carrying into prose

S29−S9BA improved/tied/declined counts are66/2/17 in the4-posthoctesttable versus65/4/16 in theadditionaldescriptive table. Numericaltie-threshold differences are a plausible explanation but were not independently resolved. Means,CI,p andS29Wcounts agree. Do not promote the optionalS29BAcount until the exacttie rule is reconciled. PrimaryS60W72/10/3andjoint66/85numbers are consistent.

The machine-readable companion `version_inventory.json` preserves exact original CSV values and all15savedHPCcontrasts/methodmeans for drafting.
