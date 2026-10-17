"""One isolated analysis process. The API worker supervises its lifetime."""

import argparse
import json
import logging
import math
import subprocess
from pathlib import Path

from .analyzer import AnalysisUnavailable, analyze_video
from .schemas import AnalysisResult
from .storage import Store

logger = logging.getLogger(__name__)


class InvalidVideo(Exception):
    pass


def probe_video(path: Path, ffprobe: str) -> float:
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=format_name,duration:stream=codec_type,width,height,duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise InvalidVideo("Не удалось прочитать видео за отведённое время.") from exc
    except FileNotFoundError as exc:
        raise AnalysisUnavailable("На сервере не найден FFprobe. Установите FFmpeg.") from exc
    if result.returncode:
        raise InvalidVideo("Файл повреждён или не является поддерживаемым MOV-видео.")
    try:
        metadata = json.loads(result.stdout)
        container = metadata.get("format", {})
        streams = [s for s in metadata.get("streams", []) if s.get("codec_type") == "video"]
        if "mov" not in container.get("format_name", "").split(",") or not streams:
            raise ValueError
        duration = float(container.get("duration") or streams[0].get("duration", 0))
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError
        if not streams[0].get("width") or not streams[0].get("height"):
            raise ValueError
        return duration
    except (ValueError, TypeError, KeyError) as exc:
        raise InvalidVideo("Не удалось определить видеопоток и длительность MOV.") from exc


def process_job(store: Store, job_id: str, upload_dir: Path, ffprobe: str) -> None:
    path = upload_dir / f"{job_id}.mov"
    try:
        duration = probe_video(path, ffprobe)
        result = AnalysisResult.model_validate(analyze_video(path, duration=duration))
        for event in result.violations:
            if event.timecode_sec > duration or any(
                frame.timestamp_sec > duration for frame in event.evidence_frames
            ):
                raise ValueError("Model returned timestamps outside the video")
            if event.rule is None:
                raise ValueError("Each detected event requires a verified rule source")
        store.complete(job_id, result)
    except (InvalidVideo, AnalysisUnavailable) as exc:
        store.fail(job_id, str(exc))
    except Exception:
        logger.exception("Analysis failed for job %s", job_id)
        store.fail(job_id, "Внутренняя ошибка обработки видео. Попробуйте повторить загрузку.")
    finally:
        # Videos are temporary; the result contains only the selected evidence frames.
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("job_id")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--upload-dir", type=Path, required=True)
    parser.add_argument("--ffprobe", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    process_job(Store(args.database), args.job_id, args.upload_dir, args.ffprobe)
