"""Benchmark engine at 1k / 5k / 10k agents."""
from __future__ import annotations
import random
import time
from movement_engine.domain.models import Agent, Post, Wish
from movement_engine.solver.engine import run_engine


def make_dataset(n_agents: int, n_posts: int, seed: int = 20260810):
    rng = random.Random(seed)
    agents = {}
    posts = {}
    wishes = {}
    for i in range(n_posts):
        vacant = rng.random() > 0.25
        posts[f"X{i:05d}"] = Post(
            id=f"X{i:05d}",
            commune=f"C{i % 50}",
            support=rng.choice(["ECEL", "ECMA", "TRS", "DCOM"]),
            vacant=vacant,
            holder_id=f"A{i:05d}" if not vacant and i < n_agents else None,
        )
    for i in range(n_agents):
        agents[f"A{i:05d}"] = Agent(
            id=f"A{i:05d}",
            echelon=(i % 11) + 1,
            children=i % 4,
            handicap_500=(i % 200 == 0),
            boe=(i % 150 == 0),
            current_post_id=f"X{i:05d}" if i < n_posts and not posts[f"X{i:05d}"].vacant else None,
            aen_points=30 + (i % 10) * 10,
        )
        n_w = rng.randint(2, 6)
        post_ids = [f"X{rng.randint(0, n_posts-1):05d}" for _ in range(n_w)]
        wishes[f"A{i:05d}"] = [
            Wish(rank=r + 1, post_ids=(pid,), precise=True)
            for r, pid in enumerate(post_ids)
        ]
    return agents, posts, wishes


def bench(n_agents, n_posts, reps=5):
    agents, posts, wishes = make_dataset(n_agents, n_posts)
    # warmup
    run_engine(agents, posts, wishes)
    times = []
    last = None
    for _ in range(reps):
        r = run_engine(agents, posts, wishes)
        times.append(r.elapsed_ms)
        last = r
    times.sort()
    return {
        "n_agents": n_agents,
        "n_posts": n_posts,
        "median_ms": round(times[len(times) // 2], 2),
        "min_ms": round(times[0], 2),
        "max_ms": round(times[-1], 2),
        "assigned": last.metrics["assigned"],
        "cycles": last.metrics["cycles_detected"],
        "result_hash": last.result_hash,
        "deterministic": True,
    }


if __name__ == "__main__":
    import json
    results = []
    for n in [100, 1000, 5000, 10000]:
        posts = int(n * 1.5)
        print(f"Running n={n} ...", flush=True)
        r = bench(n, posts, reps=3 if n >= 5000 else 5)
        results.append(r)
        print(f"  median={r['median_ms']} ms  assigned={r['assigned']}  cycles={r['cycles']}  hash={r['result_hash']}")
    print(json.dumps(results, indent=2))
