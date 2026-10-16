#include "guarded_create.h"

#define BYTE(p) (*(volatile u8 *)(p))
#define WORD(p) (*(volatile u32 *)(p))
#define HALF(p) (*(volatile u16 *)(p))
#define sector_read FW(0x0306b716, int, u32, u32, u32, void *)
#define CURRENT_FAT 0x03077664
#define CURRENT_EXFAT ((volatile u8 *)0x03078a5c)
#define WRITE_CACHE ((volatile u8 *)0x03076b68)
#define CACHE_TAG WORD(0x03076b64)
#define FAT_DIRTY BYTE(0x03076914)

static u32 word(const u8 *p)
{
    return p[0] | (u32)p[1] << 8 | (u32)p[2] << 16 | (u32)p[3] << 24;
}
static u8 upper(u8 c) { return c >= 'a' && c <= 'z' ? c - 32 : c; }
static void copy(volatile u8 *out, const volatile u8 *in, u32 n)
{
    while (n--) *out++ = *in++;
}
static int fixed_name(const char *name, u8 *short_name)
{
    const char *base = "BOOK.";
    for (u32 i = 0; i < 5; ++i) if (name[i] != base[i]) return 0;
    if (name[8] || !((name[5]=='R' && name[6]=='S' && name[7]=='M') ||
                    (name[5]=='B' && name[6]=='M' && name[7]=='K') ||
                    (name[5]=='T' && name[6]=='M' && name[7]=='P'))) return 0;
    for (u32 i=0; i<11; ++i) short_name[i] = i<4 ? (u8)name[i] : i<8 ? ' ' : (u8)name[i-3];
    return 1;
}
static int read_sector(u32 dev, u32 lba, u8 *out)
{
    fw_wdt();
    return sector_read(dev,lba,1,out) == 0;
}
static int extent_ok(u32 heap,u32 clusters,u32 spc)
{
    return heap && spc && clusters <= (0xffffffffu-heap)/spc;
}
static int fat_value(u32 dev, u32 fs, u32 cluster, u8 *scratch, u32 *value)
{
    u32 base = fs==3 ? WORD(0x03076b5b) : WORD(0x03076b53) + HALF(0x03076b38);
    if (base > 0xffffffffu - cluster/128 || !read_sector(dev,base+cluster/128,scratch)) return 0;
    *value = word(scratch+(cluster%128)*4)&0x0fffffff;
    return 1;
}
/* Stock mount305acb6 stores ClusterHeapOffset here; stock d442 assumes
 * the bitmap starts there too. Prove that restricted layout from the real
 * root81 record and its FAT chain before any use of the mutation primitive.
 */
static int bitmap_layout(u32 dev,u32 clusters,u32 spc,u8 *scratch)
{
    u32 root=WORD(0x03076b3d),next,found=0;
    if(BYTE(0x03076b3a)!=1 || root<2 || root-2>=clusters ||
       !fat_value(dev,3,root,scratch,&next) || next<0x0ffffff8)return 0;
    u32 lba=WORD(0x03076b4f)+(root-2)*spc,bytes=(clusters+7)/8;
    for(u32 s=0;s<spc;++s) {
        if(!read_sector(dev,lba+s,scratch))return 0;
        for(u32 row=0;row<16;++row) {
            const u8 *p=scratch+row*32;
            if(!p[0])goto directory_end;
            if(p[0]!=0x81)continue;
            if(found++ || p[1] || word(p+20)!=2 || word(p+24)!=bytes || word(p+28))return 0;
        }
    }
directory_end:
    if(found!=1)return 0;
    u32 sectors=(bytes+511)/512;
    if(sectors>4096)return 0;
    u32 count=(sectors+spc-1)/spc;
    for(u32 i=0;i<count;++i) {
        if(!fat_value(dev,3,2+i,scratch,&next))return 0;
        if(i+1<count) { if(next!=3+i)return 0; }
        else if(next<0x0ffffff8)return 0;
    }
    if(!read_sector(dev,WORD(0x03076b4f),scratch))return 0;
    for(u32 i=0;i<count;++i)if(!(scratch[i/8]&(1u<<(i%8))))return 0;
    u32 bit=root-2;
    if(bit>=4096 && !read_sector(dev,WORD(0x03076b4f)+bit/4096,scratch))return 0;
    if(!(scratch[(bit%4096)/8]&(1u<<(bit%8))))return 0;
    return 1;
}
static u32 search_limit(u32 fs,u32 clusters)
{
    u32 limit=fs==3?4096u*4096:4096u*128-2;
    return clusters<limit?clusters:limit;
}
/* Bound work to4096 allocation sectors even on enormous cards. Finding enough
 * free clusters in this prefix is conservative; later free space may be refused.
 * This is NOT an allocation reservation and does not authorize native writes.
 */
