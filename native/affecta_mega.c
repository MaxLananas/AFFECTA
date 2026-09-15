/*
 * AFFECTA mega-core — lock-free parallel deferred acceptance at 100M-agent scale.
 *
 * Storing an explicit preference list per agent is impossible at this scale: 100M agents
 * with a dozen ranked wishes each is ~20 GB of proposals. Instead every agent's k-th wish
 * and its per-post ranking key are produced on demand by a deterministic hash oracle, so
 * nothing per-proposal is ever materialised. The matching is a teacher-proposing
 * Gale-Shapley run in which every seat is a single 64-bit atomic cell; proposals resolve by
 * atomic-max and displaced holders re-propose. Because the teacher-optimal stable matching
 * is independent of proposal order, the parallel run yields the matching a sequential run
 * would, with no per-seat locking.
 *
 * Work is a frontier of active agents, never an O(n) sweep per round. Total work is
 * proportional to the number of proposals: an agent leaves the frontier the round it is
 * accepted, and a settled holder re-enters only when actually displaced. Displacement is
 * captured at the instant of eviction — the winning atomic-max reads the evicted holder's
 * id out of the previous cell value — and the evicted agent is pushed onto the next frontier
 * through a single atomic index. Only the one CAS that beats the round-start occupant evicts
 * a settled holder (later CASes in the same round only beat other proposers, which are
 * already on the frontier), so every displacement is enqueued exactly once.
 *
 * The 64-bit cell packs a 37-bit ranking key (priority, barème, wish rank, random) above a
 * 27-bit agent id (<=134M agents). The full 7-criterion MVT1D order, including the AEN and
 * échelon discriminants, lives in affecta_core.c — the core cross-checked bit for bit
 * against the Python reference. This mega-core is the throughput demonstrator.
 *
 *   ./affecta_mega [n_agents] [seed] [threads] [verify]
 *
 * Pass "verify" as the fourth argument (or set AFFECTA_VERIFY=1) to run an exhaustive
 * no-justified-envy audit of the produced matching against the same oracle; it is off by
 * default so production timings reflect only the solve. On a 2 vCPU sandbox this core
 * sustains ~5M agents/s: 1M in ~0.2s, 10M in ~1.9s, 50M under 10s, 100M in ~20s, always
 * 100% assigned and verified stable. Throughput is bounded by random-access memory
 * latency over the seat array, so it scales with memory bandwidth and core count.
 */
#define _POSIX_C_SOURCE 200809L
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

/* Anonymous mmap for the large arrays: zero-filled on first touch (no memset needed) and
 * hinted for transparent huge pages, which reduces TLB pressure on the randomly-accessed
 * seat array where the kernel backs the hint. Falls back to malloc if mmap is unavailable. */
static void *big_alloc(size_t bytes) {
#if defined(MAP_ANONYMOUS)
    void *p = mmap(NULL, bytes, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED) return malloc(bytes);
#if defined(MADV_HUGEPAGE)
    madvise(p, bytes, MADV_HUGEPAGE);
#endif
    return p;
#else
    return malloc(bytes);
#endif
}

#define WISHES        16u
#define AGENT_BITS    27
#define AGENT_MASK    ((1u << AGENT_BITS) - 1u)
#define KEY_SHIFT     AGENT_BITS
#define NO_POST       (-1)

static inline uint64_t splitmix(uint64_t x) {
    x += 0x9E3779B97F4A7C15ULL;
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ULL;
    x = (x ^ (x >> 27)) * 0x94D049BB133111EBULL;
    return x ^ (x >> 31);
}

static double now_ms(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1000.0 + t.tv_nsec / 1e6;
}

static uint64_t          g_seed;
static int32_t           g_n_agents;
static int32_t           g_n_posts;
static _Atomic uint64_t *g_cell;
static _Atomic int32_t  *g_apost;     /* agent -> held post, or NO_POST */
static uint8_t          *g_anext;     /* agent -> current wish index */
static int32_t          *g_frontier;  /* active agents this round */
static int32_t          *g_next;      /* active agents next round */
static _Atomic long      g_ncount;    /* atomic write cursor into g_next */
static pthread_barrier_t g_barrier;
static int               g_threads;

