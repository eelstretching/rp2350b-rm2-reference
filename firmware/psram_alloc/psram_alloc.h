// A heap in PSRAM, separate from the SDK's malloc (which stays in on-chip SRAM).
//
// Needs pico-sdk 2.3.0 or later: hardware_psram brings the PSRAM up at boot from
// PICO_PSRAM_CS_PIN / PICO_PSRAM_SIZE_BYTES in the board header. The heap covers the PSRAM
// left over after any __in_psram / __uninitialized_psram variables.
//
// Allocations are 8-byte aligned, like malloc. The calls are safe from both cores but not
// from interrupt handlers (they take a mutex). The allocator is TLSF: constant-time malloc
// and free, low fragmentation; its ~3 KB control block lives in SRAM, taken from malloc on
// first use.
#ifndef PSRAM_ALLOC_H
#define PSRAM_ALLOC_H

#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// Set up the heap. Optional: the first allocation calls it. Returns false if there is no
// PSRAM (or no room left in it), in which case every allocation returns NULL.
bool psram_heap_init(void);

void *psram_malloc(size_t size);
void *psram_calloc(size_t count, size_t size);
// Shrinks in place; growing always moves the block (allocate, copy, free).
void *psram_realloc(void *ptr, size_t size);
// align must be a power of two (e.g. for DMA ring buffers).
void *psram_memalign(size_t align, size_t size);
// ptr must come from this heap (or be NULL); anything else panics.
void psram_free(void *ptr);

// True if ptr points into the PSRAM heap.
bool psram_heap_owns(const void *ptr);

typedef struct {
    size_t total;         // bytes the heap can hand out when empty
    size_t used;          // bytes in allocated blocks
    size_t free;          // bytes in free blocks
    size_t largest_free;  // largest single free block: the biggest allocation that can succeed
    size_t blocks_used;
    size_t blocks_free;
} psram_heap_stats_t;

// Walks the heap, so it takes time proportional to the number of blocks.
void psram_heap_stats(psram_heap_stats_t *stats);

#ifdef __cplusplus
}
#endif

#endif
