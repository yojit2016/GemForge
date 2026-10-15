"""Local API: no execution, repository writes, or AI requests on scan."""

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
from .schemas import ExitCapsule, Schema

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "1"}


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
    id = uuid4().hex
    with _analysis_lock:
        _analyses[id] = capsule
        while len(_analyses) > 20:
            _analyses.popitem(last=False)
    return AnalysisResponse(id=id, capsule=capsule)


@app.get("/analyses/{analysis_id}", response_model=ExitCapsule)
def get_analysis(analysis_id: str) -> ExitCapsule:
    with _analysis_lock:
        capsule = _analyses.get(analysis_id)
    if capsule is None:
        raise HTTPException(
            status_code=404, detail="Analysis not found or expired from the in-memory cache."
        )
    return capsule


@app.get("/analyses/{analysis_id}/export")
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
