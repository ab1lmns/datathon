"""Fresh sequential API regression. References are used only after inference.

Run with FORTE_API_KEY in the environment. No video bytes/keys enter the report.
"""
import argparse
import base64
import hashlib
import json
import os
import time
from pathlib import Path

import httpx


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--videos', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--base', default='http://127.0.0.1:17070')
    a = p.parse_args()
    if a.output.exists():
        raise FileExistsError(a.output)
    refs = json.loads(a.reference.read_text())['rows']
    paths = []
    hashes = set()
    for r in refs:
        path = a.videos / (r['video'].replace('X', 'Х') + '.mov')
        if not path.exists():
            path = a.videos / (r['video'] + '.mov')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in hashes:
            raise ValueError('duplicate source video')
        hashes.add(digest)
        paths.append((r['video'], path, digest))
    session = httpx.Client(trust_env=False)
    session.headers['X-API-Key'] = os.environ['FORTE_API_KEY']
    rows = []
    a.output.parent.mkdir(parents=True, exist_ok=True)
    for number, (name, path, digest) in enumerate(paths, 1):
        # Yield the GPU to externally submitted work between our jobs.
        start_wait = time.monotonic()
        while True:
            h = session.get(a.base + '/api/v1/health', timeout=15)
            h.raise_for_status()
            health = h.json()
            if not health.get('busy') and not health.get('queue', 0):
                break
            if time.monotonic() - start_wait > 600:
                raise TimeoutError('API did not become idle')
            time.sleep(2)
        start = time.monotonic()
        with path.open('rb') as f:
            r = session.post(a.base + '/api/v1/analyze', files={'file': ('video.mov', f, 'video/quicktime')}, timeout=60)
        r.raise_for_status()
        job = r.json()['job_id']
        while True:
            r = session.get(a.base + '/api/v1/jobs/' + job, timeout=30)
            r.raise_for_status()
            response = r.json()
            if response['status'] in ('done', 'failed'):
                break
            if time.monotonic() - start > 320:
                raise TimeoutError(job)
            time.sleep(0.5)
        events = []
        for event in response.get('violations', []):
            event = dict(event)
            clean_frames = []
            for frame in event.get('evidence_frames', []):
                frame = dict(frame)
                jpeg = base64.b64decode(frame.pop('image_base64'), validate=True)
                if not jpeg.startswith(b'\xff\xd8'):
                    raise ValueError('invalid JPEG evidence')
                frame['image_sha256'] = hashlib.sha256(jpeg).hexdigest()
                clean_frames.append(frame)
            if not 1 <= len(clean_frames) <= 3:
                raise ValueError('expected 1-3 evidence frames')
            event['evidence_frames'] = clean_frames
            events.append(event)
        row = dict(video=name, source_sha256=digest, job_id=job,
                   status=response['status'], verdict=response.get('verdict'), events=events,
                   wall_sec=round(time.monotonic()-start, 2))
        rows.append(row)
        a.output.write_text(json.dumps({'status': 'running', 'rows': rows}, ensure_ascii=False, indent=2))
        print(f"{number}/{len(paths)} {name} {row['status']} {row['verdict']} {row['wall_sec']}s", flush=True)
        if row['status'] != 'done':
            raise RuntimeError(f'failed job: {job}')
    counts = dict(tp=0, fn=0, fp=0, tn=0)
    misses, false_positives = [], []
    for row, ref in zip(rows, refs):
        positive = row['verdict'] == 'violation'
        category = ('tp' if positive else 'fn') if ref['label_positive'] else ('fp' if positive else 'tn')
        counts[category] += 1
        if category == 'fn':
            misses.append(row['video'])
        if category == 'fp':
            false_positives.append(row['video'])
    result = dict(status='completed', dataset='Known development videos; not independent evaluation',
                  counts=counts, misses=misses, false_positives=false_positives, rows=rows)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(counts), flush=True)


if __name__ == '__main__':
    main()