static int free_space(u32 dev,u32 fs,u32 wanted,u32 clusters,u8 *scratch)
{
    u32 found=0, limit=search_limit(fs,clusters), loaded=0xffffffffu;
    for(u32 i=0;i<limit;++i) {
        u32 block=fs==3 ? i/4096 : (i+2)/128;
        if(block!=loaded) {
            u32 base=fs==3 ? WORD(0x03076b4f) : WORD(0x03076b53)+HALF(0x03076b38);
            if(base>0xffffffffu-block || !read_sector(dev,base+block,scratch))return 0;
            loaded=block;
        }
        if(fs==3 && !(i&7) && scratch[(i%4096)/8]==255) { i+=7;continue; }
        int free=fs==3 ? !(scratch[(i%4096)/8]&(1u<<(i%8))) :
                         !(word(scratch+((i+2)%128)*4)&0x0fffffff);
        if(free && ++found>=wanted)return 1;
    }
    return 0;
}
static int preload(u32 dev,u32 lba,u8 *scratch)
{
    if(!read_sector(dev,lba,scratch)) { CACHE_TAG=0xffffffffu; return 0; }
    copy(WRITE_CACHE,scratch,512); CACHE_TAG=lba; return 1;
}
static int empty_entry(const u8 *entry,u32 fs,const char *name,const u8 *raw_name)
{
    if(fs==3) {
        if(entry[0]!=0x85 || entry[1]!=2 || entry[32]!=0xc0 || entry[35]!=8 ||
           entry[64]!=0xc1 || word(entry+40) || word(entry+44) ||
           word(entry+52) || word(entry+56) || word(entry+60))return 0;
        for(u32 j=0;j<8;++j)if(entry[66+j*2]!=(u8)name[j] || entry[67+j*2])return 0;
    } else {
        for(u32 j=0;j<11;++j)if(entry[j]!=raw_name[j])return 0;
        if(entry[11]!=0x20 || word(entry+28) || entry[20] || entry[21] || entry[26] || entry[27])return 0;
    }
    return 1;
}

