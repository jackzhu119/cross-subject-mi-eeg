# Publication release plan and integrity checklist

Prepared before modifying the default homepage or publishing an archive. Intended candidate tag: **paper-v1.0**; the author has now explicitly confirmed final review/approval; journal submission remains separate. Preserve all historical branches and avoid force pushes. The paper branch remains `paper/zero-calibration-q16-20261006`.

## Frozen scientific identities

- Q15 scientific code: `271af288a2f3863430ab80e3145c2dee9bd5571d`.
- Q15 validated result publication: `bc48b257eb44f412ad069f50d0f1a72a33c3c520`.
- Q16 parameter/pre-power freeze: `050e01b028aaab8e3d745934b13b2d17e9bb0a7a`.
- Q16 completed result: `research_runs/Q16-P001-BNCI-20261006/run_manifest.json`, `summary.json` and `independent_validation.json`, bound to exact output hashes. The publication receipt will identify the immutable paper/result snapshot.
- Manuscript directory: `research_runs/PAPER_FINAL_20261006/`.

## Gates — all must pass before homepage update or public release

1. Confirm branch and inspect existing changes. Bind protected scientific results, numeric tables, scientific figures, manifests, contracts and scripts to their previous hashes.
2. Validate manuscript display against `paper_numbers.json`, Q15 audits and Q16 saved summaries. No raw EEG processing, decoder fits, inference or selection is executed.
3. Check all citations, continuous numbering, metadata, complete figure/table populations and current DOCX/PDF exports. Disclose the actual native TeX compilation result.
4. Refresh the editorial/numerical review with current source/export SHA bindings, retaining the archived independent scientific checks and their limits.
5. Run final delivery validation and create a ZIP, manifest and archive checksum; test every archived member.
6. Commit and push only permitted paper/publication files. Read every public artifact back from its immutable GitHub revision and compare SHA-256 and byte length.
7. Update the default-branch README in an isolated checkout, with links to verified immutable paper/results. No scientific branches are merged merely to update the homepage; no frozen result changes or force pushes are allowed.
8. Create the candidate tag/archive only after those checks. GitHub release may be a prerelease while author actions remain. A Zenodo DOI-ready package/metadata can be prepared, but no DOI is claimed without an actual minting receipt.

## Release contents

Source Markdown/structured JSON/standalone TeX, PDF, DOCX, separate supplement, figure PNG/PDF/SVG, saved tables, bibliography, reproduction instructions, immutable Q15/Q16 pointers, validation evidence, manifest and ZIP checksum. Original EEG, credentials, caches and private server files are excluded.

## AUTHOR ACTION REQUIRED

The author has supplied final review/approval, a sole-author free-text contribution statement, Github-only publication history, exclusive-submission status, data-term checks, institutional wording confirmation and author-reported ChatGPT/GPT-6 use. No unconfirmed detailed CRediT roles or full historical model set are invented. Complete JNE system declarations and license agreements at actual submission. No committee-issued ethics decision or journal submission is inferred from a repository release.

## DOI-ready metadata

Title: Source-only model selection and limits of fixed spectral-sharing pipelines in cross-subject motor-imagery EEG decoding.
Creator: Ziyuan Zhu. Affiliation: College of Artificial Intelligence Medicine, Chongqing Medical University, Chongqing, China.
Resource: research manuscript and reproducibility materials; version paper-v1.0.
Existing repository LICENSE does not automatically settle all source-data or manuscript rights. Select and confirm archive licensing before depositing with Zenodo. DOI: **not created**.
