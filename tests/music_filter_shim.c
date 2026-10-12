#include "fw.h"
static int (*fat_read)(u8 *, u32, u32);
static int (*exfat_read)(u8 *, const void *, u32);
void music_test_readers(void *fat, void *exfat)
{
    fat_read = fat;
    exfat_read = exfat;
}
int music_fat_original(u8 *out, u32 cluster, u32 index)
{
    return fat_read(out, cluster, index);
}
int music_exfat_original(u8 *out, const void *desc, u32 index)
{
    return exfat_read(out, desc, index);
}
void music_watchdog(void) {}
