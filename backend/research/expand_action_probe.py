"""Reviewed cash-stage extension and leave-one-scene-group-out training.

Labels below describe only visible contact, not violations or machine operation.
They were authored by the assistant from uniformly sampled original-frame sheets
and detailed originals. No new human verification is claimed.
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

from .train_action_probe import CONFIG, TASKS, Features, views, encode_sequence, decision, validate

# Original-frame visual review. All lack a visitor inside the room.
SPECS = [
    (14, [2, 4, 6], 'NO', 'Opening green bag, hands away from counting machine.'),
    (14, [30, 32, 34], 'NO', 'Taking bundles out of bag onto table, not machine.'),
    (14, [46, 48, 50], 'UNKNOWN', 'Near machine, exact note contact partly obscured at sampled moments.'),
    (14, [50, 52, 54], 'YES', 'Visible bundle at machine intake in original 52s frame.'),
    (14, [62, 64, 66], 'YES', 'Bundle handled at machine intake; original 64s frame inspected.'),
    (14, [86, 88, 90], 'NO', 'Hands handle bundles at centre of desk, away from machine.'),
    (14, [116, 118, 120], 'NO', 'Bundles move towards safe; no contact with counting machine.'),
    (14, [134, 136, 138], 'NO', 'Typing at laptop, not counting machine.'),
    (13, [18, 20, 22], 'NO', 'Opening bag and taking out bundles, away from machine.'),
    (13, [40, 42, 44], 'NO', 'Picking bundles up from table, no machine interaction.'),
    (13, [46, 48, 50], 'NO', 'Moving bundles into safe, no machine interaction.'),
    (13, [58, 60, 62], 'NO', 'Cashier leaves; this is not visitor departure.'),
]


def fit(train, vectors):
    # Repeated windows ending on the same frame are not extra presence examples.
    unique = {}
    for r in train:
        hs = tuple(f['sha256'] for f in r['frames'])
        key = hs[-1:] if r['task']==TASKS[0] else hs
        unique[key] = r
    train = list(unique.values())
    groups = collections.Counter(r['scene_group'] for r in train)
    weights = np.array([1/groups[r['scene_group']] for r in train])
    weights *= len(weights)/weights.sum()
    labels = [r['target']['label'] for r in train]
    if len(set(labels)) < 2:
        raise ValueError('insufficient class support')
    head = make_pipeline(StandardScaler(), LogisticRegression(C=CONFIG['logistic_C'],
        class_weight='balanced', max_iter=2000, random_state=CONFIG['seed']))
    head.fit(np.array([vectors[r['id']] for r in train]), labels,
             logisticregression__sample_weight=weights)
    assert head[-1].n_iter_.max() < 2000
    return head


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root', type=Path, required=True)
    p.add_argument('--review-root', type=Path, required=True)
    p.add_argument('--previous', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    torch.set_num_threads(2)
    rows = []
    for split in ('train', 'evaluation'):
        rows.extend(json.loads(line) for line in (a.data_root/f'data/action_stages_v1/{split}_manifest.jsonl').read_text().splitlines())
    validate(rows)
    for r in rows:
        r['prior_split'] = r.pop('split')
        r['protocol'] = 'leave_one_scene_group_out'
        for f in r['frames']:
            f['path'] = str(a.data_root/f['path'])
    for i, (video, pts, cash, reason) in enumerate(SPECS):
        root = a.review_root/f'X-{video}'
        fs = json.loads((root/'frames.json').read_text())
        chosen = [dict(min(fs, key=lambda f: abs(t-f['pts_sec']))) for t in pts]
        assert all(abs(t-f['pts_sec']) < .05 for t, f in zip(pts, chosen))
        for f in chosen:
            f['path'] = str(root/f['path'])
        for task, label in zip(TASKS, ('NO', 'NO', cash)):
            rows.append(dict(id=f'bagpair_{i:02d}_{task}', source_video=chosen[0]['source_video'],
                source_sha256=chosen[0]['source_sha256'], scene_group='bag_recount_pair', task=task,
                target=dict(label=label), frames=chosen, protocol='leave_one_scene_group_out',
                annotation_status='ASSISTANT_VISUALLY_REVIEWED', human_verified=False,
                provenance='Uniform original-frame visual review on 2026-10-18; 52s and 64s originals inspected in detail.',
                note=reason, independent_evaluation=False))
    groups = sorted({r['scene_group'] for r in rows})
    # Verify every fold before any fit; paired sources never split into frames.
    for group in groups:
        fold = [dict(r, split='evaluation' if r['scene_group']==group else 'train') for r in rows]
        validate(fold)
    manifest = a.output/'manifest.jsonl'
    manifest.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
    (a.output/'config.json').write_text(json.dumps(dict(CONFIG,
        protocol='Leave one entire scene group out; all prior splits reused as development data.',
        manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        acceptance='All held-out positive stages recognized, zero unsupported YES, UNKNOWN preserved.'), indent=2))
    previous_config = json.loads((a.previous/'config.json').read_text())
    assert all(previous_config[k]==v for k,v in CONFIG.items())
    features = joblib.load(a.previous/'frame_features.joblib')
    frames = {f['sha256']: f for r in rows for f in r['frames']}
    for digest, f in frames.items():
        assert hashlib.sha256(Path(f['path']).read_bytes()).hexdigest()==digest
    extractor = Features('cuda')
    for digest, f in frames.items():
        if digest in features:
            continue
        image = Image.open(f['path']).convert('RGB')
        vs = []
        for view in views(image):
            patches, _ = extractor(view)
            v = patches.mean(axis=0)
            vs.append(v/max(float(np.linalg.norm(v)), 1e-8))
        features[digest] = np.concatenate(vs)
    del extractor
    torch.cuda.empty_cache()
    joblib.dump(features, a.output/'frame_features.joblib')
    vectors = {r['id']: encode_sequence(r['task'], [features[f['sha256']] for f in r['frames']]) for r in rows}
    predictions, metrics, fold_metrics = [], collections.defaultdict(collections.Counter), {}
    for group in groups:
        train = [r for r in rows if r['scene_group']!=group]
        test = [r for r in rows if r['scene_group']==group]
        heads = {task: fit([r for r in train if r['task']==task], vectors) for task in TASKS}
        joblib.dump(dict(heads=heads, config=CONFIG, heldout_group=group), a.output/f'fold_{group}.joblib')
        fm = collections.defaultdict(collections.Counter)
        for r in test:
            task, expected = r['task'], r['target']['label']
            label, probabilities = decision(heads[task], vectors[r['id']])
            for m in (metrics[task], fm[task]):
                m['questions'] += 1; m['correct'] += label==expected
                m['expected_'+expected] += 1
                m['recognized_yes'] += expected=='YES' and label=='YES'
                m['unsupported_yes'] += expected!='YES' and label=='YES'
                m['unknown_preserved'] += expected=='UNKNOWN' and label=='UNKNOWN'
            predictions.append(dict(id=r['id'], source_video=r['source_video'], heldout_group=group,
                task=task, expected=expected, predicted=label, probabilities=probabilities,
                pts=[f['pts_sec'] for f in r['frames']]))
        fold_metrics[group] = dict(fm)
        print(group, json.dumps(fm), flush=True)
    final_heads = {task: fit([r for r in rows if r['task']==task], vectors) for task in TASKS}
    final = a.output/'all_development_heads.joblib'
    joblib.dump(dict(heads=final_heads, config=CONFIG, status='research_only'), final)
    reloaded = joblib.load(final)['heads']
    for r in rows:
        assert decision(final_heads[r['task']], vectors[r['id']]) == decision(reloaded[r['task']], vectors[r['id']])
    accepted = {task: m['recognized_yes']==m['expected_YES'] and m['unsupported_yes']==0
                and m['unknown_preserved']==m['expected_UNKNOWN'] for task,m in metrics.items()}
    result = dict(questions=len(rows), unique_frames=len(frames), scene_groups=groups,
        metrics=dict(metrics), fold_metrics=fold_metrics, heads_pass_gate=accepted,
        full_video_candidate_allowed=all(accepted.values()), production_changed=False,
        independent_evaluation=False, seconds=round(time.monotonic()-start, 2),
        checkpoint_sha256=hashlib.sha256(final.read_bytes()).hexdigest(),
        target_x34=[r for r in predictions if r['id'].startswith('stage_02_')],
        limitations=['Reused development scenes and assistant labels; not a blind final evaluation.',
            'Stage windows selected by annotation, no full-video event score.',
            'Contact with counting machine is not evidence of completed recount.',
            'Final all-development checkpoint has no separate held-out score; metrics are from fold models.'])
    (a.output/'predictions.json').write_text(json.dumps(predictions, ensure_ascii=False, indent=2))
    (a.output/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(dict(metrics=dict(metrics), accepted=accepted, seconds=result['seconds'])), flush=True)


if __name__ == '__main__':
    main()
