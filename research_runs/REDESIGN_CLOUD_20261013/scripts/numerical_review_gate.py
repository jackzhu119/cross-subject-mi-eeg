"""Fail-closed pre-resumption review gate; does not create or approve a review."""
from pathlib import Path
from cloud_contract import read, sha
from formal_core_inputs import numerical_identity

FULL_PACKAGE_SHA = '2871f422755bf5d0b939d0db59fc41547b192d6c939db1a6a13b97a91ba49ae9'


def verify_review(job):
    job = Path(job)
    review = read(job / 'numerical_execution_review.json')
    acceptance_path = job / 'formal_source_acceptance.json'
    acceptance = read(acceptance_path)
    identity = numerical_identity()
    if (review.get('status') != 'PASS_FORMAL_SOURCE_NUMERICAL_REVIEW_TARGET_GATES_REQUIRED'
            or review.get('numerical_execution') != identity
            or review.get('source_acceptance_sha256') != sha(acceptance_path)
            or review.get('private_full_package_sha256') != FULL_PACKAGE_SHA):
        raise ValueError('formal_numerical_review_absent_or_changed')
    if (acceptance.get('status') != 'SOURCE_NUMERICAL_ACCEPTANCE_MATCH_TRAINING_STILL_BLOCKED'
            or acceptance.get('numerical_execution') != identity
            or acceptance.get('source_complete_exact_hash_gate_passed') is not True
            or acceptance.get('training_consumer_imports_verified') is not True
            or acceptance.get('private_full_package_independently_verified') is not True
            or acceptance.get('private_full_package_sha256') != FULL_PACKAGE_SHA
            or acceptance.get('training_authorization') is not False):
        raise ValueError('actual_formal_source_acceptance_required')
    return review
