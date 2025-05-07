#include <stdint.h>

// Simple C-style enum
enum Color {
    Red,
    Green,
    Blue = 5,
    Yellow
};

// Scoped enum with default int base type
enum class Direction {
    North,
    South,
    East,
    West
};

// C++11 enum with explicit underlying type
enum class StatusCode : uint8_t {
    OK = 0,
    Error = 1,
    Timeout = 2,
    Unknown = 255
};

// Unscoped enum with explicit base
enum ErrorLevel : int16_t {
    Info = 1,
    Warning = 2,
    Critical = 3
};

// Anonymous enum
enum {
    FLAG_READ = 1,
    FLAG_WRITE = 2,
    FLAG_EXEC = 4
};
