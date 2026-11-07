# mxp-optimization, run inside the hpc-lab-mxp container (dev/bin/box make ...): build the app
# with RAPTOR and run each step of the raptorize and optimize stages.
#
#   make [all|check|clean]             app/ (check FULL=1 adds the 15-minute test)
#   make RAPTOR=0 check                without the RAPTOR plugin
#   make run STAGE=<stage> E=<name>    new instance: experiments/<E>/<n>-<stage> (prints R)
#   make evaluate|redteam|status|resume|harvest EXP=<R>
#   make apply EXP=<R> ID=<id>         an accepted candidate over the seed
#   make restore EXP=<R>               the seed back

LLVM_VER           ?= 20
RAPTOR_INSTALL_DIR ?= /opt/raptor-install
RAPTOR_PLUGIN      := $(RAPTOR_INSTALL_DIR)/lib/LLVMRaptor-$(LLVM_VER).so
RAPTOR             ?= $(if $(wildcard $(RAPTOR_PLUGIN)),1,0)
RAPTOR_CXX         := clang++-$(LLVM_VER)
RAPTOR_CXXFLAGS    := -DBUBBLE_RAPTOR=1 -I$(RAPTOR_INSTALL_DIR)/include -include raptor/raptor.h \
                      -fpass-plugin=$(RAPTOR_PLUGIN)
RAPTOR_LDLIBS      := -L$(RAPTOR_INSTALL_DIR)/lib -lRaptor-RT-$(LLVM_VER) -lmpfr -lstdc++

export RAPTOR RAPTOR_CXX RAPTOR_CXXFLAGS RAPTOR_LDLIBS

PY  ?= python3
RUN := $(PY) dev/workflows/optimize/run.py

.PHONY: all check clean debug run evaluate redteam status resume harvest apply restore

all check clean debug:
	@$(MAKE) -C app -j4 $@

run:
	@$(RUN) new $(STAGE) $(E)

evaluate:
	$(PY) $(EXP)/evaluator.py

redteam status resume harvest restore:
	@$(RUN) $@ $(EXP)

apply:
	@$(RUN) apply $(EXP) $(ID)
