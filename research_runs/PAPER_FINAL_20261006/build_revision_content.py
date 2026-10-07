"""Restructure the audited manuscript without changing archived decoder results.

This module only builds text blocks from completed, verified Q16 outputs;
it performs no model or raw-data work.
Citations use the original references.json order and are remapped by build_content.
"""
from __future__ import annotations

import copy
import re


def paragraph(text):
    return {'type': 'paragraph', 'text': text}


def heading(text, level=2):
    return {'type': 'heading', 'level': level, 'text': text}


def make_table(label, headers, rows, note):
    return {'type': 'table', 'label': label, 'headers': headers, 'rows': rows, 'note': note}


def revise_blocks(original_blocks):
    blocks = copy.deepcopy(original_blocks)

    def index(text):
        matches = [i for i, b in enumerate(blocks)
                   if b['type'] == 'heading' and b['text'] == text]
        if len(matches) != 1:
            raise ValueError(f'Expected one section named {text!r}, found {len(matches)}')
        return matches[0]

    def contents(text):
        start = index(text) + 1
        end = next((i for i in range(start, len(blocks))
                    if blocks[i]['type'] == 'heading'), len(blocks))
        return copy.deepcopy(blocks[start:end])

    def section(text, new_heading):
        return [heading(new_heading)] + contents(text)

    introduction = contents('1. Introduction')
    if len(introduction) != 5:
        raise ValueError('Audited introduction shape changed; review section extraction.')

    # The structured abstract describes complete selected pipelines because
    # external epoch schedules differ. Physiology remains post-outcome context.
    blocks[1]['text'] = (
        'Objective. We examined source-only training-duration selection and fixed shared mu/beta '
        'input pipelines for cross-subject motor-imagery EEG decoding. Approach. An exploratory '
        'four-class study used nine BNCI2014_001 participants, excluding both target sessions from '
        'each corresponding fit and selection. Separate frozen binary pipelines were evaluated '
        'on PhysioNet (109 people), Cho2017 (52) and Lee2019 offline-training runs (54, two sessions), '
        'without target fitting or adaptation. We re-audited saved predictions and source partitions. '
        'A downstream BNCI signal analysis, specified after decoder outcomes were known, described '
        'baseline-relative mu/beta power and associations with saved binary LOSO balanced accuracy. Main results. '
        'Mean-rank rather than mean-loss duration selection increased internal balanced accuracy '
        'from 33.72% to 42.67%; S3 and S8 contributed 87.57% of the aggregate gain. A matched-runtime '
        'fixed-duration control improved four of nine people despite a positive mean. Shared-minus-broad '
        'external differences were +0.573 percentage points (pp) on PhysioNet (95% person-bootstrap '
        'interval [−0.097,1.242]), −1.513 pp on Cho2017 [−2.249,−0.804] and +0.204 pp on Lee2019 '
        '[−0.515,0.969]. Cho2017 and Lee2019 Holm-adjusted permutation p-values were 0.000100 and '
        '0.604. These complete-pipeline contrasts used unequal source-selected durations. The BNCI signal '
        'analysis retained all 5,184 trials; its 2,592 hand-imagery trials gave mean signed laterality '
        'of −0.250 dB in mu and −0.168 dB in beta, with variable person-level signs. Significance. Training-duration choices yielded '
        'large but concentrated gains in this development benchmark. The shared-input pipelines offered no consistent '
        'external advantage. BNCI sensor patterns provide descriptive context; nine-person associations '
        'do not establish a decoder mechanism. Unknown voltage calibration and offline evaluation '
        'limit deployment conclusions.')

    related_work = [heading('2. Related Work', 1),
        paragraph('Spatial and spectral structure motivate classical motor-imagery decoders. '
                  'CSP estimates discriminative spatial projections from class covariance structure [4], '
                  'and filter-bank CSP combines spatial features across frequency bands [5,6]. '
                  'These approaches motivate the spatial and spectral controls here, although the '
                  'implemented filter bank is FBCSP-inspired rather than an exact reproduction. '
                  'Its projections, feature scaling and classifiers are fitted on source partitions '
                  'under the same target-information restriction as the neural models.'),
        paragraph('Compact convolutional models provide another representation family. EEGNet combines '
                  'temporal filtering, depthwise spatial filtering and separable convolutions [3]; '
                  'broader CNN work investigates learned EEG decoding and visualization [7]. '
                  'Our shared-input model sends predefined mu and beta views through one configured '
                  'EEGNet and averages class logits. Its parameter count matches one branch, while '
                  'two-view computation and shared BatchNorm exposure differ. The tested bands '
                  'are experimental views rather than verified physiological source separation.'),
        paragraph('Algorithm reviews and multi-dataset benchmarking emphasize variation between methods, '
                  'people and datasets [16,17]. Model selection also belongs inside a domain-generalization '
                  'evaluation [18]. We distinguish fitting restricted to source participants within a '
                  'repeatedly used development benchmark from external evaluation of frozen pipelines. '
                  'Methods that fit on target labels or unlabeled target distributions use a different '
                  'information budget and were not compared directly in this study.'),
        paragraph('Recent EEG pretraining studies broaden the representation-learning landscape. '
                  'LaBraM learns generic representations from large EEG collections [25], while '
                  'EEGPT uses pretrained transformers for transferable EEG representations [26]. '
                  'Their pretraining data and downstream fitting procedures introduce information '
                  'and computational budgets that must be specified for a fair comparison. We did '
                  'not evaluate either model or establish equivalence to our target-information '
                  'contract; the present findings concern the selected source-only pipelines.'),
        paragraph('Event-related desynchronization and synchronization describe decreases and '
                  'increases in spectral power relative to a reference interval [23]. '
                  'Earlier motor-imagery work investigated sensorimotor rhythm changes [24]. '
                  'These concepts motivate a separate measured-signal characterization, with '
                  'the baseline and estimator stated explicitly. A scalp power pattern does '
                  'not establish anatomical source localization or show that a learned '
                  'decoder relied on that pattern.'),
    ]

    related_work.insert(4, paragraph('Recent domain-generalization studies address unseen-subject '
        'motor-imagery decoding through learned source-domain invariance. EEG-DG aligns marginal '
        'and conditional distributions across multiple source domains [27]. Zheng et al. combine '
        'spectral/task knowledge distillation with cross-source correlation alignment and '
        'distance regularization [28]. These studies motivate source-only generalization without '
        'target adaptation; their information budgets and selection procedures must still be '
        'checked for a matched comparison. The present study does not introduce a new '
        'domain-generalization algorithm or rank against those methods. It audits source-only '
        'model selection, participant heterogeneity and complete frozen-pipeline transfer, '
        'retaining adverse and null results with an inspectable evidence chain.'))

    intro = [heading('1. Introduction', 1), introduction[0], introduction[2], introduction[3], introduction[4]]
    intro[-2]['text'] = intro[-2]['text'].replace(
        'Second, does processing predefined mu/beta views with one shared EEGNet improve on a broad input',
        'Second, how does a pipeline processing predefined mu/beta views with one shared EEGNet compare with broad input')
    intro[-2]['text'] = intro[-2]['text'].replace(
        'Third, how does that representation behave in external binary transfer?',
        'Third, how do those complete source-selected pipelines behave in external binary transfer? '
        'A separate descriptive component characterizes measured BNCI sensor signals without changing the decoders.')
    intro[-1]['text'] = intro[-1]['text'].replace(
        'independent reanalysis of saved predictions', 'independent reanalysis of saved predictions and a separate raw-signal characterization')

    design = [heading('3.1. Experimental Design'),
        paragraph('The study separates exploratory development from two external-evaluation stages. '
                  'The four-class BNCI2014_001 development stage holds out both sessions of the current '
                  'target person from all corresponding fitting and duration selection. Earlier benchmark '
                  'outcomes informed later candidates, so these nine-person comparisons remain exploratory. '
                  'Q14 evaluates separately fitted binary BNCI models on PhysioNet; a metadata-driven '
                  'sampling-rate amendment followed partial target execution. Q15 fits a new binary '
                  'source pipeline with a different montage, crop and reference, then evaluates its '
                  'frozen broad, shared-input and CSP models on Cho2017 and Lee2019 offline-training '
                  'segments. These datasets are external to fitting, but cross-provider identity '
                  'nonoverlap was not independently established.'),
        paragraph('The primary external estimand is the equal-person mean paired balanced-accuracy '
                  'difference between the frozen shared-input and broad pipelines, separately by cohort. '
                  'Q14 uses 17 shared and 18 broad epochs; Q15 uses 19 shared and 14 broad epochs, '
                  'all selected on source data. The contrasts therefore evaluate complete selected '
                  'pipelines rather than the isolated effect of sharing. CSP is contextual, and '
                  'neither external stage tests rank versus mean-loss selection. Q16 is a separate '
                  'BNCI-only signal characterization defined after decoder results were known; '
                  'its raw-signal summaries and associations cannot modify a decoder or establish '
                  'its physiological mechanism.'),
        {'type': 'figure', 'name': 'figure_workflow_zero_calibration', 'label': 'Figure WORKFLOW',
         'caption': 'Study workflow and information boundaries. Both sessions of each internal target '
                    'person are excluded from the corresponding source fit; the development programme '
                    'remains exploratory. Q14 and Q15 use separate binary models and preprocessing '
                    'contracts. Target inference applies deterministic adapters and frozen source-derived '
                    'transformations with no fitting, adaptation or BatchNorm update. Event and class '
                    'metadata support eligibility, canonical label mapping and scoring. A separate '
                    'BNCI-only physiological branch reads native signals and labels after the decoder '
                    'outcomes are known, without feedback into fitting or selection. People remain the '
                    'aggregation unit. Q14\'s post-partial-run amendment and both external duration '
                    'differences are detailed in the Methods and comparison-fairness table.'},
    ]

    contract = [heading('3.3. Strict Zero-calibration Information Contract'),
        paragraph('We define strict zero-calibration within each evaluation fit as inference with no '
                  'parameter, state, preprocessing coefficient, hyperparameter, duration, seed, decision '
                  'threshold or model choice fitted or selected using the current target person’s '
                  'recordings or labels in that fit. Neural weights and BatchNorm statistics, '
                  'shallow-model coefficients, source-fitted transforms and source-selected schedules '
                  'are fixed before target inference. There is no target normalization fit, covariance '
                  'alignment, adaptation, BatchNorm update, target-based stopping or seed selection. '
                  'This restriction does not make the repeatedly used BNCI development programme '
                  'independent of earlier target outcomes.'),
        paragraph('Target EEG supplies model inputs, and event and class metadata implement declared '
                  'eligibility and canonical label mappings. Labels then score saved predictions. '
                  'Cho recordings are stored in class-specific containers, so the adapter is not '
                  'blind to native class metadata. Fixed filtering, channel selection, resampling and '
                  'common-average referencing compute functions of target signals without estimating '
                  'a target-dependent decoder. The Q15 Helmert basis depends only on channel count; '
                  'scalers, CSP/PCA, whitening and EOG-regression coefficients, where used, are '
                  'estimated on source-training data and applied unchanged. Separate physiological '
                  'summaries may read raw signals and labels, but provide no feedback into bands, '
                  'crops, weights, thresholds, schedules or model choice.'),
        paragraph('Zero target fitting is distinct from known physical acquisition calibration. '
                  'Q15’s native-numeric-as-microvolt convention does not verify the exported voltage '
                  'units. Earlier within-person and cross-session P2 models use target-person labeled '
                  'calibration and remain outside the strict zero-calibration endpoints. The '
                  'source-fitted P4 EOG regression uses synchronous target EOG and therefore requires '
                  'additional sensors even though it fits no target coefficients.'),
        make_table('Table CONTRACT. Target information and fitting boundaries.',
            ['Operation', 'Information read', 'Target fitting', 'Interpretation'], [
                ['Eligibility, fixed channel and class maps, cue indexing', 'Native rate/channel/event/class metadata', 'None', 'Declared metadata adapter'],
                ['Filtering, resampling, crop and Q15 CAR', 'Target EEG, fixed native metadata', 'None', 'Deterministic offline operations'],
                ['Q15 Helmert coordinates', 'Channel count and signal', 'None', 'Analytical CAR-subspace basis'],
                ['Source-fitted scaler/CSP/PCA/whitening/EOG regression', 'Source data to fit; target signal to apply', 'None', 'Frozen source coefficients; EOG needs extra sensors'],
                ['Neural inference', 'Target tensors', 'None; weights and BatchNorm fixed', 'Strict zero-calibration prediction'],
                ['Scoring and separate Q16 characterization', 'Predictions/raw signals and canonical labels', 'None', 'Downstream analyses with no decoder feedback'],
                ['P2 within-person or cross-session models', 'Target-person labeled training trials', 'Yes', 'Calibrated context; separate endpoint'],
            ], 'The restriction concerns fitting and selecting the corresponding decoder, rather than '
               'prohibiting all computations on target signals or all label access. Metadata inspection '
               'and downstream scoring/physiology do not make the development history outcome-blind.'),
    ]

    fairness = make_table('Table FAIRNESS. Matching and remaining differences in decoder comparisons.',
        ['Comparison', 'Matched aspects', 'Remaining difference / scope'], [
            ['Q5 mean-loss vs Q8 mean-rank', 'Nine-person all-trial LOSO, 22×750, 4–40 Hz, original 36 inner trajectories, final seeds', 'Schedule changes; candidate arose after BNCI outcomes; exploratory'],
            ['Q5 raw vs Q6 source normalization', 'Same all-trial targets and EEGNet family; source-only scaler fit', 'Selected epochs also change: S3 2→16, S5 13→12; not normalization alone'],
            ['Q7 S3 raw/normalized ×2/16 epochs', 'Epochs fixed within each raw/normalized pair', 'One-person diagnostic'],
            ['Q9 broad vs shared, reselected durations', 'Same targets, dimensions, EEGNet parameter count, optimizer/seeds', 'Bands, two-view computation, BatchNorm exposure and schedules differ'],
            ['Q9-E002 fixed-schedule broad/shared', 'Same targets and frozen Q8 per-target epochs', 'Duration-controlled sensitivity; views/computation still differ'],
            ['Q10 CSP vs PCA neural projections', 'Eight source-fitted components per band; 16 projected channels and source scaling', 'Matched to each other, not to 22-channel shared-logit input'],
            ['Q11 independent branches vs capacity comparator', 'Same targets; approximate trainable capacity', '5,864 vs 5,914 parameters; branch computation/normalization differ'],
            ['Q12 GroupDRO vs balanced ERM', 'Same runtime and batching/sampling policy', 'Declared objective comparison'],
            ['Q12 whitening/augmentation vs historical Q8', 'Same nominal target population and source-only rule', 'Historical baseline uses another runtime'],
            ['Q13 fixed20 vs matched-runtime CE schedule', 'Same actual runtime, raw files and three seeds', 'Historical epochs replayed, not reselected in the newer runtime'],
            ['Q13 source-session 0train vs 1test', '2,304 source trials, 20 epochs, 720 updates', 'Session composition changes; both-session anchor also changes exposure'],
            ['Q14 external broad vs shared', '109 people/4,918 trials; 22×480; same source seeds and target rule', '18 vs 17 epochs; metadata amendment after partial execution'],
            ['Q15 external broad vs shared', 'Identical people/trials within cohort; 21×320 adapter, neural family/seeds', '14 vs 19 epochs and one-view vs two-view processing'],
            ['Q14/Q15 CSP4+LDA context', 'Same cohort scoring population; source-only fit', 'One shallow model vs three neural seeds; Q15 Helmert; differs from Q4 CSP8/OAS'],
        ], 'These are implementation-specific controls rather than interchangeable model-class '
           'benchmarks. Matching selected aspects does not isolate every causal factor. Q14/Q15 '
           'external effects compare complete frozen pipelines; CSP comparisons remain descriptive.')

    neural = section('2.4. Neural representation and spatial-spectral controls',
                     '3.6. Neural Representation and Baseline Fairness') + [fairness]
    duration = section('2.3. Training-duration selection and diagnostic controls',
                       '3.5. Training-duration Selection and Diagnostic Controls')
    duration += [paragraph('The population raw-versus-source-normalized Q5/Q6 comparison also changes '
                           'the selected duration for S3 from 2 to 16 epochs and S5 from 13 to 12. '
                           'Its aggregate difference therefore does not isolate normalization. '
                           'The fixed-duration Q7 four-cell diagnostic provides a more direct '
                           'separation of normalization and duration for S3 only.')]
    q14 = section('2.6. Earlier binary source freeze and PhysioNet evaluation',
                   '3.8. Earlier Binary Source Freeze and PhysioNet Evaluation (Q14)')
    q14[1]['text'] += (' The external neural contrast compares complete pipelines with unequal '
                      'source-selected durations, rather than isolating the effect of parameter sharing.')
    q15 = section('2.7. New binary source freeze and external cohorts (Q15)',
                   '3.9. Frozen Cho2017/Lee2019 Transfer (Q15)')
    q15[-2]['text'] += (' The repository-defined freezes follow external metadata inspection and '
                        'are not independently registered preregistration.')
    q15[-1]['text'] = ('All 52 Cho2017 and 54 Lee2019 participants were processed under the '
                        'declared adapters. The archived independent computational validator '
                        'replays raw-to-epoch and frozen-model prediction calculations, checks '
                        'canonical events and scoring populations, verifies inference and '
                        'source-artifact bindings, and recalculates aggregate statistics. '
                        'Validation passed with the stated acquisition-calibration limitations. '
                        'The supplementary reproducibility documentation records the exact '
                        'input, parameter, checkpoint and result revisions.')


    physiology = [heading('3.10. BNCI-only Physiological Signal Characterization (Q16)'),
        paragraph('Q16 performed a separate descriptive analysis of native BNCI2014_001 recordings: '
                  '18 files, 108 motor-imagery runs, nine people and both sessions, retaining all '
                  '5,184 four-class trials and their artifact flags in the primary population. '
                  'The signals retain all 22 EEG sensors at native 250 Hz, with no extra bandpass, '
                  'notch, resampling, reference transform, source scaler or learned projection. '
                  'Three EOG channels are excluded. EEG column order follows the provider montage; '
                  'individual MAT files do not contain channel-name strings. '
                  'Native one-based trial starts are converted to zero-based samples; the cue is '
                  '500 samples after the trial start. The fixed cue-relative baseline is '
                  '[−1.5,−0.5) s and task window is [0.5,2.5) s. Before power calculation, the '
                  'analysis requires rehashing all originals against the archived source provenance '
                  'and checking labels, artifact flags, finite samples, the declared montage order and complete '
                  'window bounds. All 18 source SHA-256 digests, 5,184 event identities and '
                  '228,096 trial-channel-band eligibility rows passed; no power-guard failure '
                  'excluded a trial. The primary population retained all 488 flagged trials, '
                  'including 246 of the 2,592 hand trials.'),
        paragraph('Welch power is defined separately within each trial’s baseline and task windows '
                  'using float64 native numeric values, a periodic Hann taper, 250-sample segments, '
                  '125-sample overlap, 250-point FFT, linear detrending, one-sided density and '
                  'arithmetic segment averaging. This gives 1-Hz bins. Closed 8–13-Hz and '
                  '13–30-Hz masks are integrated with the trapezoidal rule in physical frequency; '
                  'the 13-Hz boundary supplies half-bin weights to the adjacent integrals. '
                  'The trial-level change is 10 log10(Ptask/Pbaseline), in dB. Nonfinite or '
                  'nonpositive powers require an explicit invalid-row receipt rather than an '
                  'epsilon or clipped ratio. The 1-s baseline contributes one Welch segment and '
                  'the 2-s task contributes three overlapping segments. Unequal log-power estimator '
                  'variance can create a positive offset even without a true power change, so '
                  'these dB summaries are not claimed to be unbiased ERD estimates.'),
        paragraph('Arithmetic mean trial dB is aggregated within person, session, class, channel '
                  'and band, followed by equal averaging of the two sessions. This averages log '
                  'ratios rather than taking the logarithm of averaged powers. Left/right-hand '
                  'C3/C4 summaries use common trial eligibility. The signed hand descriptor is '
                  'L = [(C3right − C4right) + (C4left − C3left)]/2. A negative descriptor means '
                  'the contralateral task/baseline change is lower than the ipsilateral change; it '
                  'does not alone establish absolute contralateral ERD. C3, Cz and C4 absolute '
                  'changes, separate hand terms, full scalp summaries, sessions and artifact '
                  'strata are retained to show that distinction.'),
        paragraph('The parameter specification was frozen on 6 October 2026 after the decoder '
                  'outcomes were known, before the new physiological calculation. The analysis '
                  'is therefore descriptive rather than an independent confirmation. Associations '
                  'use existing matched-binary Q14-E001 BNCI LOSO scores, averaged over the three '
                  'fixed neural seeds within each of the same nine people; all-nine-source fits '
                  'and external-cohort scores are ineligible. The broad EEGNet score is the '
                  'designated descriptive endpoint. Six Spearman coefficients cover the three '
                  'fixed models and two fixed bands, with no '
                  'p-values, tertile groups or outcome-selected bands/models. Decoder imagery '
                  'covers [0.5,3.5) s, whereas Q16 power covers [0.5,2.5) s. No external physiology '
                  'was calculated, and no Q16 output fitted, selected or updated a decoder. '
                  'The parameter freeze is commit 050e01b028aaab8e3d745934b13b2d17e9bb0a7a; '
                  'its public readback preceded raw-power calculation. The preprocessing freeze, '
                  'raw receipt, execution manifest and final independent validation bind the '
                  'specification, inputs and completed tables in Q16-P001-BNCI-20261006.'),
    ]

    old_statistics = contents('2.8. Endpoints, uncertainty, and evidence verification')
    statistics = [heading('3.11. Statistical Analysis')] + old_statistics[:-1]
    statistics += [paragraph('Q16 is a post-decoder-outcome descriptive component. Its physiological '
                            'aggregation and decoder association use nine person-level records, '
                            'without treating channels, trials, sessions or seeds as independent '
                            'people. The six Spearman coefficients are '
                            'descriptive; no physiological p-values or confirmatory family are '
                            'introduced. They are separate from Q15’s frozen two-cohort tests and '
                            'cannot retrospectively confirm the decoder contrasts.')]
    verification = [heading('3.12. Reproducibility and Validation Scope'),
        paragraph('Saved predictions were independently reaggregated to check trial identities, '
                  'scoring populations, person-level confusion matrices, seed-averaged scores '
                  'and reported statistical results. This numerical reanalysis did not load '
                  'decoder checkpoints or generate predictions. Q15 additionally has a '
                  'completed raw-to-epoch and frozen-model prediction replay; the earlier '
                  'PhysioNet portability audit rechecked saved outputs without replaying '
                  'inference. Validation coverage for earlier experiments remains '
                  'experiment-specific and is documented in the supplement.'),
        paragraph('Q16 was checked independently against native BNCI recordings. An explicit '
                  'detrending, periodic-Hann FFT and trapezoidal integration calculation '
                  'reproduced all 31,104 C3/Cz/C4 trial-band pairs: the maximum relative power '
                  'difference was 1.85 × 10^−15 and the maximum absolute dB difference was '
                  '7.11 × 10^−15, within fixed 10^−10 tolerances. Raw spectral replay covered '
                  'these three central channels; identities and eligibility were checked '
                  'for all 228,096 saved rows, and all aggregation and association tables '
                  'were recomputed. Numerical agreement establishes implementation '
                  'consistency, not independent laboratory replication.')]

    verification += [paragraph('OpenAI Codex assisted analysis-code development and verification-code '
                               'preparation. The computations use explicitly specified algorithms; '
                               'the archived validation reports document the numerical checks. '
                               'AI-assisted code generation is distinct from a learned decoder '
                               'or a physiological model.')]
    methods = [heading('3. Materials and Methods', 1)] + design
    methods += section('2.1. Datasets, populations, and task separation', '3.2. Datasets, Populations and Task Separation')
    methods += contract
    methods += section('2.2. Offline preprocessing and source-only partitions', '3.4. Offline Preprocessing and Source-only Partitions')
    methods += duration + neural
    methods += section('2.5. Source-only robustness interventions', '3.7. Source-only Robustness Interventions')
    methods += q14 + q15 + physiology + statistics + verification

    results_start, results_end = index('3. Results'), index('4. Discussion')
    results = copy.deepcopy(blocks[results_start:results_end])
    for block in results:
        if block['type'] == 'heading':
            block['text'] = re.sub(r'^3(?=\.| )', '4', block['text'])
        if block['type'] == 'paragraph':
            block['text'] = block['text'].replace(
                'shared input reduced mean left-hand recall', 'the shared-input pipeline had lower mean left-hand recall')
            if block['text'].startswith('Source-only per-channel normalization increased'):
                block['text'] += (' Its selected schedules also changed for S3 (2 to 16 epochs) '
                                  'and S5 (13 to 12), so this population contrast combines '
                                  'normalization and duration changes.')
            block['text'] = block['text'].replace(
                'corrected adverse result for the declared representation contrast',
                'corrected adverse result for the declared complete-pipeline contrast')
    results += [heading('4.7. Descriptive BNCI Sensor Physiology and Decoder Associations (Q16)'),
                paragraph('All 18 raw files, 108 labeled runs and 5,184 trials passed the fixed '
                          'coverage gates. All 228,096 trial-channel-band rows had finite, positive '
                          'baseline and task power. No trial, session or person was excluded; '
                          'the 488 provider-flagged trials remained in the primary summaries. '
                          'Figure PHYSIO shows equal-person scalp means and all nine C3/Cz/C4 '
                          'profiles. These fixed-estimator task/baseline changes varied by '
                          'sensor, imagined hand and person.'),
                make_table('Table PHYSIO. Baseline-relative hand power and signed C3/C4 laterality.',
                    ['Band', 'Contra. mean (dB)', 'Ipsi. mean (dB)', 'Mean L (dB)', 'Person L range (dB)', 'L signs (−/+)'], [
                        ['Mu, 8–13 Hz', '−0.308', '−0.058', '−0.250', '−1.432 to +0.336', '6 / 3'],
                        ['Beta, 13–30 Hz', '−0.439', '−0.272', '−0.168', '−0.519 to +0.133', '8 / 1'],
                    ], 'Means give equal weight to nine people, each with equal-session mean trial dB '
                       'from both hands. Contra. and ipsi. average the relevant C3/C4 hand components; '
                       'L is contra. minus ipsi. All 2,592 hand trials, including 246 flagged trials, '
                       'are retained. Negative L indicates a lower contralateral than ipsilateral '
                       'task/baseline change; it does not establish an absolute decrease in '
                       'contralateral power. Values are displayed to three decimals; full precision '
                       'is retained in the supplied data tables. These are descriptive '
                       'fixed-estimator ratios, not unbiased ERD estimates.'),
                paragraph('Mu signed laterality averaged −0.250 dB, with six negative and three '
                          'positive person descriptors; beta averaged −0.168 dB, with eight '
                          'negative and one positive descriptor (Table PHYSIO). Contralateral and '
                          'ipsilateral group means were both negative in each band, but absolute '
                          'contralateral changes were not negative for every person. For example, '
                          'S2 had negative mu laterality (−0.203 dB) while both its contralateral '
                          '(+1.491 dB) and ipsilateral (+1.694 dB) means were positive. '
                          'Separate session, hand and flagged/unflagged cells are supplied in the '
                          'verified supplementary tables; they are descriptive sensitivity records '
                          'and do not replace the all-trial population.'),
                {'type': 'figure', 'name': 'figure_q16_bnci_physiology', 'label': 'Figure PHYSIO',
                 'caption': 'Descriptive native BNCI task/baseline power changes. A–D show '
                            'equal-person hand-imagery means for mu (8–13 Hz) and beta (13–30 Hz) '
                            'at all 22 EEG sensors. The schematic standard-1020 geometry has '
                            'anterior upward and left scalp on viewer left; linear interpolation '
                            'is restricted to the sensor convex hull. The fixed ±6-dB color '
                            'range clips no sensor or interpolated grid values. E–F show all '
                            'nine equal-session C3/Cz/C4 profiles (thin lines) and their '
                            'equal-person means (thick lines). Trial dB uses cue baseline '
                            '[−1.5,−0.5) s and task [0.5,2.5) s, with one versus three overlapping '
                            'Welch segments. Negative values mean lower task power under this '
                            'estimator, whose unequal window precision can bias log ratios. '
                            'All trials and artifact flags are retained. Template topography '
                            'does not localize cortical sources or attribute decoder decisions.'},
                paragraph('The designated broad-EEGNet descriptive associations between signed '
                          'laterality and saved binary LOSO balanced accuracy were rho = −0.150 '
                          'for mu and +0.600 for beta. Shared-input coefficients were −0.083 '
                          'and +0.483, and CSP4+LDA coefficients were +0.067 and +0.317, '
                          'respectively (Table S4; Figure S3). All six retain the same nine people '
                          'and have no p-values. A positive beta coefficient means higher balanced accuracy '
                          'accompanied a larger, less-negative signed descriptor; it does not '
                          'support a benefit from stronger relative contralateral suppression.')]

    discussion = [heading('5. Discussion', 1)]
    discussion += section('4.1. Duration selection can dominate a representation comparison',
                          '5.1. Training-duration Sensitivity in a Small Development Benchmark')
    discussion += section('4.2. Spectral sharing has cohort-dependent costs',
                          '5.2. Complete Spectral Pipelines Have Cohort-dependent Outcomes')
    for block in discussion:
        if block['type'] != 'paragraph':
            continue
        block['text'] = block['text'].replace(
            'a consistent advantage of this fixed representation',
            'a consistent advantage of this fixed shared-input pipeline')
        block['text'] = block['text'].replace(
            'sharing reduced mean left-hand recall',
            'the shared-input pipeline had lower mean left-hand recall')
    discussion += [paragraph('The external duration mismatch is part of this interpretation: '
                             'broad/shared fits used 18/17 epochs in Q14 and 14/19 in Q15. '
                             'Their paired effects include the selected schedules as well as '
                             'input views and shared normalization. Neither evaluation identifies '
                             'the causal contribution of parameter sharing alone.')]
    discussion += [heading('5.3. Person-level Evidence and Descriptive Signal Characterization')]
    discussion += contents('4.3. The unit of evidence is the person')
    discussion += [paragraph('The measured BNCI signals add a sensor-level description without '
                             'explaining the decoder contrasts. Mean signed hand laterality was '
                             'negative in both bands: six of nine people had negative mu laterality '
                             'and eight had negative beta laterality; the remaining signs were '
                             'positive. Absolute components matter: a '
                             'negative descriptor can coexist with increased power on both '
                             'sides, as observed in S2. The broad beta correlation was positive, '
                             'so higher balanced accuracy coincided with less-negative relative laterality '
                             'rather than stronger suppression. None of the six small-sample '
                             'associations supports a subgroup threshold or model selection.'),
                   paragraph('A lateralized group-average scalp pattern or a correlation with '
                             'LOSO balanced accuracy does not establish a cortical source, exclude ocular '
                             'or muscle contributions, or show that EEGNet used the depicted '
                             'signal. The physiology was specified after decoder outcomes were '
                             'known and concerns BNCI only. It therefore cannot explain the '
                             'adverse Cho contrast or validate an external physiological mechanism.')]
    discussion += [heading('5.4. Limitations'),
        paragraph('The same nine BNCI people informed successive development conditions. '
                  'Per-fit target exclusion does not remove outcome-informed candidate design '
                  'or dependence through overlapping LOSO training sets. The internal '
                  'rank-selection gain was concentrated in two people, and external stages '
                  'did not test that selection-rule contrast. Several controls differ in '
                  'runtime, training examples, update exposure, sensor width or approximate '
                  'capacity. No common-budget comparison against contemporary target-adaptation '
                  'or foundation-model methods was performed.'),
        paragraph('Q14 and Q15 use distinct montages, windows, references, filter scopes and '
                  'source checkpoints. Q14’s metadata amendment followed partial execution. '
                  'Q15’s repository freezes precede its fitting or inference stages but '
                  'follow metadata inspection and are not independently registered '
                  'preregistration. Cross-provider participant identities are unverified. '
                  'External bootstrap intervals condition on one frozen source cohort and '
                  'do not include source-sampling, adapter or development-history uncertainty.'),
    ]
    discussion += [paragraph('The external source-duration schedules were selected from four fixed '
                             'BNCI validation groups with unequal participant counts (2/2/2/3) '
                             'and equal fold weighting. This grouping was frozen before target '
                             'inference but represents one arbitrary source-validation design. '
                             'Grouping sensitivity was not evaluated prospectively.')]
    discussion += contents('4.4. External validation does not resolve every acquisition assumption')
    discussion += [paragraph('Q16 uses a one-segment baseline and a three-segment task estimator; '
                             'unequal log-power variance can bias their dB difference. Its signed '
                             'descriptor measures relative contralateral–ipsilateral change and '
                             'can be negative through ipsilateral increases without absolute '
                             'contralateral suppression. The descriptor and binary decoder also '
                             'use different task windows. Nine descriptive person records and '
                             'overlapping LOSO fits cannot establish a subgroup biomarker or '
                             'mechanistic model attribution. Baseline-relative ratios cancel '
                             'only a constant multiplicative gain and do not correct reference, '
                             'timing, spatial mapping or artifacts. External native voltage '
                             'calibration remains unknown, and external physiology is unrun.')]

    conclusion = [heading('6. Conclusion', 1),
        paragraph('Source-only training-duration choices produced large but concentrated gains '
                  'in the nine-person BNCI development benchmark. The evaluated shared-input '
                  'pipelines showed no consistent external advantage: compared with broad '
                  'EEGNet, balanced accuracy was 1.513 pp lower on Cho2017, whereas the Lee2019 '
                  'contrast remained compatible with a small effect in either direction. '
                  'These complete-pipeline comparisons include unequal source-selected durations '
                  'and do not isolate parameter sharing. The post-outcome BNCI signal analysis '
                  'found negative mean signed hand laterality in mu and beta with substantial '
                  'participant variation; it does not establish a decoder mechanism or external '
                  'physiological replication. Unknown acquisition calibration and offline '
                  'evaluation limit deployment conclusions.')]

    declarations = [heading('Data and code availability', 1),
        paragraph('Public BNCI2014_001, PhysioNet, Cho2017 and Lee2019 recordings are available '
                  'from the original providers [1,2,9,10,12–15], subject to their licenses and '
                  'terms of use. PhysioNet platform publications are cited separately [11,22]. '
                  'Analysis code, saved predictions, participant-level summaries, parameter '
                  'specifications and numerical validation reports are available at '
                  'https://github.com/jackzhu119/cross-subject-mi-eeg. The supplementary '
                  'reproducibility documentation identifies the exact source and result '
                  'revisions. Raw EEG is not redistributed in the manuscript bundle.'),
        heading('Ethics statement', 1),
        paragraph('This study involved secondary analysis of public EEG recordings and recruited '
                  'no new participants. The original studies report their collection ethics '
                  'and participant consent. The author confirms that neither ethics approval '
                  'nor an exemption was required for this secondary analysis.'),
        heading('Funding', 1), paragraph('This research received no funding.'),
        heading('Competing interests', 1), paragraph('The author declares no competing interests.'),
        heading('Author contributions', 1), paragraph('Ziyuan Zhu undertook the study as the sole author, prepared the manuscript, checked and revised its content, and approved the final version.'),
        heading('Acknowledgements', 1), heading('AI assistance disclosure', 2),
        paragraph('ChatGPT (GPT-6, as reported by the author) assisted information retrieval, grammar revision, and preparation of instructions for publishing research materials to GitHub. OpenAI Codex assisted source and literature checks, analysis-code and verification-code development, saved-result consistency checks, figure preparation, and manuscript drafting and language revision. The author personally reviewed and revised the final manuscript and takes responsibility for its scientific content.')]
    supplementary = copy.deepcopy(blocks[index('Supplementary material'):])
    supplementary += [heading('S9. Descriptive BNCI-only Physiological Characterization'),
        paragraph('The separate Q16 methods document native raw-file/hash and event gates, fixed '
                  'Welch parameters, trial-level dB aggregation, hand descriptors, artifact/session '
                  'strata and all-nine-person Q14-E001 matched-binary LOSO associations. Its '
                  'parameter specification follows known decoder outcomes; no external physiology, '
                  'p-values, subgroup selection, decoder fits or new decoder inference is added. '
                  'The public parameter freeze is 050e01b028aaab8e3d745934b13b2d17e9bb0a7a. '
                  'The final independent validation passed for all central-channel raw power '
                  'replays, all saved aggregation tables and all six signed correlations. '
                  'The bundle preserves the freeze/readback, raw and execution receipts, '
                  'summary, independent validation, person/session/artifact tables and '
                  'the corresponding figure input/export hashes.'),
        make_table('Table S4. All six descriptive physiology–balanced-accuracy associations.',
            ['Saved binary LOSO model', 'Band', 'Spearman rho', 'People', 'Context'], [
                ['Broad EEGNet', 'Mu', '−0.150', '9', 'Designated descriptive endpoint'],
                ['Broad EEGNet', 'Beta', '+0.600', '9', 'Designated descriptive endpoint'],
                ['Shared mu/beta EEGNet', 'Mu', '−0.083', '9', 'Context'],
                ['Shared mu/beta EEGNet', 'Beta', '+0.483', '9', 'Context'],
                ['CSP4 + LDA', 'Mu', '+0.067', '9', 'Context'],
                ['CSP4 + LDA', 'Beta', '+0.317', '9', 'Context'],
            ], 'Spearman rho is the Pearson correlation of average ranks. Each person supplies '
               'one equal-session signed C3/C4 hand descriptor and one saved Q14-E001 binary '
               'LOSO balanced-accuracy score (three-seed mean for neural models; one CSP fit). '
               'All nine people are retained. Positive rho links higher balanced accuracy to a larger '
               'signed descriptor, which is less relatively suppressive when negative. '
               'Coefficients are displayed to three decimals; full precision is retained in '
               'the supplied data tables. These post-decoder-outcome associations have no '
               'p-values, confirmatory claims or external physiological test.'),
        {'type': 'figure', 'name': 'figureS_q16_physiology_associations', 'label': 'Figure S3',
         'caption': 'All six descriptive BNCI associations. The same nine people appear in '
                    'each model/band panel, labeled by person ID, with signed C3/C4 hand '
                    'laterality on the horizontal axis and saved binary Q14-E001 LOSO '
                    'balanced accuracy on the vertical axis. Neural scores average three '
                    'seeds within person; CSP uses one frozen fit. The physiology window '
                    '[0.5,2.5) s differs from the decoder window [0.5,3.5) s. All points '
                    'are retained; no fitted lines, p-values, subgroup thresholds or '
                    'decoder updates are introduced. Positive beta correlations associate '
                    'higher balanced accuracy with less-negative laterality. These post-outcome '
                    'descriptions do not show mechanism, causality or a validated biomarker.'}]

    revised = blocks[:3] + intro + related_work + methods + results + discussion + conclusion + declarations + supplementary
    # Semantic names lead the main narrative; exact IDs remain in tables,
    # implementation descriptions and supplementary inventories.
    narrative_names = {
        'Q14 evaluates separately fitted': 'The earlier PhysioNet external evaluation (Q14) evaluates separately fitted',
        'Q15 fits a new binary source': 'The frozen Cho2017/Lee2019 transfer experiment (Q15) fits a new binary source',
        'Q14 uses 17 shared': 'The PhysioNet evaluation uses 17 shared',
        'Q15 uses 19 shared': 'the frozen Cho2017/Lee2019 evaluation uses 19 shared',
        'Q16 is a separate BNCI-only': 'The descriptive BNCI physiological characterization (Q16) is a separate BNCI-only',
        'Q16 performed a separate': 'The BNCI characterization performed a separate',
        'Q16 is a post-decoder-outcome': 'The physiological characterization is a post-decoder-outcome',
        'Q16 uses a one-segment': 'The physiological analysis uses a one-segment',
        'Q16 was checked independently': 'The physiological analysis was checked independently',
        'Q15 is a distinct binary transfer experiment': 'The frozen Cho2017/Lee2019 experiment is a distinct binary transfer experiment',
        'Q15’s repository freezes': 'The frozen transfer experiment’s repository freezes',
        'Q16’s frozen': 'the physiological analysis’s frozen',
        'Q15 additionally has': 'The Cho2017/Lee2019 experiment additionally has',
        'Q16 power covers': 'the physiological power analysis covers',
        'no Q16 output fitted': 'no physiological-analysis output fitted',
        'Q5 and Q8': 'the mean-loss development condition (Q5) and mean-rank follow-up (Q8)',
        'Q12 robustness interventions': 'the source-only robustness interventions (Q12)',
        'Q13 additive controls': 'the matched-runtime additive controls (Q13)',
    }
    for block in revised:
        if block['type'] == 'heading' and block['text'] == 'Supplementary material':
            break
        if block['type'] not in ('paragraph', 'heading'):
            continue
        for old, new in narrative_names.items():
            block['text'] = block['text'].replace(old, new)
        block['text'] = block['text'].replace('lower accuracy on Cho2017', 'lower balanced accuracy on Cho2017')
        block['text'] = block['text'].replace('The The ', 'The ').replace('the The ', 'the ')
    renumber_main_items(revised)
    for block in revised:
        if block['type'] == 'figure':
            for field in ('label', 'caption'):
                block[field] = block[field].replace('Independent-cohort binary transfer',
                                                     'Separate-cohort binary transfer')
        if block['type'] == 'table':
            block['rows'] = [[re.sub(r'(?<![A-Za-z0-9])-(?=\d)', '−', str(cell))
                              for cell in row] for row in block['rows']]
            for row in block['rows']:
                for i, cell in enumerate(row):
                    if cell.startswith('[') and cell.endswith(']'):
                        row[i] = re.sub(r',\s*', ', ', cell)
    return revised


def renumber_main_items(blocks):
    """Number main items by first appearance and repair existing cross-references."""
    mappings = {}
    counts = {'table': 0, 'figure': 0}
    for block in blocks:
        if block['type'] == 'heading' and block['text'] == 'Supplementary material':
            break
        kind = block['type']
        if kind not in counts:
            continue
        counts[kind] += 1
        noun = 'Table' if kind == 'table' else 'Figure'
        old_label = re.match(rf'^{noun} [^.]+', block['label']).group(0)
        new_label = f'{noun} {counts[kind]}'
        if old_label in mappings:
            raise ValueError(f'Duplicate main item label {old_label}')
        mappings[old_label] = new_label
        block['label'] = block['label'].replace(old_label, new_label, 1)
    if mappings:
        pattern = re.compile('|'.join(re.escape(key) for key in sorted(mappings, key=len, reverse=True)) + r'(?=\b|[A-Z])')
        for block in blocks:
            for field in ('text', 'caption', 'note'):
                if field in block:
                    block[field] = pattern.sub(lambda match: mappings[match.group(0)], block[field])
