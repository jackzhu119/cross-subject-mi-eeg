# Independent numbers for the English paper

Q8/Q9/Q12/Q13/Q14; Q15 excluded; Q5 read only as the explicitly reused Q13 historical comparator. Read-only arithmetic; no model/checkpoint execution, new fits or edits to old results.

38 arms checked; every saved all-stratum cell BA matches independent equal-class recall at1e-12. Persons are the inference unit after averaging all fixed seeds/subsets within person. CSP deterministic is a single arm, not an extra seed.

| Arm | Classes | People | Evaluation cells | Equal-person BA |
| --- | ---: | ---: | ---: | ---: |
| Q8-E001/BROAD_MEAN_RANK | 4 | 9 | 27 | 0.426697531 |
| Q9-A001/PSD44_LDA | 4 | 9 | 9 | 0.362847222 |
| Q9-A001/PSD44_LINEAR_SVM | 4 | 9 | 9 | 0.357831790 |
| Q9-E001/BETA_13_30 | 4 | 9 | 27 | 0.315329218 |
| Q9-E001/MID_8_30 | 4 | 9 | 27 | 0.445537551 |
| Q9-E001/MU_8_13 | 4 | 9 | 27 | 0.432998971 |
| Q9-E001/MU_BETA_SHARED | 4 | 9 | 27 | 0.421875000 |
| Q9-E002/MID_8_30_Q8_EPOCHS | 4 | 9 | 27 | 0.427276235 |
| Q9-E002/MU_BETA_SHARED_Q8_EPOCHS | 4 | 9 | 27 | 0.434992284 |
| Q9-E004/MU_BETA_SHARED_SOURCE_CLEAN | 4 | 9 | 27 | 0.421103395 |
| Q9-E005/MU_BETA_SHARED_SOURCE_NORM | 4 | 9 | 27 | 0.415252058 |
| Q12-E001/SOURCE_BALANCED_ERM | 4 | 9 | 27 | 0.431841564 |
| Q12-E001/SOURCE_GROUP_DRO | 4 | 9 | 27 | 0.367348251 |
| Q12-E001/SOURCE_POOLED_WHITEN | 4 | 9 | 27 | 0.443351337 |
| Q12-E002/CHANNEL_AND_GAIN | 4 | 9 | 27 | 0.409207819 |
| Q12-E002/CHANNEL_DROPOUT | 4 | 9 | 27 | 0.410043724 |
| Q12-E002/GAIN_PERTURB | 4 | 9 | 27 | 0.434220679 |
| Q13-E001/Q8_FIXED20 | 4 | 9 | 27 | 0.439879115 |
| Q13-E001/Q9_SHARED_FIXED20 | 4 | 9 | 27 | 0.439750514 |
| Q13-E001/Q9_SHARED_RAW_CE | 4 | 9 | 27 | 0.400655864 |
| Q13-E004/Q8_SRC2 | 4 | 9 | 108 | 0.329571759 |
| Q13-E004/Q8_SRC4 | 4 | 9 | 108 | 0.388904964 |
| Q13-E004/Q8_SRC6 | 4 | 9 | 108 | 0.431552212 |
| Q13-E004/Q9_SHARED_SRC2 | 4 | 9 | 108 | 0.347431199 |
| Q13-E004/Q9_SHARED_SRC4 | 4 | 9 | 108 | 0.388888889 |
| Q13-E004/Q9_SHARED_SRC6 | 4 | 9 | 108 | 0.424848894 |
| Q13-E005/Q8_SOURCE_SESSION_E | 4 | 9 | 27 | 0.414030350 |
| Q13-E005/Q8_SOURCE_SESSION_T | 4 | 9 | 27 | 0.422453704 |
| Q13-E005/Q9_SHARED_SOURCE_SESSION_E | 4 | 9 | 27 | 0.418917181 |
| Q13-E005/Q9_SHARED_SOURCE_SESSION_T | 4 | 9 | 27 | 0.418081276 |
| Q13-E006/Q8_RAW_CE_MATCHED | 4 | 9 | 27 | 0.339248971 |
| Q14-E001/BROAD_EEGNET | 2 | 9 | 27 | 0.682098765 |
| Q14-E002R2/BROAD_EEGNET | 2 | 109 | 327 | 0.618145919 |
| Q14-E001/MU_BETA_SHARED | 2 | 9 | 27 | 0.673482510 |
| Q14-E002R2/MU_BETA_SHARED | 2 | 109 | 327 | 0.623878881 |
| Q14-E001/CSP4_LDA | 2 | 9 | 9 | 0.615354938 |
| Q14-E002R2/CSP4_LDA | 2 | 109 | 109 | 0.544617198 |
| Q5-HISTORICAL/RAW_CE_REUSE | 4 | 9 | 27 | 0.337191358 |

## Matched and reported contrasts

All6 saved Q12 and11 Q13 means, person-bootstrap intervals, exact sign-flip values and within-family Holm values were recomputed. All99 Q13 saved person differences were checked. Other contrasts are explicitly exploratory descriptive calculations, without fabricated correction families.

