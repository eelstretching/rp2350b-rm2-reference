// PSRAM bring-up test: checks that the SDK brought the PSRAM up, tests every byte of it,
// measures throughput and exercises the psram_alloc heap. Reports on USB/UART stdio and
// repeats the verdict every few seconds for terminals that connect late.
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hardware/psram.h"
#include "hardware/regs/addressmap.h"
#include "hardware/xip_cache.h"
#include "psram_alloc.h"

#if LIB_PICO_STDIO_USB
#include "pico/stdio_usb.h"
#endif

// The PSRAM (QMI chip select 1) through the XIP cache, and the uncached alias of the same
// memory. The memory tests write and check through the uncached alias, so they see the chip
// rather than the cache.
#define PSRAM_ADDR 0x11000000u
#define PSRAM_CACHED ((volatile uint32_t *)(XIP_BASE + 0x01000000u))
#define PSRAM_UNCACHED ((volatile uint32_t *)(XIP_NOCACHE_NOALLOC_BASE + 0x01000000u))

static uint32_t errors;

static void report(const char *test, uint32_t word, uint32_t expected, uint32_t got) {
    if (errors++ < 10) {
        printf("  %s: at 0x%08" PRIx32 " expected 0x%08" PRIx32 ", read 0x%08" PRIx32 "\n",
               test, PSRAM_ADDR + 4 * word, expected, got);
    }
}

static uint32_t xorshift32(uint32_t *s) {
    uint32_t x = *s;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    return *s = x;
}

// Walking ones and zeros on one word: finds stuck or shorted data lines (SIO0-3 on a QSPI bus
// show up as stuck bit groups).
static void data_bus_test(void) {
    volatile uint32_t *p = PSRAM_UNCACHED;
    for (int bit = 0; bit < 32; bit++) {
        uint32_t ones = 1u << bit, zeros = ~ones;
        p[0] = ones;
        if (p[0] != ones) report("data bus (walking 1)", 0, ones, p[0]);
        p[0] = zeros;
        if (p[0] != zeros) report("data bus (walking 0)", 0, zeros, p[0]);
    }
}

// One word at each power-of-two offset: finds address bits that are stuck, shorted or not
// decoded, which would make parts of the chip alias each other (or the size wrong).
static void address_bus_test(uint32_t words) {
    volatile uint32_t *p = PSRAM_UNCACHED;
    const uint32_t a = 0xaaaaaaaau, b = 0x55555555u;
    for (uint32_t off = 1; off < words; off <<= 1) p[off] = a;
    p[0] = b;
    for (uint32_t off = 1; off < words; off <<= 1) {
        if (p[off] != a) report("address bus (stuck high)", off, a, p[off]);
    }
    p[0] = a;
    for (uint32_t test = 1; test < words; test <<= 1) {
        p[test] = b;
        if (p[0] != a) report("address bus (aliases 0)", 0, a, p[0]);
        for (uint32_t off = 1; off < words; off <<= 1) {
            if (off != test && p[off] != a) report("address bus (aliases)", off, a, p[off]);
        }
        p[test] = a;
    }
}

// Fill all of the PSRAM and read it back through the uncached alias. With via_cache set the
// fill goes through the XIP cache and is written back with xip_cache_clean_all() first, which
// checks the cache's write-back path as well.
static void fill_test(const char *name, uint32_t words, uint32_t seed, bool via_cache) {
    uint32_t before = errors;
    absolute_time_t t0 = get_absolute_time();
    uint32_t s = seed;
    volatile uint32_t *w = via_cache ? PSRAM_CACHED : PSRAM_UNCACHED;
    for (uint32_t i = 0; i < words; i++) w[i] = xorshift32(&s);
    if (via_cache) xip_cache_clean_all();
    int64_t t_write = absolute_time_diff_us(t0, get_absolute_time());

    s = seed;
    volatile uint32_t *r = PSRAM_UNCACHED;
    for (uint32_t i = 0; i < words; i++) {
        uint32_t expected = xorshift32(&s), got = r[i];
        if (got != expected) report(name, i, expected, got);
    }
    int64_t t_total = absolute_time_diff_us(t0, get_absolute_time());
    printf("  %-28s %s  (fill %lld ms, check %lld ms)\n", name, errors == before ? "ok  " : "FAIL",
           t_write / 1000, (t_total - t_write) / 1000);
}

