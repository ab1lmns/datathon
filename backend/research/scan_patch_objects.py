"""Full-video development scan of a trained folder head, outside production.

Uses fresh baseline scene detections and uniformly sampled original frames.
Reports observable unattended-folder candidates, not automatic legal conclusions.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import cv2
import joblib
import numpy as np
import torch
from PIL import Image

from train_patch_objects import Features, boxes_from_probabilities, iou, CONFIG


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--videos', type=Path, required=True)
    p.add_argument('--backend', type=Path, required=True)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise FileExistsError(a.output)
    sys.path.insert(0, str(a.backend))
    from forte.scene import build_scene, inside, center
    torch.set_num_threads(2)
    bundle = joblib.load(a.checkpoint)
    assert bundle['config'] == CONFIG
    head = bundle['heads']['folder']
    baseline = json.loads(a.baseline.read_text())
    assert baseline['status']=='completed'
    extractor = Features('cuda')
    results = []
    for n, row in enumerate(baseline['rows'], 1):
        start = time.monotonic()
        path = a.videos/(row['video'].replace('X', 'Х')+'.mov')
        if not path.exists():
            path = a.videos/(row['video']+'.mov')
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['source_sha256']
        scene = build_scene(row['job_id'])
        cap = cv2.VideoCapture(str(path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            raise ValueError('unknown source FPS')
        step = max(1, round(fps/2))
        observations, candidates, previous = [], [], []
        index = -1
        last_pts = -1
        while cap.grab():
            index += 1
            if index % step:
                continue
            ok, frame = cap.retrieve()
            if not ok:
                raise RuntimeError('failed sampled frame decode')
            pts = cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            if pts <= last_pts:
                raise ValueError('non-monotone decoded timestamps')
            last_pts = pts
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            features, grid = extractor(image)
            dets = boxes_from_probabilities(head.predict_proba(features)[:, 1], grid, image.size)
            nearest = int(np.argmin(np.abs(scene.times-pts)))
            empty = bool(scene.n_people[nearest] == 0 and abs(scene.times[nearest]-pts) <= 0.5)
            on_desk = [d for d in dets if scene.desk and inside(center(d['box']), scene.desk, 0.05)]
            obs = dict(frame_index=index, pts_sec=round(pts, 6), folder=dets, empty=empty,
                       on_desk=on_desk)
            observations.append(obs)
            if empty and on_desk:
                # Same localized object at two adjacent observations, >=0.45 s apart.
                for prev in previous:
                    if 0.45 <= pts-prev['pts_sec'] <= 0.8 and any(iou(x['box'], y['box']) >= 0.3 for x in on_desk for y in prev['on_desk']):
                        candidates.append(dict(start_pts_sec=prev['pts_sec'], condition_pts_sec=round(pts, 6),
                                               frame_indices=[prev['frame_index'],index]))
                        break
                previous = [obs]
            else:
                previous = []
        cap.release()
        results.append(dict(video=row['video'], source_sha256=row['source_sha256'],
            baseline_verdict=row['verdict'], sampled_frames=len(observations),
            observations=observations, unattended_folder_candidates=candidates,
            wall_sec=round(time.monotonic()-start,2)))
        a.output.write_text(json.dumps(dict(status='running', rows=results), ensure_ascii=False))
        print(n, row['video'], 'frames', len(observations), 'candidates', len(candidates), flush=True)
    a.output.write_text(json.dumps(dict(status='completed',
        checkpoint_sha256=hashlib.sha256(a.checkpoint.read_bytes()).hexdigest(),
        interpretation='Observable folder candidate only; contents and regulatory applicability not inferred',
        development_only=True, rows=results), ensure_ascii=False))


if __name__ == '__main__':
    main()
