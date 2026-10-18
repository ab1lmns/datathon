"""Isolated learned action-stage probe on existing, provenance-tagged frames.

Fixed experiment: frozen DINOv2 + spatial views + logistic heads. Never creates
violation events or imports production inference. Last-frame presence has no
access to preceding frames. Stage labels do not prove machine operation.
"""
import argparse
import collections
import hashlib
import json
import time
from pathlib import Path

import joblib
import numpy as np
import torch
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .train_patch_objects import Features, MODEL, REVISION

TASKS = ('visitor_present_end', 'visitor_exit', 'banknotes_at_counter_machine')
CONFIG = dict(seed=20261018, logistic_C=0.1, confidence_threshold=0.8,
              views='full frame + fixed overlapping quadrants (10% overlap)',
              backbone=MODEL, revision=REVISION,
              decision='UNKNOWN unless most probable class has probability >= 0.8',
              train_sampling='equal total weight per scene group within each task')


def views(image):
    w, h = image.size
    return [image] + [image.crop(tuple(round(v) for v in box)) for box in (
        (0, 0, .55*w, .55*h), (.45*w, 0, w, .55*h),
        (0, .45*h, .55*w, h), (.45*w, .45*h, w, h))]


def encode_sequence(task, vectors):
    z = np.asarray(vectors, dtype=np.float32)
    if task == 'visitor_present_end':
        return z[-1].copy()
    if task not in TASKS:
        raise ValueError(task)
    # Ordered endpoints, change, and aggregate context, not metadata or GT time.
    return np.concatenate((z[0], z[-1], z[-1]-z[0], z.mean(axis=0)))


def decision(head, vector):
    probs = head.predict_proba(np.asarray(vector)[None])[0]
    best = int(probs.argmax())
    label = str(head.classes_[best]) if probs[best] >= CONFIG['confidence_threshold'] else 'UNKNOWN'
    return label, dict(zip(map(str, head.classes_), map(float, probs)))


