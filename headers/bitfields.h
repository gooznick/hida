// Basic bitfield usage
struct StatusFlags {
    unsigned int ready : 1;
    unsigned int error : 1;
    unsigned int reserved : 6;
};

// Bitfields with mixed signedness and widths
struct ControlRegister {
    unsigned mode : 3;
    signed speed : 5;
    unsigned enable : 1;
    unsigned reserved : 23;
};

// Struct with full 32-bit packing
struct Packed32 {
    unsigned a : 8;
    unsigned b : 8;
    unsigned c : 8;
    unsigned d : 8;
};

// Nested bitfields
struct Nested {
    unsigned outer : 4;
    struct {
        unsigned inner1 : 2;
        unsigned inner2 : 6;
    } inner;
};

// Anonymous bitfield struct (fields accessed directly)
struct Flat {
    unsigned top : 4;
    union {
        struct {
            unsigned u1 : 3;
            unsigned u2 : 5;
        };
        unsigned raw : 8;
    };
};
