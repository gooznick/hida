#pragma once
#include <stdint.h>

namespace demo {

struct Inner {
    uint8_t  a;
    uint16_t b;
};

struct Wrapper {
    uint32_t x;
    Inner    inner;
    uint8_t  y;
};

// Optional: shows that arrays of composites remain as-is
// unless you enable flatten_arrays=True in your manipulator.
struct WrapperArr {
    Inner items[2];
};

} // namespace demo
