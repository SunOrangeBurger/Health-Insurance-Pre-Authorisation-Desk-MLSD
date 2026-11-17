"""Bounded local benchmark supervisor. Run from project root on Windows."""
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import psutil
import argparse
import httpx

ROOT = Path.cwd()
OUT = ROOT / 'loadtest/results/desk'


def telemetry_snapshot():
    """Keep stage-local histogram boundaries; never use lifetime percentiles."""
    response = httpx.get('http://localhost:9090/api/v1/query', params={
        'query': '{__name__=~"preauth_worker_run_seconds_(bucket|count|sum)|llm_call_seconds_(bucket|count|sum)|agent_step_seconds_(bucket|count|sum)|agent_runs_total"}'}, timeout=5)
    response.raise_for_status()
    payload = response.json()
    if payload.get('status') != 'success':
        raise RuntimeError('Prometheus histogram snapshot failed')
    return {'time': time.time(), 'series': payload['data']['result']}


def queue_state():
    script = 'local x=redis.call("ZRANGE",KEYS[1],0,0,"WITHSCORES"); local t=redis.call("TIME"); return {redis.call("ZCARD",KEYS[1]),x[2] or "0",t[1]} '
    command = ['wsl', '-d', 'Ubuntu', '--', '/usr/bin/docker', 'exec', 'mlsd-mini-project-redis-1',
               'redis-cli', '--raw', 'EVAL', script, '1', 'arq:queue']
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    result.check_returncode()
    count, score, server_time = result.stdout.strip().splitlines()
    return {'queue_depth_including_running': int(count), 'oldest_job_age_seconds': max(0, float(server_time)-float(score)/1000) if int(count) else 0}


def stage(label, users, seconds=180, workload_env=None):
    prefix = OUT / label
    memory = psutil.virtual_memory()
    reserve = max(2*1024**3, memory.total*.15)
    if memory.available < reserve:
        result = {'label': label, 'users': users, 'duration_seconds': 0, 'exit_code': None,
                  'guard_stop': 'Preflight RAM below reserve; load was not started',
                  'minimum_available_bytes': memory.available, 'required_reserve_bytes': reserve,
                  'samples': [], 'unobserved_assessments': 0}
        (OUT/(label+'.json')).write_text(json.dumps(result, indent=2))
        print(json.dumps(result), flush=True)
        return result
    command = [sys.executable, '-m', 'locust', '-f', 'loadtest/desk.py', '--headless', '-u', str(users), '-r', '1',
               '--run-time', str(seconds)+'s', '--stop-timeout', '120', '--host', 'http://localhost:8000',
               '--csv', str(prefix), '--csv-full-history', '--only-summary']
    samples = [{'time': time.time(), 'available_bytes': memory.available}]
    stopped = None
    low_since = None
    started = time.perf_counter()
    before_metrics = telemetry_snapshot()
    with (OUT/(label+'.log')).open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   env={**os.environ, **(workload_env or {}), 'DESK_FINAL_STATS_PREFIX': str(prefix)})
        while process.poll() is None:
            memory = psutil.virtual_memory()
            sample = {'time': time.time(), 'available_bytes': memory.available, 'cpu_percent': psutil.cpu_percent()}
            try:
                sample.update(queue_state())
                metrics = httpx.get('http://localhost:9090/api/v1/query', params={
                    'query': 'process_resident_memory_bytes{job=~"api|worker"}'}, timeout=5).json()
                sample['service_rss_bytes'] = {r['metric']['job']+':'+r['metric']['instance']: float(r['value'][1])
                                               for r in metrics['data']['result']}
                if not {'api', 'worker'}.issubset({key.split(':', 1)[0] for key in sample['service_rss_bytes']}):
                    raise ValueError('Essential service telemetry missing')
                sample['ollama_rss_bytes'] = sum(p.info['memory_info'].rss for p in psutil.process_iter(['name', 'memory_info'])
                                               if (p.info['name'] or '').lower().startswith('llama-server'))
                if len(samples) % 6 == 0:
                    try:
                        gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used,utilization.gpu,temperature.gpu',
                                                       '--format=csv,noheader,nounits'], text=True, timeout=5).splitlines()[0]
                        used, utilization, temperature = [float(x.strip()) for x in gpu.split(',')]
                        sample['gpu'] = {'memory_used_mib': used, 'utilization_percent': utilization, 'temperature_c': temperature}
                    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
                        sample['gpu_telemetry_unavailable'] = True
                if sample['oldest_job_age_seconds'] > 180:
                    stopped = 'Oldest queued/running job exceeded 180 seconds'
                    stop_load(process)
            except (subprocess.SubprocessError, ValueError, KeyError, httpx.HTTPError, psutil.Error):
                stopped = 'Queue/resource monitor failed'
                stop_load(process)
            samples.append(sample)
            reserve = max(2*1024**3, memory.total*.15)
            if memory.available < reserve:
                low_since = low_since or time.time()
                if time.time()-low_since >= 30:
                    stopped = 'RAM reserve breached for 30 seconds'
                    stop_load(process)
            else:
                low_since = None
            time.sleep(5)
        code = process.wait()
    result = {'label': label, 'users': users, 'duration_seconds': seconds, 'elapsed_seconds': time.perf_counter()-started,
              'exit_code': code, 'guard_stop': stopped,
              'telemetry_before': before_metrics, 'telemetry_after': telemetry_snapshot(),
              'minimum_available_bytes': min(s['available_bytes'] for s in samples), 'samples': samples}
    for artifact in OUT.glob(label+'*.csv'):
        raw = artifact.read_bytes()
        artifact.write_bytes(raw.replace(b'\r\r\n', b'\n').replace(b'\r\n', b'\n'))
    final_path = Path(str(prefix)+'_final_stats.csv')
    stats_path = final_path if final_path.exists() else Path(str(prefix)+'_stats.csv')
    if stats_path.exists():
        rows = list(csv.DictReader(stats_path.open()))
        result['statistics_source'] = stats_path.name
        result['stats'] = rows
        e2e = next((r for r in rows if r.get('Type') == 'E2E'), None)
        if e2e:
            result['assessment'] = {k: e2e[k] for k in ['Request Count', 'Failure Count', '50%', '95%', '99%', 'Requests/s']}
            submitted = next((r for r in rows if r.get('Name') == 'case submission'), {})
            accepted = int(submitted.get('Request Count', 0))-int(submitted.get('Failure Count', 0))
            result['unobserved_assessments'] = max(0, accepted-int(e2e['Request Count']))
    (OUT/(label+'.json')).write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k not in {'samples', 'stats', 'telemetry_before', 'telemetry_after'}}), flush=True)
    return result


