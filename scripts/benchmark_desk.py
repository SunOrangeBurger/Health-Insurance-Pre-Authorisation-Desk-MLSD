"""Bounded local benchmark supervisor. Run from project root on Windows."""
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import psutil

ROOT = Path.cwd()
OUT = ROOT / 'loadtest/results/desk'
COMPOSE = ['wsl', '-d', 'Ubuntu', '--cd', '/mnt/d/Fedora-Recovery/Projects/mlsd-mini-project', '--',
           'env', 'OLLAMA_HOST_IP=172.27.160.1', '/usr/bin/docker', 'compose', '-f', 'docker-compose.yml', '-f', 'docker-compose.desk.yml']


def queue_state():
    script = 'local x=redis.call("ZRANGE",KEYS[1],0,0,"WITHSCORES"); return {redis.call("ZCARD",KEYS[1]),x[2] or "0"}'
    command = ['wsl', '-d', 'Ubuntu', '--', '/usr/bin/docker', 'exec', 'mlsd-mini-project-redis-1',
               'redis-cli', '--raw', 'EVAL', script, '1', 'arq:queue']
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    result.check_returncode()
    count, score = result.stdout.strip().splitlines()
    return {'queue_depth_including_running': int(count), 'oldest_job_age_seconds': max(0, time.time()-float(score)/1000) if int(count) else 0}


def stage(label, users, seconds=180):
    prefix = OUT / label
    command = [sys.executable, '-m', 'locust', '-f', 'loadtest/desk.py', '--headless', '-u', str(users), '-r', '1',
               '--run-time', str(seconds)+'s', '--stop-timeout', '120', '--host', 'http://localhost:8000',
               '--csv', str(prefix), '--csv-full-history', '--only-summary']
    samples = []
    stopped = None
    low_since = None
    with (OUT/(label+'.log')).open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        while process.poll() is None:
            memory = psutil.virtual_memory()
            sample = {'time': time.time(), 'available_bytes': memory.available, 'cpu_percent': psutil.cpu_percent()}
            try:
                sample.update(queue_state())
                if sample['oldest_job_age_seconds'] > 180:
                    stopped = 'Oldest queued/running job exceeded 180 seconds'
                    process.terminate()
            except (subprocess.SubprocessError, ValueError):
                stopped = 'Queue/resource monitor failed'
                process.terminate()
            samples.append(sample)
            reserve = max(2*1024**3, memory.total*.15)
            if memory.available < reserve:
                low_since = low_since or time.time()
                if time.time()-low_since >= 30:
                    stopped = 'RAM reserve breached for 30 seconds'
                    process.terminate()
            else:
                low_since = None
            time.sleep(5)
        code = process.wait()
    result = {'label': label, 'users': users, 'duration_seconds': seconds, 'exit_code': code, 'guard_stop': stopped,
              'minimum_available_bytes': min(s['available_bytes'] for s in samples), 'samples': samples}
    if Path(str(prefix)+'_stats.csv').exists():
        rows = list(csv.DictReader(Path(str(prefix)+'_stats.csv').open()))
        result['stats'] = rows
        e2e = next((r for r in rows if r.get('Type') == 'E2E'), None)
        if e2e:
            result['assessment'] = {k: e2e[k] for k in ['Request Count', 'Failure Count', '50%', '95%', '99%', 'Requests/s']}
            submitted = next((r for r in rows if r.get('Name') == 'case submission'), {})
            accepted = int(submitted.get('Request Count', 0))-int(submitted.get('Failure Count', 0))
            result['unobserved_assessments'] = max(0, accepted-int(e2e['Request Count']))
    (OUT/(label+'.json')).write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k not in {'samples', 'stats'}}), flush=True)
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for users in [1, 2, 4, 8]:
        result = stage('workers3-users'+str(users), users)
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
    results.append(stage('workers3-recovery', 1, 60))
    (OUT/'benchmark-summary.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
