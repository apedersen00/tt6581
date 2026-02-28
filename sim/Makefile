ifeq ($(VERILATOR_ROOT),)
  VERILATOR = verilator
  VERILATOR_COVERAGE = verilator_coverage
else
  export VERILATOR_ROOT
  VERILATOR = $(VERILATOR_ROOT)/bin/verilator
  VERILATOR_COVERAGE = $(VERILATOR_ROOT)/bin/verilator_coverage
endif

# Verilator flags
VERILATOR_FLAGS += -cc --exe
VERILATOR_FLAGS += -x-assign fast
VERILATOR_FLAGS += -Wall
# VERILATOR_FLAGS += --trace
VERILATOR_FLAGS += --assert -Wno-EOFNEWLINE

# Simulation targets
TARGETS = mult spi multi_voice envelope svf delta_sigma tt6581 tt6581_player tt6581_bode

# Module source dependencies
SRCS_sine   	= ../src/sine.sv
SRCS_mult   	= ../src/mult.sv
SRCS_spi		= ../src/spi.sv
SRCS_voice		= ../src/voice.sv
SRCS_envelope	= ../src/envelope.sv ../src/mult.sv
SRCS_svf		= ../src/svf.sv ../src/mult.sv
SRCS_delta_sigma = ../src/delta_sigma.sv
SRCS_tt6581		= ../src/tt6581.sv ../src/multi_voice.sv ../src/spi.sv ../src/reg_file.sv ../src/controller.sv ../src/tick_gen.sv ../src/envelope.sv ../src/mult.sv ../src/svf.sv ../src/delta_sigma.sv
SRCS_tt6581_player	= ../src/tt6581.sv ../src/multi_voice.sv ../src/spi.sv ../src/reg_file.sv ../src/controller.sv ../src/tick_gen.sv ../src/envelope.sv ../src/mult.sv ../src/svf.sv ../src/delta_sigma.sv
SRCS_tt6581_bode	= ../src/tt6581.sv ../src/multi_voice.sv ../src/spi.sv ../src/reg_file.sv ../src/controller.sv ../src/tick_gen.sv ../src/envelope.sv ../src/mult.sv ../src/svf.sv ../src/delta_sigma.sv

######################################################################
default: help

core:
	@echo
	@echo "-- VERILATE $@ ----------------"
	$(VERILATOR) $(VERILATOR_FLAGS) --top-module tb_$@ \
		tb/tb_$@.sv cpp/sim_$@.cpp

	@echo
	@echo "-- BUILD $@ -------------------"
	$(MAKE) -j -C obj_dir -f Vtb_$@.mk

	@echo
	@echo "-- RUN $@ ---------------------"
	@rm -rf logs
	@mkdir -p logs
	obj_dir/Vtb_$@ +trace

	@echo
	@echo "-- DONE $@ --------------------"
	@echo "To see waveforms, open logs/tb_$@.vcd in a waveform viewer"
	@echo

$(filter-out core,$(TARGETS)): %:
	@echo
	@echo "-- VERILATE $@ ----------------"
	$(VERILATOR) $(VERILATOR_FLAGS) --top-module tb_$@ \
		$(SRCS_$@) tb/tb_$@.sv cpp/sim_$@.cpp

	@echo
	@echo "-- BUILD $@ -------------------"
	$(MAKE) -j -C obj_dir -f Vtb_$@.mk

	@echo
	@echo "-- RUN $@ ---------------------"
	@rm -rf logs
	@mkdir -p logs
	obj_dir/Vtb_$@ +trace

	@echo
	@echo "-- DONE $@ --------------------"
	@echo "To see waveforms, open logs/tb_$@.vcd in a waveform viewer"
	@echo

	@if [ "$@" = "envelope" ]; then \
		echo; \
		echo "-- PLOT $@ --------------------"; \
		cd scripts && uv run envelope.py; \
	fi

	@if [ "$@" = "svf" ]; then \
		echo; \
		echo "-- PLOT $@ --------------------"; \
		cd scripts && uv run svf.py; \
	fi

	@if [ "$@" = "delta_sigma" ]; then \
		echo; \
		echo "-- PLOT $@ --------------------"; \
		cd scripts && uv run delta_sigma.py; \
	fi

	@if [ "$@" = "tt6581" ]; then \
		echo; \
		echo "-- PLOT $@ --------------------"; \
		cd scripts && uv run bin_to_wav.py; \
	fi

	@if [ "$@" = "tt6581_player" ]; then \
		echo; \
		echo "-- PLOT $@ --------------------"; \
		cd scripts && uv run bin_to_wav.py; \
	fi

	@if [ "$@" = "tt6581_bode" ]; then \
		echo; \
		echo "-- PLOT $@ --------------------"; \
		cd scripts && uv run bode.py; \
	fi

all: $(TARGETS)

help:
	@echo "Available simulation targets:"
	@echo "  help         - Show this help"

clean mostlyclean distclean maintainer-clean::
	-rm -rf obj_dir logs *.log *.dmp *.vpd coverage.dat core
