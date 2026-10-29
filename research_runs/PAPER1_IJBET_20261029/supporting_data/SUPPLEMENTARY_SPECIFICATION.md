# Supplementary specification for the completed experiments

This supplement accompanies the manuscript's two completed experiments. It supplies previously saved selection records, numerical inventories and figure data. No experimental run, endpoint, bootstrap interval or significance test was added during manuscript preparation.

## Data-version map

| Item | Study 1 | Study 2 |
|---|---|---|
| Source cohorts | BNCI and Yang; S9, fixed S29 and S60 rosters | BNCI and Yang; S60 |
| Source representation | Original eligible-v3, original Figshare v5 input identity | Separately reconstructed arrays, official NEMAR privacy-corrected Yang v1.0.5 |
| Input | 18 channels, broadband/mu/beta views, 160 Hz, 320 samples, per-trial broadband RMS scale | Same nominal representation; separate numerical identity |
| Implementation | Braindecode 1.5.1 EEGNet, batch 64 | Direct PyTorch EEGNet-style, batch 128; NumPy 2.2.6/SciPy 1.15.3 reconstruction |
| Completed neural fits | 90 development + 18 all-source final | 75 development + 15 all-source final |
| Conventional fits | Nine CSP–LDA | None in the objective comparison |
| External population | 85 people, 80 trials each | Same 85 people and trials |

Study 2 array fingerprint: `115eb0e80294031a7f47b9f7908aa918092a41a9a2e3396ffdc95d84a4c8adb2`. Separate identities are retained. An across-study numerical difference does not isolate the effect of an objective. The external population had prior project exposure and is exploratory; its reuse is not an independent replication.

## Study 1 inventories

`Study1_checkpoint_selection_freeze.json` is the unchanged original freeze: all source pools, input pipelines, eight selection rules, selected epochs and saved epoch curves. Source scores used cohort-balanced participant weights after seed averaging. The worst-tail selectors used exactly one-third of the weighted participant mass, including a fractional boundary participant. Mean-rank and other score ties follow the manuscript's separate rules.

`Study1_neural_condition_summaries.csv` and `Study1_classical_condition_summaries.csv` retain all saved condition summaries. `Study1_complete_expansion_inventory.csv` retains the complete source-expansion comparison inventory, including adverse effects. The 144 final neural prediction conditions reuse checkpoints from 18 trajectories; they are not 144 additional fits.

`Study1_frozen_comparisons.csv` retains the original primary comparison and three-test secondary Holm family. `Study1_existing_posthoc_comparisons.csv` retains its separately labelled four-test post hoc family. These files preserve original units and inference. `Study1_fixed20_seed_means.csv` and `Study1_fixed20_seed_differences.csv` describe common-duration checkpoints at 20 epochs and 2,560 updates. They are descriptive controls. `Study1_absolute_recall_gap.csv` and the 85-person figure table contain the existing class-gap and paired-change reconstructions.

## Study 2 inventories

The three `Study2_*_source.json` files are unchanged saved analysis outputs: nested source evaluation, external epoch-40 evaluation, and external source-selected evaluation. They retain all registered comparators, signed effects, participant counts, original pointwise bootstrap intervals and the stored test-family assignments. Source participants receive equal cohort and equal within-cohort weight. External participants receive equal participant weight after averaging the three final seeds.

`Fig2_objective_profiles.csv` contains all 12 weaker-class-recall contrasts shown in Figure 2. Both external panels use checkpoints from the same final trajectories and the same people. The balanced ERM reference and the TAIL component comparisons remain part of the interpretation of TC versus GroupDRO.

## Source integrity and contents

The numerical files were copied from completed research records without editing their bytes. The data archive's `MANIFEST.json` lists each payload's length and SHA256. It contains compact numerical outputs, not raw EEG, fitted weights or complete raw prediction archives. Original complete prediction evidence is retained separately in the executed research record.
