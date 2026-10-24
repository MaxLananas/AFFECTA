# AFFECTA native core build.
#   make            -> shared library (libaffecta.so) + benchmark + verifier
#   make bench      -> run a quick 1M-agent benchmark
#   make verify     -> exhaustive stability check on a small instance
#   make mega       -> build the 100M-scale parallel throughput demonstrator
#   make mega-bench -> run the mega-core on 10M agents with a stability audit
#   make sanitize   -> build+run everything under ASan+UBSan (memory/UB safety)
#   make tsan       -> run the parallel mega-core under ThreadSanitizer (race safety)
#   make clean

CC      ?= gcc
CFLAGS  ?= -O3 -march=native -funroll-loops -fno-plt -Wall -Wextra -std=c11
LDFLAGS ?=

# Sanitizer flags: address + undefined-behaviour, no optimisation, frame pointers kept.
SANFLAGS  := -O1 -g -std=c11 -fno-omit-frame-pointer -fsanitize=address,undefined
TSANFLAGS := -O1 -g -std=c11 -pthread -fsanitize=thread

LIB    := libaffecta.so
BENCH  := affecta_bench
VERIFY := affecta_verify
MEGA   := affecta_mega

.PHONY: all bench verify mega mega-bench sanitize tsan clean

all: $(LIB) $(BENCH) $(VERIFY)

$(LIB): affecta_core.c affecta_core.h
	$(CC) $(CFLAGS) -fPIC -shared -o $@ affecta_core.c

$(BENCH): affecta_bench.c affecta_core.c affecta_core.h
	$(CC) $(CFLAGS) -o $@ affecta_bench.c affecta_core.c $(LDFLAGS)

$(VERIFY): affecta_verify.c affecta_core.c affecta_core.h
	$(CC) $(CFLAGS) -o $@ affecta_verify.c affecta_core.c $(LDFLAGS)

bench: $(BENCH)
	./$(BENCH) 1000000

verify: $(VERIFY)
	./$(VERIFY) 20000

# The mega-core is a self-contained pthreads program (no dependency on affecta_core.c);
# it needs -pthread and does not use the -Wall/-Wextra strictness of the library build.
$(MEGA): affecta_mega.c
	$(CC) -O3 -march=native -funroll-loops -std=c11 -pthread -o $@ affecta_mega.c

mega: $(MEGA)

mega-bench: $(MEGA)
	./$(MEGA) 10000000 42 $(shell nproc) verify

# Memory- and UB-safety gate. Builds the verifier and the mega-core with ASan+UBSan and
# runs them across small AND degenerate sizes; any out-of-bounds access, use of
# uninitialised memory, or undefined behaviour aborts the run. LeakSanitizer is disabled
# for the throwaway test harnesses (their main() allocations live until process exit).
sanitize:
	$(CC) $(SANFLAGS) -o /tmp/affecta_verify_san affecta_verify.c affecta_core.c
	$(CC) $(SANFLAGS) -pthread -o /tmp/affecta_mega_san affecta_mega.c
	@echo "== verifier (core) under ASan+UBSan =="
	@for n in 1 2 1000 50000; do ASAN_OPTIONS=detect_leaks=0 /tmp/affecta_verify_san $$n; done
	@echo "== mega-core under ASan+UBSan (incl. degenerate sizes) =="
	@for a in "0 1 1" "1 1 1" "3 42 4" "1000 1 8" "50000 9 2"; do \
	    ASAN_OPTIONS=detect_leaks=0 /tmp/affecta_mega_san $$a verify | grep -E "assigned|stability"; done
	@echo "OK: no memory or UB errors"

# Data-race gate for the lock-free parallel mega-core.
tsan:
	$(CC) $(TSANFLAGS) -o /tmp/affecta_mega_tsan affecta_mega.c
	TSAN_OPTIONS=halt_on_error=1 /tmp/affecta_mega_tsan 20000 7 4 verify | grep -E "assigned|stability"
	@echo "OK: no data races"

clean:
	rm -f $(LIB) $(BENCH) $(VERIFY) $(MEGA)
