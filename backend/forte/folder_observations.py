"""Folder observations from full frames; no video identity or expected labels."""
import base64
import copy
import time
import cv2
import numpy as np
from PIL import Image
from .patch_features import boxes_from_probabilities
from .scene import iou

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
                     model_version="folder-v1")))
    return result, True

