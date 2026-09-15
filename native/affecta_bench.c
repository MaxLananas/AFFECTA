/*
 * AFFECTA scaling benchmark.
 *
 * Generates a synthetic intra-departmental campaign whose statistical shape mirrors
 * the real Guadeloupe dataset (post/vacancy ratios, wish-list lengths, priority mix,
 * barème spread) and times the native deferred-acceptance core on it.
 *
 *   ./affecta_bench [n_agents] [seed]
 *
 * Reports build time, solve time, throughput, assignment rate and wish-1 rate.
 * The generator and solver together stay within a couple of GB for a few million
 * agents so the whole thing runs on a single modest core.
 */
#define _POSIX_C_SOURCE 199309L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

extern int32_t affecta_da_solve(
    int32_t n_agents, int32_t n_posts,
    const int32_t *off, const int32_t *pref_post,
    const int32_t *pref_priority, const int32_t *pref_bareme,
    const int32_t *pref_wish, const int32_t *pref_sous,
    const uint8_t *pref_incumbent, const uint64_t *agent_tie,
    const int32_t *post_capacity, const int32_t *cap_offset,
    int32_t *out_post, int32_t *out_wish);

/* splitmix64: fast, well-distributed deterministic PRNG */
static inline uint64_t sm64(uint64_t *s) {
    uint64_t z = (*s += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}
static inline uint32_t rnd(uint64_t *s, uint32_t n) { return (uint32_t)(sm64(s) % n); }

static double now_ms(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1000.0 + t.tv_nsec / 1e6;
}

int main(int argc, char **argv) {
    int32_t  n_agents = argc > 1 ? atoi(argv[1]) : 1000000;
    uint64_t seed     = argc > 2 ? strtoull(argv[2], NULL, 10) : 20260914ULL;
    if (n_agents < 1) n_agents = 1;

    /* Real dataset shape: ~2 agents per post-slot, ~19% of posts vacant. Scale posts
     * with agents so capacity slightly exceeds demand (a solvable campaign). */
    int32_t n_posts   = (int32_t)((int64_t)n_agents * 60 / 100 + 16);
    int32_t wishes    = 12;                 /* precise wishes per agent */

    uint64_t s = seed;

    double t0 = now_ms();

    /* Capacities: mostly 1-2, a few larger (grouped supports). */
    int32_t *cap    = (int32_t *)malloc((size_t)n_posts * sizeof(int32_t));
    int32_t *capoff = (int32_t *)malloc((size_t)(n_posts + 1) * sizeof(int32_t));
    int64_t total_cap = 0;
    for (int32_t j = 0; j < n_posts; ++j) {
        uint32_t r = rnd(&s, 100);
        int32_t c = r < 55 ? 1 : (r < 90 ? 2 : (r < 98 ? 3 : 5));
        cap[j] = c;
        capoff[j] = (int32_t)total_cap;
        total_cap += c;
    }
    capoff[n_posts] = (int32_t)total_cap;

    /* An incumbent holds a fraction of slots; a subset participates in the movement. */
    int32_t *off    = (int32_t *)malloc((size_t)(n_agents + 1) * sizeof(int32_t));
    int64_t  total_pref = (int64_t)n_agents * (wishes + 1);   /* +1 possible incumbent */
    int32_t *pp     = (int32_t *)malloc((size_t)total_pref * sizeof(int32_t));
    int32_t *ppri   = (int32_t *)malloc((size_t)total_pref * sizeof(int32_t));
    int32_t *pbar   = (int32_t *)malloc((size_t)total_pref * sizeof(int32_t));
    int32_t *pwish  = (int32_t *)malloc((size_t)total_pref * sizeof(int32_t));
    int32_t *psous  = (int32_t *)malloc((size_t)total_pref * sizeof(int32_t));
    uint8_t *pinc   = (uint8_t *)malloc((size_t)total_pref * sizeof(uint8_t));
    uint64_t*tie    = (uint64_t*)malloc((size_t)n_agents * sizeof(uint64_t));
    int32_t *opost  = (int32_t *)malloc((size_t)n_agents * sizeof(int32_t));
    int32_t *owish  = (int32_t *)malloc((size_t)n_agents * sizeof(int32_t));

    if (!cap || !capoff || !off || !pp || !ppri || !pbar || !pwish ||
        !psous || !pinc || !tie || !opost || !owish) {
        fprintf(stderr, "allocation failed for %d agents\n", n_agents);
        return 1;
    }

    int64_t w = 0;
    for (int32_t i = 0; i < n_agents; ++i) {
        off[i] = (int32_t)w;
        tie[i] = sm64(&s);

        /* Priority mix (art. 60 order): mostly standard (15); a minority carry a
         * legal priority 1..5, a few large barème bonuses. */
        uint32_t pr = rnd(&s, 1000);
        int32_t priority, bareme;
        if      (pr < 8)   { priority = 1; bareme = 150 + (int32_t)rnd(&s, 450); } /* rappr. conjoint */
        else if (pr < 14)  { priority = 2; bareme = 800; }                          /* handicap */
        else if (pr < 20)  { priority = 3; bareme = 300 + (int32_t)rnd(&s, 200); } /* QPV */
        else if (pr < 26)  { priority = 4; bareme = 600; }                          /* CIMM */
        else if (pr < 30)  { priority = 5; bareme = 200; }                          /* suppr. poste */
        else               { priority = 15; bareme = 21 + (int32_t)rnd(&s, 260); } /* barème standard */

        /* 62% are incumbents holding a current post that they may keep. */
        int32_t has_incumbent = rnd(&s, 100) < 62;
        if (has_incumbent) {
            int32_t home = (int32_t)rnd(&s, (uint32_t)n_posts);
            pp[w] = home; ppri[w] = priority; pbar[w] = bareme;
            pwish[w] = 0; psous[w] = 0; pinc[w] = 1; ++w;
        }

        for (int32_t k = 0; k < wishes; ++k) {
            pp[w]   = (int32_t)rnd(&s, (uint32_t)n_posts);
            ppri[w] = priority;
            pbar[w] = bareme;
            pwish[w]= k + 1;
            psous[w]= (int32_t)rnd(&s, 3);
            pinc[w] = 0;
            ++w;
        }
    }
    off[n_agents] = (int32_t)w;

    double t1 = now_ms();

    int32_t assigned = affecta_da_solve(
        n_agents, n_posts, off, pp, ppri, pbar, pwish, psous, pinc, tie,
        cap, capoff, opost, owish);

    double t2 = now_ms();

    if (assigned < 0) { fprintf(stderr, "solver allocation failed\n"); return 1; }

    int64_t wish1 = 0, top3 = 0;
    for (int32_t i = 0; i < n_agents; ++i) {
        if (opost[i] < 0) continue;
        if (owish[i] == 1) ++wish1;          /* incumbent stay counts as wish 0 */
        if (owish[i] >= 1 && owish[i] <= 3) ++top3;
    }

    double build = t1 - t0, solve = t2 - t1;
    printf("agents=%d posts=%d slots=%lld proposals=%lld\n",
           n_agents, n_posts, (long long)total_cap, (long long)w);
    printf("build=%.1f ms  solve=%.1f ms  throughput=%.2f M agents/s\n",
           build, solve, n_agents / solve / 1000.0);
    printf("assigned=%d (%.2f%%)  wish1=%lld (%.2f%%)  top3(1-3)=%lld (%.2f%%)\n",
           assigned, 100.0 * assigned / n_agents,
           (long long)wish1, 100.0 * wish1 / n_agents,
           (long long)top3, 100.0 * top3 / n_agents);

    free(cap); free(capoff); free(off); free(pp); free(ppri); free(pbar);
    free(pwish); free(psous); free(pinc); free(tie); free(opost); free(owish);
    return 0;
}