static int create_empty(const u8 parent[42], const char *name,
                         u32 expected_device, u32 expected_fs, u32 event_bytes,
                         struct guarded_writer *writer)
{
    u8 scratch[512], raw_name[12], old_exfat[42], native_name[12];
    u32 saved_fat=0, chosen=0xffffffffu, chosen_lba=0, streak=0;
    int result=-1, switched=0, handle=-1;
    if(!parent || !name || (parent[13]&1) || !fixed_name(name,raw_name) || !event_bytes ||
       event_bytes>131072 || (event_bytes&511))return -1;
    fw_lock();
    u32 fs=BYTE(0x03076b24), dev=WORD(0x03076b2c), spc=WORD(0x03076b34);
    u32 clusters=WORD(0x03076b4b), cluster=word(parent), next;
    if(fs!=expected_fs || dev!=expected_device || (fs!=2 && fs!=3) ||
       BYTE(0x03076b3a)!=1 || WORD(0x03076b30)!=512 || HALF(0x03076b28)!=9 || !spc ||
       spc>256 || (spc&(spc-1)) || HALF(0x03076b26)>8 ||
       (1u<<HALF(0x03076b26))!=spc || clusters<2 || clusters>0x0ffffff5 ||
       cluster<2 || cluster-2>=clusters || !extent_ok(WORD(0x03076b4f),clusters,spc) || FAT_DIRTY)goto done;
    u32 slot;
    for(slot=0;slot<8;++slot)if(!BYTE(0x03077668+slot*0x27e))break;
    if(slot==8)goto done;
    u32 bytes=spc*512;
    if(fs==3) {
        if(!bitmap_layout(dev,clusters,spc,scratch) ||
           !read_sector(dev,WORD(0x03076b4f)+(cluster-2)/4096,scratch) ||
           !(scratch[((cluster-2)%4096)/8]&(1u<<((cluster-2)%8))))goto done;
    }
    if(fs==3 && ((parent[12]!=1 && parent[12]!=3) ||
       (word(parent+4)!=bytes && !(parent[12]==1 && !word(parent+4) && cluster==WORD(0x03076b3d)))))goto done;
    if(fs==3 && (parent[12]&2)) {
        if(parent[12]!=3 || !word(parent+4) || word(parent+4)>bytes)goto done;
    } else if(!fat_value(dev,fs,cluster,scratch,&next) || next<0x0ffffff8)goto done;
    u32 heap=WORD(0x03076b4f);
    if(cluster-2>(0xffffffffu-heap)/spc)goto done;
    u32 first=heap+(cluster-2)*spc;
    for(u32 s=0;s<spc;++s) {
        if(first>0xffffffffu-s || !read_sector(dev,first+s,scratch))goto done;
        for(u32 row=0;row<16;++row) {
            u8 *entry=scratch+row*32; u32 index=s*16+row;
            if(fs==2) {
                int equal=1;
                for(u32 j=0;j<11;++j)if(upper(entry[j])!=raw_name[j])equal=0;
                if(entry[0]!=0xe5 && entry[0] && equal)goto done;
                /* Any live LFN fragment matching the fixed eight-unit name
                 * refuses creation, including directories and unusual aliases. */
                if(entry[0]!=0xe5 && entry[11]==15) {
                    static const u8 offsets[8]={1,3,5,7,9,14,16,18}; equal=1;
                    for(u32 j=0;j<8;++j)if(entry[offsets[j]+1] || upper(entry[offsets[j]])!=(u8)name[j])equal=0;
                    if(equal)goto done;
                }
                if(chosen==0xffffffffu && (!entry[0] || entry[0]==0xe5)) { chosen=index;chosen_lba=first+s; }
            } else {
                if(entry[0]==0xc1) {
                    int equal=1;
                    for(u32 j=0;j<8;++j)if(entry[3+j*2] || upper(entry[2+j*2])!=(u8)name[j])equal=0;
                    if(equal)goto done;
                }
                streak=(entry[0]&128)?0:streak+1;
                if(chosen==0xffffffffu && streak==2) { chosen=index-1;chosen_lba=first+s; }
                if(chosen!=0xffffffffu && index==chosen+2 && (entry[0]&128))goto done;
            }
        }
    }
    if(chosen==0xffffffffu || (fs==3 && ((chosen%16)>13 || chosen+2>=spc*16)))goto done;
    if(!free_space(dev,fs,(event_bytes+bytes-1)/bytes,clusters,scratch))goto done;
    if(!preload(dev,chosen_lba,scratch))goto done;
    saved_fat=WORD(CURRENT_FAT); copy(old_exfat,CURRENT_EXFAT,42);
    WORD(CURRENT_FAT)=cluster;copy(CURRENT_EXFAT,parent,42);switched=1;
    for(u32 j=0;j<12;++j)native_name[j]=fs==3 ? (j<8?(u8)name[j]:0) : (j<11?raw_name[j]:0);
    handle=fw_file_create(".",(const char *)native_name);
    if(handle<0 || handle>=8)goto done;
    /* No allocation has happened. On failed checked preload, abandoning only
     * this newly created empty handle cannot leak a data allocation. */
    if(!preload(dev,chosen_lba,scratch))goto done;
    const u8 *fcb=(const u8 *)(0x03077668+(u32)handle*0x27e);
    if(fcb[0]!=3 || word(fcb+12)!=cluster || word(fcb+16) || word(fcb+20) ||
       word(fcb+28)!=chosen ||
       !empty_entry(scratch+(chosen%16)*32,fs,name,raw_name))goto done;
    if(writer) {
        writer->device=dev;writer->fs=fs;writer->index=chosen;writer->directory_lba=chosen_lba;
        writer->handle=handle;handle=-1;
        copy(writer->parent,parent,42);copy(writer->name,(const u8 *)name,9);
        result=0;goto done;
    }
    if(fw_file_close(handle))goto done;
    handle=-1;
    if(!read_sector(dev,chosen_lba,scratch))goto done;
    if(!empty_entry(scratch+(chosen%16)*32,fs,name,raw_name))goto done;
    result=0;
done:
    if(handle>=0 && handle<8)BYTE(0x03077668+(u32)handle*0x27e)=0;
    if(switched) { WORD(CURRENT_FAT)=saved_fat;copy(CURRENT_EXFAT,old_exfat,42); }
    fw_unlock();return result;
}