static void throughput(void) {
    static uint32_t sram_buf[16 * 1024];  // 64 kB in on-chip SRAM
    const uint32_t bytes = 1024 * 1024;
    uint32_t *psram = (uint32_t *)PSRAM_CACHED;

    absolute_time_t t0 = get_absolute_time();
    memset(psram, 0x5a, bytes);
    xip_cache_clean_all();
    int64_t us = absolute_time_diff_us(t0, get_absolute_time());
    printf("  write (memset 1 MB, cached)   %5.1f MB/s\n", bytes / (double)us);

    static volatile uint32_t __unused sink;  // keeps the read loop from being optimised away
    t0 = get_absolute_time();
    uint32_t sum = 0;
    for (uint32_t i = 0; i < bytes / 4; i++) sum += psram[i];
    sink = sum;
    us = absolute_time_diff_us(t0, get_absolute_time());
    printf("  read  (sum 1 MB, cached)      %5.1f MB/s\n", bytes / (double)us);

    t0 = get_absolute_time();
    for (uint32_t off = 0; off < bytes; off += sizeof(sram_buf)) {
        memcpy(sram_buf, (const uint8_t *)psram + off, sizeof(sram_buf));
        __compiler_memory_barrier();  // each copy overwrites the last: keep them all
    }
    us = absolute_time_diff_us(t0, get_absolute_time());
    printf("  copy  (PSRAM -> SRAM, 1 MB)   %5.1f MB/s\n", bytes / (double)us);

    t0 = get_absolute_time();
    for (uint32_t off = 0; off < bytes; off += sizeof(sram_buf)) {
        memcpy((uint8_t *)psram + off, sram_buf, sizeof(sram_buf));
        __compiler_memory_barrier();
    }
    xip_cache_clean_all();
    us = absolute_time_diff_us(t0, get_absolute_time());
    printf("  copy  (SRAM -> PSRAM, 1 MB)   %5.1f MB/s\n", bytes / (double)us);
}

static void fill_block(uint8_t *p, size_t n, uint32_t tag) {
    for (size_t k = 0; k < n; k++) p[k] = (uint8_t)(tag * 31u + k * 7u);
}

static bool check_block(const uint8_t *p, size_t n, uint32_t tag) {
    for (size_t k = 0; k < n; k++) {
        if (p[k] != (uint8_t)(tag * 31u + k * 7u)) return false;
    }
    return true;
}

static void heap_fail(const char *what) {
    errors++;
    printf("  heap: %s\n", what);
}