def validate(rows):
    for r in rows:
        assert r['task'] in TASKS
        assert r['target']['label'] in ('YES', 'NO', 'UNKNOWN')
        assert r['annotation_status'] == 'ASSISTANT_VISUALLY_REVIEWED'
        pts = [f['pts_sec'] for f in r['frames']]
        assert pts == sorted(set(pts)), 'frames must have strictly ordered PTS'
        assert all(f['source_sha256'] == r['source_sha256'] for f in r['frames'])
    train = [r for r in rows if r['split'] == 'train']
    test = [r for r in rows if r['split'] == 'evaluation']
    for k in ('source_sha256', 'scene_group'):
        assert not {r[k] for r in train} & {r[k] for r in test}, k
    assert not {f['sha256'] for r in train for f in r['frames']} & {
        f['sha256'] for r in test for f in r['frames']}
    # Same visual input cannot receive conflicting target labels.
    known = {}
    for r in rows:
        hashes = tuple(f['sha256'] for f in r['frames'])
        key = (r['task'], hashes[-1:] if r['task'] == TASKS[0] else hashes)
        if key in known:
            assert known[key] == r['target']['label'], 'contradictory visual labels'
        known[key] = r['target']['label']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--device', default='cuda', choices=('cpu', 'cuda'))
    a = parser.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    torch.set_num_threads(2)
    torch.manual_seed(CONFIG['seed'])
    rows, manifests = [], {}
    for split in ('train', 'evaluation'):
        path = a.data_root / f'data/action_stages_v1/{split}_manifest.jsonl'
        manifests[split] = hashlib.sha256(path.read_bytes()).hexdigest()
        rs = [json.loads(line) for line in path.read_text().splitlines()]
        assert all(r['split'] == split for r in rs)
        rows.extend(rs)
    validate(rows)
    frozen = dict(CONFIG, manifests=manifests,
        scope='Known development scenes. Assistant labels reused; not newly human verified.',
        acceptance='All evaluation YES recognized, no unsupported YES, all UNKNOWN preserved, '
                   'no X-34 end-presence contradiction; required before full-video event work.')
    (a.output/'config.json').write_text(json.dumps(frozen, ensure_ascii=False, indent=2))
    extractor = Features(a.device)
    frames = {f['sha256']: f for r in rows for f in r['frames']}
    features = {}
    for i, (digest, f) in enumerate(frames.items(), 1):
        path = a.data_root/f['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        image = Image.open(path).convert('RGB')
        vectors = []
        for view in views(image):
            patches, _ = extractor(view)
            v = patches.mean(axis=0)
            vectors.append(v / max(float(np.linalg.norm(v)), 1e-8))
        features[digest] = np.concatenate(vectors)
        if i % 20 == 0 or i == len(frames):
            print(f'features {i}/{len(frames)}', flush=True)
    joblib.dump(features, a.output/'frame_features.joblib')
    del extractor
    if a.device == 'cuda':
        torch.cuda.empty_cache()
    vectors = {r['id']: encode_sequence(r['task'], [features[f['sha256']] for f in r['frames']]) for r in rows}
    heads, support = {}, {}
    for task in TASKS:
        train = [r for r in rows if r['split']=='train' and r['task']==task]
        group_counts = collections.Counter(r['scene_group'] for r in train)
        weights = np.array([1/group_counts[r['scene_group']] for r in train])
        weights *= len(weights)/weights.sum()
        head = make_pipeline(StandardScaler(), LogisticRegression(C=CONFIG['logistic_C'],
            class_weight='balanced', max_iter=2000, random_state=CONFIG['seed']))
        head.fit(np.array([vectors[r['id']] for r in train]),
                 [r['target']['label'] for r in train], logisticregression__sample_weight=weights)
        assert head[-1].n_iter_.max() < 2000, 'optimizer did not converge'
        heads[task] = head
        support[task] = {label: sorted({r['scene_group'] for r in train if r['target']['label']==label})
                         for label in ('YES', 'NO', 'UNKNOWN')}
        print('trained', task, support[task], flush=True)
    checkpoint = a.output/'stage_heads.joblib'
    joblib.dump(dict(heads=heads, config=CONFIG), checkpoint)
    restored = joblib.load(checkpoint)['heads']
    predictions, metrics = [], collections.defaultdict(collections.Counter)
    for r in rows:
        task, expected = r['task'], r['target']['label']
        label, probs = decision(heads[task], vectors[r['id']])
        assert (label, probs) == decision(restored[task], vectors[r['id']])
        m = metrics[r['split']+':'+task]
        m['questions'] += 1
        m['correct'] += label == expected
        m['expected_'+expected] += 1
        m['recognized_yes'] += expected == 'YES' and label == 'YES'
        m['unsupported_yes'] += expected != 'YES' and label == 'YES'
        m['unknown_preserved'] += expected == 'UNKNOWN' and label == 'UNKNOWN'
        predictions.append(dict(id=r['id'], task=task, split=r['split'], source_video=r['source_video'],
            expected=expected, predicted=label, probabilities=probs,
            pts=[f['pts_sec'] for f in r['frames']]))
    (a.output/'predictions.json').write_text(json.dumps(predictions, ensure_ascii=False, indent=2))
    accepted = {}
    for task in TASKS:
        m = metrics['evaluation:'+task]
        accepted[task] = bool(m['expected_YES'] and m['recognized_yes']==m['expected_YES']
            and m['unsupported_yes']==0 and m['unknown_preserved']==m['expected_UNKNOWN'])
    target = [p for p in predictions if p['id'].startswith('stage_02_')]
    target_ok = all(p['predicted'] == p['expected'] for p in target)
    result = dict(metrics=dict(metrics), train_scene_support=support, heads_pass_gate=accepted,
        target_x34=target, target_x34_consistent=target_ok,
        full_video_candidate_allowed=all(accepted.values()) and target_ok,
        production_changed=False, checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        seconds=round(time.monotonic()-started, 2), independent_evaluation=False,
        limitations=['Window-selected stage evaluation, not full-video detection.',
            'Banknote-machine contact does not prove counting or ownership.',
            'Fixed spatial views may overfit camera layout.',
            'No X-13 action-stage labels in this manifest.',
            'Confidence scores are not calibrated; UNKNOWN abstention is not certainty.'])
    (a.output/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
