# rd2d: mixed Fortran/C++ build. Sources in src/ are discovered, Fortran in module order.
CXX      := g++
FC       := gfortran
CXXFLAGS := -O2 -std=c++17 -Wall -Wextra -Iinclude -Isrc
FFLAGS   := -O2 -Wall -Jbuild
LDLIBS   := -lgfortran -lm

F90 := $(shell python3 ../dev/tools/index.py order)
CPP := $(sort $(wildcard src/*.cpp))
F90_OBJ := $(patsubst src/%.F90,build/%.o,$(F90))
CPP_OBJ := $(patsubst src/%.cpp,build/%.o,$(CPP))

.PHONY: all run clean
all: rd2d

build:
	@mkdir -p build

build/fortran.stamp: $(F90) | build
	@for f in $(F90); do echo "$(FC) -c $$f"; $(FC) $(FFLAGS) -c $$f -o build/$$(basename $$f .F90).o || exit 1; done
	@touch $@

build/%.o: src/%.cpp $(wildcard src/*.hpp include/*.hpp) | build
	$(CXX) $(CXXFLAGS) -c $< -o $@

rd2d: build/fortran.stamp $(CPP_OBJ)
	$(CXX) $(F90_OBJ) $(CPP_OBJ) -o $@ $(LDLIBS)

run: rd2d
	./rd2d

clean:
	rm -rf build rd2d *.mod
