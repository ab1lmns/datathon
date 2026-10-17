"""Integration point for a future LOCAL model. No network calls or demo predictions."""

from pathlib import Path

from .schemas import AnalysisResult

MODEL_NOT_CONFIGURED = (
    "Модель анализа пока не подключена. API работает, но анализ видео ещё недоступен."
)


class AnalysisUnavailable(Exception):
    pass


def analyze_video(video_path: Path, *, duration: float) -> AnalysisResult:
    """Return real observations, timestamps, JPEG evidence and verified rule sources.

    This function runs in a separate process with a deadline. Replace its body when
    a local model is available. Never infer a verdict from filenames or dataset labels.
    For a large model, evolve the worker into a persistent model process to avoid
    loading weights for every job; benchmark against the five-minute case limit.
    """
    raise AnalysisUnavailable(MODEL_NOT_CONFIGURED)