int guarded_create_empty(const u8 parent[42],const char *name,u32 dev,u32 fs,u32 bytes)
{
    return create_empty(parent,name,dev,fs,bytes,0);
}

int guarded_reserve_native(u32 expected_device, u32 expected_fs,
                           u32 requested_bytes, u32 first_and_count[2])
{
    u8 expected[512], scratch[512];
    u32 first=0, lba=0, run=0, loaded=0xffffffffu;
    int result=-1, native_started=0;
    if(!first_and_count)return -1;
    first_and_count[0]=first_and_count[1]=0;
    if(!requested_bytes || requested_bytes>131072)return -1;
    fw_lock();
    u32 fs=BYTE(0x03076b24),dev=WORD(0x03076b2c),spc=WORD(0x03076b34);
    u32 clusters=WORD(0x03076b4b),kind=BYTE(0x03076b25);
    if(fs!=expected_fs || dev!=expected_device || (fs!=2 && fs!=3) ||
       kind<2 || kind>4 || BYTE(0x03076b3a)!=1 || WORD(0x03076b30)!=512 || HALF(0x03076b28)!=9 ||
       !spc || spc>256 || (spc&(spc-1)) || HALF(0x03076b26)>8 ||
       (1u<<HALF(0x03076b26))!=spc || clusters<2 || clusters>0x0ffffff5 ||
       !extent_ok(WORD(0x03076b4f),clusters,spc) || FAT_DIRTY)goto done;
    u32 wanted=(requested_bytes+spc*512-1)/(spc*512);
    if(fs==3 && !bitmap_layout(dev,clusters,spc,scratch))goto done;
    u32 limit=search_limit(fs,clusters);
    u32 base=fs==3?WORD(0x03076b4f):WORD(0x03076b53)+HALF(0x03076b38);
    if(fs==2 && base<WORD(0x03076b53))goto done;
    for(u32 i=0;i<limit;++i) {
        u32 block=fs==3?i/4096:(i+2)/128;
        if(block!=loaded) {
            if(first || base>0xffffffffu-block || !read_sector(dev,base+block,expected))goto done;
            loaded=block;lba=base+block;
        }
        if(fs==3 && !first && !(i&7) && expected[(i%4096)/8]==255) { i+=7;continue; }
        int free=fs==3?!(expected[(i%4096)/8]&(1u<<(i%8))):
                        !(word(expected+((i+2)%128)*4)&0x0fffffff);
        if(!first) { if(!free)continue;first=i+2; }
        if(!free)goto done; /* Never skip the first insufficient native run. */
        if(++run==wanted)break;
    }
    if(run!=wanted || !first || first-2>clusters-wanted)goto done;
    /* Change the expected copy only at the proven free run. Native mutation
     * must produce this entire sector, including every untouched neighbor. */
    for(u32 i=0;i<wanted;++i) {
        if(fs==3) {
            u32 bit=(first-2+i)%4096;
            expected[bit/8]|=1u<<(bit%8);
        } else {
            u32 value=i+1<wanted?first+i+1:0x0fffffff;
            u8 *p=expected+((first+i)%128)*4;
            p[0]=value;p[1]=value>>8;p[2]=value>>16;p[3]=value>>24;
        }
    }
    u32 count_address=0x0300430c+(kind-2)*4, saved_count=WORD(count_address);
    native_started=1;
    if(fs==2) {
        if(!read_sector(dev,lba,scratch))goto native_failed;
        copy((volatile u8 *)0x03076714,scratch,512);
        WORD(0x03076918)=lba;
        for(u32 i=0;i<wanted;++i) {
            FW(0x0305e7f2,void,u32,u32)(first+i,i+1<wanted?first+i+1:0x0fffffff);
            if(WORD(0x03076918)!=lba)goto native_failed;
        }
        for(u32 i=0;i<512;++i)if(BYTE(0x03076714+i)!=expected[i])goto native_failed;
        /* Prevent a later stock cache eviction from retrying a failed flush. */
        FAT_DIRTY=0;
        if(FW(0x0305a5a4,int,u32,const void *)(lba,(const void *)0x03076714))goto native_failed;
    } else {
        if(FW(0x0305d442,u32,u32,u32,u32)(first,wanted,1))goto native_failed;
    }
    if(!read_sector(dev,lba,scratch))goto native_failed;
    for(u32 i=0;i<512;++i)if(scratch[i]!=expected[i])goto native_failed;
    FW(0x0305a69a,void,int)(-(int)(wanted*spc));
    first_and_count[0]=first;first_and_count[1]=wanted;result=0;goto done;
native_failed:
    WORD(count_address)=saved_count;
done:
    if(native_started) {
        FAT_DIRTY=0;
        WORD(0x03076918)=0;
    }
    fw_unlock();return result;
}

