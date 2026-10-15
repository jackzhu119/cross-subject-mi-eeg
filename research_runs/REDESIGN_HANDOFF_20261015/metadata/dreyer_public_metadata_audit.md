# Frozen Dreyer metadata recovery — no EEG or Pod access

The frozen acquisition inventory and license evidence were independently verified from the already archived public metadata. This audit recovers **174 unique EDF paths, sizes and SHA-256 values, totalling 2,515,343,396 bytes**. Every row matches the provider sourcedata provenance and has a pointer-blob entry in frozen NEMAR tree `f77f8859a84df42bd775920d288261260b2236db`. All 87 participants have R1/R2 acquisition runs.

The [machine-readable audit](dreyer_public_metadata_audit.json) includes all 174 rows. `restore_relative_path` is the committed importer layout; **it is not an R2 object key**. Every `r2_object_key` is null because no authentic target upload receipt was recovered in this public/local scope. This does not imply private R2 backups are absent. Current accessibility and remote object content identity remain unobserved. Do not fabricate keys from basenames, hashes, provider URLs or annex paths.

## Frozen identities and population

- Frozen acquisition manifest file SHA-256: `2cfdf35aa7990df880826d1b84d1230e0bda3c9393c17d3ec6e27b7b311d2bf2`.
- Underlying saved provider manifest SHA-256: `061a8e215093e1bb0db8f80f95b112c60266acfa640284d05f92c0c6a5ddc544`. These are distinct files and must not be substituted for one another.
- Provider provenance SHA-256: `0d45bdd3394555e33d8dd153ad1ff15f9340f6f867a99e7bd13cf1e3b582b274`.
- Primary frozen roster: 85 participants / 6,800 events, after provider montage exclusions A17/A41. Prior exposure remains unknown; external evaluation remains exploratory. No participant, trial, exclusion, label mapping or analysis rule changed.

This inventory concerns **NEMAR nm000250 v1.0.5 sourcedata EDF**, declared by its provider to be an unchanged MOABB/OSF mirror. It does not establish byte identity with original Zenodo GDF ZIP files, and must not be replaced by the root BIDS-derived BDF dataset. The original Zenodo archive is a different 27,475,466,178-byte ZIP object whose published MD5 is not an EDF SHA-256.

## License and provenance

CC BY 4.0 is independently declared in the saved provider sourcedata README, provenance JSON and dataset description. The original [Zenodo record](https://doi.org/10.5281/zenodo.8089820) API metadata also declares `cc-by-4.0`. The saved description and Zenodo metadata match their original successful metadata fetch receipts; the saved provider README/provenance/description text matches the Git blob IDs in the frozen tree. No fresh online policy or license request was made in this audit.

Preserve creator attribution, dataset source and DOI, the [CC BY 4.0 license link](https://creativecommons.org/licenses/by/4.0/), and an indication of processing/conversion changes. Software licensing does not replace dataset licensing. Dataset sources: [NEMAR](https://doi.org/10.82901/nemar.nm000250), [original dataset](https://doi.org/10.5281/zenodo.8089820), [original paper](https://doi.org/10.1038/s41597-023-02445-z).

## Remaining recovery gate

An authentic, complete 192-file R2 mapping is still required: 18 BNCI source objects plus all 174 Dreyer objects. Each actual key must come from an existing backup/upload receipt or authorized metadata inventory and bind to the frozen relative path, byte size and SHA-256. An R2 ETag is not sufficient to replace SHA-256. This audit neither authorizes target restore nor actual training. The existing strict mapping/runtime/accounting/budget gates remain in force, and paper2 retains absolute scheduling priority.

No Pod operation, R2 request, credential read, target EEG read/download, dependency installation, source diagnostic/acceptance rerun or GPU fit occurred.
