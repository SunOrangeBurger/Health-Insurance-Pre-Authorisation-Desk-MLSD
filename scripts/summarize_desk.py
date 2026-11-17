"""Summarize completed Locust stage artifacts without hiding guard stops."""
import json
from pathlib import Path


def main():
    paths = sorted(Path('loadtest/results/desk').rglob('workers*-users*.json'))
    paths += sorted(Path('loadtest/results/desk').rglob('workers*-recovery.json'))
    rows = []
    lines = ['# Local load and stress results', '',
        'Real Ollama with one global inference slot. Root/nommap attempts used the 7B model; qwen3/cache0 profiles used Qwen3 4B. Profile metadata records the exact configuration. Virtual users share a seeded hospital login; login capacity and human turnaround are excluded.', '',
        '| Stage | Observations | Failed | Unobserved | p50 s | p95 s | p99 s | Assessment/s | Min free RAM GiB | Status |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for path in paths:
        result = json.loads(path.read_text())
        if 'minimum_available_bytes' not in result:
            continue  # Phase/evaluation sidecars are not load stages.
        result['label'] = str(path.relative_to('loadtest/results/desk').with_suffix('')).replace('\\', '/')
        assessment = result.get('assessment', {})
        count = int(assessment.get('Request Count', 0))
        failures = int(assessment.get('Failure Count', 0))
        unseen = result.get('unobserved_assessments', 0)
        status = 'guard stopped' if result.get('guard_stop') else ('completed' if result.get('exit_code') == 0 else 'failed exit')
        values = [float(assessment.get(key, 0)) / 1000 for key in ['50%', '95%', '99%']]
        request_rows = [r for r in result.get('stats', []) if r.get('Type') not in {'', 'E2E'} and r.get('Name') != 'login']
        api_errors = sum(int(r['Failure Count']) for r in request_rows)
        api_p95 = max((float(r['95%']) for r in request_rows), default=0)
        api_p99 = max((float(r['99%']) for r in request_rows), default=0)
        passed = status == 'completed' and result.get('exit_code') == 0 and unseen == 0 and count > 0 and failures/max(count, 1) < .01 and values[1] <= 30 and values[2] <= 60 and api_errors == 0 and api_p95 <= 1000 and api_p99 <= 2000
        rows.append({'stage': result['label'], 'observations': count, 'failures': failures, 'unobserved': unseen,
                     'status': status, 'slo_met_on_observed_samples': passed, 'api_errors': api_errors,
                     'maximum_api_endpoint_p95_ms': api_p95, 'maximum_api_endpoint_p99_ms': api_p99, 'p50_s': values[0], 'p95_s': values[1], 'p99_s': values[2]})
        lines.append(f"| {result['label']} | {count} | {failures} | {unseen} | {values[0]:.2f} | {values[1]:.2f} | {values[2]:.2f} | {float(assessment.get('Requests/s',0)):.3f} | {result['minimum_available_bytes']/2**30:.2f} | {status} |")
    lines += ['', 'Percentiles use Locust histogram buckets. Small samples, especially fewer than 100 assessments, cannot establish a robust p99. Guard-stopped runs and unobserved assessments are never reported as passing. Initial model loading may be included; no inference warmup is removed retroactively.', '',
              'A completed stage is an observation, not a claim that all SLOs passed. Machine assessment includes queue wait and polling overhead; dashboard worker processing excludes queue wait. Human approval latency is excluded. Soak testing is separate and is not established by these stages.']
    Path('docs/LOAD_STRESS_RESULTS.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    Path('loadtest/results/desk/results-summary.json').write_text(json.dumps(rows, indent=2))
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
