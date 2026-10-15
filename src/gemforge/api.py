"""Local API: no execution, repository writes, or AI requests on scan."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import Field

from .engine import scan_repository
from .schemas import ExitCapsule, Schema

app = FastAPI(title="GemForge", version="0.1.0")


class ScanRequest(Schema):
    path: str = Field(min_length=1)
    import_map: dict[str, str] = Field(default_factory=dict)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "1"}


@app.post("/scan", response_model=ExitCapsule)
def scan(request: ScanRequest) -> ExitCapsule:
    try:
        return scan_repository(Path(request.path), request.import_map)
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
