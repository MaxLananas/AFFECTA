#ifndef AFFECTA_CORE_H
#define AFFECTA_CORE_H
#include <stdint.h>

/*
 * Teacher-proposing deferred acceptance over a CSR proposal layout.
 * See affecta_core.c for the full contract. Returns the number of assigned
 * agents, or -1 on allocation failure.
 */
int32_t affecta_da_solve(
    int32_t        n_agents,
    int32_t        n_posts,
    const int32_t *off,            /* n_agents + 1  (CSR offsets)              */
    const int32_t *pref_post,      /* proposal -> target post index           */
    const int32_t *pref_priority,  /* proposal -> priority (lower better)      */
    const int32_t *pref_bareme,    /* proposal -> barème (higher better)       */
    const int32_t *pref_wish,      /* proposal -> wish rank (lower better)     */
    const int32_t *pref_sous,      /* proposal -> sub-rank (lower better)      */
    const uint8_t *pref_incumbent, /* proposal -> 1 if agent's current post    */
    const uint64_t*agent_tie,      /* n_agents -> deterministic tie-break      */
    const int32_t *post_capacity,  /* n_posts                                  */
    const int32_t *cap_offset,     /* n_posts + 1 (prefix sum of capacity)     */
    int32_t       *out_post,       /* n_agents -> assigned post, or -1         */
    int32_t       *out_wish);      /* n_agents -> winning wish rank, or -1     */

#endif /* AFFECTA_CORE_H */
