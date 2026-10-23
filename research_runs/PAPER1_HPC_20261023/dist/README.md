# Fixed offline distribution

This archive contains code/configuration and two official CPU preprocessing wheels, not EEG, models or credentials.

Source commit: `74faa2e580263da1486be35bf9fd73e6a9754b9f`.

Archive bytes: 53,189,869. SHA256: `72225f30c83be9bbc94d52eac672bee272690f6cf9949933e3d61380401d2675`.

Its 68 payloads were fully read back against `OFFLINE_MANIFEST.json`. The archive is versioned here because the Release asset upload endpoint rejected the current connector credentials; normal authenticated Git publication succeeded. The release notes link to this fixed distribution.

Verify with `sha256sum -c paper1-hpc-offline.tar.gz.sha256`, then extract once on the school shared storage. See the package `README_zh.md` for data recovery and one-line launch/resume.
