#include "graph6.hpp"

#include <stdexcept>

Graph parse_graph6(const std::string& s) {
    if (s.empty()) {
        throw std::invalid_argument("empty graph6 string");
    }
    if (s[0] == '~') {
        throw std::invalid_argument("graph6 strings with n > 62 are not supported");
    }

    int n = static_cast<int>(static_cast<unsigned char>(s[0])) - 63;
    if (n < 0 || n > 62) {
        throw std::invalid_argument("invalid graph6 header byte");
    }

    Graph g(n);

    size_t byte_index = 1;
    int bits_left_in_byte = 0;
    uint8_t current_byte = 0;

    auto next_bit = [&]() -> int {
        if (bits_left_in_byte == 0) {
            if (byte_index >= s.size()) {
                throw std::invalid_argument("graph6 string truncated");
            }
            int raw = static_cast<int>(static_cast<unsigned char>(s[byte_index++])) - 63;
            if (raw < 0 || raw > 63) {
                throw std::invalid_argument("invalid graph6 data byte");
            }
            current_byte = static_cast<uint8_t>(raw);
            bits_left_in_byte = 6;
        }
        bits_left_in_byte--;
        return (current_byte >> bits_left_in_byte) & 1;
    };

    for (int x = 1; x < n; x++) {
        for (int y = 0; y < x; y++) {
            if (next_bit()) {
                g.add_edge(x, y);
            }
        }
    }

    return g;
}
