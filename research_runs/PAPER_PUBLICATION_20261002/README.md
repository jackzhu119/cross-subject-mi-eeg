# Paper archive and continuation — 2 October 2026

The user authorized GitHub storage and an additional Cloudflare R2 backup of the previously prepared English paper and Chinese explanation. This directory records that storage phase. It does not record journal submission or acceptance.

## Read the paper

The original author-review bundle is preserved unchanged in [`../PAPER_DRAFT_20261002/`](../PAPER_DRAFT_20261002/):

- [`manuscript_en.pdf`](../PAPER_DRAFT_20261002/manuscript_en.pdf): 17-page reading copy, exported with ReportLab.
- [`manuscript_en.docx`](../PAPER_DRAFT_20261002/manuscript_en.docx): editable English manuscript.
- [`中文说明.md`](../PAPER_DRAFT_20261002/中文说明.md): Chinese explanation of results and limitations.
- [`paper_bundle_20261002.zip`](../PAPER_DRAFT_20261002/paper_bundle_20261002.zip): 49 archived files, including the integrity manifest, four figures in three formats, seven tables, inventories, and review evidence.

ZIP SHA-256: `b70c648caf0b4a77dfa261d42eadd30c890fbe1986fb2abd7007cf62502267ae`.

## Scope of the historical statements

The original draft's README, Chinese companion, and `evidence/delivery_validation.json` describe the earlier manuscript-preparation phase. Their statements that no GitHub push or external publication occurred, and the field `external_publication_or_submission=false`, remain accurate for that phase. This later archive phase stores the draft on GitHub and privately in R2. The original source snapshot remains `adb2d406b4300e2c8e4d5112969291c0331f3ed5`; a storage commit is not a new experiment or a replacement scientific source snapshot.

The draft still requires author, affiliation, funding, contribution, ethics, disclosure, and journal-specific review. LaTeX compilation remains unverified; the existing PDF is a ReportLab export. No claims of journal submission, ethics approval, checkpoint accessibility, or new experiment results are added by this archive.

## Storage and next chat

GitHub branch: `paper/non-q15-manuscript-20261002`. A draft pull request provides a reviewable archive. The publication receipt records its URL and the paper commit.

The private R2 prefix is:

```text
papers/non-q15/20261002/b70c648caf0b4a77dfa261d42eadd30c890fbe1986fb2abd7007cf62502267ae/
```

The R2 backup includes the complete ZIP, PDF, DOCX, Chinese explanation, manifest, archive notes, and continuation records. Read-back SHA-256 verification is required before recording success. The bucket stays private; use authenticated access with environment-configured credentials. No signed download URL or credential value belongs in this repository.

Read [`CONTINUE_IN_ANOTHER_CHAT.md`](CONTINUE_IN_ANOTHER_CHAT.md) before continuing Q15. `publication_receipt.json` records completed GitHub storage and verified R2 backup, when present. A separate private R2 handoff retains connection details without publishing them to GitHub.

This storage task performs no model fit, preprocessing, inference, or training deployment. Q15 remains `fits_started = 0`; its raw-data audit and preprocessing contract are not frozen.
