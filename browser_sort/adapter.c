#include "fw.h"
#include "order.h"
#include "natural.h"
#include "queue.h"
#include "browser_playback.h"
#include "content_roots.h"
#include "../experiments/auto_book_prepare/playlist.h"
#include "../experiments/native_file_creation/guarded_create.h"
struct preparation {
    u32 keys[256],identity[256],count,prefix,native_device,lease;
    struct book_playlist_workspace encoder;
    struct guarded_writer writer;
    struct book_playlist_plan plan;
    u16 path[256];
    u8 parent[42];
};
static union {
    struct playlist_queue queue;
    struct preparation preparation;
    u8 saved_nodes[1248];
    u8 rows[2][624];
} temporary;
#define staged_queue temporary.queue
#define PREP temporary.preparation
#define rows temporary.rows
_Static_assert(sizeof(struct preparation)<=sizeof(struct playlist_queue),"preparation scratch exceeds dead launch queue");
#define DEVICE (*(volatile u8 *)0x0300d173)
#define B ((u8 *)0x03005f6c)
#define H(p) (*(u16 *)(p))
#define W(p) (*(u32 *)(p))
#define copy __builtin_memcpy
#define zero(p,n) __builtin_memset(p,0,n)
static int different(const void *a,const void *b,unsigned n)
{
    const u8 *x=a,*y=b;while(n--)if(*x++!=*y++)return 1;return 0;
}
static struct browser_order work;
static u8 folder[56],descriptor[72],entry[32];
static u32 filter,kind,base,seen,dirs,fs,device;
static u32 valid __attribute__((section(".sort_metadata")))=0;
static u8 preparing __attribute__((section(".sort_metadata")))=0;
static u8 preparation_error __attribute__((section(".sort_metadata")))=0;
extern int browser_sort_native_count(u32,void *,u32);
static int raw(u32 index,u8 *out)
{
    fw_wdt();
    return (fs==3?fw_exfat_entry(out,folder+12,index):
        FW(0x0305b3ea,int,u8 *,u32,u32)(out,W(folder+8),index))?-1:0;
}
/* Checked keyed names: native name helpers ignore read errors and FAT accepts
 * up to260 units. Never expose either behavior to the comparator or a node. */
static int load(u32 key,u16 *name,u8 *out)
{
    u8 e[32];unsigned n=0;
    if(raw(key,out))return -1;
    zero(name,512);
    if(fs==3){
        if(out[0]!=0x85 || raw(key+1,e) || e[0]!=0xc0 || !e[3])return -1;
        n=e[3];u8 attr=out[4],flags=e[1];u32 cluster=W(e+20),size=W(e+8);
        if(out[1]<1+(n+14)/15)return -1;
        for(unsigned j=0;j<n;j++){
            if(!(j%15) && (raw(key+2+j/15,e)||e[0]!=0xc1))return -1;
            name[j]=H(e+2+2*(j%15));if(!name[j])return -1;
        }
        FW(0x0305fa94,void,void *,const u16 *)(out,name);
        out[11]=attr;out[13]=flags;H(out+20)=cluster>>16;H(out+26)=cluster;W(out+28)=size;
        return 0;
    }
    if(!out[0] || out[0]==0xe5 || out[11]==15)return -1;
    u8 sum=0;for(unsigned j=0;j<11;j++)sum=(sum>>1)+(sum<<7)+out[j];
    static const u8 pos[13]={1,3,5,7,9,14,16,18,20,22,24,28,30};
    for(unsigned seq=1;key && seq<=20;seq++){
        if(raw(key-seq,e))return -1;
        if(e[11]!=15)break;
        if((e[0]&31)!=seq || e[13]!=sum || e[12] || H(e+26))return -1;
        for(unsigned j=0;j<13;j++){
            unsigned at=(seq-1)*13+j;u16 c=H(e+pos[j]);
            if(at<255)name[at]=c==0xffff?0:c;
            else if(c && c!=0xffff)return -1;
        }
        if(e[0]&64){if(name[0])return 0;return -1;}
        if(seq>=key)return -1;
    }
    zero(name,512);
    for(unsigned j=0;j<11;j++){
        if(j==8 && out[8]!=' ')name[n++]='.';
        if(out[j]!=' '){u16 c=out[j];if((out[12]&(j<8?8:16)) && c>='A' && c<='Z')c+=32;name[n++]=c;}
    }
    return n?0:-1;
}
static int reset(void *unused)
{
    (void)unused;zero(descriptor,sizeof descriptor);copy(descriptor+28,folder+12,42);
    W(descriptor)=W(folder+8);W(descriptor+8)=H(folder);seen=dirs=0;return 0;
}
static int next(void *unused,uint32_t *key)
{
    (void)unused;
    fw_wdt();
    int r=FW(0x0305dcb4,int,void *,void *,u32,u32)(entry,descriptor,filter,kind);
    if(r)return seen==H(folder)&&dirs==H(folder+4)?0:-1;
    if(++seen>H(folder))return -1;
    if(entry[11]&16)dirs++;
    *key=W(descriptor+4)-1;return 1;
}
static int name(void *unused,uint32_t key,u16 out[256],unsigned *directory)
{
    (void)unused;u8 e[32];if(load(key,out,e))return -1;*directory=!!(e[11]&16);return 0;
}
static const struct browser_order_provider provider={0,reset,next,name};
static int page(u32 rank)
{
    if(!valid || rank<base){base=0;valid=0;}
    while(!valid || rank>=base+work.count){
        int after=valid;u32 pivot=after?work.keys[work.count-1]:0;
        if(after){if(work.count<BROWSER_ORDER_CAPACITY)return -1;base+=work.count;}
        valid=0;if(browser_order_window(&work,&provider,after,pivot)<0)return -1;
        valid=1;if(!work.count)return -1;
    }
    return 0;
}
static void clear(void *nodes,void *f)
{
    valid=0;H(f)=H((u8 *)f+2)=H((u8 *)f+4)=0;H(B+8)=0;
    u8 *p=nodes;for(unsigned i=0;i<2 && p;i++){
        p[0x4e]=0xff;zero(p+0x4f,32);zero(p+0x70,512);p=(void *)W(p+4);
    }
}
/* Find the key represented by stock physical ordinal (reentry), or by child
 * cluster (Back), then locate its rank through bounded sorted windows. */
