"""#194: the one-live-file-per-process guard."""
from _live_guard import live_modules, multi_live_error

A = "tests/integration/test_issue168_wordform_category_link_live.py::test_x"
B = "tests/integration/test_issue169_relocated_dedup_live.py::test_y"
ORDER = "tests/integration/test_034_move_gate_order.py::test_z"
LIVE = {"FLEXLIBS_REQUIRE_LIVE": "1"}


def test_two_live_files_rejected():
    msg = multi_live_error([A, B], LIVE)
    assert msg and "#194" in msg


def test_one_live_file_many_tests_ok():
    assert multi_live_error([A, A + "2"], LIVE) is None


def test_non_live_files_do_not_count():
    assert live_modules([A, ORDER]) == [A.split("::")[0]]
    assert multi_live_error([A, ORDER], LIVE) is None


def test_inert_without_require_live_and_with_override():
    assert multi_live_error([A, B], {}) is None
    assert multi_live_error([A, B], dict(LIVE, GRAMTRANS_ALLOW_MULTI_LIVE="1")) is None


def test_windows_separators():
    assert len(live_modules([A.replace("/", "\\"), B.replace("/", "\\")])) == 2
