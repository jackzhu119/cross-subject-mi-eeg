# Yang v5: event timing and integrity evidence

Checked on 2026-10-17. This note records source evidence and the fixed analysis
decision. No model scores were computed to choose the interval.

## Public provenance

- Data paper: <https://doi.org/10.1038/s41597-025-04826-y>.
- Frozen data version: <https://doi.org/10.25452/figshare.plus.22671172.v5>.
- Fixed archive download: <https://ndownloader.figshare.com/files/51001884>.
- Official MOABB adapter: <https://github.com/NeuroTechX/moabb/blob/develop/moabb/datasets/yang2025.py>;
  inspected commit `ed1aacdb39a445efe13a4f026673b14cc2913b85`. The moving
  develop URL is for attribution; see that commit for the inspected implementation.

The paper describes a 1.5-second video/audio instruction followed by four
seconds of imagery. Its preprocessing description says the four-second imagery
period is extracted using the markers. It does not unambiguously establish
which edge of the instruction the raw marker denotes.

The author-supplied archive member
`WBCIC_SHU Motor Imagery dataset/code/pre-processed/preprocessed.m`
epochs task markers `1`, `2`, `3`, and `4` over `[0,4]` seconds. There is no explicit
1.5-second shift in this supplied script. The extracted file has SHA-256
`3aa23e802ed1c3ed117abfe404ca47fdf756ddabfdfb51c7242abbedabc619d4`.
Its extraction receipt is `yang_v5_preprocessing_code_receipt.json`.

The inspected MOABB adapter instead defines the imagery interval as `[1.5,5.5]`
relative to the marker and directly attaches the event-file annotations. These
two interpretations have not been independently reconciled with acquisition
logs or the study authors.

## Fixed analysis interval

The expansion task retains **marker + [2,4) seconds**, with the real native
**marker + [0,6) seconds** as its filtering context. The retained two seconds
lie inside the intersection of both reported imagery intervals. This is a
fixed conservative interval choice, not a verified assertion of the precise MI
onset. It must not be described as phase-identical to BNCI or Dreyer trials
cropped relative to their verified task anchors.

## Actual event-file check

`yang_2c_sub001_ses01_evt.bdf` is the complete 63,186-byte event-only member.
It contains one all-zero placeholder and a BDF annotation channel, with no EEG
signal channel. Its SHA-256 is
`b12154047ed2587adb6f04ac9282576f42246f681e7e777a5ede01253420d80a`.

The header has `BDF+C`, 206 records, a nominal one-second record duration, and
one and 100 samples per record for the placeholder and annotation channels.
The task markers are 100 left (`1`) and 100 right (`2`); each consecutive
40-task-marker block contains 20 of each. Other markers are `7` once, `8` once,
and `9` four times. The first task marker is `1` at 231.965 seconds, and the
last is at 2221.858 seconds. Event and signal recording dates/times match.

The event file stores sparse events by record despite its continuous label;
do not infer a 206-second task-recording duration from its record count or
enforce signal-style one-second timekeeping on these annotation records.
The complete event-file receipt is `../validation/yang_event_validation.json`.

## Integrity boundaries

The selective downloader pins archive size 65,630,556,299 bytes and central
directory SHA-256
`cecd7ea0895da6ef85f01405960f4844c42d788ad33186b1f3fca91744d6874a`.
It verifies every fully extracted member against its directory CRC32 and
records a SHA-256 for later raw-file verification. Selective extraction does
**not** verify the complete archive's published MD5.

The one-trial real-signal validation in
`../validation/yang_first_real_context_qc.json` reads only the required
prefix and context of one EEG member. That separate partial inspection does
**not** verify that complete signal member's CRC32. It verifies the production
context decoding and preprocessing against a real retained source context,
including invariance under a common positive unit multiplier. Its scope is
one source trial; full dataset preparation and training remain runtime work.
