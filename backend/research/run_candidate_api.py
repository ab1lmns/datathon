"""One isolated loopback API regression; cleans up its process group on exit.

Runs on the existing GPU host. Reads the authorized baseline key from its process
environment without printing it. It never restarts or modifies production.
"""
import argparse
import base64
import hashlib
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and not any(
                part in ('data', '.git', '__pycache__') for part in p.relative_to(root).parts)
            and p.suffix in ('.py', '.joblib', '.json', '.css', '.html')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production', type=Path, required=True)
    parser.add_argument('--experiment', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--videos', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--port', type=int, default=17071)
    parser.add_argument('--analyzer-module', choices=('folder_candidate', 'reflection_candidate'), default='folder_candidate')
    a = parser.parse_args()
    a.production = a.production.resolve()
    a.experiment = a.experiment.resolve()
    if a.experiment == a.production or a.experiment.is_relative_to(a.production):
        raise ValueError('experiment must be separate from production')
    a.experiment.mkdir(parents=True, exist_ok=False)
    before = hashes(a.production)
    (a.experiment/'production_before.json').write_text(json.dumps(before, indent=2))
    backend = a.experiment/'backend'
    shutil.copytree(a.production, backend, ignore=shutil.ignore_patterns('data', '.git', '__pycache__', 'research'))
    (backend/'research').mkdir()
    for script in Path(__file__).parent.glob('*.py'):
        shutil.copy2(script, backend/'research'/script.name)
    worker = backend/'service/worker.py'
    source = worker.read_text()
    old = 'from forte.pipeline import Analyzer'
    if source.count(old) != 1:
        raise ValueError('unexpected worker import; refusing patch')
    worker.write_text(source.replace(old, f'from research.{a.analyzer_module} import Analyzer'))
    pid = subprocess.check_output(['supervisorctl', 'pid', 'forte_api'], text=True).strip()
    entries = Path('/proc/'+pid+'/environ').read_bytes().split(b'\0')
    key = next(x.split(b'=', 1)[1].decode() for x in entries if x.startswith(b'FORTE_API_KEY='))
    temporary_key = secrets.token_hex(32)
    env = os.environ.copy()
    env.update(FORTE_API_KEY=temporary_key, FORTE_BASE_API_KEY=key,
               FORTE_BASE_API_URL='http://127.0.0.1:17070', FORTE_BASE_BACKEND=str(a.production),
               FORTE_CANDIDATE_ONLY='1', FORTE_FOLDER_CHECKPOINT=str(a.checkpoint.resolve()),
               FORTE_DATA_DIR=str(backend/'data/service'), FORTE_KEEP_API_VIDEOS='0',
               FORTE_JOB_TIMEOUT='285', FORTE_MAX_ACTIVE_JOBS='1', FORTE_LEGACY_DB='',
               HF_HOME='/workspace/.hf_home', HF_HUB_OFFLINE='1',
               OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', TOKENIZERS_PARALLELISM='false')
    base = f'http://127.0.0.1:{a.port}'
    client = httpx.Client(trust_env=False)
    process = None
    try:
        with (a.experiment/'api.log').open('w') as log:
            process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'service.app:app',
                '--host', '127.0.0.1', '--port', str(a.port)], cwd=backend, env=env,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            for _ in range(90):
                if process.poll() is not None:
                    raise RuntimeError('candidate API exited during startup')
                try:
                    h = client.get(base+'/api/v1/health', timeout=2)
                    if h.status_code == 200 and h.json().get('worker') == 'ready':
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            else:
                raise TimeoutError('candidate worker did not become ready')
            print('candidate worker ready', flush=True)
            auth = client.get(base+'/api/v1/jobs/nonexistent', timeout=5)
            assert auth.status_code == 401
            with (a.experiment/'regression.log').open('w') as output:
                done = subprocess.run([sys.executable, str(backend/'research/baseline_api.py'),
                    '--videos', str(a.videos), '--reference', str(a.reference),
                    '--output', str(a.experiment/'candidate_api_40.json'), '--base', base],
                    env=env, stdout=output, stderr=subprocess.STDOUT, timeout=3600)
            if done.returncode:
                raise RuntimeError('candidate regression failed; inspect regression.log')
            report = json.loads((a.experiment/'candidate_api_40.json').read_text())
            unchanged, added = [], []
            for row in report['rows']:
                j = json.loads((backend/'data/service/jobs'/f"{row['job_id']}.json").read_text())
                result = j['result']
                upstream_id = result['meta']['candidate']['upstream_job_id']
                baseline = json.loads((a.production/'data/service/jobs'/f'{upstream_id}.json').read_text())['result']
                n = len(baseline['violations'])
                assert result['violations'][:n] == baseline['violations'], 'baseline events were modified'
                assert result['explain'][:len(baseline['explain'])] == baseline['explain']
                unchanged.append(row['video'])
                for event in result['violations'][n:]:
                    frames = event['evidence_frames']
                    assert len(frames) == 3
                    pts = [f['timestamp_sec'] for f in frames]
                    images = [base64.b64decode(f['image_base64'], validate=True) for f in frames]
                    assert len(set(pts)) == len(set(hashlib.sha256(im).hexdigest() for im in images)) == 3
                    assert pts[0] < event['timecode_sec'] <= pts[-1]
                    evidence_dir = a.experiment/'evidence'/row['video']
                    evidence_dir.mkdir(parents=True, exist_ok=True)
                    for frame, im in zip(frames, images):
                        (evidence_dir/f"{frame['timestamp_sec']:.6f}.jpg").write_bytes(im)
                    added.append(dict(video=row['video'], type=event['type'], timecode_sec=event['timecode_sec'], evidence_pts=pts))
            summary = dict(counts=report['counts'], videos=len(report['rows']),
                baseline_events_preserved=len(unchanged), added=added,
                max_request_sec=max(r['wall_sec'] for r in report['rows']),
                unauthenticated_status=auth.status_code, production_deployed=False,
                architecture='isolated loopback API + live local baseline worker + '+a.analyzer_module,
                legal_basis_for_folder='not_established', independent_evaluation=False)
            (a.experiment/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
            print(json.dumps(summary, ensure_ascii=False), flush=True)
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
            except ProcessLookupError:
                pass
        after = hashes(a.production)
        changed = sorted(k for k in set(before)|set(after) if before.get(k)!=after.get(k))
        (a.experiment/'production_integrity.json').write_text(json.dumps(dict(
            checked_files=len(before), changed=changed,
            health=client.get('http://127.0.0.1:17070/api/v1/health', timeout=15).json()), indent=2))
        assert not changed, changed
        client.close()


if __name__ == '__main__':
    main()
