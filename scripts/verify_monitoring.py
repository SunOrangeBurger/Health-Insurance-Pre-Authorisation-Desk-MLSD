"""Telemetry startup smoke; does not measure capacity or load-test percentiles."""
import json
import time
from pathlib import Path
import httpx


def main():
    client = httpx.Client(timeout=5)
    for attempt in range(45):
        try:
            targets = client.get('http://localhost:9090/api/v1/targets').json()['data']['activeTargets']
            if len(targets) == 4 and all(t['health'] == 'up' for t in targets):
                break
        except (httpx.HTTPError, KeyError, ValueError):
            pass
        time.sleep(1)
    else:
        raise AssertionError('Not all four monitoring targets became healthy')
    dashboard = client.get('http://localhost:3000/api/dashboards/uid/preauth-overview').json()
    assert dashboard['meta']['provisioned']
    panels = dashboard['dashboard']['panels']
    assert any('p99' in p.get('title', '') for p in panels)
    health = client.get('http://localhost:3000/api/health').json()
    assert health['database'] == 'ok'
    services = client.get('http://localhost:16686/api/services').json()['data']
    assert {'preauth-worker', 'preauth-api'}.issubset(services)
    traces = client.get('http://localhost:16686/api/traces', params={'service': 'preauth-worker', 'limit': 1}).json()['data']
    assert traces
    query = client.get('http://localhost:9090/api/v1/query', params={'query': 'sum(preauth_worker_run_seconds_count)'}).json()
    assert query['status'] == 'success' and query['data']['result']
    result = {'passed': True, 'targets': [{'job': t['labels']['job'], 'health': t['health']} for t in targets],
        'grafana_health': health, 'dashboard_uid': 'preauth-overview', 'p99_panel_present': True,
        'jaeger_services': services, 'worker_trace_id': traces[0]['traceID'],
        'worker_observations': query['data']['result'],
        'limitation': 'Startup and ingestion smoke only; not load/stress/soak evidence.'}
    Path('docs/evidence/monitoring-smoke.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
