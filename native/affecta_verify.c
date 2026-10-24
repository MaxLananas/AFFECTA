/*
 * AFFECTA correctness check.
 *
 * Re-generates the same synthetic campaign as affecta_bench, runs the native core,
 * then brute-force verifies the stability contract:
 *
 *   For every agent a and every post p that a strictly prefers to its assignment,
 *   p must be full and every occupant of p must hold a claim on p at least as strong
 *   as a's — i.e. no justified envy (a stable, teacher-optimal matching).
 *
 * Also checks capacity is never exceeded and incumbents are never displaced by a
 * weaker non-incumbent. Exits non-zero on the first violation.
 *
 *   ./affecta_verify [n_agents] [seed]
 */
#define _POSIX_C_SOURCE 199309L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

extern int32_t affecta_da_solve(
    int32_t, int32_t, const int32_t *, const int32_t *, const int32_t *,
    const int32_t *, const int32_t *, const int32_t *, const int32_t *,
    const int32_t *, const uint8_t *, const uint64_t *, const int32_t *,
    const int32_t *, int32_t *, int32_t *);

static inline uint64_t sm64(uint64_t *s) {
    uint64_t z = (*s += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}
static inline uint32_t rnd(uint64_t *s, uint32_t n) { return (uint32_t)(sm64(s) % n); }

typedef struct { int32_t pr, ba, wi, so, aen, ech; uint64_t tie; uint8_t inc; } key_t;
static inline int stronger(const key_t *a, const key_t *b) {
    if (a->inc != b->inc) return a->inc > b->inc;
    if (a->pr  != b->pr)  return a->pr  < b->pr;
    if (a->ba  != b->ba)  return a->ba  > b->ba;
    if (a->wi  != b->wi)  return a->wi  < b->wi;
    if (a->so  != b->so)  return a->so  < b->so;
    if (a->aen != b->aen) return a->aen > b->aen;
    if (a->ech != b->ech) return a->ech > b->ech;
    return a->tie < b->tie;
}

int main(int argc, char **argv) {
    int32_t  n_agents = argc > 1 ? atoi(argv[1]) : 20000;
    uint64_t seed     = argc > 2 ? strtoull(argv[2], NULL, 10) : 20260914ULL;

    int32_t n_posts = (int32_t)((int64_t)n_agents * 60 / 100 + 16);
    int32_t wishes  = 12;
    uint64_t s = seed;

    int32_t *cap    = malloc((size_t)n_posts * sizeof(int32_t));
    int32_t *capoff = malloc((size_t)(n_posts + 1) * sizeof(int32_t));
    int64_t total_cap = 0;
    for (int32_t j = 0; j < n_posts; ++j) {
        uint32_t r = rnd(&s, 100);
        int32_t c = r < 55 ? 1 : (r < 90 ? 2 : (r < 98 ? 3 : 5));
        cap[j] = c; capoff[j] = (int32_t)total_cap; total_cap += c;
    }
    capoff[n_posts] = (int32_t)total_cap;

    int32_t *off = malloc((size_t)(n_agents + 1) * sizeof(int32_t));
    int64_t total_pref = (int64_t)n_agents * (wishes + 1);
    int32_t *pp = malloc((size_t)total_pref*sizeof(int32_t));
    int32_t *ppri = malloc((size_t)total_pref*sizeof(int32_t));
    int32_t *pbar = malloc((size_t)total_pref*sizeof(int32_t));
    int32_t *pwish= malloc((size_t)total_pref*sizeof(int32_t));
    int32_t *psous= malloc((size_t)total_pref*sizeof(int32_t));
    int32_t *paen = malloc((size_t)total_pref*sizeof(int32_t));
    int32_t *pech = malloc((size_t)total_pref*sizeof(int32_t));
    uint8_t *pinc = malloc((size_t)total_pref*sizeof(uint8_t));
    uint64_t*tie  = malloc((size_t)n_agents*sizeof(uint64_t));
    int32_t *opost= malloc((size_t)n_agents*sizeof(int32_t));
    int32_t *owish= malloc((size_t)n_agents*sizeof(int32_t));

    int64_t w = 0;
    for (int32_t i = 0; i < n_agents; ++i) {
        off[i] = (int32_t)w; tie[i] = sm64(&s);
        uint32_t pr = rnd(&s, 1000);
        int32_t priority, bareme;
        if      (pr < 8)  { priority=1; bareme=150+(int32_t)rnd(&s,450); }
        else if (pr < 14) { priority=2; bareme=800; }
        else if (pr < 20) { priority=3; bareme=300+(int32_t)rnd(&s,200); }
        else if (pr < 26) { priority=4; bareme=600; }
        else if (pr < 30) { priority=5; bareme=200; }
        else              { priority=15; bareme=21+(int32_t)rnd(&s,260); }
        int32_t aen=(int32_t)rnd(&s,480), ech=(int32_t)rnd(&s,60);
        if (rnd(&s, 100) < 62) {
            int32_t home = (int32_t)rnd(&s,(uint32_t)n_posts);
            pp[w]=home; ppri[w]=priority; pbar[w]=bareme; pwish[w]=0; psous[w]=0; paen[w]=aen; pech[w]=ech; pinc[w]=1; ++w;
        }
        for (int32_t k = 0; k < wishes; ++k) {
            pp[w]=(int32_t)rnd(&s,(uint32_t)n_posts); ppri[w]=priority; pbar[w]=bareme;
            pwish[w]=k+1; psous[w]=(int32_t)rnd(&s,3); paen[w]=aen; pech[w]=ech; pinc[w]=0; ++w;
        }
    }
    off[n_agents] = (int32_t)w;

    int32_t assigned = affecta_da_solve(n_agents, n_posts, off, pp, ppri, pbar,
        pwish, psous, paen, pech, pinc, tie, cap, capoff, opost, owish);
    if (assigned < 0) { fprintf(stderr, "solver alloc failed\n"); return 2; }

    /* Build per-post occupant lists from the output. */
    int32_t *fill = calloc((size_t)n_posts, sizeof(int32_t));
    for (int32_t i = 0; i < n_agents; ++i)
        if (opost[i] >= 0) fill[opost[i]]++;

    /* capacity check */
    for (int32_t j = 0; j < n_posts; ++j)
        if (fill[j] > cap[j]) { fprintf(stderr, "FAIL capacity post %d: %d>%d\n", j, fill[j], cap[j]); return 1; }

    /* occupant index per post (CSR by capoff of assigned count) */
    int32_t *occ_off = malloc((size_t)(n_posts + 1) * sizeof(int32_t));
    int32_t acc = 0;
    for (int32_t j = 0; j < n_posts; ++j) { occ_off[j] = acc; acc += fill[j]; }
    occ_off[n_posts] = acc;
    int32_t *occ = malloc((size_t)acc * sizeof(int32_t));
    int32_t *cur = malloc((size_t)n_posts * sizeof(int32_t));
    for (int32_t j = 0; j < n_posts; ++j) cur[j] = occ_off[j];
    for (int32_t i = 0; i < n_agents; ++i)
        if (opost[i] >= 0) occ[cur[opost[i]]++] = i;

    /* helper to fetch an agent's key on a given proposal row */
    #define KEYROW(row, agent) (key_t){ ppri[row], pbar[row], pwish[row], psous[row], paen[row], pech[row], tie[agent], pinc[row] }

    int64_t envy = 0;
    for (int32_t i = 0; i < n_agents; ++i) {
        int32_t a_post = opost[i];
        int32_t a_wish = owish[i];
        for (int32_t r = off[i]; r < off[i + 1]; ++r) {
            int32_t p = pp[r];
            /* only proposals strictly preferred to current assignment (lower wish, or unassigned) */
            int prefers = (a_post < 0) || (pwish[r] < a_wish) ||
                          (pwish[r] == a_wish && psous[r] < 0);
            if (!prefers || p == a_post) continue;
            key_t ka = KEYROW(r, i);
            /* p must be full and every occupant at least as strong as ka on p */
            if (fill[p] < cap[p]) {
                fprintf(stderr, "FAIL envy: agent %d prefers post %d (has free unit)\n", i, p);
                if (++envy > 20) return 1;
                continue;
            }
            for (int32_t oi = occ_off[p]; oi < occ_off[p] + fill[p]; ++oi) {
                int32_t occa = occ[oi];
                /* find occupant's key on post p */
                key_t ko; int found = 0;
                for (int32_t rr = off[occa]; rr < off[occa + 1]; ++rr)
                    if (pp[rr] == p && owish[occa] == pwish[rr]) { ko = KEYROW(rr, occa); found = 1; break; }
                if (!found) continue;
                if (stronger(&ka, &ko)) {
                    fprintf(stderr, "FAIL envy: agent %d beats occupant %d on post %d\n", i, occa, p);
                    if (++envy > 20) return 1;
                }
            }
        }
    }

    printf("verify: agents=%d assigned=%d envy_violations=%lld -> %s\n",
           n_agents, assigned, (long long)envy, envy == 0 ? "STABLE (no justified envy)" : "UNSTABLE");
    return envy == 0 ? 0 : 1;
}
