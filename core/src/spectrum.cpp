#include "spectrum.hpp"

namespace {

// DFS from `cur` toward `target`, tracking which lengths (edge counts) have
// been achieved so far in `achieved`. Stops a branch as soon as every length
// still relevant to the running spectrum intersection (`target_mask`) has
// been found for this pair -- we only need existence, never enumeration.
void dfs(const Graph& g, int cur, int target, uint64_t visited, int length,
         uint64_t& achieved, uint64_t target_mask) {
    if (cur == target) {
        if (length > 0) {
            achieved |= (uint64_t(1) << length);
        }
        return;
    }
    if ((achieved & target_mask) == target_mask) {
        return;
    }
    uint64_t candidates = g.adj[static_cast<size_t>(cur)] & ~visited;
    while (candidates) {
        int next = __builtin_ctzll(candidates);
        candidates &= candidates - 1;
        dfs(g, next, target, visited | (uint64_t(1) << next), length + 1, achieved, target_mask);
        if ((achieved & target_mask) == target_mask) {
            return;
        }
    }
}

}  // namespace

std::set<int> uniform_spectrum(const Graph& g) {
    int n = g.n;
    uint64_t spectrum_mask = 0;
    for (int k = 1; k <= n - 1; k++) {
        spectrum_mask |= (uint64_t(1) << k);
    }

    for (int u = 0; u < n && spectrum_mask != 0; u++) {
        for (int v = u + 1; v < n && spectrum_mask != 0; v++) {
            uint64_t achieved = 0;
            dfs(g, u, v, (uint64_t(1) << u), 0, achieved, spectrum_mask);
            spectrum_mask &= achieved;
        }
    }

    std::set<int> result;
    for (int k = 1; k <= n - 1; k++) {
        if (spectrum_mask & (uint64_t(1) << k)) {
            result.insert(k);
        }
    }
    return result;
}
