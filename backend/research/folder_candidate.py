"""Temporary candidate worker: local baseline API plus learned folder probe.

Never imported by the production worker. The isolated test runner installs the
worker import into a separate backend copy. No video identities/GT enter inference.
"""
import base64
import copy
import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

import cv2
import httpx
import joblib
import numpy as np
import torch
from PIL import Image

from .train_patch_objects import CONFIG, Features, boxes_from_probabilities, iou


def scan_video(path, scene, extractor, head, deadline):
    from forte.scene import inside, center
    observations, candidates = [], []
    previous = None
    cap = cv2.VideoCapture(str(path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            raise ValueError('unknown source FPS')
        step = max(1, round(fps/2))
        index, last_pts = -1, -1
        while cap.grab():
            index += 1
            if time.monotonic() > deadline:
                raise TimeoutError('candidate processing deadline exceeded')
            if index % step:
                continue
            ok, frame = cap.retrieve()
            if not ok:
                raise RuntimeError('sampled frame decode failed')
            pts = cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            if pts <= last_pts:
                raise ValueError('non-monotone decoded timestamps')
            last_pts = pts
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            features, grid = extractor(image)
            detections = boxes_from_probabilities(head.predict_proba(features)[:, 1], grid, image.size)
            nearest = int(np.argmin(np.abs(scene.times-pts)))
            empty = bool(scene.n_people[nearest] == 0 and abs(scene.times[nearest]-pts) <= 0.5)
            on_desk = [d for d in detections if scene.desk and inside(center(d['box']), scene.desk, 0.05)]
            obs = dict(frame_index=index, pts_sec=round(pts, 6), folder=detections,
                       on_desk=on_desk, empty=empty)
            observations.append(obs)
            if empty and on_desk:
                if previous and 0.45 <= pts-previous['pts_sec'] <= 0.8 and any(
                        iou(a['box'], b['box']) >= 0.3 for a in on_desk for b in previous['on_desk']):
                    candidates.append(dict(start_pts_sec=previous['pts_sec'], condition_pts_sec=round(pts, 6),
                                           frame_indices=[previous['frame_index'], index]))
                previous = obs
            else:
                previous = None
        if not observations:
            raise ValueError('no decodable observations')
    finally:
        cap.release()
    return observations, candidates


def evidence_observations(observations, event_time):
    selected = []
    for target in (event_time-1, event_time, event_time+0.5):
        obs = min(observations, key=lambda o: abs(o['pts_sec']-target))
        if all(o['frame_index'] != obs['frame_index'] for o in selected):
            selected.append(obs)
    return sorted(selected, key=lambda o: o['pts_sec'])


def render_evidence(path, observations):
    from forte.evidence_labels import render_labels
    cap = cv2.VideoCapture(str(path))
    frames = []
    try:
        for obs in observations:
            cap.set(cv2.CAP_PROP_POS_FRAMES, obs['frame_index'])
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError('evidence decode failed')
            pts = cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            if abs(pts-obs['pts_sec']) > 0.001:
                raise ValueError('evidence seek timestamp does not match decoded scan')
            labels = []
            for d in obs['on_desk']:
                box = d['box']
                cv2.rectangle(frame, tuple(map(int, box[:2])), tuple(map(int, box[2:])), (112, 35, 160), 2)
                labels.append((box, (112, 35, 160), 'Папка', False))
            frame = render_labels(frame, labels)
            cv2.putText(frame, f'{pts:.3f} s', (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            ok, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if not ok:
                raise RuntimeError('evidence encode failed')
            frames.append(dict(timestamp_sec=round(pts, 6), image_base64=base64.b64encode(jpeg).decode()))
    finally:
        cap.release()
    return frames


def append_folder_event(baseline, event_time, frames):
    from forte.registry import REGISTRY
    result = copy.deepcopy(baseline)
    kind = REGISTRY['A_unattended_valuables']['name']
    if any(v['type'] == kind and abs(v['timecode_sec']-event_time) < 3 for v in result['violations']):
        return result, False
    description = (
        f'На рабочем столе остаётся распознанная папка после ухода кассира ({event_time:.1f} с). '
        'Содержимое папки по видео не установлено. Применимость требования о хранении '
        'ценностей или документов требует подтверждения; прямая нормативная ссылка этому наблюдению не назначена.'
    )
    result['violations'].append(dict(type=kind, timecode_sec=event_time, description=description,
                                     evidence_frames=frames))
    result['verdict'] = 'violation'
    result.setdefault('explain', []).append(dict(code='A_unattended_valuables', name=kind,
        observed=description, refs=[], direct=False, norm='', score=None,
        details=dict(object='folder', contents='unknown', basis_status='not_established',
                     experimental=True)))
    return result, True


class Analyzer:
    def __init__(self):
        if os.environ.get('FORTE_CANDIDATE_ONLY') != '1':
            raise RuntimeError('candidate worker requires explicit isolated configuration')
        started = time.monotonic()
        self.base = os.environ['FORTE_BASE_API_URL'].rstrip('/')
        if urlparse(self.base).hostname not in ('localhost', '127.0.0.1'):
            raise ValueError('candidate accepts a loopback baseline API only')
        self.source_root = Path(os.environ['FORTE_BASE_BACKEND']).resolve()
        from forte.labels import ROOT
        if self.source_root == ROOT.resolve():
            raise ValueError('refusing to operate in production backend directory')
        self.client = httpx.Client(trust_env=False, headers={'X-API-Key': os.environ['FORTE_BASE_API_KEY']})
        path = Path(os.environ['FORTE_FOLDER_CHECKPOINT'])
        bundle = joblib.load(path)
        if bundle['config'] != CONFIG:
            raise ValueError('checkpoint configuration mismatch')
        self.checkpoint_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        self.head = bundle['heads']['folder']
        torch.set_num_threads(2)
        self.extractor = Features('cuda')
        self.device = 'cuda'
        self.load_sec = time.monotonic()-started

    def warmup(self):
        self.extractor(Image.new('RGB', (464, 848)))

    def run(self, video_path, job_id):
        from forte.scene import CACHE, build_scene
        start = time.monotonic()
        deadline = start+275
        path = Path(video_path)
        with path.open('rb') as stream:
            response = self.client.post(self.base+'/api/v1/analyze',
                files={'file': ('video.mov', stream, 'video/quicktime')}, timeout=30)
        response.raise_for_status()
        upstream_id = response.json()['job_id']
        if not re.fullmatch(r'[0-9a-f]{12}', upstream_id):
            raise ValueError('invalid upstream ID')
        while True:
            response = self.client.get(self.base+'/api/v1/jobs/'+upstream_id, timeout=20)
            response.raise_for_status()
            public = response.json()
            if public['status'] == 'done':
                break
            if public['status'] == 'failed':
                raise RuntimeError('baseline processing failed')
            if time.monotonic() > deadline:
                raise TimeoutError('baseline processing deadline exceeded')
            time.sleep(0.2)
        # Read only the exact new job produced above, not arbitrary historic jobs.
        stored = self.source_root/'data/service/jobs'/f'{upstream_id}.json'
        baseline = json.loads(stored.read_text())['result']
        if baseline['violations'] != public['violations'] or baseline['verdict'] != public['verdict']:
            raise ValueError('baseline API and stored result disagree')
        CACHE.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.source_root/'data/cache'/f'{upstream_id}.json', CACHE/f'{job_id}.json')
        scene = build_scene(job_id)
        observations, candidates = scan_video(path, scene, self.extractor, self.head, deadline)
        result, appended = copy.deepcopy(baseline), False
        if candidates:
            event_time = candidates[0]['condition_pts_sec']
            frames = render_evidence(path, evidence_observations(observations, event_time))
            result, appended = append_folder_event(result, event_time, frames)
        result.setdefault('meta', {})['candidate'] = dict(upstream_job_id=upstream_id,
            model_sha256=self.checkpoint_hash, appended=appended,
            sampled_frames=len(observations), candidates=candidates,
            total_sec=round(time.monotonic()-start, 3), experimental=True)
        # The candidate's own job identifier must not masquerade as its upstream job.
        result['meta']['job_id'] = job_id
        return result
