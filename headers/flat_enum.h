#pragma once
#include <stdint.h>

namespace demo {

enum class Color : uint8_t {
    Red   = 1,
    Green = 2
};

typedef Color ColorAlias;

struct UsesColor {
    Color      c1;
    ColorAlias c2;
    uint8_t    n;
};

} // namespace demo
