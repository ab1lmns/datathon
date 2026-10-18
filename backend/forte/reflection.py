"""Bounded visual check of tracks suppressed by the geometric reflection filter.

Uses existing frozen Qwen weights; this is an inference/filter experiment, not
fine-tuning. Image inputs contain no source name, expected answer or event label.
"""
import copy
import time
from pathlib import Path

import cv2
import numpy as np

PROMPT = (
    'One comparison image has two labeled panels: A on the left and B on the right. '
    'Each panel is a crop of a detected figure from the same surveillance frame. '
    'Compare the central figure in A against the central figure in B. '
    'Determine whether these are clearly different people, or could be '
    'the same person seen twice because of a glass reflection or overlapping detections. '
    'Compare visible clothes, hair and body appearance. Position alone is NOT evidence. '
    'A mirror can reverse appearance and change brightness. If resolution, occlusion or '
    'lighting prevents a reliable distinction, answer uncertain. '
    'Do not infer identity, authorization or violations. JSON only: '
    '{"relationship":"different_people"|"same_person_or_reflection"|"uncertain",'
    '"visual_reason":"visible clothing difference or similarity, maximum 12 words"}.'
)
CONFIG = dict(samples=3, min_different=2, no_same_votes=True, max_candidates=4,
              max_comparators=2, context_long_side=448, crop_long_side=336,
              model='Qwen/Qwen3-VL-4B-Instruct',
              revision='ebb281ec70b05090aa6165b016eac8ec08e71b17', prompt=PROMPT)
CONFIG['input_format'] = 'single labeled pair canvas; no third context image in model input'
CONFIG['restoration_scope'] = 'only intervals bounded by consecutive different_people answers from every comparator'


def suppressed_pairs(cache):
    import forte.scene as s
    w, h = cache['info']['w'], cache['info']['h']
    desk, door = s.estimate_desk(cache, w, h), s.estimate_door(cache)
    if door is None:
        return []
    times = np.array([f['t'] for f in cache['frames']])
    tracks = [tr for tr in s.build_tracks(times, [s.room_persons(f['det'], desk, h)
              for f in cache['frames']], h) if s.real_track(tr, desk, door, h)]
    static = [tr for tr in tracks if s.is_static_late(tr, h)
              and np.median([b[3] for b in tr.boxes]) < door[3]-.01*h]
    moving = [tr for tr in tracks if tr not in static]
    out = []
    for tr in static:
        if not s.has_twin(tr, moving, w, h):
            continue
        twins = [other for other in moving if s.has_twin(tr, [other], w, h)]
        if not twins or len(twins)>CONFIG['max_comparators']:
            continue  # ambiguous aggregate match, leave baseline suppression unchanged
        comparisons = []
        for other in twins:
            common = sorted(set(tr.idx)&set(other.idx))
            selected = sorted({common[int(i)] for i in np.linspace(0, len(common)-1, CONFIG['samples'])})
            comparisons.append(dict(other_tid=other.tid, samples=[dict(
                time_sec=float(times[k]), box_a=tr.boxes[tr.idx.index(k)],
                box_b=other.boxes[other.idx.index(k)]) for k in selected]))
        out.append(dict(track=tr, comparisons=comparisons))
    return out[:CONFIG['max_candidates']]


def resized(frame, side):
    h, w = frame.shape[:2]
    scale = side/max(w, h)
    return cv2.resize(frame, (max(1, round(w*scale)), max(1, round(h*scale))))


def pair_images(frame, box_a, box_b):
    from forte.vlm import crop_region
    context = frame.copy()
    for name, box, color in [('A', box_a, (220, 0, 220)), ('B', box_b, (0, 180, 230))]:
        x1, y1, x2, y2 = map(int, box)
        cv2.rectangle(context, (x1, y1), (x2, y2), color, 2)
        cv2.putText(context, name, (x1, max(18, y1)), cv2.FONT_HERSHEY_SIMPLEX, .65, color, 2)
    crops = [crop_region(frame, b, .05, .05, .05, min_side=0) for b in (box_a, box_b)]
    return [resized(context, CONFIG['context_long_side'])]+[resized(c, CONFIG['crop_long_side']) for c in crops]


def confirmed_distinct(answers):
    votes = [a.get('relationship', 'uncertain') for a in answers]
    return len(votes)==CONFIG['samples'] and votes.count('different_people')>=CONFIG['min_different'] \
        and 'same_person_or_reflection' not in votes


