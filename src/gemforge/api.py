"""Local trusted API; scan is read-only, verification requires explicit consent."""

from collections import OrderedDict
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import Field

from .analysis import analyze_repository
from .engine import scan_repository
from .exporters import capsule_markdown
from .repairs import suggest_repair
from .schemas import ExitCapsule, ModelProbe, Schema, VerificationView
from .verification import verify_repository
from .verification_views import verification_view

app = FastAPI(title="GemForge", version="0.1.0")
_analyses: OrderedDict[str, ExitCapsule] = OrderedDict()
_analysis_lock = Lock()


class ScanRequest(Schema):
    path: str = Field(min_length=1)
    import_map: dict[str, str] = Field(default_factory=dict)


class AnalysisRequest(ScanRequest):
    ai: bool = False
    allow_hosted: bool = False
    max_ai_packages: int = Field(default=10, ge=1, le=50)


class AnalysisResponse(Schema):
    id: str
    capsule: ExitCapsule


class VerificationRequest(Schema):
    path: str = Field(min_length=1)
    dependency: str = Field(min_length=1)
    target: str | None = None
    analysis_id: str | None = None
    confirm_execution: bool = False
    probes: list[ModelProbe] = Field(default_factory=list, max_length=20)
    import_module: str | None = None
    timeout: int = Field(default=60, ge=1, le=300)
    install_timeout: int = Field(default=180, ge=1, le=600)


class RepairRequest(Schema):
    analysis_id: str = Field(min_length=1)
    dependency: str = Field(min_length=1)
    ai: bool = False
    allow_hosted: bool = False


def store_analysis(capsule: ExitCapsule) -> AnalysisResponse:
    id = uuid4().hex
    with _analysis_lock:
        _analyses[id] = capsule
        while len(_analyses) > 20:
            _analyses.popitem(last=False)
    return AnalysisResponse(id=id, capsule=capsule)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "3"}


@app.post("/scan", response_model=ExitCapsule)
def scan(request: ScanRequest) -> ExitCapsule:
    try:
        return scan_repository(Path(request.path), request.import_map)
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/analyze", response_model=AnalysisResponse, status_code=201)
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    """Synchronous analysis; retain only the last 20 capsules in process memory."""
    try:
        capsule = analyze_repository(
            request.path,
            ai=request.ai,
            allow_hosted=request.allow_hosted,
            import_map=request.import_map,
            max_ai_packages=request.max_ai_packages,
        )
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return store_analysis(capsule)


@app.post("/verify", response_model=AnalysisResponse, status_code=201)
def verify(request: VerificationRequest) -> AnalysisResponse:
    """Local trusted use only. Consent is required to execute target code."""
    prior = get_analysis(request.analysis_id) if request.analysis_id else None
    try:
        capsule = verify_repository(
            request.path,
            request.dependency,
            request.target,
            analysis=prior,
            confirm_execution=request.confirm_execution,
            probes=request.probes,
            import_module=request.import_module,
            timeout=request.timeout,
            install_timeout=request.install_timeout,
        )
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return store_analysis(capsule)


@app.get("/analyses/{analysis_id}", response_model=ExitCapsule)
def get_analysis(analysis_id: str) -> ExitCapsule:
    with _analysis_lock:
        capsule = _analyses.get(analysis_id)
    if capsule is None:
        raise HTTPException(
            status_code=404, detail="Analysis not found or expired from the in-memory cache."
        )
    return capsule


@app.post("/analyses/import", response_model=AnalysisResponse, status_code=201)
def import_analysis(capsule: ExitCapsule) -> AnalysisResponse:
    """Restore a saved capsule to the local cache; not an attestation or a rerun."""
    if len(capsule.model_dump_json().encode("utf-8")) > 2_000_000:
        raise HTTPException(status_code=400, detail="Imported capsule exceeds 2 MB.")
    return store_analysis(capsule.model_copy(deep=True))


@app.get("/analyses/{analysis_id}/verification", response_model=VerificationView)
def get_verification(analysis_id: str) -> VerificationView:
    return verification_view(get_analysis(analysis_id))


@app.post("/repairs", response_model=AnalysisResponse, status_code=201)
def repair(request: RepairRequest) -> AnalysisResponse:
    """Create a new unverified suggestion capsule, preserving its parent result."""
    parent = get_analysis(request.analysis_id)
    try:
        capsule = suggest_repair(
            parent, request.dependency, ai=request.ai, allow_hosted=request.allow_hosted
        )
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return store_analysis(capsule)


@app.get(
    "/analyses/{analysis_id}/export",
    responses={
        200: {
            "description": "Dependency Exit Capsule JSON or Markdown.",
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/ExitCapsule"}},
                "text/markdown": {"schema": {"type": "string"}},
            },
        },
    },
)
def export_analysis(analysis_id: str, format: Literal["json", "markdown"] = "json") -> Response:
    capsule = get_analysis(analysis_id)
    markdown = format == "markdown"
    return Response(
        capsule_markdown(capsule) if markdown else capsule.model_dump_json(indent=2),
        media_type="text/markdown" if markdown else "application/json",
        headers={
            "Content-Disposition": f'attachment; filename="gemforge-{analysis_id}.{"md" if markdown else "json"}"'
        },
    )