static int restore(u32 target,int cluster,u32 *rank)
{
    uint32_t key=0;u32 index=0,found=0;unsigned nd=0,nf=0;int r;
    reset(0);
    while((r=next(0,&key))>0){
        if(cluster){if((entry[11]&16) && (((u32)H(entry+20)<<16)|H(entry+26))==target){index=key;found=1;}}
        else {u32 ordinal=(entry[11]&16)?nd++:H(folder+4)+nf++;if(ordinal==target){index=key;found=1;}}
    }
    if(r<0)return -1;
    *rank=0;if(!found)return 0;
    valid=0;base=0;
    for(u32 at=0;at<H(folder);at+=work.count){
        if(page(at))return -1;
        for(unsigned j=0;j<work.count;j++)if(work.keys[j]==index){*rank=at+j;return 0;}
    }
    return -1;
}
void browser_sort_enumerate(u32 f,void *nodes,void *record,u32 start,u32 k)
{
    u32 caller=(u32)__builtin_return_address(0)&~1u;
    fw_lock();
    if(!valid || filter!=f || kind!=k || fs!=FS_TYPE || device!=DEVICE || different(folder,record,54)){
        valid=0;copy(folder,record,54);filter=f;kind=k;fs=FS_TYPE;device=DEVICE;base=0;
    }
    if(caller==0x030798c8 || caller==0x03079cee){
        u32 rank;unsigned depth=H(B+0x1cc);
        u32 target=caller==0x03079cee?W(B+56*(depth+1)+(fs==3?24:20)):start+H(B+0x1ee);
        if(restore(target,caller==0x03079cee,&rank))goto fail;
        start=rank&~1u;H(B+0x1ce +2*depth)=start;H(B+0x1ee)=H(B+0x1f0)=rank&1;
    }
    if(start>=H(folder)){clear(nodes,record);goto done;}
    unsigned count=H(folder)-start;if(count>2)count=2;
    for(unsigned i=0;i<count;i++){
        if(page(start+i))goto fail;
        u32 key=work.keys[start+i-base];u8 *p=rows[i];
        zero(p,624);W(p+8)=W(folder+8);W(p+12)=key;copy(p+0x24,folder+12,42);
        if(load(key,(u16 *)(p+0x70),p+0x4f))goto fail;
        p[0x4e]=(p[0x5a]&16)?0:kind==1?1:*FW(0x03079484,u8 *,void *)(p+0x4f);
    }
    u8 *p=nodes;
    for(unsigned i=0;i<2;i++){
        if(i<count)copy(p+8,rows[i]+8,616);
        else {p[0x4e]=0xff;zero(p+0x70,512);}
        p=(void *)W(p+4);
    }
    goto done;
fail:clear(nodes,record);
done:fw_unlock();
}
int browser_sort_count(u32 f,void *record,u32 k)
{
    valid=0;return browser_sort_native_count(f,record,k);
}
int browser_sort_validate(const u8 *node)
{
    if(node[0x4e]==0xff)return 0;
    /* exFAT's native short alias contains a clock-derived suffix (305fa94).
     * Its first11 bytes are not identity. Keep the stable metadata and full
     * UTF16 name check; FAT's on-disk short name remains part of identity. */
    unsigned skip=fs==3?11:0;
    fw_lock();int ok=valid && device==DEVICE && fs==FS_TYPE && W(node+8)==W(folder+8) &&
        !load(W(node+12),work.names[0],entry) &&
        !different(entry+skip,node+0x4f+skip,32-skip) &&
        !different(work.names[0],node+0x70,512);
    if(!ok)clear((void *)W(B),B+56*H(B+0x1cc)+12);
    fw_unlock();return ok;
}

