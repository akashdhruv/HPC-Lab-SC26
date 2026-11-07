# Deforming Bubble mini-app: build and tests.  Run through the root Makefile
# (`make`, `make check`) or here; paths are relative to app/.
#
#   src/*.cpp          -> ./bubble
#   tests/test_*.cpp   -> build/test_*, run by `make check`
#
# No -ffast-math (breaks the 1e-12 reproducibility tolerance).

CXX      := mpicxx
# OMPI_SKIP_MPICXX: only the C API is used; the deprecated C++ bindings
# trip -Werror (cast-function-type) with newer compilers.
CXXFLAGS := -std=c++17 -O2 -g -Wall -Wextra -Werror -MMD -MP -DOMPI_SKIP_MPICXX
LDFLAGS  :=
LDLIBS   := -lm

BIN      := bubble
SRCDIR   := src
OBJDIR   := build
TESTDIR  := tests

SRCS     := $(sort $(wildcard $(SRCDIR)/*.cpp))
OBJS     := $(patsubst $(SRCDIR)/%.cpp,$(OBJDIR)/%.o,$(SRCS))
# everything except main.o, so tests can link the library part
LIBOBJS  := $(filter-out $(OBJDIR)/main.o,$(OBJS))

TESTSRCS := $(sort $(wildcard $(TESTDIR)/test_*.cpp))
TESTBINS := $(patsubst $(TESTDIR)/%.cpp,$(OBJDIR)/%,$(TESTSRCS))

DEPS     := $(OBJS:.o=.d) $(TESTBINS:=.d)

.PHONY: all clean check debug tests

all: $(BIN)

$(BIN): $(OBJS)
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $^ $(LDLIBS)

$(OBJDIR)/%.o: $(SRCDIR)/%.cpp | $(OBJDIR)
	$(CXX) $(CXXFLAGS) -I$(SRCDIR) -c -o $@ $<

$(OBJDIR)/%: $(TESTDIR)/%.cpp $(LIBOBJS) | $(OBJDIR)
	$(CXX) $(CXXFLAGS) -I$(SRCDIR) $(LDFLAGS) -o $@ $< $(LIBOBJS) $(LDLIBS)

$(OBJDIR):
	mkdir -p $(OBJDIR)

tests: $(TESTBINS)

# Each test binary is an MPI program. Ranks it should run on are declared by the
# test itself through a `// ranks: ...` comment on its first lines; default 1.
# test_conservation takes ~15 minutes: only with FULL=1
CHECKS := $(if $(FULL),$(TESTBINS),$(filter-out $(OBJDIR)/test_conservation,$(TESTBINS)))

check: $(BIN) $(CHECKS)
	@sh tests/run_tests.sh "$(OBJDIR)" $(CHECKS)

debug:
	$(MAKE) clean
	$(MAKE) CXXFLAGS="-std=c++17 -O1 -g -Wall -Wextra -Werror -MMD -MP -DOMPI_SKIP_MPICXX -fsanitize=address,undefined" \
	        LDFLAGS="-fsanitize=address,undefined" all tests

clean:
	rm -rf $(OBJDIR) $(BIN)

-include $(DEPS)
