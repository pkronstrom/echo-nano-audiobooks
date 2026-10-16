#ifndef ECHO_AUTO_PLAYLIST_H
#define ECHO_AUTO_PLAYLIST_H
#include <stdint.h>
/* Cold browser metadata constructor, also exercised by standalone host tests.
 * Source supplies verified natural-order file names;
 * no filesystem writes or creation are performed by this encoder itself.
 * name returns 1 with a NUL-terminated UTF-16 basename in out[128]. Source count
 * and names must remain stable across planning/emission. Workspace is exclusive
 * and nonreentrant. write returns the exact byte count on success; every other
 * result fails. Discard output on any failure: even a complete trailer is not
 * proof of successful emission or permission to publish a temporary file. */
typedef int (*book_name_fn)(void *,uint32_t,uint16_t out[128]);
typedef int (*book_write_fn)(void *,uint32_t,const void *,uint32_t);
typedef uint32_t (*book_crc_fn)(const void *,uint32_t);
struct book_playlist_source {
    void *context;uint32_t count;book_name_fn name;
    /* UTF-16 units in normalized absolute parent path INCLUDING final slash.
     * Caller resolves/validates that path. Includes both halves of surrogates.
     * 1..247 leaves room for BOOK.M3U within the native 255-unit path limit. */
    uint32_t prefix_units;
};
struct book_playlist_workspace { uint8_t block[512];uint16_t name[128]; };
struct book_playlist_plan { uint32_t bytes,fingerprint,count; };
int book_playlist_plan(const struct book_playlist_source *,struct book_playlist_workspace *,struct book_playlist_plan *);
int book_playlist_emit(const struct book_playlist_source *,struct book_playlist_workspace *,const struct book_playlist_plan *,book_write_fn,void *);
void book_prepare_sector(void *,uint32_t magic,book_crc_fn);
#endif
