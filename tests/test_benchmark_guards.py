import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


def test_low_memory_prevents_starting_load_or_recovery(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / 'scripts/benchmark_desk.py'
    spec = importlib.util.spec_from_file_location('benchmark_guard_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = tmp_path
    monkeypatch.setattr(module.psutil, 'virtual_memory', lambda: SimpleNamespace(total=16*1024**3, available=1024**3))
    def forbidden(*args, **kwargs):
        raise AssertionError('Low-memory guard must prevent starting a subprocess')
    monkeypatch.setattr(module.subprocess, 'Popen', forbidden)
    for label in ['load', 'recovery']:
        result = module.stage(label, 1)
        assert result['duration_seconds'] == 0
        assert 'Preflight RAM' in result['guard_stop']


def test_queue_age_uses_redis_clock_not_windows_clock(monkeypatch):
    path = Path(__file__).resolve().parents[1] / 'scripts/benchmark_desk.py'
    spec = importlib.util.spec_from_file_location('benchmark_clock_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: SimpleNamespace(
        stdout='1\n1000000\n1010\n', check_returncode=lambda: None))
    monkeypatch.setattr(module.time, 'time', lambda: 500)
    assert module.queue_state() == {'queue_depth_including_running': 1, 'oldest_job_age_seconds': 10}
