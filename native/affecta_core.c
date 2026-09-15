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

/*
 * Packed comparison key. To minimise the per-slot footprint (the dominant memory-
 * bandwidth cost at millions of slots) the whole regulatory ordering is folded into two
 * "strength" words (higher = stronger candidate) plus the full 64-bit random tie-break:
 *
 *   hi  bit 63      : incumbent (absolute right on own post)
 *       bits 62..55 : 255 - priority        (priority ASC  -> higher = stronger)
 *       bits 54..31 : barème (24 bits)       (barème  DESC -> higher = stronger)
 *       bits 30..16 : 0x7FFF - wish          (wish    ASC  -> higher = stronger)
 *       bits 15..0  : 0xFFFF - sous          (sub-rank ASC -> higher = stronger)
 *   lo  bits 63..32 : AEN seniority          (discriminant 1, DESC)
 *       bits 31..0  : échelon seniority       (discriminant 2, DESC)
 *   tie             : 64-bit random           (discriminant 3, ASC)
 *
 * This preserves EXACTLY the lexicographic order of CandidateScore.regulatory_key()
 * (verified byte-for-byte against the Python reference), while cutting the comparator to
 * three branches and the struct to 24 bytes.
 */
typedef struct {
    uint64_t hi;   /* higher is stronger */
    uint64_t lo;   /* higher is stronger */
    uint64_t tie;  /* lower is stronger */
} key_t;

static inline uint64_t clamp_u(int32_t v, uint64_t max) {
    if (v < 0) return 0;
    return (uint64_t)v > max ? max : (uint64_t)v;
}

static inline key_t pack_key(int32_t priority, int32_t bareme, int32_t wish,
                             int32_t sous, int32_t aen, int32_t ech,
                             uint64_t tie, uint8_t incumbent) {
    uint64_t pr = 255u - clamp_u(priority, 255u);
    uint64_t ba = clamp_u(bareme, 0xFFFFFFu);
    uint64_t wi = 0x7FFFu - clamp_u(wish, 0x7FFFu);
    uint64_t so = 0xFFFFu - clamp_u(sous, 0xFFFFu);
    key_t k;
    k.hi = ((uint64_t)(incumbent ? 1u : 0u) << 63)
         | (pr << 55) | (ba << 31) | (wi << 16) | so;
    k.lo = (clamp_u(aen, 0xFFFFFFFFu) << 32) | clamp_u(ech, 0xFFFFFFFFu);
    k.tie = tie;
    return k;
}

/* returns 1 if key a is a strictly stronger claim than key b. */
static inline int stronger(const key_t *a, const key_t *b) {
    if (a->hi != b->hi) return a->hi > b->hi;
    if (a->lo != b->lo) return a->lo > b->lo;
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
    const int32_t *pref_aen,      /* total proposals (discriminant 1) */
    const int32_t *pref_ech,      /* total proposals (discriminant 2) */
    const uint8_t *pref_incumbent,/* total proposals */
    const uint64_t*agent_tie,     /* n_agents */
    const int32_t *post_capacity, /* n_posts */
    const int32_t *cap_offset,    /* n_posts + 1 (prefix sum of capacity) */
    int32_t       *out_post,      /* n_agents */
    int32_t       *out_wish)      /* n_agents */
{
    /* Defensive validation at the ctypes boundary: never dereference a required array that
     * is NULL, and treat a degenerate population as a trivially solved empty instance
     * rather than performing out-of-bounds arithmetic. Robustness over assumptions. */
    if (n_agents < 0 || n_posts < 0) return -1;
    if (!off || !pref_post || !pref_priority || !pref_bareme || !pref_wish ||
        !pref_sous || !pref_aen || !pref_ech || !pref_incumbent || !agent_tie ||
        !post_capacity || !cap_offset || !out_post || !out_wish)
        return -1;
    for (int32_t a = 0; a < n_agents; ++a) { out_post[a] = -1; out_wish[a] = -1; }
    if (n_agents == 0) return 0;

    int64_t total_slots = cap_offset[n_posts];
    if (total_slots < 0) return -1;

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

            key_t k = pack_key(pref_priority[p], pref_bareme[p], pref_wish[p],
                               pref_sous[p], pref_aen[p], pref_ech[p],
                               agent_tie[a], pref_incumbent[p]);

            int32_t base = cap_offset[post];

            if (fill[post] < cap) {
                int32_t s = base + fill[post];
                slot_agent[s] = a;
                slot_key[s]   = k;
                ++fill[post];
                out_post[a] = post;
                out_wish[a] = pref_wish[p];
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
                out_wish[a] = pref_wish[p];
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
