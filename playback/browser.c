#include "browser.h"
static u16 half(const u8 *p) { return p[0] | (u16)p[1] << 8; }
static u32 word(const u8 *p) { return half(p) | (u32)half(p+2) << 16; }
static int append(u16 *out, u32 *used, const u16 *name)
{
    u32 n = 0;
    while (n < 256 && name[n]) {
        u16 c = name[n++];
        if (c < 32 || c == '/' || c == '\\' || c == ':' || c == '*' ||
            c == '?' || c == '"' || c == '<' || c == '>' || c == '|') return 0;
        if (c >= 0xd800 && c <= 0xdbff) {
            if (n >= 256 || name[n] < 0xdc00 || name[n] > 0xdfff) return 0;
            n++;
        } else if (c >= 0xdc00 && c <= 0xdfff) return 0;
    }
    if (!n || n == 256 || (name[0] == '.' && (n == 1 || (n == 2 && name[1] == '.')))) return 0;
    u32 separator = *used > 1;
    if (*used + separator + n >= 256) return 0;
    if (separator) out[(*used)++] = '/';
    __builtin_memcpy(out+*used, name, n*2);
    *used += n; out[*used] = 0;
    return 1;
}
static int browser_path(media_read_fn read, void *ctx, int exfat, const u8 *browser,
                        const u8 *node, u32 root_cluster, u16 *out, int directory)
{
    u16 component[256];
    out[0] = 0;
    u32 depth = half(browser+0x1cc);
    if (depth > 7) return 0;
    struct media_dir parent = {0};
    struct media_ref ref;
    u32 used = 1;
    out[0] = '/'; out[1] = 0;
    for (u32 level = 1; level <= depth; level++) {
        u32 child = word(browser + level*56 + (exfat ? 24 : 20));
        if (media_directory_name(read, ctx, exfat, &parent, child, component, &ref) != 1 ||
            !append(out, &used, component)) goto invalid;
        parent = (struct media_dir){ref.cluster, ref.size, 0, ref.flags};
    }
    u32 selected_parent = word(node+8);
    if (depth ? selected_parent != parent.cluster :
                (selected_parent && selected_parent != root_cluster)) goto invalid;
    /* Copy unaligned UI UTF16 data; never retain the browser's node pointer. */
    for (u32 n = 0; n < 256; n++) component[n] = half(node+0x70+n*2);
    if (!append(out, &used, component)) goto invalid;
    if (media_resolve(read, ctx, exfat, out, &ref) != 1 ||
        !!(ref.attrs & 16) != directory || ref.index != word(node+12)) goto invalid;
    if (directory && ref.cluster != ((u32)half(node+0x63)<<16 | half(node+0x69))) goto invalid;
    if (depth ? ref.parent.cluster != selected_parent :
                (ref.parent.cluster && ref.parent.cluster != root_cluster)) goto invalid;
    return 1;
invalid:
    out[0] = 0;
    return 0;
}

int media_browser_path(media_read_fn read, void *ctx, int exfat, const u8 *browser,
                       const u8 *node, u32 root_cluster, u16 *out)
{ return browser_path(read,ctx,exfat,browser,node,root_cluster,out,0); }
int media_browser_directory(media_read_fn read, void *ctx, int exfat, const u8 *browser,
                            const u8 *node, u32 root_cluster, u16 *out)
{ return browser_path(read,ctx,exfat,browser,node,root_cluster,out,1); }