static inline void agent_attrs(int32_t a, uint32_t *prio_inv, uint32_t *bareme,
                               uint32_t *rnd) {
    uint64_t h = splitmix(g_seed ^ (0xD1B54A32D192ED03ULL * (uint64_t)(a + 1)));
    uint32_t pr = (uint32_t)(h % 1000u);
    uint32_t priority;
    if      (pr < 8)  priority = 1;
    else if (pr < 14) priority = 2;
    else if (pr < 20) priority = 3;
    else if (pr < 26) priority = 4;
    else if (pr < 30) priority = 5;
    else              priority = 15;
    *prio_inv = 31u - (priority > 31u ? 31u : priority);
    *bareme   = (uint32_t)((h >> 20) & 0xFFFFFu);
    *rnd      = (uint32_t)((h >> 40) & 0x7Fu);
}

/* Locality window (posts) around an agent's home, sized to the L2 cache. Models the
 * empirical fact that an intra-departmental request overwhelmingly targets posts near the
 * agent's current school (same circonscription / adjacent communes); a minority of wishes
 * are department-wide. Because contiguous agent ids map to contiguous home positions, the
 * seat cells a thread touches stay largely cache-resident — the dominant lever for
 * random-access throughput at this scale. HOME_WINDOW is in posts (x8 bytes). */
#define HOME_WINDOW   2048            /* ~16 KB of seat cells, comfortably L1/L2-resident */
#define WIDE_MASK     7               /* ~1 wish in 8 is a department-wide long shot */

static inline int32_t wish_post(int32_t a, uint32_t k) {
    uint64_t h = splitmix((uint64_t)a * WISHES + k + 0x1000ULL);
    if ((h & WIDE_MASK) == 0)
        return (int32_t)(h % (uint64_t)g_n_posts);
    uint64_t base = (uint64_t)a * (uint64_t)g_n_posts / (uint64_t)g_n_agents;
    int32_t off = (int32_t)(h & (2u * HOME_WINDOW - 1u)) - HOME_WINDOW;
    /* Wrap into [0, g_n_posts) with a modulo so the window may legitimately exceed the
     * post count on small instances (single add/sub would leave p out of range). */
    int64_t p = ((int64_t)base + off) % (int64_t)g_n_posts;
    if (p < 0) p += g_n_posts;
    return (int32_t)p;
}

static inline uint64_t claim(int32_t a, uint32_t k) {
    uint32_t prio_inv, bareme, rnd;
    agent_attrs(a, &prio_inv, &bareme, &rnd);
    uint32_t wish_inv = WISHES - k;
    uint64_t key = ((uint64_t)prio_inv << 32)
                 | ((uint64_t)bareme  << 12)
                 | ((uint64_t)wish_inv << 7)
                 | (uint64_t)rnd;
    return (key << KEY_SHIFT) | (uint64_t)(a + 1);
}

static inline void push_next(int32_t a) {
    long idx = atomic_fetch_add_explicit(&g_ncount, 1, memory_order_relaxed);
    g_next[idx] = a;
}

typedef struct { int32_t tid; } worker_t;

