#include <cstdint>  // for std::int32_t, std::uint64_t
#include <stdint.h> // for plain int32_t, uint64_t

struct A {
    std::int8_t   a1;
    std::int16_t  a2;
    std::int32_t  a3;
    std::int64_t  a4;
    std::uint8_t  a5;
    std::uint16_t a6;
    std::uint32_t a7;
    std::uint64_t a8;
};

struct B {
    int8_t   b1;
    int16_t  b2;
    int32_t  b3;
    int64_t  b4;
    uint8_t  b5;
    uint16_t b6;
    uint32_t b7;
    uint64_t b8;
};

struct C {
    std::int32_t arr1[4];
    uint64_t     arr2[2][3];
};

struct D {
    std::uint16_t d1[5][6];
    int8_t        d2[0];
};
