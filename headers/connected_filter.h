// connected_filter.h

typedef int MyInt;

struct Unused {
    double ignored;
};

struct Nested {
    MyInt value;
};

struct Wrapper {
    Nested nested;
};

union Payload {
    Wrapper wrapper;
    float fallback;
};

enum Status {
    OK = 0,
    ERROR = 1
};

struct Main {
    Payload payload;
    Status status;
};
