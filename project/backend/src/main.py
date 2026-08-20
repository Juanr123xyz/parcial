from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .solver import solve as solve_agent

app = FastAPI(title="Emergency Control Solver")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/solve")
def solve_endpoint(scenario: dict[str, Any]) -> dict[str, Any]:
    return solve_agent(scenario)
