// PSRAM heap: TLSF over the PSRAM that hardware_psram brought up at boot. See psram_alloc.h.
#include "psram_alloc.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "pico.h"
#include "pico/mutex.h"
#include "hardware/psram.h"
#include "hardware/regs/addressmap.h"
#include "tlsf/tlsf.h"

// QMI chip select 1 (the PSRAM) is mapped 16 MB above the flash: the SDK's linker scripts put
// the PSRAM region at this address too.
#define PSRAM_BASE (XIP_BASE + 0x01000000u)
#define ALIGN 8u  // malloc's alignment; TLSF on its own only guarantees 4 on 32-bit targets

extern uint32_t __psram_end__;  // end of the __in_psram / __uninitialized_psram variables

auto_init_mutex(heap_mutex);
static tlsf_t heap;
static pool_t pool;  // the PSRAM pool (tlsf_get_pool only finds pools made by tlsf_create_with_pool)
static uintptr_t pool_start, pool_end;
static size_t pool_total;
static bool init_tried;

static void stats_walker(void *ptr, size_t size, int used, void *user) {
    (void)ptr;
    psram_heap_stats_t *s = user;
    if (used) {
        s->used += size;
        s->blocks_used++;
    } else {
        s->free += size;
        s->blocks_free++;
        if (size > s->largest_free) s->largest_free = size;
    }
}

static bool init_locked(void) {
    if (init_tried) return heap != NULL;
    init_tried = true;
    if (!psram_is_available()) return false;

    uintptr_t start = ((uintptr_t)&__psram_end__ + ALIGN - 1) & ~(uintptr_t)(ALIGN - 1);
    uintptr_t end = PSRAM_BASE + psram_get_size();
    if (start < PSRAM_BASE) start = PSRAM_BASE;
    if (end <= start || end - start < tlsf_pool_overhead() + tlsf_block_size_min()) return false;

    void *control = malloc(tlsf_size());  // control block in SRAM keeps lookups fast
    if (!control) return false;
    tlsf_t t = tlsf_create(control);
    pool_t p = t ? tlsf_add_pool(t, (void *)start, end - start) : NULL;
    if (!p) {
        free(control);
        return false;
    }
    psram_heap_stats_t s = {0};
    tlsf_walk_pool(p, stats_walker, &s);
    heap = t;
    pool = p;
    pool_start = start;
    pool_end = end;
    pool_total = s.free;
    return true;
}

static bool ready(void) {
    return heap != NULL || psram_heap_init();
}

bool psram_heap_init(void) {
    mutex_enter_blocking(&heap_mutex);
    bool ok = init_locked();
    mutex_exit(&heap_mutex);
    return ok;
}

bool psram_heap_owns(const void *ptr) {
    return (uintptr_t)ptr >= pool_start && (uintptr_t)ptr < pool_end;
}

static void check_owned(const void *ptr, const char *fn) {
    if (!psram_heap_owns(ptr)) panic("%s: %p is not from the PSRAM heap", fn, ptr);
}

void *psram_memalign(size_t align, size_t size) {
    if (!size || (align & (align - 1)) || !ready()) return NULL;
    if (align < ALIGN) align = ALIGN;
    mutex_enter_blocking(&heap_mutex);
    void *p = tlsf_memalign(heap, align, size);
    mutex_exit(&heap_mutex);
    return p;
}

void *psram_malloc(size_t size) {
    return psram_memalign(ALIGN, size);
}

void *psram_calloc(size_t count, size_t size) {
    if (size && count > SIZE_MAX / size) return NULL;
    void *p = psram_malloc(count * size);
    if (p) memset(p, 0, count * size);
    return p;
}

void *psram_realloc(void *ptr, size_t size) {
    if (!ptr) return psram_malloc(size);
    if (!size) {
        psram_free(ptr);
        return NULL;
    }
    check_owned(ptr, "psram_realloc");
    mutex_enter_blocking(&heap_mutex);
    size_t old = tlsf_block_size(ptr);
    void *p;
    if (size <= old) {
        p = tlsf_realloc(heap, ptr, size);  // TLSF trims in place, so the alignment holds
    } else {
        // tlsf_realloc would move the block to a 4-byte-aligned address, so move it here
        p = tlsf_memalign(heap, ALIGN, size);
        if (p) {
            memcpy(p, ptr, old);
            tlsf_free(heap, ptr);
        }
    }
    mutex_exit(&heap_mutex);
    return p;
}

void psram_free(void *ptr) {
    if (!ptr) return;
    check_owned(ptr, "psram_free");
    mutex_enter_blocking(&heap_mutex);
    tlsf_free(heap, ptr);
    mutex_exit(&heap_mutex);
}

void psram_heap_stats(psram_heap_stats_t *stats) {
    memset(stats, 0, sizeof(*stats));
    if (!ready()) return;
    mutex_enter_blocking(&heap_mutex);
    tlsf_walk_pool(pool, stats_walker, stats);
    mutex_exit(&heap_mutex);
    stats->total = pool_total;
}
