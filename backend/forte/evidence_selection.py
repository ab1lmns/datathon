"""Choose at most three distinct moments, preserving event time and temporal context."""
import math


def select_evidence_times(event_time, evidence_times, duration):
    if not math.isfinite(duration) or duration <= 0:
        return []
    hi = max(0.0, duration - 0.05)
    main = min(max(0.0, float(event_time)), hi)
    if not math.isfinite(main):
        return []
    selected = [main]
    # Preserve original evidence before adding contextual frames.
    for value in sorted(evidence_times):
        value = float(value)
        if not math.isfinite(value):
            continue
        value = min(max(0.0, value), hi)
        if all(abs(value - prior) >= 0.4 for prior in selected):
            selected.append(value)
    if len(selected) > 3:
        selected = sorted(set([main, min(selected), max(selected)]))
    # Prefer a missing side of the event; near boundaries use remaining valid context.
    candidates = [main - 1.0, main + 1.0, min(selected) - 1.0, max(selected) + 1.0, 0.0, hi]
    for value in candidates:
        if len(selected) >= 3:
            break
        if 0 <= value <= hi and all(abs(value - prior) >= 0.4 for prior in selected):
            selected.append(value)
    return sorted(selected)
