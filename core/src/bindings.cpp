#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <utility>
#include <vector>

#include "graph.hpp"
#include "graph6.hpp"

namespace py = pybind11;

namespace {

std::vector<std::pair<int, int>> parse_graph6_edges(const std::string& g6) {
    Graph g = parse_graph6(g6);
    std::vector<std::pair<int, int>> edges;
    for (int u = 0; u < g.n; u++) {
        uint64_t above_u = ~((uint64_t(1) << (u + 1)) - 1);
        uint64_t neighbors = g.adj[static_cast<size_t>(u)] & above_u;
        while (neighbors) {
            int v = __builtin_ctzll(neighbors);
            neighbors &= neighbors - 1;
            edges.emplace_back(u, v);
        }
    }
    return edges;
}

}  // namespace

PYBIND11_MODULE(uniform_spectrum_core, m) {
    m.def("parse_graph6_edges", &parse_graph6_edges,
          "Parse a graph6 string and return its edges as (u, v) pairs with u < v");
}