def stop_load(process):
    """Stop the owned tree, including Windows virtualenv redirector children."""
    try:
        parent = psutil.Process(process.pid)
        owned = parent.children(recursive=True) + [parent]
        for child in owned:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(owned, timeout=5)
        for child in alive:
            child.kill()
    except psutil.NoSuchProcess:
        pass


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, choices=[1, 3], default=1)
    parser.add_argument('--users', type=int, nargs='+', default=[1, 2, 4, 8])
    parser.add_argument('--seconds', type=int, default=180)
    parser.add_argument('--output-dir', default='loadtest/results/desk')
    parser.add_argument('--soak-minutes', type=int, choices=[0, 5, 30, 120], default=0)
    parser.add_argument('--soak-rps', type=float)
    args = parser.parse_args()
    if not os.environ.get('DESK_HOSPITAL_PASSWORD'):
        raise SystemExit('Set DESK_HOSPITAL_PASSWORD for the seeded synthetic benchmark account before starting load')
    OUT = Path(args.output_dir).resolve()
    if not OUT.is_relative_to(ROOT):
        raise SystemExit('Benchmark output must stay inside this project')
    if not all(1 <= n <= 16 for n in args.users) or not 30 <= args.seconds <= 1800:
        raise SystemExit('Users must be 1–16 and stage duration 30–1800 seconds')
    OUT.mkdir(parents=True, exist_ok=True)
    if args.soak_minutes:
        if args.soak_rps is None or not 0 < args.soak_rps <= 1:
            raise SystemExit('Specify measured sustainable soak-rps between 0 and 1')
        result = stage('workers'+str(args.workers)+'-soak', 2, args.soak_minutes*60,
                       {'DESK_SOAK_RPS': str(args.soak_rps), 'DESK_SOAK_USERS': '2', 'DESK_MIXED_WORKLOAD': '1'})
        (OUT/('workers'+str(args.workers)+'-soak-summary.json')).write_text(json.dumps(result, indent=2))
        return
    results = []
    for users in args.users:
        result = stage('workers'+str(args.workers)+'-users'+str(users), users, args.seconds)
        results.append(result)
        if result['guard_stop']:
            break
        e2e = result.get('assessment')
        if e2e and (float(e2e['95%']) > 30000 or int(e2e['Failure Count']) > 0):
            print('Saturation/failure observed; stopping escalation and measuring recovery.', flush=True)
            break
    for _ in range(36):
        if queue_state()['queue_depth_including_running'] == 0:
            break
        time.sleep(5)
    results.append(stage('workers'+str(args.workers)+'-recovery', 1, 60))
    (OUT/('workers'+str(args.workers)+'-benchmark-summary.json')).write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
