# Core source trainer: software candidate and blocked execution gates

Prepared 13 October 2026. This is a tested **software candidate**, not a completed new neural experiment or a ready paid deployment. The default command reads no EEG, fits no model, computes no target prediction and does not buy or start a machine:

```bash
python research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts/train_source_selection_core.py
```

The actual CPU software environment is recorded in `evidence/core_cpu_software_runtime.json` and `requirements-core-cpu-software.txt`. Torch and torchaudio are the compatible official 2.11.0+cpu wheels; Braindecode is 1.5.1. `pip check` passed. The CPU requirements are for software tests; installing them cannot satisfy the live CUDA gate. Thirty-nine source-training tests and thirty-two separate inference tests passed together. Real Braindecode forward/backward probes used synthetic mathematical arrays only. They are not scientific EEG fits.

The root-authenticated source19 input probe is separately recorded in `evidence/core_source_input_probe.json`. It re-extracted 2,592 original source trials into actual 19-channel/320-sample broad/μ/β arrays, with source file, label, flag, configuration and array fingerprints. It did not fit a model and does not qualify the target cohort, a GPU runtime or a paid authorization.

## What the source runner implements

`core_source_inputs.py` re-extracts genuine source sensors including FCz and excluding P1/P2/POz. It applies CAR over these exact 19 channels, per-native-trial six-second filtering, fixed resampling to 160 Hz and the locked 0.5–2.5 s crop. No old Q15 tensor/model is truncated. Source artifact flags remain included. Source values retain the recorded native microvolt convention; original device calibration is not newly established by this code.

Four held-out source-participant groups supply one 40-epoch trajectory per architecture. Both sessions of a validation person are excluded from that fold's training. Mean-loss and mean-rank use the same four complete source validation CE curves, equal fold weights, average rank ties and the earliest minimum. Fixed20 is unchanged. All-source final models use the three specified seeds. Identical architecture/seed/duration schedules have one actual owner checkpoint with explicit aliases for all nominal conditions, rather than fictitious additional fits. Started/completed fits, actual optimizer updates, curves, partition/input/checkpoint hashes, parameters, model structure, timing and peak memory are recorded.

Shared input concatenates the two views through one backbone and averages logits before CE. Its convolution/linear MAC count is twice the broad model's for the same trial; the recorded FLOP estimate deliberately excludes filtering, pooling, BatchNorm, activations, backward and optimizer computation. Equal epochs or parameters must not be described as equal total compute.

## Gates that remain required before any real neural fit

1. **Complete data/author evidence.** `evidence/core_data_gate.json` must bind a real author prior-use declaration, the full 174-file acquisition receipt, an actual passing full-cohort raw-only QC report, eligible participant/event roster and adapter. The shared `infer_selection_core.verify_target_gate` checks those artifact contents, all provider identities/hashes, genuine event mapping, input fingerprints and eligibility. A `PASS` wrapper containing the hash of a failed QC report does not pass. Integer 1 is not author-confirmed Boolean true. Header-only/bounded metadata work is not full signal QC or original-conversion confirmation. The chosen provenance qualification must explicitly distinguish an independently qualified original route from operational derivatives.
2. **Real immutable public preanalysis.** `evidence/core_neural_preanalysis_receipt.json` must name the actual full commit and publicly read-back hashes for configuration, trainer, loader, qualification/adapter/access/statistical scripts, design/statistical/execution plans, exact GPU runtime lock, actual author/QC/acquisition/roster records and frozen source provenance. The runner checks local files, git objects and live public immutable bytes; a self-written `PASS` dictionary is insufficient. Commit the final executable implementation before fitting. A design-only commit is not this executable freeze.
3. **Actual GPU runtime.** `evidence/core_runtime_lock.json` must have status `FROZEN_BEFORE_SOURCE_FITS`, exact installed package versions, Python version and CUDA runtime obtained from the approved live machine. Braindecode must remain 1.5.1. CPU probes and the CPU dependency file do not satisfy this gate. A live UUID-identified CUDA device must pass arithmetic preflight.
4. **Explicit machine/budget approval.** `evidence/gpu_execution_authorization.json` must record actual author approval, machine hostname/GPU UUID, exact config SHA, a currently valid time interval, source-only scope and the concrete quoted rate. Bounds are at most 26 real neural fits, 34,440 optimizer updates, 8 GPU hours, US$0.75/hour, US$2 contingency and US$10 total. Optional groupings and target fits/predictions remain unauthorized. Do not populate author approval from an assumption or copy a test fixture. A worker budget abort stops computation; it does **not** stop a billable cloud instance or authenticate provider charges.

Required gate examples are specifications, not issued authorization: all pending fields must be filled from actual records and independently reviewed. No usable author, runtime, full-data or paid-GPU `PASS` receipt is fabricated in this delivery.

## Future execution and acceptance

Only after those gates actually pass on the approved machine:

```bash
python research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts/train_source_selection_core.py \
  --execute --source-data-dir /path/to/authenticated/original/bnci
```

The run gets a new directory. A failed attempt is retained with counters and error status; this candidate does not silently resume or overwrite it. A complete source grid is labelled `source_grid_completed_pending_independent_validation_no_target_predictions`. It is not a finished external experiment. Independent checks must reconstruct all source partitions, raw identities, input hashes, curves, selectors, checkpoint states and actual updates, then a separate public source-model/adapter/roster/inference freeze and separately authorized target inference must precede score release. No target centering, BatchNorm updates, target fit or target-driven selector change belongs in this source job.

Full GPU training, technical failure recovery, target-cohort qualification, target inference and independent neural scientific validation have not been run. The work package remains blocked for those scientific gates even though the listed software and source-only preprocessing checks passed.
