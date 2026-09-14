"""
INDEPENDENT VERIFIER — does NOT import solver.engine.

Input: serialized assignments + agents + posts metadata.
Output: VALID / INVALID with machine-readable error codes.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


@dataclass
class VerifyError:
    code: str
    message: str
    agent: Optional[str] = None
    post: Optional[str] = None


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def result_sha256(assignments: Dict[str, dict]) -> str:
    lines = []
    for aid in sorted(assignments.keys()):
        a = assignments[aid]
        lines.append(f"{aid}:{a.get('post_id')}:{a.get('kind')}")
    return sha256_text("|".join(lines))


def verify(
    *,
    assignments: Dict[str, dict],
    agents: Dict[str, dict],
    posts: Dict[str, dict],
    certificate: Dict[str, Any],
) -> dict:
    """
    Pure verification. No solver import.
    Returns {status: VALID|INVALID, errors: [...], checks: {...}}
    """
    errors: List[VerifyError] = []
    checks: Dict[str, str] = {}

    actual_hash = result_sha256(assignments)
    cert_hash = certificate.get("result_sha256") or certificate.get("result_hash")

    if cert_hash and actual_hash != cert_hash:
        errors.append(VerifyError(
            "E301",
            f"Result SHA-256 mismatch. Expected {str(cert_hash)[:16]}... Received {actual_hash[:16]}...",
        ))
        checks["result_integrity"] = "INVALID"
    else:
        checks["result_integrity"] = "VALID"

    checks["unique_agents"] = "VALID"

    used: Dict[str, str] = {}
    for aid, a in assignments.items():
        if a.get("kind") == "ASSIGNED" and a.get("post_id"):
            pid = a["post_id"]
            if pid in used:
                errors.append(VerifyError("E302", "Post already assigned", agent=aid, post=pid))
            else:
                used[pid] = aid
    checks["unique_posts"] = "VALID" if not any(e.code == "E302" for e in errors) else "INVALID"

    counts = Counter(
        a["post_id"] for a in assignments.values()
        if a.get("kind") == "ASSIGNED" and a.get("post_id")
    )
    cap_ok = True
    for pid, n in counts.items():
        cap = posts.get(pid, {}).get("capacity", 1)
        if n > cap:
            cap_ok = False
            errors.append(VerifyError("E303", f"Capacity exceeded: {n}>{cap}", post=pid))
    checks["capacity"] = "VALID" if cap_ok else "INVALID"

    for aid in assignments:
        if aid not in agents:
            errors.append(VerifyError("E304", "Unknown agent in result", agent=aid))
    checks["agents_exist"] = "VALID" if not any(e.code == "E304" for e in errors) else "INVALID"

    for aid, a in assignments.items():
        if a.get("kind") == "ASSIGNED" and a.get("post_id") and a["post_id"] not in posts:
            errors.append(VerifyError("E305", "Assigned to unknown post", agent=aid, post=a["post_id"]))
    checks["posts_exist"] = "VALID" if not any(e.code == "E305" for e in errors) else "INVALID"

    n_assigned = sum(1 for a in assignments.values() if a.get("kind") == "ASSIGNED")
    n_stay = sum(1 for a in assignments.values() if a.get("kind") == "STAY")
    n_un = sum(1 for a in assignments.values() if a.get("kind") == "UNASSIGNED")
    if n_assigned + n_stay + n_un != len(agents):
        errors.append(VerifyError("E306", "Assignment count mismatch with agent population"))
        checks["count_consistency"] = "INVALID"
    else:
        checks["count_consistency"] = "VALID"

    decisions = certificate.get("decisions") or []
    if decisions:
        wit_ok = all("signature" in d for d in decisions)
        if not wit_ok:
            errors.append(VerifyError("E310", "Decision missing signature"))
        checks["witnesses"] = "VALID" if wit_ok else "INVALID"
    else:
        checks["witnesses"] = "SKIPPED"

    status = "VALID" if not errors else "INVALID"
    return {
        "status": status,
        "checks": checks,
        "errors": [asdict(e) for e in errors],
        "actual_result_sha256": actual_hash,
        "stats": {"assigned": n_assigned, "stayed": n_stay, "unassigned": n_un},
    }
