"""
AFFECTA — pont ctypes vers le cœur natif d'acceptation différée (native/libaffecta.so).

Le cœur C (native/affecta_core.c) produit l'appariement stable optimal-enseignant en
temps quasi linéaire et passe à l'échelle du million d'agents. Ce module :

  * réutilise `_build_preferences` / `_effective_capacity` du solveur Python de
    référence, donc la sémantique réglementaire (clé par poste, droit du titulaire,
    vœu sur son propre poste ignoré, capacités multi-postes) est STRICTEMENT identique ;
  * encode les listes de préférence dans une disposition CSR compacte (int32) ;
  * appelle le noyau natif et réassemble des objets `Assignment` du domaine.

Le résultat est byte-à-byte identique à `run_deferred_acceptance(..., allow_pure_exchanges=True)`
(appariement stable de base, sans la politique conservatrice d'annulation des échanges
purs). Si la bibliothèque native n'est pas compilée, `native_available()` renvoie False
et l'appelant doit retomber sur le solveur Python pur.

La clé de départage déterministe est le hash SHA-256 tronqué à 16 hexadigits ; converti
en entier 64 bits il conserve EXACTEMENT l'ordre lexicographique utilisé par le solveur
Python (largeur fixe), donc l'appariement reste identique et reproductible.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import time
from typing import Dict, List, Optional

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.regulatory.registry import RuleRegistry, guadeloupe_registry
from movement_engine.solver.engine import EngineResult, _tie_key
from movement_engine.solver.deferred_acceptance import (
    _build_preferences,
    _effective_capacity,
    _assemble,
)

_LIB_PATH = os.path.join(os.path.dirname(__file__), "..", "native", "libaffecta.so")
_lib = None


def _load():
    global _lib
    if _lib is not None:
        return _lib
    path = os.path.abspath(_LIB_PATH)
    if not os.path.exists(path):
        return None
    lib = ctypes.CDLL(path)
    lib.affecta_da_solve.restype = ctypes.c_int32
    lib.affecta_da_solve.argtypes = [
        ctypes.c_int32, ctypes.c_int32,
        ctypes.POINTER(ctypes.c_int32),   # off
        ctypes.POINTER(ctypes.c_int32),   # pref_post
        ctypes.POINTER(ctypes.c_int32),   # pref_priority
        ctypes.POINTER(ctypes.c_int32),   # pref_bareme
        ctypes.POINTER(ctypes.c_int32),   # pref_wish
        ctypes.POINTER(ctypes.c_int32),   # pref_sous
        ctypes.POINTER(ctypes.c_uint8),   # pref_incumbent
        ctypes.POINTER(ctypes.c_uint64),  # agent_tie
        ctypes.POINTER(ctypes.c_int32),   # post_capacity
        ctypes.POINTER(ctypes.c_int32),   # cap_offset
        ctypes.POINTER(ctypes.c_int32),   # out_post
        ctypes.POINTER(ctypes.c_int32),   # out_wish
    ]
    _lib = lib
    return _lib


def native_available() -> bool:
    return _load() is not None


def _arr(ctype, values):
    return (ctype * len(values))(*values)


def run_deferred_acceptance_native(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
    registry: Optional[RuleRegistry] = None,
    *,
    campaign_seed: str = "20260810",
) -> EngineResult:
    """Base stable matching via the native core (== allow_pure_exchanges=True)."""
    lib = _load()
    if lib is None:
        raise RuntimeError("native core not built; run `make -C native`")
    registry = registry or guadeloupe_registry()

    t0 = time.perf_counter()
    prefs, scores = _build_preferences(agents, posts, wishes, registry, campaign_seed)

    # Stable index spaces.
    agent_ids = list(agents.keys())
    aidx = {aid: i for i, aid in enumerate(agent_ids)}
    post_ids = list(posts.keys())
    pidx = {pid: j for j, pid in enumerate(post_ids)}
    n_agents = len(agent_ids)
    n_posts = len(post_ids)

    # Capacity prefix sum.
    eff_cap = _effective_capacity(posts, agents)
    cap = [max(0, int(eff_cap.get(pid, 0))) for pid in post_ids]
    cap_off = [0] * (n_posts + 1)
    for j in range(n_posts):
        cap_off[j + 1] = cap_off[j] + cap[j]

    # Flatten preferences to CSR, preserving each agent's declared order.
    off = [0] * (n_agents + 1)
    pref_post: List[int] = []
    pref_pri: List[int] = []
    pref_bar: List[int] = []
    pref_wish: List[int] = []
    pref_sous: List[int] = []
    pref_inc: List[int] = []
    ties: List[int] = [0] * n_agents

    BIG = 2_000_000_000
    for i, aid in enumerate(agent_ids):
        off[i] = len(pref_post)
        ties[i] = int(_tie_key(aid, campaign_seed), 16) & 0xFFFFFFFFFFFFFFFF
        for (pid, wr, sr, ekey, is_fb) in prefs.get(aid, []):
            j = pidx.get(pid)
            if j is None:
                continue
            pref_post.append(j)
            if is_fb:
                # incumbent fallback (STAY on own post): dominates everything
                pref_pri.append(0)
                pref_bar.append(0)
                pref_wish.append(0)
                pref_sous.append(0)
                pref_inc.append(1)
            else:
                # ekey = (priority_rank, -bareme, wish_rank, sous_rank, tie_str)
                pref_pri.append(int(ekey[0]))
                pref_bar.append(-int(ekey[1]))            # store barème as positive
                pref_wish.append(int(ekey[2]))
                sval = int(ekey[3])
                pref_sous.append(sval if sval < BIG else 0)
                pref_inc.append(0)
    off[n_agents] = len(pref_post)

    c_off = _arr(ctypes.c_int32, off)
    c_post = _arr(ctypes.c_int32, pref_post or [0])
    c_pri = _arr(ctypes.c_int32, pref_pri or [0])
    c_bar = _arr(ctypes.c_int32, pref_bar or [0])
    c_wish = _arr(ctypes.c_int32, pref_wish or [0])
    c_sous = _arr(ctypes.c_int32, pref_sous or [0])
    c_inc = _arr(ctypes.c_uint8, pref_inc or [0])
    c_tie = _arr(ctypes.c_uint64, ties or [0])
    c_cap = _arr(ctypes.c_int32, cap or [0])
    c_capoff = _arr(ctypes.c_int32, cap_off)
    c_out_post = _arr(ctypes.c_int32, [-1] * n_agents)
    c_out_wish = _arr(ctypes.c_int32, [-1] * n_agents)

    rc = lib.affecta_da_solve(
        n_agents, n_posts, c_off, c_post, c_pri, c_bar, c_wish, c_sous,
        c_inc, c_tie, c_cap, c_capoff, c_out_post, c_out_wish,
    )
    if rc < 0:
        raise MemoryError("native core allocation failed")

    # Rebuild a {agent_id: post_id} match, translating incumbent STAY back.
    match: Dict[str, str] = {}
    for i, aid in enumerate(agent_ids):
        j = c_out_post[i]
        if j >= 0:
            match[aid] = post_ids[j]

    raw = _assemble(match, agents, posts, scores)
    elapsed = (time.perf_counter() - t0) * 1000

    canon = "|".join(
        f"{a}:{raw[a].post_id}:{raw[a].kind}" for a in sorted(raw)
    )
    result_hash = hashlib.sha256(canon.encode()).hexdigest()[:16]
    input_hash = hashlib.sha256(
        f"{len(agents)}:{len(posts)}:{campaign_seed}".encode()
    ).hexdigest()[:16]

    metrics = {
        "agents": len(agents),
        "posts": len(posts),
        "assigned": sum(1 for a in raw.values() if a.kind == "ASSIGNED"),
        "stayed": sum(1 for a in raw.values() if a.kind == "STAY"),
        "unassigned": sum(1 for a in raw.values() if a.kind == "UNASSIGNED"),
        "cycles_detected": 0,
        "passes": 1,
        "scores_computed": len(scores),
        "proposals": len(pref_post),
        "method": "DEFERRED_ACCEPTANCE_NATIVE",
    }
    return EngineResult(
        assignments=raw,
        cycles=[],
        metrics=metrics,
        elapsed_ms=elapsed,
        input_hash=input_hash,
        result_hash=result_hash,
    )