/* 0 refuses, 1 preserves native navigation, 2 completed an ordered launch.
 * The staged queue stays in browser memory only until the resident API has
 * stopped/saved the old context and copied it synchronously. */
int browser_sort_select(const u8 *node)
{
    if(!browser_sort_validate(node))return 0;
    if(node[0x4e]!=1 || H((u8 *)0x0300ec1c+8)!=3)return 1;
    fw_lock();
    staged_queue.count=0;staged_queue.signature=0;
    u32 selected=0,target=W(node+12);
    for(u32 rank=0;rank<H(folder);rank++){
        if(page(rank))goto fail;
        u32 key=work.keys[rank-base];
        if(load(key,work.names[0],entry))goto fail;
        if(entry[11]&16 || *FW(0x03079484,u8 *,void *)(entry)!=1)continue;
        unsigned units=0;while(units<256 && work.names[0][units])units++;
        u32 n=staged_queue.count,cluster=(u32)H(entry+20)<<16|H(entry+26);
        if(n==PLAYLIST_CAPACITY || key>=65536 || cluster<2 ||
           (fs==3 && (units>127 || W(folder+24)>255)))goto fail;
        staged_queue.tracks[n]=(struct queued_file){W(folder+8),fs==3?W(folder+16):0,cluster};
        staged_queue.indices[n]=key;staged_queue.flags[n]=fs==3?W(folder+24):0;
        staged_queue.count=n+1;
        if(key==target)selected=n+1;
    }
    fw_unlock();
    if(!selected)return 0;
    return FW(FOLDER_LAUNCH_ADDR,int,const struct playlist_queue *,u32)
        (&staged_queue,selected)?2:0;
fail:
    staged_queue.count=0;fw_unlock();return 0;
}

/* Preparation borrows the inactive folder-launch queue. Names and physical
 * identities are rescanned for each emission pass; filesystem ownership is
 * serialized with the existing nonblocking journal writer guard. */
