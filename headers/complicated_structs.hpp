// complicated_structs.hpp

#ifndef COMPLICATED_STRUCTS_HPP
#define COMPLICATED_STRUCTS_HPP

#include <cstdint>
#include <cstddef>

namespace OuterNamespace {

    enum class Color : uint16_t {
        Red = 1,
        Green,
        Blue = 255
    };

    typedef int32_t CustomInt;

    namespace InnerNamespace {

        enum SimpleEnum {
            First,
            Second = 100,
            Third
        };

        #pragma pack(push, 1)
        struct PackedStruct {
            CustomInt id;
            char flags : 3;
            bool is_valid : 1;
            uint8_t reserved : 4;

            union {
                float value;
                uint32_t raw_value;
            };

            struct {
                double x;
                double y;
            } coordinates;
        };
        #pragma pack(pop)

        typedef PackedStruct PS;

        class ComplexClass {
        public:
            enum NestedEnum : uint8_t {
                Alpha,
                Beta,
                Gamma
            };

            typedef void(*Callback)(int, const char*);

            struct NestedStruct {
                Callback cb;
                NestedEnum status;
                void* context;
            };

            union DataUnion {
                int32_t int_data;
                struct {
                    uint16_t a;
                    uint16_t b;
                } split_data;
            };

            PS packed_data;
            NestedStruct nested;
            DataUnion data_union;

            uint64_t ids[5];
            uint64_t array2[5][2];
            uint64_t array3[5][2][7];
            uint64_t array4[5][2][1][3];
            const char* name;

            struct {
                bool enabled;
                uint8_t priority : 4;
                uint8_t type : 4;
            } flags;
        };

    } // namespace InnerNamespace

    struct Container {
        InnerNamespace::ComplexClass complex;
        Color container_color;

        union {
            uint8_t bytes[8];
            uint64_t value;
        } id_union;

        struct {
            int x;
            int y;
            int z;
        } position;

        bool (*comparator)(const Container&, const Container&);
    };

    typedef Container ContainerAlias;

} // namespace OuterNamespace

static const int INT_CONST = 42;
static const char CHAR_CONST = 'A';
static const float FLOAT_CONST = 3.14f;
static const double DOUBLE_CONST = 2.718281828459045;
static const char* STRING_CONST = "Hello, World!";

#endif // COMPLICATED_STRUCTS_HPP