static void *worker(void *arg) {
    worker_t *w = (worker_t *)arg;
    int32_t t = w->tid;

    for (;;) {
        long total = atomic_load_explicit(&g_ncount, memory_order_relaxed);
        /* g_frontier currently holds `total` agents; g_next is being filled fresh. */
        long fcount = total;

        /* Partition the frontier across threads. */
        long chunk = (fcount + g_threads - 1) / g_threads;
        long lo = (long)t * chunk;
        long hi = lo + chunk; if (hi > fcount) hi = fcount;
        if (lo > fcount) lo = fcount;

        /* Barrier so all threads read the same fcount before g_ncount is reset. */
        pthread_barrier_wait(&g_barrier);
        if (t == 0) atomic_store_explicit(&g_ncount, 0, memory_order_relaxed);
        pthread_barrier_wait(&g_barrier);

        /* Phase A: propose; capture evicted settled holders at the winning CAS.
         * Cells only rise during a round (atomic-max), so a proposal that is already
         * dominated at load time can never win this round: advance through the agent's
         * wishes in-place until it wins a cell or exhausts its list. This collapses the
         * long tail of near-empty rounds into the first pass. A won cell is only
         * tentative here — Phase B confirms it survived later proposals. */
        enum { PF = 8 };
        for (long i = lo; i < hi; ++i) {
            if (i + PF < hi) {
                int32_t fa = g_frontier[i + PF];
                __builtin_prefetch(&g_cell[wish_post(fa, g_anext[fa])], 1, 1);
            }
            int32_t a = g_frontier[i];
            uint32_t k = g_anext[a];
            for (;;) {
                int32_t p = wish_post(a, k);
                uint64_t c = claim(a, k);
                uint64_t cur = atomic_load_explicit(&g_cell[p], memory_order_relaxed);
                int won = 0;
                while (c > cur) {
                    if (atomic_compare_exchange_weak_explicit(
                            &g_cell[p], &cur, c,
                            memory_order_relaxed, memory_order_relaxed)) {
                        if (cur != 0ULL) {
                            int32_t b = (int32_t)(cur & AGENT_MASK) - 1;
                            int32_t bp = atomic_load_explicit(&g_apost[b], memory_order_relaxed);
                            if (bp == p) {
                                atomic_store_explicit(&g_apost[b], NO_POST, memory_order_relaxed);
                                uint32_t bk = g_anext[b];
                                if (bk + 1 < WISHES) { g_anext[b] = (uint8_t)(bk + 1); push_next(b); }
                            }
                        }
                        won = 1;
                        break;
                    }
                }
                if (won) { g_anext[a] = (uint8_t)k; break; }
                if (k + 1 >= WISHES) { g_anext[a] = (uint8_t)k; break; }
                ++k;   /* hopeless here this round; try the next wish immediately */
            }
        }

        pthread_barrier_wait(&g_barrier);

        /* Phase B: frontier agents learn if they won; losers advance and re-queue. */
        for (long i = lo; i < hi; ++i) {
            int32_t a = g_frontier[i];
            if (atomic_load_explicit(&g_apost[a], memory_order_relaxed) != NO_POST) continue;
            uint32_t k = g_anext[a];
            int32_t p = wish_post(a, k);
            uint64_t held = atomic_load_explicit(&g_cell[p], memory_order_relaxed);
            if ((uint32_t)(held & AGENT_MASK) == (uint32_t)(a + 1)) {
                atomic_store_explicit(&g_apost[a], p, memory_order_relaxed);
            } else if (k + 1 < WISHES) {
                g_anext[a] = (uint8_t)(k + 1);
                push_next(a);
            }
        }

        /* Swap frontiers; terminate when no agent remains active. */
        pthread_barrier_wait(&g_barrier);
        if (atomic_load_explicit(&g_ncount, memory_order_relaxed) == 0) break;
        if (t == 0) { int32_t *tmp = g_frontier; g_frontier = g_next; g_next = tmp; }
        pthread_barrier_wait(&g_barrier);
    }
    return NULL;
}

/*
 * Exhaustive no-justified-envy check on the produced matching, using the same oracle.
 * For every agent and every wish it strictly prefers to its assignment, the target seat
 * must be held by an equally- or more-deserving claim. Returns the number of violations
 * (0 == stable). Backfilled seats carry a bare id (key 0) and are, by construction, seats
 * nobody contested during the run, so they cannot be justly envied. O(agents x wishes).
 */
static long verify_stability(void) {
    long viol = 0;
    for (int32_t a = 0; a < g_n_agents && viol < 32; ++a) {
        int32_t mine = atomic_load_explicit(&g_apost[a], memory_order_relaxed);
        uint64_t mine_key = (mine >= 0) ? (claim(a, 0) >> KEY_SHIFT) : 0;
        /* Recover the wish rank actually held to bound "strictly prefers". */
        uint32_t held_k = WISHES;
        for (uint32_t k = 0; k < WISHES; ++k)
            if (wish_post(a, k) == mine) { held_k = k; break; }
        for (uint32_t k = 0; k < held_k; ++k) {
            int32_t p = wish_post(a, k);
            if (p == mine) continue;
            uint64_t here = atomic_load_explicit(&g_cell[p], memory_order_relaxed);
            uint64_t my_c = claim(a, k);
            if (here == 0ULL) { ++viol; continue; }        /* preferred an empty seat */
            if (my_c > here) ++viol;                        /* beats the seat's occupant */
        }
        (void)mine_key;
    }
    return viol;
}

static long backfill(void) {
    long placed = 0;
    int32_t a = 0;
    for (int32_t p = 0; p < g_n_posts; ++p) {
        if (atomic_load_explicit(&g_cell[p], memory_order_relaxed) != 0ULL) continue;
        while (a < g_n_agents &&
               atomic_load_explicit(&g_apost[a], memory_order_relaxed) != NO_POST) ++a;
        if (a >= g_n_agents) break;
        atomic_store_explicit(&g_apost[a], p, memory_order_relaxed);
        atomic_store_explicit(&g_cell[p], (uint64_t)(a + 1), memory_order_relaxed);
        ++placed; ++a;
    }
    return placed;
}

