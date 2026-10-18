"""Isolated supervised DINOv2 patch heads: folder, bag, cash vs background.

Inputs to prediction are full images only. Boxes supervise training and score
localization afterwards; never crop or select the inference region. Fixed
configuration, source-group split, no production imports or model replacement.
"""
import argparse
import collections
import hashlib
import json
import time
from pathlib import Path

import cv2
import joblib
import numpy as np
import torch
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from transformers import AutoImageProcessor, AutoModel

MODEL = 'facebook/dinov2-base'
REVISION = 'f9e44c814b77203eaa57a6bdbbd535f21ede1415'
CLASSES = ('folder', 'bag', 'cash')
CONFIG = dict(long_side=784, patch_size=14, threshold=0.90, min_patches=2,
              negatives_per_frame=128, seed=20261018, logistic_C=1.0,
              hard_negative_rounds=2, mining_threshold=0.5)


class Features:
    def __init__(self, device):
        self.device = device
        self.processor = AutoImageProcessor.from_pretrained(MODEL, revision=REVISION, local_files_only=True)
        self.model = AutoModel.from_pretrained(MODEL, revision=REVISION, local_files_only=True).to(device).eval()

    @torch.inference_mode()
    def __call__(self, image):
        w, h = image.size
        scale = CONFIG['long_side'] / max(w, h)
        nw, nh = [max(14, round(x*scale/14)*14) for x in (w, h)]
        image = image.resize((nw, nh), Image.Resampling.BICUBIC)
        inputs = self.processor(images=image, do_resize=False, do_center_crop=False, return_tensors='pt').to(self.device)
        features = self.model(**inputs).last_hidden_state[:, 1:]
        features = torch.nn.functional.normalize(features, dim=-1)
        return features[0].float().cpu().numpy(), (nh//14, nw//14)


def boxes_from_probabilities(probs, grid, size):
    h, w = grid
    iw, ih = size
    mask = (probs.reshape(h, w) >= CONFIG['threshold']).astype('uint8')
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = []
    for k in range(1, n):
        x, y, bw, bh, area = stats[k]
        if area < CONFIG['min_patches']:
            continue
        out.append(dict(box=[x/w*iw, y/h*ih, (x+bw)/w*iw, (y+bh)/h*ih],
                        score=float(probs.reshape(h, w)[labels == k].mean())))
    return out


def predict(heads, features, grid, size):
    return {c: boxes_from_probabilities(heads[c].predict_proba(features)[:, 1], grid, size) for c in CLASSES}


def patch_labels(grid, size, target):
    gh, gw = grid
    iw, ih = size
    yy, xx = np.mgrid[:gh, :gw]
    x0, x1 = xx.ravel()/gw*iw, (xx.ravel()+1)/gw*iw
    y0, y1 = yy.ravel()/gh*ih, (yy.ravel()+1)/gh*ih
    labels = np.zeros(gh*gw, dtype=int)
    if target['label'] == 'UNKNOWN':
        return np.full(gh*gw, -1)
    if target['label'] == 'NO':
        return labels
    a, b, c, d = target['bbox_xyxy']
    overlap = np.maximum(0, np.minimum(x1, c)-np.maximum(x0, a))*np.maximum(0, np.minimum(y1, d)-np.maximum(y0, b))
    # Ignore uncertain boundary patches; learn positive interior and real background.
    labels[overlap > 0] = -1
    labels[overlap / ((x1-x0)*(y1-y0)) >= 0.5] = 1
    return labels


def iou(a, b):
    inter = max(0, min(a[2], b[2])-max(a[0], b[0]))*max(0, min(a[3], b[3])-max(a[1], b[1]))
    return inter / max(1e-9, (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--device', choices=['cuda', 'cpu'], default='cpu')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(2)
    torch.manual_seed(CONFIG['seed'])
    rng = np.random.default_rng(CONFIG['seed'])
    start = time.monotonic()
    annotations = a.data_root/'data/object_grounding_v1/annotations.jsonl'
    records = [json.loads(line) for line in annotations.read_text().splitlines()]
    records = [r for r in records if r['object'] in CLASSES]
    frames = collections.defaultdict(dict)
    for r in records:
        assert r['review_status'] == 'ASSISTANT_REVIEWED'
        assert r['object'] not in frames[r['frame']['id']]
        frames[r['frame']['id']][r['object']] = r
    train = [r for r in records if r['split']=='train']
    evaluation = [r for r in records if r['split']=='evaluation']
    for field in ('source_sha256', 'scene_group'):
        assert not {r[field] for r in train} & {r[field] for r in evaluation}
    assert not {r['frame']['sha256'] for r in train} & {r['frame']['sha256'] for r in evaluation}
    (a.output/'config.json').write_text(json.dumps(dict(CONFIG, backbone=MODEL, revision=REVISION,
        annotation_sha256=hashlib.sha256(annotations.read_bytes()).hexdigest(),
        hypothesis='Supervised spatial patch features with explicit background; no GT crop at inference',
        scope='known development scenes, no held-out positive folder scene'), indent=2))
    extractor = Features(a.device)
    cache = {}
    for fid, entries in frames.items():
        r = next(iter(entries.values()))
        path = a.data_root/r['frame']['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == r['frame']['sha256']
        image = Image.open(path).convert('RGB')
        features, grid = extractor(image)
        cache[fid] = dict(features=features, grid=grid, size=image.size)
    # Features are frozen; training never sees evaluation features or labels.
    heads, training_counts = {}, {}
    for c in CLASSES:
        xs, ys, training_pools = [], [], []
        for fid, entries in frames.items():
            r = entries[c]
            if r['split'] != 'train' or not r['train_eligible']:
                continue
            z = cache[fid]
            labels = patch_labels(z['grid'], z['size'], r['target'])
            pos, neg = np.flatnonzero(labels==1), np.flatnonzero(labels==0)
            if len(neg) > CONFIG['negatives_per_frame']:
                neg = rng.choice(neg, CONFIG['negatives_per_frame'], replace=False)
            idx = np.concatenate((pos, neg))
            if len(idx):
                xs.append(z['features'][idx]); ys.append(labels[idx])
                training_pools.append((z['features'], labels, set(idx.tolist())))
        x, y = np.concatenate(xs), np.concatenate(ys)
        assert len(set(y)) == 2
        head = make_pipeline(StandardScaler(), LogisticRegression(C=CONFIG['logistic_C'],
                 class_weight='balanced', max_iter=1000, random_state=CONFIG['seed']))
        head.fit(x, y)
        mined = []
        # Only training frames participate. Never mine evaluation scenes.
        for _ in range(CONFIG['hard_negative_rounds']):
            additions = []
            for features, labels, seen in training_pools:
                idx = np.flatnonzero((labels == 0) & (head.predict_proba(features)[:, 1] >= CONFIG['mining_threshold']))
                idx = np.array([i for i in idx if int(i) not in seen], dtype=int)
                if len(idx):
                    additions.append(features[idx])
                    seen.update(idx.tolist())
            added = sum(len(v) for v in additions)
            mined.append(added)
            if not added:
                break
            x = np.concatenate([x]+additions)
            y = np.concatenate([y, np.zeros(added, dtype=int)])
            head.fit(x, y)
        if head[-1].n_iter_.max() >= 1000:
            raise RuntimeError('logistic head failed to converge')
        heads[c] = head
        training_counts[c] = dict(positive_patches=int((y==1).sum()), negative_patches=int((y==0).sum()), mined_per_round=mined)
        print('trained', c, training_counts[c], flush=True)
    joblib.dump(dict(heads=heads, config=CONFIG, backbone=MODEL, revision=REVISION), a.output/'patch_heads.joblib')
    restored = joblib.load(a.output/'patch_heads.joblib')['heads']
    sample = next(iter(cache.values()))['features']
    for c in CLASSES:
        np.testing.assert_allclose(heads[c].predict_proba(sample), restored[c].predict_proba(sample))
    predictions, counts = [], collections.defaultdict(collections.Counter)
    for fid, entries in frames.items():
        z = cache[fid]
        found = predict(restored, z['features'], z['grid'], z['size'])
        for c, r in entries.items():
            expected = r['target']['label']
            dets = found[c]
            localized = expected == 'YES' and any(iou(d['box'], r['target']['bbox_xyxy']) >= 0.25 for d in dets)
            metric = counts[r['split']+':'+c]
            metric['questions'] += 1
            metric['expected_'+expected] += 1
            if expected == 'YES':
                metric['localized_yes'] += int(localized)
                metric['detected_yes'] += bool(dets)
            elif expected == 'NO':
                metric['false_yes'] += bool(dets)
            else:
                metric['unverified_yes_on_unknown'] += bool(dets)
            predictions.append(dict(frame_id=fid, source_video=r['source_video'], split=r['split'],
                pts_sec=r['frame']['pts_sec'], object=c, expected=expected,
                expected_box=r['target']['bbox_xyxy'], detections=dets, localized=bool(localized)))
    # A failed component cannot be presented as an improved violation detector.
    reasons = []
    for key, n in counts.items():
        if n['false_yes'] or n['unverified_yes_on_unknown']:
            reasons.append(key+': unsupported positive detections')
        if n['localized_yes'] < n['expected_YES']:
            reasons.append(key+': localization misses')
    reasons.append('No held-out positive folder scene; transfer unverified')
    report = dict(status='completed', decision='RESEARCH_ONLY', production_changed=False,
        counts={k:dict(v) for k,v in counts.items()}, training_counts=training_counts,
        gate_failures=reasons, wall_sec=round(time.monotonic()-start, 2),
        device=a.device, labels='Previously assistant-reviewed, user clarifications preserved in original manifest',
        full_video_metric=None)
    (a.output/'predictions.json').write_text(json.dumps(predictions, ensure_ascii=False, indent=2))
    (a.output/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
