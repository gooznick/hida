#include <stdbool.h>
#include <wchar.h>
#include <stdint.h>

struct AllTypes {
    // Character types
    char ch;
    signed char sch;
    unsigned char uch;

    // Wide character types
    wchar_t wch;
    char16_t ch16;
    char32_t ch32;

    // Boolean
    bool b2;

    // Integer types
    short s;
    unsigned short us;
    int i;
    unsigned int ui;
    long l;
    unsigned long ul;
    long long ll;
    unsigned long long ull;

    // Fixed-width integer types
    int8_t i8;
    uint8_t ui8;
    int16_t i16;
    uint16_t ui16;
    int32_t i32;
    uint32_t ui32;
    int64_t i64;
    uint64_t ui64;

    // Floating point types
    float f;
    double d;
    long double ld;

    // Null pointer type (will appear as void*)
    void* ptr;
};
