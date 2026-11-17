"""Evaluate a completed real-model soak, retaining failures and missing evidence."""
import argparse
import json
import statistics
from pathlib import Path


def evaluate(result):
    samples = result.get('samples', [])
    start = samples[0]['time'] if samples else 0
    end = samples[-1]['time'] if samples else 0
    duration = result.get('duration_seconds', 1800)
    short = duration == 300
    warmup, window = (60, 60) if short else (300, 300)
    early = [s for s in samples if warmup <= s['time']-start < warmup+window]
    late = [s for s in samples if s['time'] >= end-window]
    keys = set.intersection(*(set(s.get('service_rss_bytes', {})) for s in early+late)) if early and late else set()
    growth = {}
    for key in keys:
        before = statistics.mean(s['service_rss_bytes'][key] for s in early)
        after = statistics.mean(s['service_rss_bytes'][key] for s in late)
        growth[key] = {'early_mean_bytes': before, 'late_mean_bytes': after,
                       'growth_percent': (after/before-1)*100 if before else None}
    if early and late and all('ollama_rss_bytes' in s for s in early+late):
        before = statistics.mean(s['ollama_rss_bytes'] for s in early)
        after = statistics.mean(s['ollama_rss_bytes'] for s in late)
        growth['ollama'] = {'early_mean_bytes': before, 'late_mean_bytes': after,
                            'growth_percent': (after/before-1)*100 if before else None}
    assessment = result.get('assessment', {})
    count = int(assessment.get('Request Count', 0))
    failures = int(assessment.get('Failure Count', 0))
    api = [r for r in result.get('stats', []) if r.get('Type') not in {'', 'E2E'} and r.get('Name') != 'login']
    checks = {
        'full_requested_duration': duration in {300, 1800, 7200} and end-start >= duration,
        'clean_exit': result.get('exit_code') == 0 and not result.get('guard_stop'),
        'all_assessments_observed': result.get('unobserved_assessments', 1) == 0 and count > 0,
        'assessment_errors_below_one_percent': count > 0 and failures/count < .01,
        'assessment_p95_under_30s': 0 < float(assessment.get('95%', 0)) <= 30000,
        'assessment_p99_under_60s': 0 < float(assessment.get('99%', 0)) <= 60000,
        'api_latency_and_errors': bool(api) and all(int(r['Failure Count']) == 0 and float(r['95%']) <= 1000 and float(r['99%']) <= 2000 for r in api),
        'service_memory_growth_under_ten_percent': bool(keys) and 'ollama' in growth and all(v['growth_percent'] is not None and v['growth_percent'] <= 10 for v in growth.values()),
        'queue_age_under_deadline': bool(samples) and max(s.get('oldest_job_age_seconds', 0) for s in samples) <= 180,
        'no_sustained_queue_growth': bool(early and late) and statistics.mean(s.get('queue_depth_including_running', 0) for s in late) <= statistics.mean(s.get('queue_depth_including_running', 0) for s in early)+1,
        'unchanged_service_instances': bool(keys) and all(set(s.get('service_rss_bytes', {})) == keys for s in early+late),
    }
    return {'passed': all(checks.values()), 'checks': checks, 'observations': count, 'failures': failures,
            'requested_seconds': duration,
            'memory_windows': f'{warmup}–{warmup+window} seconds after start versus final {window} seconds; mean RSS per unchanged service instance',
            'memory_growth': growth, 'observed_seconds': end-start,
            'p50_ms': float(assessment.get('50%', 0)), 'p95_ms': float(assessment.get('95%', 0)), 'p99_ms': float(assessment.get('99%', 0)),
            'achieved_assessments_per_second': count/result.get('elapsed_seconds', 1),
            'maximum_queue_depth': max((s.get('queue_depth_including_running', 0) for s in samples), default=0),
            'maximum_queue_age_seconds': max((s.get('oldest_job_age_seconds', 0) for s in samples), default=0),
            'peak_host_cpu_percent': max((s.get('cpu_percent', 0) for s in samples), default=0),
            'peak_gpu_memory_mib': max((s.get('gpu', {}).get('memory_used_mib', 0) for s in samples), default=0),
            'limitation': 'Synthetic local workload. Five minutes is a short stability check, not long-duration reliability evidence. Histogram percentiles, especially p99 with small samples, are estimates. Human turnaround excluded.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('artifact', type=Path)
    args = parser.parse_args()
    report = evaluate(json.loads(args.artifact.read_text()))
    outcome_path = args.artifact.with_name(args.artifact.stem+'_outcomes.json')
    outcomes = json.loads(outcome_path.read_text()) if outcome_path.exists() else {}
    report['outcomes'] = outcomes
    report['checks']['outcome_evidence_present'] = bool(outcomes)
    report['checks']['automatic_precedent_exercised'] = outcomes.get('decision_source:precedent', 0) > 0
    report['checks']['no_exception_approved'] = not any(value for key, value in outcomes.items() if key.split(':')[0] in {'injection', 'waiting_period', 'out_of_corpus'} and ':approved:' in key)
    report['passed'] = all(report['checks'].values())
    output = args.artifact.with_name(args.artifact.stem+'-evaluation.json')
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
