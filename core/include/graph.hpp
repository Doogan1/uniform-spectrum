#pragma once

#include <cstdint>
#include <vector>

struct Graph {
    int n;
    std::vector<uint64_t> adj;

    explicit Graph(int n_) : n(n_), adj(static_cast<size_t>(n_), 0) {}

    void add_edge(int u, int v) {
        adj[static_cast<size_t>(u)] |= (uint64_t(1) << v);
        adj[static_cast<size_t>(v)] |= (uint64_t(1) << u);
    }
};
