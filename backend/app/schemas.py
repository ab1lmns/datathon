import base64
import binascii
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

Seconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceFrame(ContractModel):
    timestamp_sec: Seconds
    image_base64: str = Field(min_length=1, max_length=8_000_000)

    @field_validator("image_base64")
    @classmethod
    def jpeg_base64(cls, value: str) -> str:
        try:
            image = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Expected raw JPEG base64 without a data URL prefix") from exc
        if not image.startswith(b"\xff\xd8\xff") or not image.endswith(b"\xff\xd9"):
            raise ValueError("Evidence must contain a JPEG image")
        return value


class RuleSource(ContractModel):
    document: str = Field(min_length=1)
    section: str | None = None
    url: HttpUrl | None = None


class Violation(ContractModel):
    type: str = Field(min_length=1)
    timecode_sec: Seconds
    description: str = Field(min_length=1)
    evidence_frames: list[EvidenceFrame] = Field(min_length=1, max_length=3)
    rule: RuleSource | None = None


class AnalysisResult(ContractModel):
    verdict: Literal["violation", "no_violation"]
    violations: list[Violation]

    @model_validator(mode="after")
    def consistent_verdict(self) -> Self:
        if (self.verdict == "violation") != bool(self.violations):
            raise ValueError("Verdict must agree with the list of violations")
        return self


class CreatedJob(ContractModel):
    job_id: str


class ProcessingJob(CreatedJob):
    status: Literal["processing"] = "processing"


class FailedJob(CreatedJob):
    status: Literal["failed"] = "failed"
    error: str


class DoneJob(AnalysisResult, CreatedJob):
    status: Literal["done"] = "done"


JobResponse = Annotated[ProcessingJob | FailedJob | DoneJob, Field(discriminator="status")]