static int equal_ascii(const u16 *text,const char *literal)
{
    while(*literal){u16 c=*text++;if(c>='a'&&c<='z')c-=32;
        if(c!=(u8)*literal++)return 0;}
    return !*text;
}
static int playlist_name(const u16 *text)
{
    unsigned n=0;while(n<256 && text[n])n++;
    return n>=4 && equal_ascii(text+n-4,".M3U");
}
static u32 identity(const u8 *e)
{
    u32 hash=2166136261u;
    for(unsigned i=fs==3?11:0;i<32;i++)hash=(hash^e[i])*16777619u;
    return hash;
}
static int same_medium(void)
{
    return PREP.native_device==W((u8 *)0x03076b2c) &&
           PREP.lease==((u32)FS_TYPE<<8|DEVICE);
}
static int prepared_name(void *unused,uint32_t index,u16 out[128])
{
    (void)unused;int result=-1;
    fw_lock();
    if(index<PREP.count && same_medium() && device==DEVICE && fs==FS_TYPE &&
       !load(PREP.keys[index],work.names[0],entry) &&
       identity(entry)==PREP.identity[index]){
        unsigned n=0;while(n<128 && work.names[0][n])n++;
        if(n && n<128){copy(out,work.names[0],(n+1)*2);result=1;}
    }
    fw_unlock();return result;
}
static int prepared_write(void *unused,uint32_t offset,const void *data,uint32_t length)
{
    (void)unused;
    if(!same_medium() || offset!=PREP.writer.offset)return -1;
    fw_wdt();return guarded_writer_packet(&PREP.writer,data,length);
}
static int companion(const char *extension,u32 magic)
{
    if(!same_medium())return -1;
    unsigned n=PREP.prefix;
    static const char base[]="BOOK.";
    for(unsigned i=0;i<5;i++)PREP.path[n+i]=(u8)base[i];
    for(unsigned i=0;i<3;i++)PREP.path[n+5+i]=(u8)extension[i];
    PREP.path[n+8]=0;
    struct media_ref ref;
    int found=FW(BOOK_LOOKUP_ADDR,int,const u16 *,struct media_ref *)(PREP.path,&ref);
    if(found<0 || !same_medium())return -1;
    if(found){
        if(ref.size!=1024 || (ref.attrs&17))return -1;
        int h=FW(BOOK_OPEN_ADDR,int,const struct media_ref *)(&ref);
        if(h<0)return -1;
        int valid_sector=0,failed=0;
        for(unsigned slot=0;slot<2;slot++){
            if(FW(BOOK_READ_ADDR,int,int,u32,u8 *,u32)(h,slot*512,PREP.encoder.block,512)!=512){failed=1;break;}
            int sane=1;
            if(magic==0x31424e45){
                u32 count=W(PREP.encoder.block+12);if(count>60)sane=0;
                for(u32 i=0;sane && i<count;i++)if(!W(PREP.encoder.block+16+i*8) || W(PREP.encoder.block+16+i*8)>256)sane=0;
            }
            if(sane && W(PREP.encoder.block)==magic && W(PREP.encoder.block+508)==
               FW(BOOK_CRC_ADDR,u32,const void *,u32)(PREP.encoder.block,508))valid_sector=1;
        }
        FW(BOOK_CLOSE_ADDR,void,int)(h);
        return !failed && valid_sector && same_medium()?0:-1;
    }
    char name[9]="BOOK.";
    for(unsigned i=0;i<3;i++)name[5+i]=extension[i];
    name[8]=0;
    if(!same_medium() || guarded_writer_begin(&PREP.writer,PREP.parent,name,PREP.native_device,fs,1024))return -1;
    book_prepare_sector(PREP.encoder.block,magic,FW(BOOK_CRC_ADDR,uint32_t,const void *,uint32_t));
    for(unsigned i=0;i<2;i++)if(!same_medium() || guarded_writer_packet(&PREP.writer,PREP.encoder.block,512)!=512)return -1;
    return same_medium()?guarded_writer_finish(&PREP.writer):-1;
}

/* Caller has freshly resolved this physical child and its normalized path.
 * Return1 prepared/previously prepared,0 outside supported unambiguous shape,
 * -1 refusal/failure. Existing files are never repaired or replaced. */
