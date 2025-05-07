// Simple standalone union
union IntOrFloat {
    int i;
    float f;
};

// Struct with named union
struct Packet {
    int type;
    union Payload {
        int int_val;
        float float_val;
        char bytes[4];
    } data;
};

// Struct with anonymous union
struct Mixed {
    int tag;
    union {
        double d;
        long l;
    };  // anonymous union — members accessible directly
};

// Nested union inside a union
union NestedUnion {
    int id;
    struct {
        char c;
        union {
            int inner_i;
            float inner_f;
        };
    } nested;
};

// Union inside struct, inside another union
union DeepUnion {
    struct {
        int header;
        union {
            int a;
            float b;
        } inner_union;
    } structured;
};
