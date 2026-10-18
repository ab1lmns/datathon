"""Full standalone regression with automatic restoration of the live service.

Run on the GPU host after staging a backend copy. Never writes credentials.
"""
import argparse
import base64
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
import httpx


def wait_ready(client, base, process=None):
    for _ in range(180):
        if process is not None and process.poll() is not None:
            raise RuntimeError('standalone process exited')
        try:
            h = client.get(base+'/api/v1/health', timeout=2)
            if h.status_code == 200 and h.json().get('worker') == 'ready':
                return h.json()
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise TimeoutError('worker readiness')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--backend',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--expected',type=Path,required=True)
    p.add_argument('--videos',type=Path,required=True)
    a=p.parse_args()
    a.output.mkdir(exist_ok=False,parents=True)
    client=httpx.Client(trust_env=False)
    health=client.get('http://127.0.0.1:17070/api/v1/health').json()
    if health.get('busy') or health.get('queue') or health.get('worker')!='ready':
        raise RuntimeError('production is not idle; refusing interruption')
    pid=subprocess.check_output(['supervisorctl','pid','forte_api'],text=True).strip()
    env={k.decode():v.decode() for k,v in [x.split(b'=',1) for x in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0') if b'=' in x]}
    env.update(FORTE_DATA_DIR=str(a.backend/'data/service'),FORTE_LEGACY_DB='',
               FORTE_OBSERVATIONS='1',FORTE_MAX_ACTIVE_JOBS='1',
               OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false')
    process=None
    stopped=False
    def interrupted(*args):
        raise KeyboardInterrupt('release check interrupted')
    signal.signal(signal.SIGTERM,interrupted)
    try:
        stopped=True
        subprocess.run(['supervisorctl','stop','forte_api'],check=True)
        with (a.output/'api.log').open('w') as log:
            process=subprocess.Popen([sys.executable,'-m','uvicorn','service.app:app','--host','127.0.0.1','--port','17071'],cwd=a.backend,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        print('standalone ready',wait_ready(client,'http://127.0.0.1:17071',process),flush=True)
        with (a.output/'regression.log').open('w') as log:
            subprocess.run([sys.executable,str(a.backend/'research/baseline_api.py'),
                '--base','http://127.0.0.1:17071','--videos',str(a.videos),
                '--reference',str(a.reference),'--output',str(a.output/'api_40.json')],
                env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=3600)
        actual=json.loads((a.output/'api_40.json').read_text())
        expected=json.loads(a.expected.read_text())
        by_video={r['video']:r for r in expected['rows']}
        differences=[]
        details=[]
        for row in actual['rows']:
            ref=by_video[row['video']]
            if row['events']!=ref['events'] or row['verdict']!=ref['verdict']:
                differences.append(row['video'])
            full=json.loads((a.backend/'data/service/jobs'/f"{row['job_id']}.json").read_text())['result']
            assert full['meta']['model_version']=='forte-observations-v1'
            details.append(dict(video=row['video'],meta=full['meta'],explain=full['explain']))
        assert len(actual['rows'])==40
        assert actual['counts']==dict(tp=17,fn=4,fp=0,tn=19),actual['counts']
        assert not differences, differences
        unauthorized=client.get('http://127.0.0.1:17071/api/v1/jobs/nonexistent').status_code
        assert unauthorized==401
        summary=dict(counts=actual['counts'],misses=actual['misses'],videos=40,
            exact_event_matches_with_candidate=40,max_request_sec=max(r['wall_sec'] for r in actual['rows']),
            standalone=True,unauthorized_status=unauthorized,production_deployed=False)
        (a.output/'details.json').write_text(json.dumps(details,ensure_ascii=False,indent=2))
        (a.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
        print(json.dumps(summary,ensure_ascii=False),flush=True)
    finally:
        if process is not None:
            try:
                os.killpg(process.pid,signal.SIGTERM)
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait(timeout=10)
            except ProcessLookupError:
                pass
        if stopped:
            subprocess.run(['supervisorctl','start','forte_api'],check=True)
            h=wait_ready(client,'http://127.0.0.1:17070')
            (a.output/'production_restored.json').write_text(json.dumps(h))
            print('production restored',h,flush=True)
        client.close()


if __name__=='__main__':
    main()
