"""Check the public gateway after deployment without printing credentials/video."""
import hashlib
import json
from pathlib import Path
import subprocess
import time
import httpx


def main():
    base='https://forte.makquiz.site:14901'
    root=Path('/workspace/forte_live_20261018')
    report=Path('/workspace/forte_standalone_release_20261018/evaluation')
    pid=subprocess.check_output(['supervisorctl','pid','forte_api'],text=True).strip()
    env=dict(x.split(b'=',1) for x in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0') if b'=' in x)
    with httpx.Client(trust_env=False,timeout=30) as client:
        statuses={path:client.get(base+path).status_code for path in ('/','/docs','/api/v1/health')}
        assert all(code==200 for code in statuses.values()),statuses
        unauthorized=client.get(base+'/api/v1/jobs/nonexistent').status_code
        assert unauthorized==401
        client.headers['X-API-Key']=env[b'FORTE_API_KEY'].decode()
        upload=Path('/workspace/datathon/data/fortebank_official_train/videos/Х-30.mov')
        start=time.monotonic()
        with upload.open('rb') as stream:
            response=client.post(base+'/api/v1/analyze',files={'file':('video.mov',stream,'video/quicktime')},timeout=90)
        response.raise_for_status()
        job=response.json()['job_id']
        for _ in range(150):
            response=client.get(base+'/api/v1/jobs/'+job)
            response.raise_for_status()
            data=response.json()
            if data['status'] in ('done','failed'):break
            time.sleep(2)
        assert data['status']=='done' and data['verdict']=='violation'
        full=json.loads((root/'data/service/jobs'/f'{job}.json').read_text())['result']
        assert full['meta']['model_version']=='forte-observations-v1'
        assert full['meta']['reflection']['added']==1
        assert len(data['violations'][-1]['evidence_frames'])==3
        event=data['violations'][-1]
        assert event['rule']['relation']=='RELATED_ONLY'
        assert event['rule']['sources']
        smoke=json.loads((report/'deployment.json').read_text())['smoke']
        for row in smoke:
            r=client.get(base+'/api/v1/jobs/'+row['job_id'])
            r.raise_for_status()
            assert r.json()['verdict']==row['verdict']
        result=dict(base=base,statuses=statuses,unauthorized_status=unauthorized,
                    uploaded='X-30',job_id=job,verdict=data['verdict'],
                    upload_and_analysis_sec=round(time.monotonic()-start,2),
                    evidence_pts=[f['timestamp_sec'] for f in event['evidence_frames']],
                    legal_relation=event['rule']['relation'],
                    smoke_results_visible_through_gateway=3)
        (report/'public_smoke.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