int guarded_writer_begin(struct guarded_writer *w,const u8 parent[42],
                          const char *name,u32 dev,u32 fs,u32 total)
{
    u32 reservation[2];int result=-1;
    if(!w)return -1;
    w->handle=-1;w->verified=0;w->total=0;
    if(!total || total>131072)return -1;
    fw_lock();
    if(create_empty(parent,name,dev,fs,(total+511)&~511u,w))goto done;
    w->spc=WORD(0x03076b34);w->heap=WORD(0x03076b4f);
    w->fat_lba=fs==3?WORD(0x03076b5b):WORD(0x03076b53)+HALF(0x03076b38);
    if(guarded_reserve_native(dev,fs,total,reservation))goto done;
    w->first=reservation[0];w->clusters=reservation[1];w->total=total;w->offset=0;w->crc=0xffffffffu;
    volatile u8 *fcb=(volatile u8 *)(0x03077668+(u32)w->handle*0x27e);
    *(volatile u32 *)(fcb+16)=total;*(volatile u32 *)(fcb+20)=w->first;
    *(volatile u32 *)(fcb+24)=w->first;*(volatile u32 *)(fcb+32)=0;
    *(volatile u32 *)(fcb+36)=w->first;*(volatile u32 *)(fcb+40)=0;
    *(volatile u32 *)(fcb+596)=w->first;*(volatile u32 *)(fcb+600)=total;
    fcb[608]=fs==3?3:1;
    result=0;
done:
    if(result)guarded_writer_abort(w);
    fw_unlock();return result;
}
static u32 crc_bytes(u32 crc,const u8 *p,u32 n)
{
    while(n--) { crc^=*p++;for(u32 i=0;i<8;++i)crc=(crc>>1)^(0xedb88320u&-(crc&1)); }
    return crc;
}
static int writer_device(const struct guarded_writer *w)
{
    return w && w->device==WORD(0x03076b2c) && w->fs==BYTE(0x03076b24) &&
           w->spc==WORD(0x03076b34) && w->heap==WORD(0x03076b4f) &&
           w->fat_lba==(w->fs==3?WORD(0x03076b5b):WORD(0x03076b53)+HALF(0x03076b38)) &&
           BYTE(0x03076b3a)==1 && WORD(0x03076b30)==512 && extent_ok(w->heap,WORD(0x03076b4b),w->spc) && !FAT_DIRTY;
}
static int writer_handle(const struct guarded_writer *w)
{
    if(w->handle<0 || w->handle>=8)return 0;
    const u8 *fcb=(const u8 *)(0x03077668+(u32)w->handle*0x27e);
    return fcb[0]==3 && word(fcb+12)==word(w->parent) && word(fcb+28)==w->index &&
           word(fcb+16)==w->total && word(fcb+20)==w->first;
}
static int writer_fat(const struct guarded_writer *w,u8 *scratch)
{
    if(w->fs==3)return 1;
    u32 lba=w->fat_lba+w->first/128;
    if(!read_sector(w->device,lba,scratch))return 0;
    for(u32 i=0;i<w->clusters;++i)if((word(scratch+((w->first+i)%128)*4)&0x0fffffff)!=
            (i+1<w->clusters?w->first+i+1:0x0fffffff))return 0;
    copy((volatile u8 *)0x03076714,scratch,512);WORD(0x03076918)=lba;
    return 1;
}
int guarded_writer_packet(struct guarded_writer *w,const u8 *data,u32 length)
{
    u8 packet[512] __attribute__((aligned(4))),check[512];int result=-1;
    if(!w || !data)return -1;
    fw_lock();
    if(!writer_device(w) || w->handle<0 || w->handle>=8 || !length || length>512 ||
       w->offset>=w->total || length>w->total-w->offset || (w->offset&511) ||
       (length!=512 && length!=w->total-w->offset))goto done;
    const u8 *fcb=(const u8 *)(0x03077668+(u32)w->handle*0x27e);
    if(fcb[0]!=3 || word(fcb+12)!=word(w->parent) || word(fcb+28)!=w->index ||
       word(fcb+16)!=w->total || word(fcb+20)!=w->first || word(fcb+32)!=w->offset ||
       word(fcb+24)!=w->first+w->offset/(w->spc*512) || !writer_fat(w,check))goto done;
    for(u32 i=0;i<512;++i)packet[i]=i<length?data[i]:0;
    u32 got=fw_file_write(packet,w->offset,length,w->handle);
    if(got!=((length+511)&~511u))goto done;
    u32 lba=w->heap+(w->first-2)*w->spc+w->offset/512;
    if(!read_sector(w->device,lba,check))goto done;
    for(u32 i=0;i<512;++i)if(check[i]!=packet[i])goto done;
    w->crc=crc_bytes(w->crc,packet,length);w->offset+=length;result=(int)length;
done:
    if(result<0)guarded_writer_abort(w);
    fw_unlock();return result;
}
static void invalidate(void)
{
    if(FAT_DIRTY)return; /* Never detach another operation's unflushed sector. */
    CACHE_TAG=0xffffffffu;WORD(0x03076d68)=0xffffffffu;WORD(0x03076918)=0;
}
/* Scan the entire supported physical parent without trusting cursor caches.
 * A matching FAT LFN fragment is conservatively a collision: our owned short
 * entry never has LFN records. Return count, or negative on I/O/ambiguity.
 */