int browser_prepare_book(const u8 parent[42],const u16 *path,u32 native_device,u32 lease)
{
    u8 saved_folder[56];u32 saved_fs=fs,saved_device=device,saved_valid=valid;
    int result=-1,book=0,custom=0,temporary_file=0,nested=0,overflow=0;
    unsigned length=0;
    if(preparing || !parent || !path || path[0]!='/' ||
       native_device!=W((u8 *)0x03076b2c) || lease!=((u32)FS_TYPE<<8|DEVICE))return -1;
    while(length<248 && path[length])length++;
    if(!length || length>=248 || path[length-1]=='/')return -1;
    if(!FW(BOOK_WRITE_TRY_ADDR,int,void)())return -1;
    preparing=1;copy(saved_folder,folder,56);zero(&PREP,sizeof PREP);
    PREP.writer.handle=-1;copy(PREP.parent,parent,42);copy(PREP.path,path,(length+1)*2);
    PREP.native_device=native_device;PREP.lease=lease;
    PREP.path[length]='/';PREP.path[length+1]=0;PREP.prefix=length+1;
    fs=FS_TYPE;device=DEVICE;zero(folder,56);W(folder+8)=W(parent);copy(folder+12,parent,42);
    u32 limit=W((u8 *)0x03076b34)*16;
    if(!limit || PREP.prefix>247)goto done;
    /* Large clusters are outside creation's bound, not outside playback's.
     * Keep the existing playlist/native folder route, as for large directories. */
    if(limit>4096){result=0;goto done;}
    fw_lock();
    /* Generation only scans a single cluster. A larger directory must reach
     * existing native playlist handling unchanged, even when its BOOK/custom
     * M3U lies past the scanned prefix. Probe on an independent cursor. */
    u8 probe[42];copy(probe,parent,42);
    int beyond=fs==3?fw_exfat_entry(entry,probe,limit):
        FW(0x0305b3ea,int,u8 *,u32,u32)(entry,W(parent),limit);
    if(!beyond){result=0;fw_unlock();goto done;}
    for(u32 key=0;key<limit;key++){
        if(raw(key,entry)){fw_unlock();goto done;}
        if(!entry[0])break;
        if(fs==3?entry[0]!=0x85:entry[0]==0xe5 || entry[11]==15 || (entry[11]&8) || entry[0]=='.')continue;
        if(load(key,work.names[0],entry)){fw_unlock();goto done;}
        if(equal_ascii(work.names[0],".AUDIOBOOK") || equal_ascii(work.names[0],".MEDITATION")){
            result=0;fw_unlock();goto done;
        }
        if(entry[11]&16){nested=1;continue;}
        if(playlist_name(work.names[0])){
            if(equal_ascii(work.names[0],"BOOK.M3U"))book=1;else custom=1;
        }
        if(equal_ascii(work.names[0],"BOOK.TMP"))temporary_file=1;
        if((entry[11]&6) || work.names[0][0]=='.' || *FW(0x03079484,u8 *,void *)(entry)!=1)continue;
        if(PREP.count==256){overflow=1;continue;}
        PREP.keys[PREP.count]=key;PREP.identity[PREP.count++]=identity(entry);
    }
    fw_unlock();
    if(!book && (custom || nested || !PREP.count)){result=0;goto done;}
    if(!book && (temporary_file || overflow))goto done;
    struct book_playlist_source source={0,PREP.count,prepared_name,PREP.prefix};
    if(!book){
        /* Only256 keys; insertion ordering avoids a second large key buffer. */
        fw_lock();
        for(u32 i=1;i<PREP.count;i++){
            u32 key=PREP.keys[i],id=PREP.identity[i],j=i;
            if(load(key,work.names[0],entry)){fw_unlock();goto done;}
            while(j){
                if(load(PREP.keys[j-1],work.names[1],entry)){fw_unlock();goto done;}
                int order=browser_natural_compare(work.names[0],work.names[1]);
                if(order>0 || (!order && key>PREP.keys[j-1]))break;
                PREP.keys[j]=PREP.keys[j-1];PREP.identity[j]=PREP.identity[j-1];j--;
            }
            PREP.keys[j]=key;PREP.identity[j]=id;
        }
        fw_unlock();
        if(book_playlist_plan(&source,&PREP.encoder,&PREP.plan)!=1)goto done;
    }
    if(companion("RSM",0x31524e45) || companion("BMK",0x31424e45))goto done;
    if(!book){
        if(!same_medium() || guarded_writer_begin(&PREP.writer,PREP.parent,"BOOK.TMP",PREP.native_device,fs,PREP.plan.bytes))goto done;
        if(book_playlist_emit(&source,&PREP.encoder,&PREP.plan,prepared_write,0)!=1 ||
           !same_medium() || guarded_writer_finish(&PREP.writer) || !same_medium() || guarded_writer_publish(&PREP.writer))goto done;
    }
    result=same_medium()?1:-1;
done:
    if(PREP.writer.handle>=0)guarded_writer_abort(&PREP.writer);
    /* The parent's key window was never modified: only child names use its
     * transient comparator buffers. Keep it valid for native Enter after a
     * no-op, and after writes confined to the child's unchanged directory. */
    valid=result>=0 && same_medium()?saved_valid:0;
    copy(folder,saved_folder,56);fs=saved_fs;device=saved_device;
    preparing=0;FW(BOOK_WRITE_END_ADDR,void,void)();return result;
}

