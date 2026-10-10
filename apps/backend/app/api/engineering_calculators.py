"""The calculators, server-side (ADR 110): the same results as the
Calculators screen, for SirisAI (via the service key) and anything else
that can't run the PWA's TypeScript.

    GET  /api/v1/engineering/calculators              the catalogue
    POST /api/v1/engineering/calculators/{id}/run     {"inputs": {"d": 0.45, ...}}
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_user
from app.engineering import calculators

router = APIRouter(prefix="/api/v1/engineering/calculators", tags=["engineering"], dependencies=[Depends(require_user)])


class RunRequest(BaseModel):
    inputs: dict[str, float] = Field(default_factory=dict)


@router.get("")
async def list_calculators() -> dict:
    return {"calculators": [c.describe() for c in calculators.CALCULATORS]}


@router.post("/{calculator_id}/run")
async def run_calculator(calculator_id: str, request: RunRequest) -> dict:
    if calculator_id not in calculators.BY_ID:
        raise HTTPException(status_code=404, detail=f"Unknown calculator: {calculator_id}. Known: {', '.join(calculators.BY_ID)}")
    try:
        return calculators.run(calculator_id, request.inputs)
    except calculators.InputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
