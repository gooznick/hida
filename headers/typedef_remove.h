// typedefs_remove.h

typedef int MyInt;
typedef MyInt Alias1;
typedef Alias1 Alias2;

typedef float MyArray[4];
typedef MyArray MyArray2D[3];

struct A {
    Alias2 value;
    MyArray arr1;
    MyArray2D arr2;
};