| Contrast | Mean BA difference | 95% person-bootstrap CI | Sign-flip p | Holm where declared |
| --- | ---: | --- | ---: | ---: |
| Q8_MEAN_RANK_minus_historical_RAW_CE | +0.089506173 | [+0.010545267,+0.200167181] | 0.015625 | not declared |
| Q9_shared_minus_mid | -0.023662551 | [-0.047710905,-0.001671811] | 0.109375 | not declared |
| Q9_shared_minus_Q8 | -0.004822531 | [-0.032021605,+0.014274691] | 0.914062 | not declared |
| Q9_mu_minus_mid | -0.012538580 | [-0.036329733,+0.009903871] | 0.359375 | not declared |
| Q9_beta_minus_mid | -0.130208333 | [-0.233093814,-0.045516654] | 0.015625 | not declared |
| Q9_shared_Q8epochs_minus_mid_Q8epochs | +0.007716049 | [-0.003086420,+0.019418724] | 0.281250 | not declared |
| Q9_source_clean_minus_shared | -0.000771605 | [-0.012924383,+0.014724794] | 0.933594 | not declared |
| Q9_source_norm_minus_shared | -0.006622942 | [-0.026043274,+0.010416667] | 0.621094 | not declared |
| SOURCE_POOLED_WHITEN-Q8-E001 | +0.016653807 | [-0.003922325,+0.036651235] | 0.179688 | 0.359375 |
| SOURCE_BALANCED_ERM-Q8-E001 | +0.005144033 | [-0.007073045,+0.017746914] | 0.476562 | 0.476562 |
| SOURCE_GROUP_DRO-SOURCE_BALANCED_ERM | -0.064493313 | [-0.114711934,-0.017875514] | 0.046875 | 0.140625 |
| CHANNEL_DROPOUT-Q8-E001 | -0.016653807 | [-0.045076196,+0.006365741] | 0.300781 | 0.761719 |
| GAIN_PERTURB-Q8-E001 | +0.007523148 | [-0.003407922,+0.018582819] | 0.253906 | 0.761719 |
| CHANNEL_AND_GAIN-Q8-E001 | -0.017489712 | [-0.050540123,+0.009130658] | 0.351562 | 0.761719 |
| Q8_BROAD_k2_minus_k8 | -0.110307356 | [-0.187950505,-0.035604343] | 0.031250 | 0.164062 |
| Q8_BROAD_k4_minus_k8 | -0.050974151 | [-0.103604038,-0.003825874] | 0.144531 | 0.433594 |
| Q8_BROAD_k6_minus_k8 | -0.008326903 | [-0.036715535,+0.018889452] | 0.566406 | 0.566406 |
| Q9_MU_BETA_SHARED_k2_minus_k8 | -0.092319316 | [-0.154144563,-0.031458976] | 0.027344 | 0.164062 |
| Q9_MU_BETA_SHARED_k4_minus_k8 | -0.050861626 | [-0.092834121,-0.013085134] | 0.058594 | 0.234375 |
| Q9_MU_BETA_SHARED_k6_minus_k8 | -0.014901620 | [-0.034127443,+0.004163452] | 0.167969 | 0.433594 |
| Q8_BROAD_1test_minus_0train | -0.008423354 | [-0.018904321,+0.001930620] | 0.175781 | 0.351562 |
| Q9_MU_BETA_SHARED_1test_minus_0train | +0.000835905 | [-0.011381173,+0.011832883] | 0.851562 | 0.851562 |
| Q8_FIXED20_minus_Q8_RAW_CE_REUSE_Q5 | +0.102687757 | [+0.009580761,+0.216243891] | 0.101562 | 0.156250 |
| Q9_SHARED_FIXED20_minus_Q9_SHARED_RAW_CE | +0.039094650 | [+0.004436728,+0.076197595] | 0.078125 | 0.156250 |
| Q8_E006_RAW_CE_minus_Q8_FIXED20 | -0.100630144 | [-0.215284208,-0.006751543] | 0.125000 | 0.125000 |
| Q13_shared_fixed20_minus_broad_fixed20 | -0.000128601 | [-0.013568994,+0.015432099] | 0.996094 | not declared |
| Q14_binary_development_shared_minus_broad | -0.008616255 | [-0.020704733,+0.002957819] | 0.218750 | not declared |

## Q14 binary external primary

109 people,4918 unique trials,34426 prediction rows and763 person/model/seed cells. Shared mu/beta minus broad=+0.005732962 BA;95% person-bootstrap CI=[-0.000966827,+0.012415551], exact two-sided sign-test p=0.064463592;63 positive,43 negative,3 ties. The interval spans zero. These reproduce the passed portable validator using its frozen exact-zero tie rule; external superiority is not established. A1e-14 numerical tie-tolerance sensitivity yields63/42/4 signs andp0.050442, also above0.05; it is not substituted for the frozen primary test.

## Q13 E006 versus the historical duration claim

Historical fixed20 minus reused Q5 rawCE=+0.102687757; preferred matched-runtime fixed20 minus historical rawCE schedule=+0.100630144. E006 preserves direction and approximate magnitude. Its exact sign-flip p=0.125; it does not establish a significant general superiority claim or rerun inner selection under the new runtime.

## Scientific status and limits

