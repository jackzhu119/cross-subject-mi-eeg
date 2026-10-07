"""Bind current editorial reviews and delivered files; never execute EEG analyses."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent


def load(name):
    return json.loads((P / name).read_text())


def sha(name):
    return hashlib.sha256((P / name).read_bytes()).hexdigest()


def verify_bindings(report, field='input_sha256'):
    for name, digest in report[field].items():
        assert sha(name) == digest, (field, name)


language = load('evidence/language_refinement/independent_scientific_language_review.json')
package = load('evidence/language_refinement/submission_package_independent_review.json')
layout = load('evidence/quality_update/layout_review.json')
numeric = load('evidence/quality_update/numeric_review.json')
edits = load('evidence/language_refinement/edit_integrity.json')
integrity = load('evidence/quality_update/submission_integrity.json')
prepared = load('evidence/author_finalization/submission_package_review.json')
prior = load('evidence/language_refinement/prior_evidence__final_scientific_review.json')
for report in [language, package]:
    assert not report['checks_failed'] and all(report['checks'].values())
    verify_bindings(report)
assert 'pass' in layout['status'].lower() and not layout['checks_failed']
assert all(layout['checks'].values())
verify_bindings(layout, 'file_sha256')
verify_bindings(numeric)
verify_bindings(edits)
verify_bindings(prepared)
assert not numeric['discrepancies'] and all(item['passed'] for item in numeric['checks'])
assert not integrity['failed_checks'] and all(integrity['checks'].values())
assert integrity['protected_scientific_file_count'] == 16417
assert len(numeric['checks']) == 422 and numeric['numeric_display_cells_checked'] == 261
assert prepared['files'] == 28 and prepared['all_archive_member_sha256_match']
assert sha('JNE_submission_package.zip') == prepared['archive_sha256']
assert language['new_editorial_version_author_approval_received'] is False
assert edits['new_editorial_version_author_approval_received'] is False
assert load('evidence/native_latex_check.json')['source_sha256'] == sha('manuscript.tex')

now = datetime.now(timezone.utc).isoformat()
actions = [
    'Author reads and approves the revised wording before actual submission; prior scientific-candidate approval is retained.',
    'Author verifies original cited sources in accordance with IOP requirements.',
    'Author completes the JNE portal submission, checks the generated review PDF and accepts the relevant submission/licensing agreements.',
    'Register ORCID if required by the submission portal; no ORCID identifier is invented.'
]
editor = {
    'schema_version': 3,
    'status': 'submission_editorial_semantic_review_passed',
    'reviewed_at_utc': now,
    'scope': 'Current independent prose/claim review. Older author/scientific receipts remain historical; changed paragraphs are reviewed by the current report, not certified through stale hashes.',
    'checks': language['checks'], 'checks_failed': [],
    'input_sha256': language['input_sha256'],
    'bound_inputs': len(language['input_sha256']),
    'remaining_submission_actions': actions,
    'new_decoder_fits': 0, 'new_checkpoint_inference': 0, 'raw_EEG_read': False,
    'prior_scientific_candidate_author_approval_retained': True,
    'new_editorial_version_author_approval_received': False,
    'journal_submission_performed': False
}
(P / 'evidence/quality_update/submission_editorial_review.json').write_text(json.dumps(editor, indent=2, ensure_ascii=False) + '\n')
(P / 'evidence/quality_update/submission_editorial_review.md').write_text(
    '# Current independent editorial review\n\n'
    f"{len(language['checks'])} current checks passed, bound to {len(language['input_sha256'])} exact inputs. "
    'The reviewed language distinguishes exploratory development from frozen external pipeline contrasts, '
    'mean benefit from participant distributions, and sensor descriptions from mechanisms. '
    'No new statistics, experiments, raw processing or inference were performed.\n\n'
    'Original titles and technical strings are retained; ordinary narrative uses British spelling with Oxford -ize/-ization. '
    'The author approved the preceding scientific candidate. The edited wording still requires an author read before actual submission. '
    'Real AI assistance remains disclosed and historical model identity remains author-reported.\n'
)

checks = {'language_' + k: v for k, v in language['checks'].items()}
checks.update({'package_' + k: v for k, v in package['checks'].items()})
checks.update({'layout_' + k: v for k, v in layout['checks'].items()})
checks.update({
    'numeric_422_checks_261_display_cells_passed': True,
    'protected_16417_scientific_files_unchanged': True,
    'current_language_numeric_citation_and_asset_checks_passed': all(edits['checks'].values()),
    'current_106_integrity_checks_passed': len(integrity['checks']) == 106,
    'all_secondary_review_bindings_current': True,
    'JNE_package_current_member_hashes_verified': True,
    'native_TeX_compilation_unverified_not_claimed': load('evidence/native_latex_check.json')['latex_compilation_confirmed'] is False,
    'prior_author_approval_retained_new_approval_not_invented': True,
    'no_journal_submission_acceptance_or_DOI_claim': True,
})
assert all(checks.values())
excluded = {
    'evidence/source_snapshot.json', 'evidence/delivery_validation.json',
    'evidence/final_scientific_review.json', 'evidence/final_scientific_review.md',
    'MANIFEST.sha256', 'paper_bundle_zero_calibration_q16_20261006.zip',
    'paper_bundle_zero_calibration_q16_20261006.zip.sha256'
}
names = {
    f.relative_to(P).as_posix() for f in P.rglob('*')
    if f.is_file() and '__pycache__' not in f.parts and f.suffix != '.pyc'
    and not f.name.startswith('.') and f.relative_to(P).as_posix() not in excluded
}
names.add('../../README.md')
hashes = {name: sha(name) for name in sorted(names)}
boundaries = list(prior['claim_boundaries'])
boundaries[7] = boundaries[7].replace('higher accuracy', 'higher balanced accuracy')
boundaries[-1] = ('No funding, no competing interests and no required ethics approval/exemption remain author-confirmed. '
    'Prior sole-authorship, originality/exclusive-submission and scientific-candidate approval declarations are retained. '
    'New editorial wording requires author reading before actual submission; no new human approval is invented.')
counts = {
    'numeric_checks': len(numeric['checks']), 'numeric_cells': numeric['numeric_display_cells_checked'],
    'language_integrity_checks': len(edits['checks']), 'edited_blocks': edits['block_edits'],
    'companion_edits': edits['companion_file_edits'],
    'independent_language_checks': len(language['checks']),
    'independent_package_checks': len(package['checks']), 'layout_checks': len(layout['checks']),
    'protected_scientific_files': integrity['protected_scientific_file_count'],
    'submission_integrity_checks': len(integrity['checks'])
}
report = {
    'schema_version': 6, 'status': 'scientific_and_numerical_review_passed',
    'scope': 'Current text/claim, export/presentation and saved-number consistency review. No frozen scientific result changed; archived raw and checkpoint validations retain their original scope and were not rerun.',
    'created_at_utc': now, 'checks': checks, 'checks_failed': [],
    'input_sha256': hashes, 'bound_artifact_count': len(hashes),
    'manuscript_block_count': len(load('manuscript_content.json')['blocks']), 'reference_count': 28,
    'new_fits': 0, 'new_checkpoint_inference': 0, 'new_decoder_inference': 0,
    'new_statistical_outputs': 0, 'raw_EEG_processed': False, 'checkpoints_deserialized': False,
    'archived_Q16_independent_raw_replay': prior['archived_Q16_independent_raw_replay'],
    'claim_boundaries': boundaries,
    'remaining_author_confirmation_items': ['read_revised_wording_before_actual_submission'],
    'prior_scientific_candidate_author_approval_retained': True,
    'new_editorial_version_author_approval_received': False,
    'remaining_submission_actions': actions,
    'historical_scientific_review': {
        'path': 'evidence/language_refinement/prior_evidence__final_scientific_review.json',
        'sha256': sha('evidence/language_refinement/prior_evidence__final_scientific_review.json'),
        'fresh_raw_or_checkpoint_replay': False,
        'prior_exact_export_bindings_are_historical_not_current': True
    },
    'fresh_secondary_reviews': counts,
    'native_TeX_compilation_confirmed': False,
    'journal_submission_performed': False, 'archive_DOI_created': False
}
(P / 'evidence/final_scientific_review.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
(P / 'evidence/final_scientific_review.md').write_text(
    '# Current language-refined manuscript delivery review\n\n'
    f"Status: {report['status']}. {len(checks)} synthesis checks passed, bound to {len(hashes)} exact files.\n\n"
    f"The saved-number review passed 422 checks for 261 display cells; {counts['language_integrity_checks']} "
    f"edit-integrity checks cover {counts['edited_blocks']} manuscript prose/caption/note changes and "
    f"{counts['companion_edits']} companion replacements. All 16,417 protected scientific files and the "
    'frozen tables, quantitative figure assets, equations and references remain byte-identical. '
    'Independent current scientific-language, layout and submission-package reviews bind the delivered exports.\n\n'
    'Three empirical contributions are foregrounded: source-only selection diagnostics, participant-level '
    'interpretation of concentrated gains, and retained frozen external adverse/uncertain evidence. '
    'Class-recall tradeoffs, conditional uncertainty and validation/measurement/physiology boundaries support them. '
    'No new algorithm, first/SOTA assertion, cohort interaction, mechanism, equivalence, clinical or online claim is introduced.\n\n'
    'Q1–Q16 model results and original independent validations keep their original scope. No new fits, '
    'checkpoint inference, raw EEG processing, statistical endpoints, p-values or intervals were computed. '
    'Older export receipts are preserved as historical records and do not certify this revision.\n\n'
    'Prior author declarations and scientific-candidate approval are retained. The revised wording needs an '
    'author read before actual JNE submission. AI assistance remains truthfully disclosed. The author handles '
    'original-source verification, portal declarations, the generated review PDF and licensing agreements. '
    'The delivered PDFs are inspected ReportLab exports; native TeX compilation remains unverified after '
    'uncompleted native-tool attempts. No submission, acceptance or DOI is claimed.\n'
)
print(json.dumps({'status': report['status'], 'checks': len(checks), 'bindings': len(hashes), 'counts': counts}))
