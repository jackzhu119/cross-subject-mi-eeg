from scripts.check_paper_env import EXPECTED, package_mismatches


def test_paper_environment_exact_top_level_pins() -> None:
    assert package_mismatches(dict(EXPECTED)) == {}
    observed = dict(EXPECTED)
    observed.update({"torch": "2.8.0+cu128", "torchaudio": "2.8.0+cu128"})
    assert package_mismatches(observed) == {}


def test_paper_environment_rejects_mixed_torchaudio_cuda() -> None:
    observed = dict(EXPECTED)
    observed["torchaudio"] = "2.11.0+cu132"
    assert package_mismatches(observed) == {"torchaudio": ("2.8.0", "2.11.0+cu132")}