def comparison_canvas(images):
    side = CONFIG['crop_long_side']
    canvas = np.full((side+32, 2*side, 3), 224, dtype=np.uint8)
    for i, crop in enumerate(images[1:]):
        h,w = crop.shape[:2]
        x = i*side+(side-w)//2
        canvas[32:32+h,x:x+w] = crop
        cv2.putText(canvas, 'A' if i==0 else 'B', (i*side+10,24),
                    cv2.FONT_HERSHEY_SIMPLEX,.8,(0,0,0),2)
    return canvas


def verified_intervals(answers):
    ordered = sorted(answers, key=lambda a: a['time_sec'])
    return [(a['time_sec'], b['time_sec']) for a,b in zip(ordered, ordered[1:])
            if a.get('relationship') == b.get('relationship') == 'different_people']


def verified_track_segment(track, comparisons):
    """A contradictory early vote never authorizes recovery of that early track."""
    from forte.scene import Track
    intervals = [(track.start, track.end)]
    for comparison in comparisons:
        intervals = [(max(a,c),min(b,d)) for a,b in intervals
                     for c,d in verified_intervals(comparison['answers']) if min(b,d)>max(a,c)]
    if not intervals:
        return None
    start,end = max(intervals, key=lambda x:x[1]-x[0])
    selected = [i for i,t in enumerate(track.t) if start<=t<=end]
    if len(selected)<3:
        return None
    return Track(track.tid, [track.t[i] for i in selected],
                 [track.boxes[i] for i in selected], [track.idx[i] for i in selected])


def verify_pairs(path, candidates, vlm, deadline=None, evidence_dir=None):
    from forte.video import read_frame
    from forte.vlm import parse_json
    recovered, diagnostics = [], []
    for item in candidates:
        comparisons = []
        for pair in item['comparisons']:
            answers = []
            for sample in pair['samples']:
                if deadline is not None and time.monotonic()>deadline:
                    raise TimeoutError('reflection verification deadline')
                frame = read_frame(path, sample['time_sec'])
                if frame is None:
                    answers.append(dict(relationship='uncertain', error='decode',
                                        time_sec=sample['time_sec']))
                    continue
                images = pair_images(frame, sample['box_a'], sample['box_b'])
                comparison = comparison_canvas(images)
                raw = vlm.ask([comparison], PROMPT, max_new_tokens=192)
                ans = parse_json(raw)
                if ans.get('relationship') not in ('different_people','same_person_or_reflection','uncertain'):
                    ans = dict(relationship='uncertain', error='invalid_response')
                ans.update(raw=raw, time_sec=sample['time_sec'])
                answers.append(ans)
                if evidence_dir:
                    evidence_dir.mkdir(parents=True, exist_ok=True)
                    for j, image in enumerate(images):
                        cv2.imwrite(str(evidence_dir/f"track{item['track'].tid}_vs{pair['other_tid']}_{sample['time_sec']:.3f}_{j}.jpg"), image)
                    cv2.imwrite(str(evidence_dir/f"track{item['track'].tid}_vs{pair['other_tid']}_{sample['time_sec']:.3f}_input.jpg"), comparison)
            comparisons.append(dict(other_tid=pair['other_tid'], answers=answers,
                                    different=confirmed_distinct(answers)))
        segment = verified_track_segment(item['track'], comparisons) if comparisons else None
        if segment is not None:
            recovered.append(segment)
        diagnostics.append(dict(tid=item['track'].tid, comparisons=comparisons, recovered=segment is not None,
            recovered_interval=[segment.start,segment.end] if segment else None))
    return recovered, diagnostics


def restore_scene(scene, recovered):
    from forte.scene import smooth_count, assign_roles
    result = copy.deepcopy(scene)
    known = {tr.tid for tr in result.tracks}
    for tr in recovered:
        if tr.tid in known:
            continue
        result.tracks.append(tr)
        for k, b in zip(tr.idx, tr.boxes):
            result.persons[k].append((1., b))
        known.add(tr.tid)
    result.tracks.sort(key=lambda tr: tr.start)
    result.n_people = smooth_count([len(p) for p in result.persons], k=5)
    result.roles = assign_roles(result.tracks)
    return result