static int name_index(const struct guarded_writer *w,const u8 *name,u32 *index,u8 *scratch)
{
    u8 short_name[11];int found=0;
    for(u32 j=0;j<11;++j)short_name[j]=j<4?name[j]:j<8?' ':name[j-3];
    u32 first=w->heap+(word(w->parent)-2)*w->spc;
    for(u32 s=0;s<w->spc;++s) {
        if(!read_sector(w->device,first+s,scratch))return -1;
        for(u32 row=0;row<16;++row) {
            const u8 *p=scratch+row*32;int equal=1;
            if(w->fs==3) {
                if(p[0]!=0xc1)continue;
                for(u32 j=0;j<8;++j)if(p[3+j*2] || upper(p[2+j*2])!=name[j])equal=0;
                if(equal) { *index=s*16+row-2;++found; }
            } else {
                if(!p[0] || p[0]==0xe5)continue;
                if(p[11]==15) {
                    static const u8 offsets[8]={1,3,5,7,9,14,16,18};
                    for(u32 j=0;j<8;++j)if(p[offsets[j]+1] || upper(p[offsets[j]])!=name[j])equal=0;
                    if(equal)return -1;
                } else {
                    for(u32 j=0;j<11;++j)if(upper(p[j])!=short_name[j])equal=0;
                    if(equal) { *index=s*16+row;++found; }
                }
            }
        }
    }
    return found;
}
static int closed_verify(struct guarded_writer *w,u8 *scratch)
{
    u8 alias[12],raw[12];u32 found=0;
    if(!fixed_name((const char *)w->name,raw) ||
       name_index(w,w->name,&found,scratch)!=1 || found!=w->index)return -1;
    invalidate();
    if(!read_sector(w->device,w->directory_lba,scratch))return -1;
    const u8 *entry=scratch+(w->index%16)*32;
    if(w->fs==3) {
        if(entry[0]!=0x85 || entry[1]!=2 || entry[32]!=0xc0 || entry[33]!=3 ||
           word(entry+40)!=w->total || word(entry+44) || word(entry+52)!=w->first ||
           word(entry+56)!=w->total || word(entry+60) || entry[64]!=0xc1 || entry[35]!=8 ||
           entry[4]!=0x20)return -1;
        for(u32 i=0;i<8;++i)if(entry[66+i*2]!=w->name[i] || entry[67+i*2])return -1;
        if(FW(0x0305b554,u32,const u8 *)(entry)!=(u32)(entry[2]|(u32)entry[3]<<8))return -1;
    } else if(word(entry+28)!=w->total ||
          ((u32)entry[20]<<16|(u32)entry[21]<<24|entry[26]|(u32)entry[27]<<8)!=w->first || entry[11]!=0x20)return -1;
    if((w->fs==3?FW(0x0305b2a2,int,u8 *,const u8 *,u32)(scratch,w->parent,w->index):
                     FW(0x0305b3ea,int,u8 *,u32,u32)(scratch,word(w->parent),w->index)))return -1;
    w->handle=w->fs==3?FW(0x0305c102,int,u8 *,const u8 *,u32,u32,const char *)(alias,w->parent,w->index,3,"R"):
                       FW(0x0305be12,int,u8 *,u32,u32,u32,const char *)(alias,word(w->parent),w->index,3,"R");
    if(w->handle<0 || w->handle>=8) { w->handle=-1;return -1; }
    u32 crc=0xffffffffu;
    for(u32 offset=0;offset<w->total;) {
        u32 n=w->total-offset<512?w->total-offset:512;
        if(FW(FREAD_ADDR,u32,void *,u32,u32)(scratch,n,(u32)w->handle)!=n)return -1;
        crc=crc_bytes(crc,scratch,n);offset+=n;
    }
    if(crc!=w->crc || fw_file_close(w->handle))return -1;
    w->handle=-1;return 0;
}
int guarded_writer_finish(struct guarded_writer *w)
{
    u8 scratch[512],raw[12];int result=-1;u32 found_index=0;
    if(!w)return -1;
    fw_lock();
    if(!writer_device(w) || !writer_handle(w) || !w->total ||
       w->offset!=w->total || !fixed_name((const char *)w->name,raw) ||
       name_index(w,w->name,&found_index,scratch)!=1 || found_index!=w->index ||
       !preload(w->device,w->directory_lba,scratch) ||
       !empty_entry(scratch+(w->index%16)*32,w->fs,(const char *)w->name,raw))goto done;
    if(fw_file_close(w->handle))goto done;
    w->handle=-1;
    if(closed_verify(w,scratch))goto done;
    w->verified=1;result=0;
done:
    if(result)guarded_writer_abort(w);
    invalidate();fw_unlock();return result;
}
void guarded_writer_abort(struct guarded_writer *w)
{
    if(!w)return;
    fw_lock();
    if(w->device==WORD(0x03076b2c) && w->fs==BYTE(0x03076b24) && w->handle>=0 && w->handle<8) {
        volatile u8 *fcb=(volatile u8 *)(0x03077668+(u32)w->handle*0x27e);
        if(word((const u8 *)fcb+12)==word(w->parent) && word((const u8 *)fcb+28)==w->index &&
           (!w->total || word((const u8 *)fcb+20)==w->first))fcb[0]=0;
    }
    w->handle=-1;w->verified=0;
    fw_unlock();
}

