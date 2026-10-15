#include "fw.h"
#include "order.h"
#include "natural.h"
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
static u8 folder[56],descriptor[72],entry[32],rows[2][624];
static u32 filter,kind,base,seen,dirs,fs,device;
static u32 valid __attribute__((section(".sort_metadata")))=0;
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
        if(after){if(work.count<1024)return -1;base+=work.count;}
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
