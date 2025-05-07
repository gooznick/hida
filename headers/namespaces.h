#pragma once

namespace TopLevel {
    struct A {
        int x;
    };
}

namespace Outer {
    namespace Inner {
        struct B {
            float y;
        };
    }
}

namespace {
    struct C {
        double z;
    };
}

// This one is global and will refer to all types for usability
struct AllNamespaces {
    TopLevel::A a;
    Outer::Inner::B b;
    C c;
};
