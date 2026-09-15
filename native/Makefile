# AFFECTA native core build.
#   make            -> shared library (libaffecta.so) + benchmark + verifier
#   make bench      -> run a quick 1M-agent benchmark
#   make verify     -> exhaustive stability check on a small instance
#   make mega       -> build the 100M-scale parallel throughput demonstrator
#   make mega-bench -> run the mega-core on 10M agents with a stability audit
#   make clean

CC      ?= gcc
CFLAGS  ?= -O3 -march=native -funroll-loops -fno-plt -Wall -Wextra -std=c11
LDFLAGS ?=

LIB    := libaffecta.so
BENCH  := affecta_bench
VERIFY := affecta_verify
MEGA   := affecta_mega

.PHONY: all bench verify mega mega-bench clean

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

clean:
	rm -f $(LIB) $(BENCH) $(VERIFY) $(MEGA)
