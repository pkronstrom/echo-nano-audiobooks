#include "content_roots.h"
static u16 u16le(const u8 *p) { return p[0] | (u16)p[1]<<8; }
static u32 u32le(const u8 *p) { return u16le(p) | (u32)u16le(p+2)<<16; }
struct reader { media_read_fn read; void *ctx; u32 left; int fs; };
static int get(struct reader *r, struct media_dir *d, u32 i, u8 *e)
{
    if (!r->left) return -1;
    r->left--;
    int v=r->read(r->ctx,r->fs,d,i,e);
    return v == 9 ? 0 : v ? -2 : e[0] ? 1 : 0;
}
static u8 mark(const u16 *n, u32 len)
{
    static const char *names[]={".audiobook", ".meditation"};
    for (u32 k=0;k<2;k++) {
        u32 j=0;
        for (; j<len && names[k][j]; j++) {
            u16 c=n[j]; if(c>='A' && c<='Z') c+=32;
            if(c!=(u8)names[k][j]) break;
        }
        if(j==len && !names[k][j]) return 1<<k;
    }
    return 0;
}
static __attribute__((noinline)) u16 sum16(u16 sum, const u8 *e, int primary)
{
    for(u32 j=0;j<32;j++) if(!primary || (j!=2 && j!=3))
        sum=(sum>>1)+(sum<<15)+e[j];
    return sum;
}
/* One physical entry/set; directories need no full name buffer. */
static int next(struct reader *r, struct media_dir *d, u32 *pos,
                struct media_ref *ref, u8 *marker)
{
    u8 e[32]; u16 name[13];
    *marker=0;
    u32 index=(*pos)++;
    int v=get(r,d,index,e); if(v<=0) return v;
    ref->attrs=0; ref->cluster=0;
    if(!r->fs) {
        u8 pending=0, sum=0;
        if(e[0]==0x41 && e[11]==15 && !e[12] && !u16le(e+26)) {
            static const u8 off[]={1,3,5,7,9,14,16,18,20,22,24,28,30};
            for(u32 j=0;j<13;j++) name[j]=u16le(e+off[j]);
            sum=e[13]; pending=1;
            index=(*pos)++;
            v=get(r,d,index,e); if(v<=0) return v;
        }
        if(e[0]==0xe5 || e[11]==15 || (e[11]&8) || e[0]=='.') return 1;
        if(pending && !(e[11]&16)) {
            u8 s=0; for(u32 j=0;j<11;j++) s=(s>>1)+((s&1)<<7)+e[j];
            u32 n=0; while(n<13 && name[n] && name[n]!=0xffff) n++;
            int valid=n<13 && !name[n];
            for(u32 j=n+1;j<13;j++) if(name[j]!=0xffff) valid=0;
            if(s==sum && valid) *marker=mark(name,n);
        }
        ref->cluster=(u32)u16le(e+20)<<16 | u16le(e+26);
        ref->size=u32le(e+28); ref->flags=0; ref->attrs=e[11];
    } else {
        if(e[0]!=0x85 || e[1]<2) return 1;
        u8 count=e[1], attrs=e[4]; u16 expected=u16le(e+2), sum=sum16(0,e,1);
        u32 length=0; int valid=!(u16le(e+4)&~0x37);
        for(u32 s=1;s<=count;s++) {
            v=get(r,d,(*pos)++,e); if(v<=0) return v<0?v:-2;
            sum=sum16(sum,e,0);
            if(s==1) {
                length=e[3]; ref->flags=e[1]; ref->cluster=u32le(e+20); ref->size=u32le(e+24);
                if(e[0]!=0xc0 || !length || count!=1+(length+14)/15 ||
                   (e[1]&~3) || !(e[1]&1) || u32le(e+28) || u32le(e+12) ||
                   u32le(e+8)>ref->size) valid=0;
            } else {
                if(e[0]!=0xc1) valid=0;
                for(u32 j=0;j<15 && (s-2)*15+j<length;j++) {
                    u16 c=u16le(e+2+j*2);
                    if(!c || c==0xffff || c=='/' || c=='\\') valid=0;
                    if(s==2 && j<13) name[j]=c;
                }
            }
        }
        if(!valid || sum!=expected) {ref->cluster=0;return 1;}
        ref->attrs=attrs;
        if(!(attrs&24) && length<=13) *marker=mark(name,length);
    }
    ref->parent=*d; ref->index=index; ref->filesystem=r->fs?3:2;
    return 1;
}
int content_scan(media_read_fn read, void *ctx, int fs, struct content_root *roots,u32 cap)
{
    struct reader r={read,ctx,65536,fs};
    struct media_dir dirs[8]={{0}};
    u32 positions[8]={0}; u8 kinds[8]={0};
    struct content_root path={0};
    u32 count=0, visited=1, depth=0;
    for(;;) {
        struct media_ref ref; u8 marker;
        int v=next(&r,&dirs[depth],&positions[depth],&ref,&marker);
        if(v<0) return v;
        if(!v) {
            if(kinds[depth]) {
                if(count>=cap || count>=CONTENT_ROOT_MAX) return -1;
                path.depth=depth; path.kind=kinds[depth]; roots[count++]=path;
            }
            if(!depth) return count;
            depth--; continue;
        }
        kinds[depth]|=marker;
        if((ref.attrs&0x1e)!=16 || ref.cluster<2 || ref.cluster>=CLUSTER_BAD || depth==7) continue;
        int cycle=0;
        for(u32 j=0;j<=depth;j++) if(dirs[j].cluster==ref.cluster) cycle=1;
        if(cycle) continue;
        if(++visited>2048 || ref.index>65535) return -1;
        path.index[depth]=ref.index; path.cluster[depth]=ref.cluster;
        depth++; dirs[depth]=(struct media_dir){ref.cluster,ref.size,0,ref.flags};
        positions[depth]=0; kinds[depth]=0;
    }
}
int content_root_chain(media_read_fn read,void *ctx,int fs,
                       const struct content_root *root,struct media_ref out[7])
{
    if(root->depth>7) return 0;
    struct reader r={read,ctx,65536,fs}; struct media_dir d={0};
    for(u32 j=0;j<root->depth;j++) {
        u32 pos=root->index[j]; u8 marker;
        int v=next(&r,&d,&pos,&out[j],&marker);
        if(v<0)return v;
        if(!v || (out[j].attrs&0x1e)!=16 || out[j].cluster!=root->cluster[j] ||
           out[j].cluster<2 || out[j].cluster>=CLUSTER_BAD) return 0;
        d=(struct media_dir){out[j].cluster,out[j].size,0,out[j].flags};
    }
    return 1;
}
