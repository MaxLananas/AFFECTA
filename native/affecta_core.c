/*
 * AFFECTA native core — teacher-proposing deferred acceptance.
 *
 * Produces the teacher-optimal stable matching (no justified envy) respecting the
 * MVT1D per-post ordering:  priority ASC, barème DESC, wish-rank ASC, sub-rank ASC,
 * deterministic tie-break ASC.  Incumbent holders keep an absolute right to their own
 * post.  Linear-ish in the total number of (agent, post) proposals; designed for
 * millions of agents on a single core with a compact CSR proposal layout.
 *
 * Compiled to a shared library and driven from Python via ctypes (engine_native.py),
 * and to a standalone benchmark binary (affecta_bench.c).
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#define AFFECTA_API __declspec(dllexport)
#else
#define AFFECTA_API __attribute__((visibility("default")))
#endif

typedef struct {
    int32_t  priority;   /* lower is better */
    int32_t  bareme;     /* higher is better */
    int32_t  wish;       /* lower is better */
    int32_t  sous;       /* lower is better */
    uint64_t tie;        /* lower is better */
    uint8_t  incumbent;  /* 1 => beats every non-incumbent claim */
} key_t;

/* returns 1 if key a is a strictly stronger claim than key b */
static inline int stronger(const key_t *a, const key_t *b) {
    if (a->incumbent != b->incumbent) return a->incumbent > b->incumbent;
    if (a->priority  != b->priority)  return a->priority  < b->priority;
    if (a->bareme    != b->bareme)    return a->bareme    > b->bareme;
    if (a->wish      != b->wish)      return a->wish      < b->wish;
    if (a->sous      != b->sous)      return a->sous      < b->sous;
    return a->tie < b->tie;
}

/*
 * Deferred acceptance.
 *
 * CSR proposal layout: agent i owns proposals [off[i], off[i+1]); each proposal has a
 * target post and its per-post key fields.  Tie-break is stored per agent.
 *
 * out_post[i]   <- assigned post index, or -1 (unassigned).
 * out_wish[i]   <- wish rank of the assignment (copied from the winning proposal), or -1.
 * returns number of assigned agents (post_id != -1).
 */
AFFECTA_API int32_t affecta_da_solve(
    int32_t        n_agents,
    int32_t        n_posts,
    const int32_t *off,           /* n_agents + 1 */
    const int32_t *pref_post,     /* total proposals */
    const int32_t *pref_priority, /* total proposals */
    const int32_t *pref_bareme,   /* total proposals */
    const int32_t *pref_wish,     /* total proposals */
    const int32_t *pref_sous,     /* total proposals */
    const uint8_t *pref_incumbent,/* total proposals */
    const uint64_t*agent_tie,     /* n_agents */
    const int32_t *post_capacity, /* n_posts */
    const int32_t *cap_offset,    /* n_posts + 1 (prefix sum of capacity) */
    int32_t       *out_post,      /* n_agents */
    int32_t       *out_wish)      /* n_agents */
{
    int64_t total_slots = cap_offset[n_posts];

    int32_t  qcap       = n_agents + 1;                /* ring buffer capacity */
    int32_t *slot_agent = (int32_t *)malloc((size_t)total_slots * sizeof(int32_t));
    key_t   *slot_key   = (key_t   *)malloc((size_t)total_slots * sizeof(key_t));
    int32_t *fill       = (int32_t *)calloc((size_t)n_posts, sizeof(int32_t));
    int32_t *next_ptr   = (int32_t *)malloc((size_t)n_agents * sizeof(int32_t));
    int32_t *queue      = (int32_t *)malloc((size_t)qcap * sizeof(int32_t));
    uint8_t *in_queue   = (uint8_t *)calloc((size_t)n_agents, sizeof(uint8_t));

    if (!slot_agent || !slot_key || !fill || !next_ptr || !queue || !in_queue) {
        free(slot_agent); free(slot_key); free(fill);
        free(next_ptr); free(queue); free(in_queue);
        return -1;
    }

    for (int64_t s = 0; s < total_slots; ++s) slot_agent[s] = -1;

    int32_t qhead = 0, qtail = 0;
    for (int32_t i = 0; i < n_agents; ++i) {
        next_ptr[i] = off[i];
        out_post[i] = -1;
        out_wish[i] = -1;
        if (off[i] < off[i + 1]) {                     /* has at least one proposal */
            queue[qtail++] = i;
            in_queue[i] = 1;
        }
    }

    while (qhead != qtail) {
        int32_t a = queue[qhead++];
        if (qhead == qcap) qhead = 0;                  /* ring buffer */
        in_queue[a] = 0;

        /* already placed? (defensive; an unplaced agent should never be queued twice) */
        if (out_post[a] != -1) continue;

        int32_t p = next_ptr[a];
        while (p < off[a + 1]) {
            int32_t post = pref_post[p];
            int32_t cap  = post_capacity[post];
            if (cap <= 0) { ++p; continue; }

            key_t k;
            k.priority  = pref_priority[p];
            k.bareme    = pref_bareme[p];
            k.wish      = pref_wish[p];
            k.sous      = pref_sous[p];
            k.tie       = agent_tie[a];
            k.incumbent = pref_incumbent[p];

            int32_t base = cap_offset[post];

            if (fill[post] < cap) {
                int32_t s = base + fill[post];
                slot_agent[s] = a;
                slot_key[s]   = k;
                ++fill[post];
                out_post[a] = post;
                out_wish[a] = k.wish;
                next_ptr[a] = p + 1;
                break;
            }

            /* post is full: find the weakest occupant */
            int32_t worst_s = base;
            for (int32_t s = base + 1; s < base + cap; ++s)
                if (stronger(&slot_key[worst_s], &slot_key[s])) worst_s = s;

            if (stronger(&k, &slot_key[worst_s])) {
                int32_t kicked = slot_agent[worst_s];
                out_post[kicked] = -1;
                out_wish[kicked] = -1;
                slot_agent[worst_s] = a;
                slot_key[worst_s]   = k;
                out_post[a] = post;
                out_wish[a] = k.wish;
                next_ptr[a] = p + 1;
                /* re-enqueue the displaced agent */
                if (!in_queue[kicked]) {
                    queue[qtail++] = kicked;
                    if (qtail == qcap) qtail = 0;
                    in_queue[kicked] = 1;
                }
                break;
            }
            ++p;   /* rejected here, try next preference */
        }
        if (p >= off[a + 1]) next_ptr[a] = p;          /* exhausted */
    }

    int32_t assigned = 0;
    for (int32_t i = 0; i < n_agents; ++i)
        if (out_post[i] != -1) ++assigned;

    free(slot_agent); free(slot_key); free(fill);
    free(next_ptr); free(queue); free(in_queue);
    return assigned;
}
