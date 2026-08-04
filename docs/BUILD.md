# Build Instructions

## Prerequisites

- Python >= 3.11
- CMake >= 3.20
- C11 compiler (GCC >= 9 or Clang >= 10)
- C++17 compiler
- pytest >= 7.0

## Building HACF R3

```bash
cd native/hacf
mkdir build && cd build
cmake ..
make -j$(nproc)
```

## Building R1 HACF wrapper

```bash
cd native/hacf_bridge
mkdir build && cd build
cmake .. -DHACF_INCLUDE_DIR=../hacf/include -DHACF_LIB_DIR=../hacf/build
make
```

## Running tests

### Grid81 Structural Semantics

```bash
export PYTHONPATH=components/Grid81StructuralSemantics/src:components/Grid81TypedProjectionCompiler/src:components/Grid81StructuralGroupProjectionCompiler/src:components/Grid81DeterministicStructuralAdjudicator/src
pytest components/Grid81StructuralSemantics/tests/ -v
```

### Runtime R0

```bash
export PYTHONPATH=runtime/R0/src:$PYTHONPATH
pytest runtime/R0/tests/ -v
```

### Runtime R1

```bash
export HACF_WRAPPER_LIB=native/hacf_bridge/build/libr1_hacf_wrapper.so
export PYTHONPATH=runtime/R1/src:$PYTHONPATH
pytest runtime/R1/tests/ -v
```

### Full verification

```bash
python tools/verify_public_release.py
```
