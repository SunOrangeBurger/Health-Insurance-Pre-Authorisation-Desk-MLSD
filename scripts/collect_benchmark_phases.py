"""Read aggregate timings for runs created during one benchmark stage.

No request content or patient fields leave PostgreSQL. Requires the local WSL
Compose database with its default synthetic demonstration database/user.
"""
import argparse
import json
import subprocess
from pathlib import Path
from uuid import UUID


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('artifact', type=Path)
    args = parser.parse_args()
    result = json.loads(args.artifact.read_text())
    samples = result.get('samples', [])
    if not samples:
        raise SystemExit('Stage has no observation window')
    start, end = float(samples[0]['time']), float(samples[-1]['time'])
    ids_path = args.artifact.with_name(args.artifact.stem+'_cases.json')
    if not ids_path.exists():
        raise SystemExit('Stage predates case-ID capture; do not attribute database rows using unsynchronized host clocks')
    case_ids = [str(UUID(value)) for value in json.loads(ids_path.read_text())]
    if not case_ids:
        raise SystemExit('No accepted cases were recorded')
    ids_sql = ','.join("'"+value+"'" for value in case_ids)
    sql = f"""
WITH selected AS (
 SELECT r.*, c.status AS case_status, c.decision->>'source' AS decision_source
 FROM runs r JOIN desk_cases c ON c.run_id=r.id
 WHERE c.id IN ({ids_sql})
), timings AS (
 SELECT 'queue_wait_seconds' AS phase, EXTRACT(EPOCH FROM started_at-created_at)::double precision AS seconds FROM selected
 UNION ALL SELECT 'worker_seconds', EXTRACT(EPOCH FROM completed_at-started_at)::double precision FROM selected
 UNION ALL SELECT 'submission_to_terminal_seconds', EXTRACT(EPOCH FROM completed_at-created_at)::double precision FROM selected
 UNION ALL SELECT 'ollama_assessment_seconds', (result->'ai_assessment'->>'inference_seconds')::double precision FROM selected
 UNION ALL SELECT 'automatic_final_seconds', EXTRACT(EPOCH FROM completed_at-created_at)::double precision FROM selected WHERE decision_source='precedent'
 UNION ALL SELECT 'retrieval_tool_seconds', (s.payload->>'elapsed_ms')::double precision/1000
 FROM run_steps s JOIN selected r ON r.id=s.run_id
 WHERE s.kind='tool_result' AND s.payload->>'tool' IN ('search_corpus','get_clause')
), phases AS (
 SELECT phase, count(seconds) AS observations,
 percentile_cont(0.5) WITHIN GROUP (ORDER BY seconds) AS p50_seconds,
 percentile_cont(0.95) WITHIN GROUP (ORDER BY seconds) AS p95_seconds,
 percentile_cont(0.99) WITHIN GROUP (ORDER BY seconds) AS p99_seconds
 FROM timings GROUP BY phase
), outcomes AS (
 SELECT status, case_status, coalesce(decision_source,'human_review_pending') AS decision_source, count(*) AS count
 FROM selected GROUP BY status,case_status,decision_source
)
SELECT json_build_object('phases', (SELECT json_agg(phases) FROM phases),
 'outcomes', (SELECT json_agg(outcomes) FROM outcomes),
 'window_start_epoch', {start}, 'window_end_epoch', {end},
 'attribution', 'Exact synthetic case IDs recorded by Locust; host and WSL clocks may differ.',
 'limitation', 'Database completion timings exclude client polling. Retrieval is per tool call. Human turnaround is not simulated. No automatic outcomes means that percentile has zero observations.');
"""
    command = ['wsl', '-d', 'Ubuntu', '--', '/usr/bin/docker', 'exec', '-i',
               'mlsd-mini-project-postgres-1', 'psql', '-U', 'postgres', '-d', 'preauth_db', '-At', '-v', 'ON_ERROR_STOP=1']
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, timeout=30, check=True)
    report = json.loads(completed.stdout)
    args.artifact.with_name(args.artifact.stem+'-phases.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