static int eligible(const u8 *node)
{
    u32 depth=H(B+0x1cc),count=*(u8 *)BOOK_ROOT_COUNT_ADDR;
    if(depth>7 || count>8 || H((u8 *)0x0300ec1c+8)!=3 || node[0x4e] ||
       *(u8 *)BOOK_CHOOSER_ADDR || *(u8 *)BOOK_MENU_ACTIVE_ADDR || *(u8 *)BOOK_MENU_RETURNING_ADDR)return 0;
    const struct content_root *roots=(const void *)BOOK_ROOTS_ADDR;
    /* A marked meditation ancestor always keeps its ordinary browser route. */
    for(u32 n=0;n<count;n++)if((roots[n].kind&2) && roots[n].depth<=depth){
        unsigned level=0;
        while(level<roots[n].depth && W(B+56*(level+1)+(FS_TYPE==3?24:20))==roots[n].cluster[level])level++;
        if(level==roots[n].depth)return 0;
    }
    for(u32 n=0;n<count;n++){
        const struct content_root *r=roots+n;
        if(!(r->kind&1) || r->depth>depth)continue;
        unsigned level=0;
        while(level<r->depth && W(B+56*(level+1)+(FS_TYPE==3?24:20))==r->cluster[level])level++;
        if(level!=r->depth || !FW(BOOK_DIRECTORY_ADDR,int,const u8 *,u16 *)(node,PREP.path))continue;
        /* Cached ancestry only narrows eligibility. A live marker lookup is
         * required on the current card before writing anything. */
        unsigned at=1,component=0;
        if(r->depth){
            while(PREP.path[at] && component<r->depth){if(PREP.path[at]=='/')component++;at++;}
            if(component!=r->depth)continue;
        }
        if(at+11>=256)continue;
        u16 saved[12];copy(saved,PREP.path+at,24);
        const char *marker=".audiobook";
        for(unsigned i=0;i<=10;i++)PREP.path[at+i]=(u8)marker[i];
        struct media_ref ref;int ok=FW(BOOK_LOOKUP_ADDR,int,const u16 *,struct media_ref *)(PREP.path,&ref);
        copy(PREP.path+at,saved,24);
        if(ok==1 && !(ref.attrs&16))return 1;
    }
    return 0;
}
u32 browser_book_event(u32 message)
{
    if(preparation_error){
        if(message==0x40000040 || message==0x20000040 || message==0x40001000){
            u8 *p=(void *)W(B);
            for(unsigned i=0;i<2;i++){copy(p,temporary.saved_nodes+i*624,624);p=(void *)W(p+4);}
            preparation_error=0;FW(0x0306b040,void,u32)(333);FW(0x0306b040,void,u32)(335);
        }
        return 1;
    }
    if(message==0x40000040 && !preparing){
        u32 native_device=W((u8 *)0x03076b2c),lease=(u32)FS_TYPE<<8|DEVICE;
        u8 *node=(void *)W(B);if(H(B+0x1ee))node=(void *)W(node+4);
        if(eligible(node)){
            u8 parent[42]={0};u16 path[256];copy(path,PREP.path,512);
            struct media_ref ref;
            int resolved=FW(BOOK_LOOKUP_ADDR,int,const u16 *,struct media_ref *)(path,&ref);
            if(resolved==1 && (ref.attrs&16) && ref.cluster==((u32)H(node+0x63)<<16|H(node+0x69)) && ref.index==W(node+12)){
                W(parent)=ref.cluster;W(parent+4)=ref.size;
                parent[12]=FS_TYPE==3?ref.flags:1;parent[13]=ref.attrs;
            }
            if(!W(parent) || browser_prepare_book(parent,path,native_device,lease)<0){
                u8 *p=(void *)W(B);const char *labels[2]={"Prepare failed","Use host tool"};
                for(unsigned i=0;i<2;i++){
                    copy(temporary.saved_nodes+i*624,p,624);zero(p+0x70,512);p[0x4e]=0xff;
                    for(unsigned j=0;labels[i][j];j++)H(p+0x70+j*2)=(u8)labels[i][j];
                    p=(void *)W(p+4);
                }
                preparation_error=1;FW(0x0306b040,void,u32)(333);FW(0x0306b040,void,u32)(335);return 1;
            }
        }
    }
    return FW(BOOK_NAV_EVENT_ADDR,u32,u32)(message);
}