- research_runs/Q8-E001/analysis/validation_report.json: passed
- results/Q9-BATCH/validation_report.json: passed_orchestration_only
- results/Q12-BATCH/scientific_validation.json: passed_scientific_checks
- results/Q13-BATCH/validation_report.json: passed
- results/Q13-E006/validation_report.json: passed
- results/Q14-E001/validation_report.json: True
- results/Q14-E002R2V1/validation_report.json: portable_independent_external_validation_passed
- results/Q14-R2BATCH/batch_status.json: failed_stopped
- results/Q14-E002R2/external/completion_receipt.json: all_109_subjects_inferred_under_r2_amendment

- CSV arithmetic and saved identity checks are independently recomputed; raw EEG/checkpoints and historical scientific validation are not rerun.
- Q9 batch status passed_orchestration_only is not scientific validation; this check does not promote it to checkpoint-replayed pass.
- Four-class BNCI chanceBA0.25 and binary BNCI/PhysioNet chanceBA0.50 differ in task and acquisition/population; do not pool/rank raw BA as one endpoint or isolate causal dataset-shift from the gap.
- Q8/Q9/Q12/Q13 reuse an already explored9-person BNCI cohort. Seeds/subsets/trials/sessions do not enlarge n; LOSO training sets overlap.
- Q13 source counts also change natural optimizer-update exposure; E006 tests only the frozen historical epoch schedule under matched runtime.
- Q14 primary positive point estimate has CI spanning zero and sign-test p>0.05; external superiority is not established.
- Disclose Q14 post-freeze metadata-triggered128-to160Hz rate amendment after partial external execution and later validation-only portability amendment; retain original failed R2 attempt.

## Recomputed versus attributed evidence

Recomputed: all selected saved prediction rows and BA cells, every person mean, all6 Q12 and11 Q13 reported contrasts/bootstrap/sign-flip/Holm values, all99 Q13 paired differences, all763 Q14 external cells and the109-person primary bootstrap/sign test. Attributed without rerun: raw-signal/checkpoint reconstruction, training/source-split/leakage validation and original scientific-pass receipts. Each controlling input is hashed below.

Reported-statistic discrepancies: 0. The JSON companion records exact errors, coverage, all person means/differences, per-seed means and paths.

