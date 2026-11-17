import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('soak_report', Path(__file__).resolve().parents[1] / 'scripts/summarize_soak.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample_result():
    return {'duration_seconds': 1800, 'elapsed_seconds': 1810, 'exit_code': 0,
            'guard_stop': None, 'unobserved_assessments': 0,
            'assessment': {'Request Count': '100', 'Failure Count': '0', '50%': '4000', '95%': '8000', '99%': '10000'},
            'stats': [{'Type': 'GET', 'Name': 'case detail', 'Failure Count': '0', '95%': '20', '99%': '30'}],
            'samples': [{'time': t, 'service_rss_bytes': {'worker:1': 1000}, 'ollama_rss_bytes': 1000,
                         'queue_depth_including_running': 0, 'oldest_job_age_seconds': 0} for t in range(0, 1806, 5)]}


def test_full_soak_and_memory_regression():
    result = sample_result()
    assert module.evaluate(result)['passed']
    for s in result['samples']:
        if s['time'] >= 1500:
            s['service_rss_bytes']['worker:1'] = 1200
    assert not module.evaluate(result)['checks']['service_memory_growth_under_ten_percent']


def test_interruption_and_failed_exit_never_pass():
    result = sample_result()
    result['samples'] = result['samples'][:100]
    assert not module.evaluate(result)['passed']
    result = sample_result()
    result['exit_code'] = 1
    assert not module.evaluate(result)['passed']


def test_user_requested_five_minute_profile_has_comparable_windows():
    result = sample_result()
    result['duration_seconds'] = 300
    result['elapsed_seconds'] = 310
    result['samples'] = result['samples'][:62]
    report = module.evaluate(result)
    assert report['passed']
    assert report['requested_seconds'] == 300
    assert '60–120' in report['memory_windows']


def test_normal_five_second_sampling_gap_does_not_shorten_runtime():
    result = sample_result()
    result['duration_seconds'] = 300
    result['elapsed_seconds'] = 302
    result['samples'] = result['samples'][:60]
    assert module.evaluate(result)['checks']['full_requested_duration']
    result['elapsed_seconds'] = 290
    assert not module.evaluate(result)['checks']['full_requested_duration']
