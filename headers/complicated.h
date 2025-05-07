#pragma once

#include <string>
#include <vector>
#include <stdint.h>
#include <wchar.h>

typedef int MyInt;
typedef unsigned long MyULong;
typedef float* FloatPtr;

typedef struct {
    int x;
    int y;
} Point;

typedef Point* PointPtr;
typedef Point Points[5];

#pragma pack(push, 1)
struct Packed {
    char c;
    int32_t i;
};
#pragma pack(pop)

enum SimpleEnum {
    One = 1,
    Two = 2
};

enum class ScopedEnum : uint8_t {
    Alpha = 0,
    Beta = 1
};

union MixedUnion {
    int i;
    float f;
    struct {
        char ch;
        int sub;
    };
};

namespace Outer {
    namespace Inner {
        struct Namespaced {
            int inside;
        };
    }
}

namespace {
    struct AnonNamespace {
        double hidden;
    };
}

struct BitfieldStruct {
    unsigned int a : 3;
    signed int b : 5;
    unsigned int : 2; // unnamed padding
    unsigned int c : 8;
};

struct Everything {
    // Basic + fixed-width
    int i;
    float f;
    bool b;
    int32_t i32;
    uint64_t u64;

    // Wide chars
    wchar_t wch;
    char16_t ch16;
    char32_t ch32;

    // Arrays
    int a1[3];
    float a2[2][2];
    double a3[2][2][2];
    char a4[2][2][2][2];

    // Pointers
    int* p_i;
    float** pp_f;
    const char* p_cstr;
    void* p_void;
    std::string* p_str;

    // Function pointer
    int (*callback)(int, float);
    void (*handlers[2])(void);

    // Typedefs
    MyInt my_i;
    MyULong my_ul;
    FloatPtr fp;
    PointPtr pt;
    Points pts;

    // Enums
    SimpleEnum e1;
    ScopedEnum e2;

    // Union
    MixedUnion mix;

    // Namespaced type
    Outer::Inner::Namespaced ns;

    // Bitfield
    BitfieldStruct bits;

    // Static constant (won't appear as variable, but tests inclusion)
    static constexpr int CONST_ID = 42;
};
