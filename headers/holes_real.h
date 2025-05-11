// holes_real.h

// Struct with padding between fields
struct Holey {
    char a;     // offset 0
    int b;      // offset 4 (likely 3 bytes of padding)
    short c;    // offset 8 (likely 2 bytes of padding at end)
};

// Struct that needs no padding
struct Packed {
    int x;
    float y;
    double z;
};

// Struct with multiple small holes
struct MultiHoles {
    char a;
    short b;
    char c;
    int d;
};