| Input | SHA-256 |
| --- | --- |
| research_runs/Q13-E006/AMENDMENT.md | 0b7da50ee7a52d62458ad6e45a3bf4b7ee69d848eddbf2199f0ffb8bd439fbbb |
| research_runs/Q8-E001/analysis/validation_report.json | 167edce7058fcf958176ac6765c92f5827e2330284fcf9e3dff9709a3a21a5aa |
| research_runs/Q8-E001/results/per_subject_metrics.csv | 3a36bf0c67eea872613b7afca4beadd1a03734069365a5c6904a34b9342bc67b |
| research_runs/Q8-E001/results/predictions.csv | 1c468c09f80ea96151b666f339ed582ef1f58dbad775b9e2c0e9addd262b8f4d |
| results/Q12-BATCH/paired_subject_contrasts.json | 3f32f1321ff833bc2a74b93bde40312bd4a5c96eca4b89321d8080cfadd4d97d |
| results/Q12-BATCH/scientific_validation.json | 739910ee03b008fb374c7b026bbade0dc6b6d8ef0016cda3fac19a071c53e7e6 |
| results/Q12-E001/SOURCE_BALANCED_ERM/per_subject_metrics.csv | 9db432d32811f0eeaabe7f89a2941425ff90028826eded33bcc3cdf9a0cdebb9 |
| results/Q12-E001/SOURCE_BALANCED_ERM/predictions.csv | 8daa9cbca9ba01c762fb01a2db1b72381fb772ac0e18878e8a0dccc538714027 |
| results/Q12-E001/SOURCE_GROUP_DRO/per_subject_metrics.csv | 23c8ebb7f5606bb84717d99e0644e5bb7a07fcc04650fc8d075b51dd60c452b6 |
| results/Q12-E001/SOURCE_GROUP_DRO/predictions.csv | 9bd4da51e698b19328c013120757b30139e43f3b615d10a4bedb87cc865feaa7 |
| results/Q12-E001/SOURCE_POOLED_WHITEN/per_subject_metrics.csv | 1909cef92d7e18bee645aede16a94bf209b47b4bde9f7f931795a3ad773ae1c8 |
| results/Q12-E001/SOURCE_POOLED_WHITEN/predictions.csv | e57234282f4c5503a47872c3af8be0ed167c4cfdc82ca948af6e5af06c2aebbf |
| results/Q12-E002/CHANNEL_AND_GAIN/per_subject_metrics.csv | 606d7e265ea81e9a827633e38f73d4b9a73ab2160fb5f32d934201af1007931f |
| results/Q12-E002/CHANNEL_AND_GAIN/predictions.csv | 1ca6ba6ace4b50af1dc286b2f066b689665d54c8913140554c6cf0864421f921 |
| results/Q12-E002/CHANNEL_DROPOUT/per_subject_metrics.csv | 42d2e4111852836d1fe469df64526387ea9c6aab0873b9421563949be1163373 |
| results/Q12-E002/CHANNEL_DROPOUT/predictions.csv | 597f5a38e1e1298c7a65e4f78c78b003d11ba5c47433b6304ab5d4a6fa105aec |
| results/Q12-E002/GAIN_PERTURB/per_subject_metrics.csv | a6856dbe04b959f651b2a4a8f93084e9dd6ea09019b6f2feb5540be139df5d52 |
| results/Q12-E002/GAIN_PERTURB/predictions.csv | e6ff78877897e286d2ce967121db80c7c576f7cc079151000c61ffdbe6e7b419 |
| results/Q13-BATCH/validation_report.json | 3d21dbb98d775a19f8328dc4ad4a5d285c6c4ee18204b22543561c4ee14a0266 |
| results/Q13-E001/Q8_FIXED20/per_subject_metrics.csv | 0293d77127d2aa2a343e48cfeaf5ca5df4cbc0710d28057f40b0da774c8107ac |
| results/Q13-E001/Q8_FIXED20/predictions.csv | 1262c152b8b56f87fee6ed79eeb50785e74900048d9b29c6f324e6e4a3c55b25 |
| results/Q13-E001/Q9_SHARED_FIXED20/per_subject_metrics.csv | 8b51132f3124ceba34cbd317270a7862391af07590ffef78a0d0643e6ac95612 |
| results/Q13-E001/Q9_SHARED_FIXED20/predictions.csv | 26f50f96b75b93d26c6daec1afbbee2f38e362df84801d983cbbcd835d72f2df |
| results/Q13-E001/Q9_SHARED_RAW_CE/per_subject_metrics.csv | f29eff1a3e9fbf45dec214a8cdc00caad153bf8ff455e8bffbcb50b50a2927eb |
| results/Q13-E001/Q9_SHARED_RAW_CE/predictions.csv | 96a57278c0f39946b37c2c09e9df1e9d576968b214145da2bf271fdb53748550 |
| results/Q13-E004/Q8_SRC2/per_subject_metrics.csv | 9ee14cf39e616878fc181404bb5a956a374ec491896547bc88502aacf18642b9 |
| results/Q13-E004/Q8_SRC2/predictions.csv | d27a28bb49ab7a105fc44adf8e6f4b1446f32fec419bc3a5a9997f0e597f5b44 |
| results/Q13-E004/Q8_SRC4/per_subject_metrics.csv | f0b3d10c11bcc5ec3c53c515de1f3e2892ff205f2b3f62e305b31548e9ea1d4b |
| results/Q13-E004/Q8_SRC4/predictions.csv | 4aa6ac97805e4c02dea0def0f63c58a28fe5d44abd1a615511420c26b148dfb4 |
| results/Q13-E004/Q8_SRC6/per_subject_metrics.csv | ed819467f3e8769056e168e629274c2c588384e3711165877226ea1b2e318afb |
| results/Q13-E004/Q8_SRC6/predictions.csv | ca6317613478c1396f71c9ddbe681ca0a501fd8b38267b0e3a598eefbbbc23f8 |
| results/Q13-E004/Q9_SHARED_SRC2/per_subject_metrics.csv | 36eecdd78fc5808cd7c9d8068af936a330e4bebfa24d2c73921f73ed16d09137 |
| results/Q13-E004/Q9_SHARED_SRC2/predictions.csv | 22574c1b35ef45ad3cf28ba0e30043176dc0eb2441066d7a5d3efdcba4ec0060 |
| results/Q13-E004/Q9_SHARED_SRC4/per_subject_metrics.csv | a8142d1c0f8e970a3f7280401e5f248b80b416748e15b20386c5b546e2c61c37 |
| results/Q13-E004/Q9_SHARED_SRC4/predictions.csv | d13332543638b3020437cc0edecc91ad34773f4bf8a682ecc2d9cb24e44ec8c0 |
| results/Q13-E004/Q9_SHARED_SRC6/per_subject_metrics.csv | 7bd0c342dc97ca73248d2e3c2e59abefb708c865fe8401fa79fca84b5975abb8 |
| results/Q13-E004/Q9_SHARED_SRC6/predictions.csv | e4b150d6ab2e56a102f9c1ec884ad8726003794a7aa6982d356da8d23c7a68ef |
| results/Q13-E005/Q8_SOURCE_SESSION_E/per_subject_metrics.csv | 90414e07b0b6b277e657c6ec94c7ef599e454d9cd598a73ab7705f1f2be60689 |
| results/Q13-E005/Q8_SOURCE_SESSION_E/predictions.csv | 621acde75da1cd90ff8e3d8339a28ca57c139260a1428910e31bbfc0cde39e30 |
| results/Q13-E005/Q8_SOURCE_SESSION_T/per_subject_metrics.csv | 4be88138c732ad5136c6267fc67009a019947996b6ca5218eb35611a1c8ef79d |
| results/Q13-E005/Q8_SOURCE_SESSION_T/predictions.csv | 8c3689332a3a01067dbf1fe6a9d4f584f8fcb89f6dc7b1ebf7f76f0376c799ed |
| results/Q13-E005/Q9_SHARED_SOURCE_SESSION_E/per_subject_metrics.csv | b7d6f06e6d1120766cec8dce9344bac2efd250a8770e281748e41da452ca4ff8 |
| results/Q13-E005/Q9_SHARED_SOURCE_SESSION_E/predictions.csv | 90820774ce75cb42f7794dd367bd97130197c182d48683358c99555b517e2e4a |
| results/Q13-E005/Q9_SHARED_SOURCE_SESSION_T/per_subject_metrics.csv | dd0197926b8488c6b20fd04c02d3ab511a30076b22cdb790a492b4be031668fa |
| results/Q13-E005/Q9_SHARED_SOURCE_SESSION_T/predictions.csv | 9531f23070c3a38fd9fc0ce7fdc8dc153c52247551c15ea200a4a5d27a0cb740 |
| results/Q13-E006/Q8_RAW_CE_MATCHED/per_subject_metrics.csv | bada29064aedb0febc6683b91b8dd0875fc28f6cc59958983eacd45db5387cc4 |
| results/Q13-E006/Q8_RAW_CE_MATCHED/predictions.csv | b55a5be08eed454927cc2240881277fc1b57ebfc292f6c69bea866273612b51a |
| results/Q13-E006/postrun_statistics/paired_contrasts.csv | 81ef4b4236c08f1bf597cc3001bda9d0877d6cdbfcc5daf74698226bc20d0239 |
| results/Q13-E006/postrun_statistics/subject_paired_differences.csv | f0b6e890226741b8be6122c7ce2fd06f718208d941fa69fef753fcc3b2c89a29 |
| results/Q13-E006/validation_report.json | ef60b412b8724dd51d648c8bc51e8f74ad5ace470bca93c0f2327ac959dd1ddd |
| results/Q14-E001/BROAD_EEGNET/target_01/final_seed_20260924/predictions.csv | c7152e3aa085bd9586c4fbcb335cf2a4d056970629aa9bc3b0ba93ba8a21022c |
| results/Q14-E001/BROAD_EEGNET/target_01/final_seed_20260925/predictions.csv | de7bbd5db2a042f1cf9c1a938431e0eeb49ca299dd6cde9486f6f5f15efe095b |
| results/Q14-E001/BROAD_EEGNET/target_01/final_seed_20260926/predictions.csv | 446e17acc54790153ce1b1461a3825669fea6b756d72b1400afeda007d1a837d |
| results/Q14-E001/BROAD_EEGNET/target_02/final_seed_20260924/predictions.csv | 8d7fd44187ba53480ee3cf36f66f52a73ceb7601171590dc6b9102c47a3632cb |
| results/Q14-E001/BROAD_EEGNET/target_02/final_seed_20260925/predictions.csv | 252d15b476da0f9e8b0054688e6f317a29cdba3b5096c11138a94d9209c46d4c |
| results/Q14-E001/BROAD_EEGNET/target_02/final_seed_20260926/predictions.csv | a8b23070e49f75fb82b9d6852953e24f659b40df32c17815ac92413549abb2c9 |
| results/Q14-E001/BROAD_EEGNET/target_03/final_seed_20260924/predictions.csv | de4983ec9537343a2e3f5a3d9fe7ad09e11ac0f75e74cd8acac926774af45002 |
| results/Q14-E001/BROAD_EEGNET/target_03/final_seed_20260925/predictions.csv | ee6d1989dddd86a59e86a01ccdafdfce9b8654176b588c83a099cff0ea1e2b6a |
| results/Q14-E001/BROAD_EEGNET/target_03/final_seed_20260926/predictions.csv | 1fae5a3c98d44d383fb3cd054e54755220e45c45d7747a36daea2f2a339e32e7 |
| results/Q14-E001/BROAD_EEGNET/target_04/final_seed_20260924/predictions.csv | bb38df56f22734c7a93a943f6cb473458ca0eae5a77e4b1296baeb32f6134bf5 |
| results/Q14-E001/BROAD_EEGNET/target_04/final_seed_20260925/predictions.csv | ddb91551fba226c924d843946cdbd76fbcf8d8de2c1bf49b29cdbace0cb9d794 |
| results/Q14-E001/BROAD_EEGNET/target_04/final_seed_20260926/predictions.csv | f37916338b6eeb5a95311aef5069dbb8ea28b635110f0e782dfc08f0d41ee029 |
| results/Q14-E001/BROAD_EEGNET/target_05/final_seed_20260924/predictions.csv | 17ebad4657a993bebfab5ee6ed9aa1d9c09283db8c0490934b1113c4cedbb65c |
| results/Q14-E001/BROAD_EEGNET/target_05/final_seed_20260925/predictions.csv | e8c2b8542a642344b803fa5a8e8d68c3e1ec4ea794434413cf8433c97649c8bd |
| results/Q14-E001/BROAD_EEGNET/target_05/final_seed_20260926/predictions.csv | 86f3a05a2bfd7e1d3717ab01b38f2eb9b3e4bb0f37e43d637ff3e461ccc43b4d |
| results/Q14-E001/BROAD_EEGNET/target_06/final_seed_20260924/predictions.csv | e4eb57b463128e377222770f6b9b66e40333e8c532d861ee4c0c3c9acad7a363 |
| results/Q14-E001/BROAD_EEGNET/target_06/final_seed_20260925/predictions.csv | 0678ca71dc601e8f92fb74bd61a9f4d87e6802f5baf75edf0385933028fab46f |
| results/Q14-E001/BROAD_EEGNET/target_06/final_seed_20260926/predictions.csv | 3c67d2d4d3102f91a8d98464587c2a35712e16316e883882579109c7c611a189 |
| results/Q14-E001/BROAD_EEGNET/target_07/final_seed_20260924/predictions.csv | b2c063c9fa3718515811d3365c02a639a6a91577db61b66cbb94e586b316c3e7 |
| results/Q14-E001/BROAD_EEGNET/target_07/final_seed_20260925/predictions.csv | 5efc2e8236534df72f2f86a9702a77b4878da27507fce0690fcb3fd0ace3b733 |
| results/Q14-E001/BROAD_EEGNET/target_07/final_seed_20260926/predictions.csv | ae8a1d9575915d4cdf2cd66f2219f2092dce6c6aa014b5a768977c8f15794e53 |
| results/Q14-E001/BROAD_EEGNET/target_08/final_seed_20260924/predictions.csv | 3b6397a50c75a81808dd635a0a1cdb499e551c6966140291b2f613c275a81b01 |
| results/Q14-E001/BROAD_EEGNET/target_08/final_seed_20260925/predictions.csv | 4fd1de72d045a7e263a8015e15eaef05e61e35d9b69481d680a7fca63c707db8 |
| results/Q14-E001/BROAD_EEGNET/target_08/final_seed_20260926/predictions.csv | 828bdcb5a5d0ab5ca5c977f00aa8cf16edb011b1c0ad89e538184ccc1cf4a2b1 |
| results/Q14-E001/BROAD_EEGNET/target_09/final_seed_20260924/predictions.csv | 03cbe7e171bccdb211863eb3816a36f0c6ff2c0449871dfc655627413c9215ea |
| results/Q14-E001/BROAD_EEGNET/target_09/final_seed_20260925/predictions.csv | b3a6ab0df4ab1b2194b00a720b22344b949db65f4258a5049f6b86104f02cea5 |
| results/Q14-E001/BROAD_EEGNET/target_09/final_seed_20260926/predictions.csv | 25cbb29bbff554be1ec578df421132593c9e8d2ba47418d9c695614477992f29 |
| results/Q14-E001/CSP4_LDA/target_01/predictions.csv | 260ff218d43ab990a703ed8e84dd113b35d1aaa3e87b23fd5367f624e802f807 |
| results/Q14-E001/CSP4_LDA/target_02/predictions.csv | 21e510c284667dbb109012025cea192cbe39a447ea4154d2c50e4ac3c475ab51 |
| results/Q14-E001/CSP4_LDA/target_03/predictions.csv | 7bf5836ff53ee95301b1dffc136edb0feb5da767c1992d61cfc2e3813120d413 |
| results/Q14-E001/CSP4_LDA/target_04/predictions.csv | 300ca64f42e0cdf367ccd0a0fced7ad9eb692e787c3125558a5f1f8393def722 |
| results/Q14-E001/CSP4_LDA/target_05/predictions.csv | 9ef97f26931d1e5cfe826bc371e9d5e8df3d56de36269bcd1ba3c95a3607c688 |
| results/Q14-E001/CSP4_LDA/target_06/predictions.csv | 3989a59b1d57b6acf366f06eed52cafcc40b8bd069980499122b613a5c12aa13 |
| results/Q14-E001/CSP4_LDA/target_07/predictions.csv | 345c7134569c25ece7c82355ef7ab07e7ebdf3c8e321fc0b70498578210cc015 |
| results/Q14-E001/CSP4_LDA/target_08/predictions.csv | acdf0e6792eb3a1441f699f140d77c89726168fce5625fd97dc25c2341ea7146 |
| results/Q14-E001/CSP4_LDA/target_09/predictions.csv | c52fc580aabf7fb75d567910cf3ded59bd0efba5dde76f8387cc589ee09fb889 |
| results/Q14-E001/MU_BETA_SHARED/target_01/final_seed_20260924/predictions.csv | 24b13862665425c81198b2665ab7c67d8b9740124b5c30bc375ce5727ea4f03e |
| results/Q14-E001/MU_BETA_SHARED/target_01/final_seed_20260925/predictions.csv | 82807206d67166622ac7abe0c14f8c818fb47c840e74ac9ec218688408a45679 |
| results/Q14-E001/MU_BETA_SHARED/target_01/final_seed_20260926/predictions.csv | 792b3a5cfa9125e6c8c27349a6ac15dc733523d6a1056524f28de7bb65c10d1d |
| results/Q14-E001/MU_BETA_SHARED/target_02/final_seed_20260924/predictions.csv | b8e0094539ff7f319c4e8a544220737bc871ce2746a94f039af74342f0ea2266 |
| results/Q14-E001/MU_BETA_SHARED/target_02/final_seed_20260925/predictions.csv | 6b4d847bf894e2344775360206da004b23c3ac83e492225344d49a53d2e0c24e |
| results/Q14-E001/MU_BETA_SHARED/target_02/final_seed_20260926/predictions.csv | 0648d28951fce91aadbf962cb3426dc69a3f09c26e3167ee4dae77bb83c4e2f2 |
| results/Q14-E001/MU_BETA_SHARED/target_03/final_seed_20260924/predictions.csv | 07e2ae2648af245a6e2c937285bea32c3b32e107635044e385731e4fa8c77912 |
| results/Q14-E001/MU_BETA_SHARED/target_03/final_seed_20260925/predictions.csv | 0bee00e2b072b91fec85addaa4818480262e0cd3db462ad4069bd9212643a30c |
| results/Q14-E001/MU_BETA_SHARED/target_03/final_seed_20260926/predictions.csv | 85e5be601d84df6d7870a5a08838b6628a2ac27c734833542a5ff816ec92200d |
| results/Q14-E001/MU_BETA_SHARED/target_04/final_seed_20260924/predictions.csv | 1ff5850beba4473fa98fdde27cb993791397701540bec62a6d96753d533ac3fc |
| results/Q14-E001/MU_BETA_SHARED/target_04/final_seed_20260925/predictions.csv | aae5555e7fa2d5c04ed9c4e31a19d4133d6453b1b9ed523899b100d8aa875ab4 |
| results/Q14-E001/MU_BETA_SHARED/target_04/final_seed_20260926/predictions.csv | 90ed95f6bcf2962891f2c82e5c6e07cfd4495fbadc2435aabed1404f756aa228 |
| results/Q14-E001/MU_BETA_SHARED/target_05/final_seed_20260924/predictions.csv | 07ed5ca053c5890943d3da6f4abf21ea6cd64b186a4a6f85dc1aa529cb6166f1 |
| results/Q14-E001/MU_BETA_SHARED/target_05/final_seed_20260925/predictions.csv | 4674be59763787efad8fd2d01ea054debd0f4929d6d0e6a53e10c1eb57ea9df4 |
| results/Q14-E001/MU_BETA_SHARED/target_05/final_seed_20260926/predictions.csv | 2e6665c6ddce1d25864ca8736580728290783f006ce16b9e43474900c523e8ff |
| results/Q14-E001/MU_BETA_SHARED/target_06/final_seed_20260924/predictions.csv | 607135f596a57d030513c2132a0b67ca69d1f3a1f900386951ef24f6172b04a1 |
| results/Q14-E001/MU_BETA_SHARED/target_06/final_seed_20260925/predictions.csv | c28c06b58dab04bcc2b52bf5f8448c712392c0ea3c2f988b986fcc85c1da8627 |
| results/Q14-E001/MU_BETA_SHARED/target_06/final_seed_20260926/predictions.csv | 612c6a8712dab63272a3326c54e61ff118e4ec65b4176710a868973450a5a70a |
| results/Q14-E001/MU_BETA_SHARED/target_07/final_seed_20260924/predictions.csv | 616f0ed1d21d92eada266afe3633d0aea216633998931e2204ad4232ff97fd44 |
| results/Q14-E001/MU_BETA_SHARED/target_07/final_seed_20260925/predictions.csv | 354cfb1d84bff680f7314473badcd142ccf37251923d426726ab63f9180ac884 |
| results/Q14-E001/MU_BETA_SHARED/target_07/final_seed_20260926/predictions.csv | dc04465942dde8d7125b6337d5630afdedc6fc109c7ba1d4053b668081c42bff |
| results/Q14-E001/MU_BETA_SHARED/target_08/final_seed_20260924/predictions.csv | fded2c3a4ee3d6c70096dd2725fa2b8f07c1a6a77c8f1a6a39afaf324a10822e |
| results/Q14-E001/MU_BETA_SHARED/target_08/final_seed_20260925/predictions.csv | 6630da8bfbb2be75da5e1ee2ec151142538f0f3aabef7c41727e0ed6f44ef4d8 |
| results/Q14-E001/MU_BETA_SHARED/target_08/final_seed_20260926/predictions.csv | 7c22e69b1ebeb819074cb25b71b3df47a9999eee47a6cba03612d5b0276c60c6 |
| results/Q14-E001/MU_BETA_SHARED/target_09/final_seed_20260924/predictions.csv | 6bb078b34a8ebb84402a2074fb3f3a07dc15b8d78561e8443318b84c7b93f129 |
| results/Q14-E001/MU_BETA_SHARED/target_09/final_seed_20260925/predictions.csv | 054fde23b5d205226569ba6103338012f6fc05d8abb6d19b49be700b09f749ff |
| results/Q14-E001/MU_BETA_SHARED/target_09/final_seed_20260926/predictions.csv | 1f7e0b82c670973f2e0cf3be740c4cb266b767e4c34c4db15c5eccede95f865e |
| results/Q14-E001/subject_seed_metrics.csv | b756700f8e22f7dcb760c8f9ee7a4e0fa7f42d9f93c237d29ab728a66d4a7de5 |
| results/Q14-E001/validation_report.json | f96296e2dec3bb45f1eddca2deb0fa4b200f2ab3066f60e4e646232b6e414d53 |
| results/Q14-E002R2/external/completion_receipt.json | b3199f751049b10a1a8b6751cbbab9d4722b4b91602e119c02ec2decdf4fd7b2 |
| results/Q14-E002R2/external/predictions.csv | fde382e9e637445ba276449224d65dbdea40ea31c209b35ec8c3075035f52e6e |
| results/Q14-E002R2V1/external/subject_metrics.csv | 2199c89b591d7f0c87fbb02ed3fd8146e7f27c174ccd6c6bd2399db487ce5e54 |
| results/Q14-E002R2V1/external/subject_primary_contrast.csv | 23c03eef128b79c2f5c853aadb1e743dc8846fe692aa6d3578980481f79cb4e0 |
| results/Q14-E002R2V1/external/subject_seed_metrics.csv | 4bbd74158d8780dfa06f03fcfd60afa871e2da97244e31c60eab6ce7ee568b8b |
| results/Q14-E002R2V1/validation_report.json | 1ed3959b303c06672257963ef177f8c7ef619bcac01e4a263cfd587e7d9b5320 |
| results/Q14-R2BATCH/batch_status.json | 20ed51e42bed3bdad1690e379e12e90b32902ce8e0fdc4e41fd57b21684869fb |
| results/Q5-E001/per_subject_metrics.csv | 3c72e370b9fd590cf154106bb1710089decb37e5c9e0ce1a370b658b01287a21 |
| results/Q5-E001/predictions.csv | 438364a8dee3b7d605bede33ab58278b1dfa9b82aaf4969d7815789d12876a33 |
| results/Q9-A001/per_subject_metrics.csv | 58afc1640c501943fb73d273561e1d5bcbe357e29173c8c6d855510acb103706 |
| results/Q9-A001/predictions.csv | c045a17aab8bbd284206b0e93b29bd32fea6892c5fdfc1d1eb6d63a1993af747 |
| results/Q9-BATCH/validation_report.json | 85fd34163ac72a9ff91d1b4ae965e5da2beb0a7a8260bb138adfe3ad26562d21 |
| results/Q9-E001/BETA_13_30/per_subject_metrics.csv | 9827ac22189e3de846af060fbee2b0f1da4e1c85b5d3f82af53ba5ecf55ba284 |
| results/Q9-E001/BETA_13_30/predictions.csv | 891259ea9a295d0759c2ac0b95cccba0fd85ddc53530cff07975e17a2c90a21a |
| results/Q9-E001/MID_8_30/per_subject_metrics.csv | 452ce6e13f269b35c6c7e5fa04207877fc53eea62e99581e04fe0cb4a9cd8cdd |
| results/Q9-E001/MID_8_30/predictions.csv | 98b9b2508b410d589a9b7a2ca05d24a58fba4a6325654d0923bb28f1c6889570 |
| results/Q9-E001/MU_8_13/per_subject_metrics.csv | f5a090c7ed0ca42f61535d4e928175aaab4540e4639ac34f9de4c6bf991f339d |
| results/Q9-E001/MU_8_13/predictions.csv | d4b74745f300f3c7a90d215e8077d6ac87de6fe96a22cd95c43976d21f96a298 |
| results/Q9-E001/MU_BETA_SHARED/per_subject_metrics.csv | 140c1e5e21d1ac39180161ddccb8ce1362936d3226bf9225bde7bf9897d64edd |
| results/Q9-E001/MU_BETA_SHARED/predictions.csv | 9774b3db174d2510d466bf034165331bf697ddf0344af110d64e040dff3ce488 |
| results/Q9-E002/MID_8_30_Q8_EPOCHS/per_subject_metrics.csv | 52f04307aea3235ad08cc1cee927b9a89d41727a6ed83a943cc78b77dc7afb3f |
| results/Q9-E002/MID_8_30_Q8_EPOCHS/predictions.csv | fb7e86ad560ee4b0e0da36279f61f9871b2509dbaba57b81686ac765e7064452 |
| results/Q9-E002/MU_BETA_SHARED_Q8_EPOCHS/per_subject_metrics.csv | 11a96d891f3cab43267da98cb324589fc0f60d830bdbf35e1c7d900f27e146d9 |
| results/Q9-E002/MU_BETA_SHARED_Q8_EPOCHS/predictions.csv | 113a8af21c62df3e1898b2b8f471d93147017ca126d1367e6a16bedd8a292352 |
| results/Q9-E004/MU_BETA_SHARED_SOURCE_CLEAN/per_subject_metrics.csv | 13161df126aae41343b85bdb4cd11067e17d77139cd5ee10a929827152cced1b |
| results/Q9-E004/MU_BETA_SHARED_SOURCE_CLEAN/predictions.csv | 389d5b4c23f9dfe2dc9ea9170c280f213d2bd66612ee3a1311da15943ceeeb9c |
| results/Q9-E005/MU_BETA_SHARED_SOURCE_NORM/per_subject_metrics.csv | 1daaca8f01dcc8e9134805de43bed8e5d9d9762405a3bca1e7a2255962a56cfa |
| results/Q9-E005/MU_BETA_SHARED_SOURCE_NORM/predictions.csv | c4c33b156d3a8bf583246e5181d6f0bd77b3f92e06a765a017a5ff97db26401c |
| scripts/q13_e006_postrun_stats.py | 4c3276921be3173e96c3c86ea8090ded00e32a5db14e67bb1e2d828b615d17f6 |
| scripts/q14_r2_validate.py | 7c3deebc223fd1b248bf408ac829974637bad1d0671064cee612195d29c83d2e |
| scripts/validate_q11_e001.py | 5e21c90a1a3c614ab4b09380aba2b27b6339bb379bf06b75b9e0a8608ade3858 |
