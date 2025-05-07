struct Pointers
 {
    int* p_int;                    // pointer to int
    float** pp_float;             // pointer to pointer to float
    void* p_void;                 // void pointer
    char* p_char;                 // pointer to char
    const double* p_const_double; // pointer to const double
    int (*func_ptr)(int, float);  // function pointer
    void (*void_func_ptr)();      // function pointer returning void
    int (*arr_func_ptr[3])(char); // array of function pointers
};