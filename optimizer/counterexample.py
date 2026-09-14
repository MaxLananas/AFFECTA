"""
Search for instances where a naive sequential greedy (no liberation multi-pass)
gets strictly fewer assignments than the exhaustive optimum.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from movement_engine.domain.models import Agent, Assignment, Post, Wish
from movement_engine.optimizer.exhaustive import exhaustive_optimize
from movement_engine.regulatory.scorer import score_candidate
from movement_engine.regulatory.registry import guadeloupe_registry


def naive_sequential_no_release(
    agents: Dict[str, Agent],
    posts: Dict[str, Post],
    wishes: Dict[str, List[Wish]],
) -> Dict[str, Assignment]:
    """
    Pure sequential: process agents in id order, assign first free vacant post
    in their wish list. Does NOT liberate occupied posts. This is the weak baseline.
    """
    reg = guadeloupe_registry()
    free = {pid for pid, p in posts.items() if p.vacant}
    assigned: Dict[str, Assignment] = {}
    used = set()

    for aid in sorted(agents.keys()):
        agent = agents[aid]
        placed = False
        for wish in wishes.get(aid, []):
            for pid in wish.post_ids:
                if pid not in free or pid in used:
                    continue
                s = score_candidate(agent, posts[pid], wish, reg)
                if not s.eligible:
                    continue
                assigned[aid] = Assignment(
                    agent_id=aid, post_id=pid, wish_rank=wish.rank,
                    kind="ASSIGNED", score=s,
                )
                used.add(pid)
                free.discard(pid)
                placed = True
                break
            if placed:
                break
        if not placed:
            cur = agent.current_post_id
            assigned[aid] = Assignment(
                agent_id=aid, post_id=cur, wish_rank=None,
                kind="STAY" if cur else "UNASSIGNED",
            )
    return assigned


def search_counterexample(
    max_agents: int = 6,
    max_posts: int = 6,
    trials: int = 2000,
    seed: int = 20260811,
) -> Optional[dict]:
    rng = random.Random(seed)
    for t in range(trials):
        n = rng.randint(3, max_agents)
        np_ = rng.randint(max(2, n - 2), max_posts)
        agents = {
            f"A{i}": Agent(id=f"A{i}", echelon=rng.randint(1, 11))
            for i in range(n)
        }
        # mix vacant and occupied
        posts = {}
        for j in range(np_):
            vacant = rng.random() > 0.3
            holder = None
            if not vacant and j < n:
                holder = f"A{j}"
                agents[f"A{j}"] = Agent(
                    id=f"A{j}", echelon=agents[f"A{j}"].echelon,
                    current_post_id=f"X{j}",
                )
            posts[f"X{j}"] = Post(
                id=f"X{j}", commune="BT", support="ECEL",
                vacant=vacant, holder_id=holder,
            )
        wishes = {}
        for i in range(n):
            k = rng.randint(1, min(3, np_))
            pids = [f"X{rng.randint(0, np_ - 1)}" for _ in range(k)]
            # dedupe preserve order
            seen = set()
            ordered = []
            for p in pids:
                if p not in seen:
                    seen.add(p)
                    ordered.append(p)
            wishes[f"A{i}"] = [
                Wish(rank=r + 1, post_ids=(p,)) for r, p in enumerate(ordered)
            ]

        naive = naive_sequential_no_release(agents, posts, wishes)
        naive_n = sum(1 for a in naive.values() if a.kind == "ASSIGNED")
        try:
            opt = exhaustive_optimize(agents, posts, wishes)
        except Exception:
            continue
        opt_n = opt["quality"]["assigned"]
        if opt_n > naive_n:
            return {
                "seed": seed,
                "trial": t,
                "n_agents": n,
                "n_posts": np_,
                "naive_assigned": naive_n,
                "optimal_assigned": opt_n,
                "loss": naive_n - opt_n,
                "agents": {aid: {"echelon": a.echelon, "current_post_id": a.current_post_id} for aid, a in agents.items()},
                "posts": {pid: {"vacant": p.vacant, "holder_id": p.holder_id} for pid, p in posts.items()},
                "wishes": {
                    aid: [{"rank": w.rank, "post_ids": list(w.post_ids)} for w in wl]
                    for aid, wl in wishes.items()
                },
                "naive": {aid: {"post": a.post_id, "kind": a.kind} for aid, a in naive.items()},
                "optimal": {
                    aid: {"post": a.post_id, "kind": a.kind}
                    for aid, a in opt["assignments"].items()
                },
            }
    return None