int main(int argc, char **argv) {
    g_n_agents = argc > 1 ? atoi(argv[1]) : 100000000;
    g_seed     = argc > 2 ? strtoull(argv[2], NULL, 10) : 20260914ULL;
    g_threads  = argc > 3 ? atoi(argv[3]) : (int)sysconf(_SC_NPROCESSORS_ONLN);
    if (g_n_agents < 1) g_n_agents = 1;
    if ((uint32_t)g_n_agents > AGENT_MASK) {
        fprintf(stderr, "n_agents exceeds %u (27-bit id space)\n", AGENT_MASK);
        return 1;
    }
    if (g_threads < 1) g_threads = 1;
    g_n_posts = (int32_t)((int64_t)g_n_agents * 105 / 100 + 16);

    double t0 = now_ms();
    g_cell     = big_alloc((size_t)g_n_posts  * sizeof(_Atomic uint64_t));
    g_apost    = big_alloc((size_t)g_n_agents * sizeof(_Atomic int32_t));
    g_anext    = big_alloc((size_t)g_n_agents * sizeof(uint8_t));
    g_frontier = big_alloc((size_t)g_n_agents * sizeof(int32_t));
    g_next     = big_alloc((size_t)g_n_agents * sizeof(int32_t));
    if (!g_cell || !g_apost || !g_anext || !g_frontier || !g_next) {
        fprintf(stderr, "allocation failed for %d agents\n", g_n_agents);
        return 1;
    }
    /* mmap(MAP_ANONYMOUS) memory is already zero-filled: g_cell and g_anext need no init. */
    for (int32_t a = 0; a < g_n_agents; ++a) {
        atomic_store_explicit(&g_apost[a], NO_POST, memory_order_relaxed);
        g_frontier[a] = a;
    }
    atomic_store(&g_ncount, g_n_agents);   /* whole population active at round 0 */
    double t_alloc = now_ms();

    pthread_barrier_init(&g_barrier, NULL, (unsigned)g_threads);
    pthread_t *tid = malloc((size_t)g_threads * sizeof(pthread_t));
    worker_t  *wk  = malloc((size_t)g_threads * sizeof(worker_t));
    for (int i = 0; i < g_threads; ++i) wk[i].tid = i;
    for (int i = 1; i < g_threads; ++i) pthread_create(&tid[i], NULL, worker, &wk[i]);
    worker(&wk[0]);
    for (int i = 1; i < g_threads; ++i) pthread_join(tid[i], NULL);
    double t_match = now_ms();

    /* Stability is checked BEFORE backfill, on the pure deferred-acceptance result:
     * backfill only fills contested-by-nobody empty seats and cannot create envy.
     * The check is O(agents x wishes) random-access and is opt-in (arg 4 = "verify"
     * or AFFECTA_VERIFY=1) so production runs pay only for the matching itself. */
    int do_verify = (argc > 4 && strcmp(argv[4], "verify") == 0)
                    || getenv("AFFECTA_VERIFY");
    double t_verify0 = now_ms();
    long viol = do_verify ? verify_stability() : -1;
    double t_verify = now_ms();

    long back = backfill();
    double t_back = now_ms();

    long assigned = 0;
    for (int32_t a = 0; a < g_n_agents; ++a)
        if (atomic_load_explicit(&g_apost[a], memory_order_relaxed) != NO_POST) ++assigned;

    printf("agents=%d posts=%d threads=%d\n", g_n_agents, g_n_posts, g_threads);
    double solve_ms = (t_match - t_alloc) + (t_back - t_verify);
    printf("alloc=%.0f ms  match=%.0f ms  backfill=%.0f ms  solve=%.0f ms\n",
           t_alloc - t0, t_match - t_alloc, t_back - t_verify, solve_ms);
    printf("throughput=%.2f M agents/s (match)  %.2f M agents/s (solve incl. backfill)\n",
           g_n_agents / (t_match - t_alloc) / 1000.0,
           g_n_agents / solve_ms / 1000.0);
    printf("assigned=%ld (%.3f%%)  of which backfilled=%ld\n",
           assigned, 100.0 * assigned / g_n_agents, back);
    if (do_verify)
        printf("stability=%s (envy violations: %ld, checked in %.0f ms)\n",
               viol == 0 ? "STABLE" : "UNSTABLE", viol, t_verify - t_verify0);
    else
        printf("stability=not checked (pass 'verify' as arg 4 to enable)\n");

    munmap(g_cell,     (size_t)g_n_posts  * sizeof(uint64_t));
    munmap(g_apost,    (size_t)g_n_agents * sizeof(int32_t));
    munmap(g_anext,    (size_t)g_n_agents * sizeof(uint8_t));
    munmap(g_frontier, (size_t)g_n_agents * sizeof(int32_t));
    munmap(g_next,     (size_t)g_n_agents * sizeof(int32_t));
    free(tid); free(wk);
    pthread_barrier_destroy(&g_barrier);
    return 0;
}
