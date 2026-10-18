"""Serializable hit regions and observed state changes, without additional inference."""
import math


def state_history(points, state_for, max_gap=None):
    out, previous_time = [], None
    for t, value in sorted(points, key=lambda p: p[0]):
        t = float(t)
        if not math.isfinite(t) or t < 0:
            continue
        if max_gap and previous_time is not None and t - previous_time > max_gap:
            out.append({"timestamp_sec": round(previous_time + max_gap, 2), "state": "Состояние не определено"})
        state = state_for(value)
        if not out or out[-1]["state"] != state:
            out.append({"timestamp_sec": round(t, 2), "state": state})
        previous_time = t
    return out


def evidence_object(object_id, kind, name, state, box, width, height, color, history=None):
    x1, y1, x2, y2 = [float(v) for v in box]
    if width <= 0 or height <= 0 or not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
        return None
    bbox = [max(0.0, min(1.0, v / size)) for v, size in zip((x1, y1, x2, y2), (width, height, width, height))]
    if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        return None
    result = {"id": object_id, "kind": kind, "name": name, "state": state,
              "bbox": bbox, "color": "#%02x%02x%02x" % tuple(reversed(color))}
    if history:
        result["history"] = history
    return result
