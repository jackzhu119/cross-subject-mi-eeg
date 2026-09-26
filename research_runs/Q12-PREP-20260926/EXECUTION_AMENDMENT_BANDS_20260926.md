# Q12 execution compatibility amendment — 2026-09-26

Before any Q12 model fit or target inference, execution exposed a configuration
interface mismatch.

Q12 inherits the frozen Q8 broad-band preprocessing definition under
`config["preprocessing"]["bands"]`.

The reused Q11 data loader expects the same band definition under
`config["bands"]`.

The Q12 runner now creates a loader-only shallow configuration view and exposes
the already-frozen preprocessing band definition at the key expected by the
reused loader.

No scientific condition is changed.

Unchanged items include:

- BNCI2014_001 dataset
- subjects 1–9
- four-class motor-imagery task
- 4–40 Hz broad-band preprocessing
- filter parameters
- epoch interval
- artifact policy
- LOSO source/target partition
- source-only selection
- seeds
- EEGNet architecture
- optimizer
- training epochs
- Q12 DG/augmentation methods
- zero target-derived fitting or model selection
- planned fit counts

At discovery, Q12 had completed zero model checkpoints and zero target
inference.
