#pragma once

// Standard library headers
#include <iostream>
#include <vector>
#include <string>
#include <map>
#include <set>
#include <array>
#include <memory>
#include <chrono>
#include <thread>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <limits>
#include <type_traits>
#include <functional>
#include <atomic>

// C headers (through C++ interface)
#include <cstdio>
#include <cstdlib>
#include <cstddef>
#include <cassert>
#include <climits>
#include <cfloat>

// Linux-specific headers (only if compiling on Linux)
#ifdef __linux__
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <pthread.h>
#include <errno.h>
#endif

// Windows-specific (just to show how you might guard)
#ifdef _WIN32
#include <windows.h>
#include <processthreadsapi.h>
#endif

// Final test struct
struct TestStruct {
    int id;
};