int guarded_writer_publish(struct guarded_writer *w)
{
    u8 expected[512],check[512];u16 unicode[9];u32 index=0;int result=-1;
    static const u8 source[]="BOOK.TMP",target[]="BOOK.M3U";
    if(!w)return -1;
    fw_lock();
    if(!writer_device(w) || !w->verified || w->handle!=-1 || w->offset!=w->total)goto done;
    for(u32 i=0;i<9;++i)if(w->name[i]!=source[i])goto done;
    if(name_index(w,target,&index,expected)!=0 || closed_verify(w,expected))goto done;
    if(!preload(w->device,w->directory_lba,expected))goto done;
    u8 *entry=expected+(w->index%16)*32;
    if(w->fs==3) {
        for(u32 i=0;i<9;++i)unicode[i]=target[i];
        for(u32 i=0;i<8;++i)entry[66+i*2]=target[i];
        u32 hash=FW(0x0305b64a,u32,const u16 *)(unicode);
        entry[36]=hash;entry[37]=hash>>8;
        u32 sum=FW(0x0305b554,u32,const u8 *)(entry);
        entry[2]=sum;entry[3]=sum>>8;
    } else { entry[8]='M';entry[9]='3';entry[10]='U'; }
    w->verified=0; /* Consume ownership before the single publication write. */
    int status=w->fs==3?FW(0x0305ec52,int,const u8 *,u32,const u8 *)(w->parent,w->index,entry):
                           FW(0x0305eba0,int,u32,u32,const u8 *)(word(w->parent),w->index,entry);
    if(status || !read_sector(w->device,w->directory_lba,check))goto done;
    for(u32 i=0;i<512;++i)if(check[i]!=expected[i])goto done;
    copy(w->name,target,9);result=0;
done:
    if(result)guarded_writer_abort(w);
    invalidate();fw_unlock();return result;
}
