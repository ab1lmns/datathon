"""Isolated API candidate: baseline + folder head + verified person intervals."""
import gc
import time
from pathlib import Path
import cv2
import torch

from .folder_candidate import Analyzer as FolderAnalyzer
from .reflection_probe import CONFIG, suppressed_pairs, verify_pairs, restore_scene


class Analyzer(FolderAnalyzer):
    def run(self, video_path, job_id):
        started = time.monotonic()
        result = super().run(video_path, job_id)
        from forte.scene import load_cache, build_scene
        pairs = suppressed_pairs(load_cache(job_id))
        result['meta']['reflection_candidate'] = dict(checked=bool(pairs), added=0, diagnostics=[])
        if not pairs:
            return result
        from forte.vlm import VLM
        snapshot = Path('/workspace/.hf_home/hub/models--Qwen--Qwen3-VL-4B-Instruct/snapshots')/CONFIG['revision']
        torch.cuda.empty_cache()
        torch.cuda.set_per_process_memory_fraction(.46)
        vlm = VLM(model_id=str(snapshot), device='cuda')
        try:
            recovered, diagnostics = verify_pairs(Path(video_path), pairs, vlm, deadline=started+270)
        finally:
            del vlm
            gc.collect()
            torch.cuda.empty_cache()
        result['meta']['reflection_candidate']['diagnostics'] = diagnostics
        if not recovered:
            return result
        from forte.rules import rule_crowd, rule_behind_cashier, dedup
        from forte.registry import REGISTRY, refs
        from forte.pipeline import draw_evidence, jpeg_b64
        scene = restore_scene(build_scene(job_id), recovered)
        events = dedup(rule_crowd(scene)+rule_behind_cashier(scene))
        cap = cv2.VideoCapture(str(video_path))
        try:
            for event in events:
                name = REGISTRY[event.type]['name']
                if any(v['type']==name and abs(v['timecode_sec']-event.t)<3 for v in result['violations']):
                    continue
                frames = []
                for t in sorted(set(max(0,min(scene.dur-.1,event.t+dt)) for dt in (-.5,0,.5))):
                    cap.set(cv2.CAP_PROP_POS_MSEC,t*1000)
                    ok,frame = cap.read()
                    if not ok:
                        raise RuntimeError('reflection event evidence decode failed')
                    actual = cap.get(cv2.CAP_PROP_POS_MSEC)/1000
                    frames.append(dict(timestamp_sec=round(actual,6),image_base64=jpeg_b64(draw_evidence(frame,scene,actual))))
                description = ('В зоне рабочего места рядом с кассиром наблюдается другой человек. '
                    'Визуальная проверка различает две фигуры на подтверждённом отрезке, '
                    'а не считает вторую отражением. Полномочия человека по видео не установлены; '
                    'эпизод требует проверки режима доступа.')
                result['violations'].append(dict(type=name,timecode_sec=round(event.t,3),
                    description=description,evidence_frames=frames))
                result['explain'].append(dict(code=event.type,name=name,observed=description,
                    refs=refs(event.type),direct=False,norm=REGISTRY[event.type]['norm'],score=None,
                    details=dict(experimental=True,authorization='unknown',basis_status='conditional',
                                 verified_intervals=[[tr.start,tr.end] for tr in recovered])))
                result['meta']['reflection_candidate']['added'] += 1
        finally:
            cap.release()
        if result['violations']:
            result['verdict'] = 'violation'
        result['meta']['reflection_candidate']['total_sec'] = round(time.monotonic()-started,3)
        return result
