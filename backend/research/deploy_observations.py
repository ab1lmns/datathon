"""Promote the tested standalone modules; rollback on startup/smoke failure."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import httpx
from research.run_standalone_release import wait_ready

LIVE=Path('/workspace/forte_live_20261018')
STAGE=Path('/workspace/forte_standalone_release_20261018/backend')
EVALUATION=STAGE.parent/'evaluation'
FILES=['forte/pipeline.py','forte/patch_features.py','forte/folder_observations.py',
       'forte/reflection.py','forte/observations.py','models/folder_patch_heads.joblib',
       'deploy/current-release-sha256.json','scripts/verify_source.py']


def main():
    report=json.loads((EVALUATION/'summary.json').read_text())
    assert report['counts']==dict(tp=17,fn=4,fp=0,tn=19)
    assert report['exact_event_matches_with_candidate']==40
    client=httpx.Client(trust_env=False)
    base='http://127.0.0.1:17070'
    h=wait_ready(client,base)
    if h['busy'] or h['queue']:
        raise RuntimeError('production busy, refusing deployment')
    pid=subprocess.check_output(['supervisorctl','pid','forte_api'],text=True).strip()
    env=dict(x.split(b'=',1) for x in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0') if b'=' in x)
    if env.get(b'FORTE_OBSERVATIONS',b'1')!=b'1':
        raise RuntimeError('deployment feature disabled in service environment')
    client.headers['X-API-Key']=env[b'FORTE_API_KEY'].decode()
    backup=Path('/workspace/forte_rollback_before_observations_20261018')
    backup.mkdir(exist_ok=False)
    absent=[]
    for name in FILES:
        assert (STAGE/name).is_file(),name
        if (LIVE/name).exists():
            (backup/name).parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(LIVE/name,backup/name)
        else:
            absent.append(name)
    (backup/'absent.json').write_text(json.dumps(absent))
    stopped=False
    try:
        stopped=True
        subprocess.run(['supervisorctl','stop','forte_api'],check=True)
        for name in FILES:
            target=LIVE/name
            target.parent.mkdir(parents=True,exist_ok=True)
            temporary=target.with_name(target.name+'.new')
            shutil.copy2(STAGE/name,temporary)
            os.replace(temporary,target)
        subprocess.run(['/workspace/forte_live_env/bin/python','scripts/verify_source.py'],cwd=LIVE,check=True)
        subprocess.run(['supervisorctl','start','forte_api'],check=True)
        wait_ready(client,base)
        # Smoke the deployed process, not the stage. Also verify the preserved negative.
        rows=[]
        for video,positive in [('X-24',True),('X-30',True),('X-19',False)]:
            path=Path('/workspace/datathon/data/fortebank_official_train/videos')/(video.replace('X','Х')+'.mov')
            with path.open('rb') as f:
                response=client.post(base+'/api/v1/analyze',files={'file':('video.mov',f,'video/quicktime')},timeout=60)
            response.raise_for_status()
            job=response.json()['job_id']
            for _ in range(300):
                r=client.get(base+'/api/v1/jobs/'+job,timeout=15)
                r.raise_for_status()
                data=r.json()
                if data['status'] in ('done','failed'):break
                time.sleep(1)
            assert data['status']=='done',data.get('status')
            assert (data['verdict']=='violation')==positive,video
            full=json.loads((LIVE/'data/service/jobs'/f'{job}.json').read_text())['result']
            assert full['meta']['model_version']=='forte-observations-v1'
            if positive:
                assert len(data['violations'][-1]['evidence_frames'])==3
            rows.append(dict(video=video,job_id=job,verdict=data['verdict']))
        result=dict(production_deployed=True,model_version='forte-observations-v1',
            smoke=rows,health=client.get(base+'/api/v1/health').json(),
            files={n:hashlib.sha256((LIVE/n).read_bytes()).hexdigest() for n in FILES},rollback=str(backup))
        (EVALUATION/'deployment.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result),flush=True)
    except BaseException:
        if stopped:
            subprocess.run(['supervisorctl','stop','forte_api'],check=False)
            for name in FILES:
                if name in absent:
                    (LIVE/name).unlink(missing_ok=True)
                else:
                    shutil.copy2(backup/name,LIVE/name)
            subprocess.run(['supervisorctl','start','forte_api'],check=True)
            wait_ready(client,base)
        raise
    finally:
        client.close()


if __name__=='__main__':main()
