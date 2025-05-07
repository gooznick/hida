typedef int MyInt;
typedef unsigned long MyULong;
typedef float* FloatPtr;
typedef void (*FuncPtr)(int, float);

typedef struct {
    int x;
    int y;
} Point;

typedef Point* PointPtr;

typedef struct {
    Point center;
    float radius;
} Circle;

typedef Circle Shapes[10];

typedef Shapes* ShapesPtr;

typedef struct {
    ShapesPtr shape_array;
    FuncPtr callback;
} ComplexStruct;

// Nested typedef through chain
typedef MyInt Alias1;
typedef Alias1 Alias2;
typedef Alias2 Alias3;

typedef int IntArray1D[5];
typedef int IntArray2D[3][4];
typedef int IntArray3D[2][3][4];

// Nested array typedefs
typedef IntArray1D Alias1D;
typedef IntArray2D Alias2D;
typedef IntArray3D Alias3D;
