# AFFECTA native core build.
#   make            -> shared library (libaffecta.so) + benchmark binary
#   make bench      -> run a quick 1M-agent benchmark
#   make clean

CC      ?= gcc
CFLAGS  ?= -O3 -march=native -funroll-loops -fno-plt -Wall -Wextra -std=c11
LDFLAGS ?=

LIB    := libaffecta.so
BENCH  := affecta_bench
VERIFY := affecta_verify

.PHONY: all bench verify clean

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

clean:
	rm -f $(LIB) $(BENCH) $(VERIFY)
