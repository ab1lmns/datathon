"""Validated additive observations; baseline events remain immutable.

Uses resident Qwen and DINO weights. No upstream API or research package needed.
Errors are reported as incomplete analysis, never silently as a clean video.
"""
import hashlib
import logging
import time
from pathlib import Path

import cv2
import joblib

from .labels import ROOT
from .patch_features import CONFIG, Features
from .folder_observations import scan_video, evidence_observations, render_evidence, append_folder_event
from .reflection import suppressed_pairs, verify_pairs, restore_scene
from .scene import build_scene, load_cache

log = logging.getLogger(__name__)
CHECKPOINT_SHA256 = '24ee6b8d06058ec202d3471df78e6400f991f81e2fdf588b3ce96b9e028af780'


class Observations:
    def __init__(self, device, vlm, embedder=None):
        path = ROOT/'models/folder_patch_heads.joblib'
        if hashlib.sha256(path.read_bytes()).hexdigest() != CHECKPOINT_SHA256:
            raise ValueError('folder checkpoint hash mismatch')
        bundle = joblib.load(path)
        if bundle['config'] != CONFIG:
            raise ValueError('folder checkpoint configuration mismatch')
        if vlm is None:
            raise RuntimeError('visual reflection verification requires Qwen')
        self.head = bundle['heads']['folder']
        self.features = Features(device, embedder=embedder)
        self.vlm = vlm

    def apply(self, result, path, job_id, deadline):
        start = time.monotonic()
        # Fresh lightweight scene: never copy model-bearing money_fn from pipeline.
        scene = build_scene(job_id)
        observations, candidates = scan_video(path, scene, self.features, self.head, deadline)
        appended = False
        if candidates:
            t = candidates[0]['condition_pts_sec']
            frames = render_evidence(path, evidence_observations(observations, t))
            result, appended = append_folder_event(result, t, frames)
        result['meta']['folder'] = dict(model_sha256=CHECKPOINT_SHA256,
            sampled_frames=len(observations), added=appended)
        pairs = suppressed_pairs(load_cache(job_id))
        recovered, diagnostics = verify_pairs(Path(path), pairs, self.vlm, deadline=deadline) if pairs else ([], [])
        added = 0
        if recovered:
            restored = restore_scene(scene, recovered)
            added = append_person_events(result, path, restored, recovered)
        result['meta']['reflection'] = dict(checked=bool(pairs), added=added, diagnostics=diagnostics)
        result['meta']['observations_sec'] = round(time.monotonic()-start, 3)
        result['meta']['model_version'] = 'forte-observations-v1'
        return result


def append_person_events(result, path, scene, recovered):
    from .rules import rule_crowd, rule_behind_cashier, dedup
    from .registry import REGISTRY, refs
    from .pipeline import draw_evidence, jpeg_b64
    added = 0
    cap = cv2.VideoCapture(str(path))
    try:
        for event in dedup(rule_crowd(scene)+rule_behind_cashier(scene)):
            name = REGISTRY[event.type]['name']
            if any(v['type']==name and abs(v['timecode_sec']-event.t)<3 for v in result['violations']):
                continue
            frames = []
            for t in sorted(set(max(0,min(scene.dur-.1,event.t+dt)) for dt in (-.5,0,.5))):
                cap.set(cv2.CAP_PROP_POS_MSEC,t*1000)
                ok,frame = cap.read()
                if not ok:
                    raise RuntimeError('person event evidence decode failed')
                actual = cap.get(cv2.CAP_PROP_POS_MSEC)/1000
                objects = []
                annotated = draw_evidence(frame,scene,actual,objects_out=objects)
                frames.append(dict(timestamp_sec=round(actual,6),image_base64=jpeg_b64(annotated),objects=objects))
            description = ('В зоне рабочего места рядом с кассиром наблюдается другой человек. '
                'Визуальная проверка различает две фигуры на подтверждённом отрезке, '
                'а не считает вторую отражением. Полномочия человека по видео не установлены; '
                'эпизод требует проверки режима доступа.')
            result['violations'].append(dict(type=name,timecode_sec=round(event.t,3),
                description=description,evidence_frames=frames))
            result['explain'].append(dict(code=event.type,name=name,observed=description,
                refs=refs(event.type),direct=False,norm=REGISTRY[event.type]['norm'],score=None,
                details=dict(model_version='reflection-v1',authorization='unknown',basis_status='conditional',
                             verified_intervals=[[tr.start,tr.end] for tr in recovered])))
            added += 1
    finally:
        cap.release()
    if result['violations']:
        result['verdict'] = 'violation'
    return added
