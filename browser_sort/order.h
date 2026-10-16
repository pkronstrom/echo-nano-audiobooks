#ifndef ECHO_BROWSER_ORDER_H
#define ECHO_BROWSER_ORDER_H
#include <stdint.h>
#ifndef BROWSER_ORDER_CAPACITY
#define BROWSER_ORDER_CAPACITY 1024u
#endif
/* Iterator emits each accepted physical entry exactly once. Names are bounded
 * to256 UTF16 units. reset/name return0 success or negative error; next returns
 * 1 key,0 EOF,negative error. The provider feeds the watchdog and owns I/O locks. */
struct browser_order_provider {
    void *context;
    int (*reset)(void *);
    int (*next)(void *,uint32_t *key);
    int (*name)(void *,uint32_t key,unsigned short out[256],unsigned *directory);
};
struct browser_order {
    uint32_t keys[BROWSER_ORDER_CAPACITY];
    unsigned short names[2][256];
    unsigned count;
};
/* Sorted next window strictly after an optional physical-key pivot. Directory
 * first, natural name, raw key. Error clears count: partial results are invalid.
 * The pivot may be outside the retained window but must still be readable. */
int browser_order_window(struct browser_order *,const struct browser_order_provider *,
                         int has_after,uint32_t after);
#endif
