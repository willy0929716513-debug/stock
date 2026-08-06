import json

from src.pipeline import health_check


def test_compute_next_count_resets_on_new_data():
    assert health_check.compute_next_count(previous_count=2, signal_count=10, data_changed=True) == 0


def test_compute_next_count_increments_when_no_data_changed():
    assert health_check.compute_next_count(previous_count=1, signal_count=10, data_changed=False) == 2


def test_compute_next_count_increments_on_zero_signals_even_if_changed():
    # 訊號數量歸零本身就是整批抓取失敗的訊號,即使檔案內容技術上「有變化」也要算失敗
    assert health_check.compute_next_count(previous_count=0, signal_count=0, data_changed=True) == 1


def test_compute_next_count_starts_at_zero_for_first_successful_run():
    assert health_check.compute_next_count(previous_count=0, signal_count=5, data_changed=True) == 0


def test_should_pause_at_threshold():
    assert health_check.should_pause(3) is True
    assert health_check.should_pause(4) is True
    assert health_check.should_pause(2) is False


def test_load_previous_count_defaults_to_zero_when_missing(tmp_path):
    path = tmp_path / "pipeline_health.json"
    assert health_check.load_previous_count(path) == 0


def test_load_previous_count_defaults_to_zero_on_corrupt_file(tmp_path):
    path = tmp_path / "pipeline_health.json"
    path.write_text("not valid json", encoding="utf-8")
    assert health_check.load_previous_count(path) == 0


def test_update_health_file_persists_and_returns_count(tmp_path):
    path = tmp_path / "pipeline_health.json"

    count1 = health_check.update_health_file(signal_count=10, data_changed=True, path=path)
    assert count1 == 0

    count2 = health_check.update_health_file(signal_count=10, data_changed=False, path=path)
    assert count2 == 1

    count3 = health_check.update_health_file(signal_count=10, data_changed=False, path=path)
    assert count3 == 2

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["consecutive_no_update"] == 2
    assert saved["last_signal_count"] == 10
    assert "last_run_at" in saved


def test_update_health_file_resets_after_recovery(tmp_path):
    path = tmp_path / "pipeline_health.json"
    health_check.update_health_file(signal_count=10, data_changed=False, path=path)
    health_check.update_health_file(signal_count=10, data_changed=False, path=path)

    recovered = health_check.update_health_file(signal_count=10, data_changed=True, path=path)
    assert recovered == 0


def test_three_consecutive_failures_reaches_pause_threshold(tmp_path):
    path = tmp_path / "pipeline_health.json"
    counts = [
        health_check.update_health_file(signal_count=0, data_changed=True, path=path)
        for _ in range(3)
    ]
    assert counts == [1, 2, 3]
    assert health_check.should_pause(counts[-1]) is True
