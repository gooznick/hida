// bitfield_holes.h
struct Holey {
    unsigned int a : 3;
    unsigned int b : 5;
    unsigned int c : 1;  // leaves 23 bits unused in 32-bit slot
};

struct Packed {
    unsigned int x : 2;
    unsigned int y : 6;
};