static void heap_test(void) {
    if (!psram_heap_init()) {
        heap_fail("psram_heap_init failed");
        return;
    }
    psram_heap_stats_t s0, s;
    psram_heap_stats(&s0);
    printf("  heap: %u bytes, largest free block %u\n", (unsigned)s0.total, (unsigned)s0.largest_free);

    enum { N = 64 };
    uint8_t *blk[N];
    size_t len[N];
    uint32_t rng = 12345;

    uint8_t *big = psram_malloc(4u * 1024 * 1024);
    if (!big) {
        heap_fail("4 MB allocation failed");
        return;
    }
    fill_block(big, 4u * 1024 * 1024, 999);

    for (int i = 0; i < N; i++) {
        len[i] = 1 + xorshift32(&rng) % (64 * 1024);
        blk[i] = psram_malloc(len[i]);
        if (!blk[i]) {
            heap_fail("small allocation failed");
            return;
        }
        if ((uintptr_t)blk[i] & 7u) heap_fail("allocation not 8-byte aligned");
        fill_block(blk[i], len[i], (uint32_t)i);
    }
    for (int i = 0; i < N; i += 2) {  // free every other block, then reuse the holes
        psram_free(blk[i]);
        len[i] = 1 + xorshift32(&rng) % (32 * 1024);
        blk[i] = psram_malloc(len[i]);
        if (!blk[i]) {
            heap_fail("reallocation into freed space failed");
            return;
        }
        fill_block(blk[i], len[i], (uint32_t)i);
    }
    // grow one block (moves it) and shrink another (in place); contents must survive
    uint8_t *grown = psram_realloc(blk[1], len[1] + 100 * 1024);
    if (!grown || ((uintptr_t)grown & 7u) || !check_block(grown, len[1], 1)) heap_fail("realloc (grow) lost data");
    else blk[1] = grown;
    uint8_t *shrunk = psram_realloc(blk[3], len[3] / 2 + 1);
    if (shrunk != blk[3]) heap_fail("realloc (shrink) moved the block");
    len[3] = len[3] / 2 + 1;

    uint8_t *aligned = psram_memalign(4096, 1000);
    if (!aligned || ((uintptr_t)aligned & 4095u)) heap_fail("memalign(4096) misaligned");
    if (psram_malloc(s0.total + 1)) heap_fail("oversized allocation succeeded");

    for (int i = 0; i < N; i++) {
        if (!check_block(blk[i], len[i], (uint32_t)i)) heap_fail("block contents corrupted");
    }
    if (!check_block(big, 4u * 1024 * 1024, 999)) heap_fail("4 MB block contents corrupted");

    psram_heap_stats(&s);
    printf("  heap: in use %u bytes in %u blocks, %u free in %u blocks\n", (unsigned)s.used,
           (unsigned)s.blocks_used, (unsigned)s.free, (unsigned)s.blocks_free);

    for (int i = 0; i < N; i++) psram_free(blk[i]);
    psram_free(big);
    psram_free(aligned);
    psram_heap_stats(&s);
    if (s.blocks_used != 0 || s.largest_free != s0.largest_free) heap_fail("heap did not return to empty");
    else printf("  heap: everything freed and coalesced back into one block\n");
}

int main(void) {
    stdio_init_all();
#if LIB_PICO_STDIO_USB
    absolute_time_t until = make_timeout_time_ms(10000);  // give a USB terminal time to attach
    while (!stdio_usb_connected() && !time_reached(until)) sleep_ms(50);
#endif
    sleep_ms(500);

    printf("\npsram_test: CS on GPIO%d, sys clock %" PRIu32 " MHz\n", PICO_PSRAM_CS_PIN,
           clock_get_hz(clk_sys) / 1000000);
    size_t size = psram_is_available() ? psram_get_size() : 0;
    if (!size) {
        errors++;
        printf("  PSRAM not set up: check PICO_PSRAM_CS_PIN / PICO_PSRAM_SIZE_BYTES in the board header\n");
    } else {
        uint32_t words = size / 4;
        printf("  %u kB configured at 0x%08x\n", (unsigned)(size / 1024), PSRAM_ADDR);

        printf("memory test:\n");
        data_bus_test();
        printf("  %-28s %s\n", "data bus", errors ? "FAIL" : "ok");
        if (errors) {
            printf("  (all 0xffffffff or 0x00000000 means the chip isn't answering: check U4's\n"
                   "  soldering, its 3V3/GND, and R11, the 0R link from GPIO47 to its CS)\n");
        } else {
            uint32_t before = errors;
            address_bus_test(words);
            printf("  %-28s %s\n", "address bus", errors == before ? "ok" : "FAIL");
            fill_test("fill (uncached)", words, 0x12345678u, false);
            fill_test("fill (inverse, uncached)", words, 0x87654321u, false);
            fill_test("fill (through the cache)", words, 0xdeadbeefu, true);
        }
        if (!errors) {
            printf("throughput:\n");
            throughput();
            printf("heap:\n");
            heap_test();
        }
    }

    while (true) {
        if (errors) {
            printf("psram_test: FAIL (%" PRIu32 " errors)\n", errors);
        } else {
            printf("psram_test: PASS (%u kB)\n", (unsigned)(size / 1024));
        }
        sleep_ms(5000);
    }
}
