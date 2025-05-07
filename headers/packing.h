#pragma once

#include <stdint.h>

// Default alignment
struct DefaultAlign {
    uint8_t a;
    uint32_t b;
};

// Packed to 1 byte
#pragma pack(push, 1)
struct Packed1 {
    uint8_t a;
    uint32_t b;
};
#pragma pack(pop)

// Packed to 2 bytes
#pragma pack(push, 2)
struct Packed2 {
    uint8_t a;
    uint32_t b;
};
#pragma pack(pop)

// Packed to 4 bytes
#pragma pack(push, 4)
struct Packed4 {
    uint8_t a;
    uint32_t b;
};
#pragma pack(pop)


