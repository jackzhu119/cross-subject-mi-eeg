import pandas as pd

from mi_eeg.evaluation.splits import iter_cross_session, iter_loso, iter_within_session


def small_metadata() -> pd.DataFrame:
    rows = []
    for subject in (1, 2):
        for session in ("0train", "1test"):
            for run in (0, 1):
                for trial, label in ((1, 1), (2, 2)):
                    rows.append(
                        {
                            "sample_id": f"s{subject}_{session}_r{run}_t{trial}",
                            "subject": subject,
                            "session": session,
                            "run": run,
                            "trial": trial,
                            "label": label,
                        }
                    )
    return pd.DataFrame(rows)


def test_within_session_holds_out_whole_run() -> None:
    meta = small_metadata()
    splits = list(iter_within_session(meta))
    assert len(splits) == 8
    for _, train, test in splits:
        assert len(train) == 2
        assert len(test) == 2
        assert len(set(meta.loc[test, "run"])) == 1
        assert set(meta.loc[train, "run"]).isdisjoint(meta.loc[test, "run"])


def test_cross_session_has_no_session_overlap() -> None:
    meta = small_metadata()
    splits = list(iter_cross_session(meta))
    assert len(splits) == 2
    for _, train, test in splits:
        assert set(meta.loc[train, "session"]) == {"0train"}
        assert set(meta.loc[test, "session"]) == {"1test"}


def test_loso_has_no_subject_overlap_and_covers_both_sessions() -> None:
    meta = small_metadata()
    splits = list(iter_loso(meta))
    assert len(splits) == 2
    for _, train, test in splits:
        assert set(meta.loc[train, "subject"]).isdisjoint(meta.loc[test, "subject"])
        assert set(meta.loc[test, "session"]) == {"0train", "1test"}
