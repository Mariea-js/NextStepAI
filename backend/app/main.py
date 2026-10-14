"""
main.py
-------
The FastAPI app. This is what your teammates (frontend, AI layer)
actually talk to.

Run it locally with (from inside backend/, venv active):
    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000/docs for an interactive test page
that FastAPI builds automatically from this file.
"""

import os
import secrets
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

from .models import StudentProfile, MatchResult
from .matching import get_matches
from .data_loader import refresh_cache, get_opportunities

app = FastAPI(title="NextStep AI - Matching Engine")

# Allows your frontend (running on a different port) to call this API
# during development. Tighten this to a specific domain before launch.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "NextStep AI matching engine is running"}


@app.get("/opportunities/count")
def opportunities_count():
    """Quick sanity check -- how many scholarships are currently loaded."""
    return {"count": len(get_opportunities())}


@app.post("/match", response_model=list[MatchResult])
def match_student(student: StudentProfile):
    """
    The main endpoint. Send a student's profile, get back every
    scholarship ranked by fit, with eligibility status and score
    breakdown for each.
    """
    return get_matches(student)


def require_admin_key(x_admin_key: str | None = Header(default=None)):
    configured = os.getenv("NEXTSTEP_ADMIN_KEY")
    if not configured or not x_admin_key or not secrets.compare_digest(x_admin_key, configured):
        raise HTTPException(status_code=403, detail="Administrative access denied")


@app.post("/admin/refresh-data", dependencies=[Depends(require_admin_key)])
def refresh_data():
    """
    Call this after the spreadsheet has been updated with new
    scholarships, so the API picks up the changes without restarting.
    """
    opportunities = refresh_cache()
    return {"status": "refreshed", "count": len(opportunities)}
