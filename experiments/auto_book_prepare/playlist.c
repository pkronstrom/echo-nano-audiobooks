#include "playlist.h"
static const char header[]="#EXTM3U\n#ECHO-BOOK-1\n",footer[]="#ECHO-END\n";
struct stream {
    struct book_playlist_workspace *workspace;
    book_write_fn write;void *context;
    uint32_t used,offset;
};
static int flush(struct stream *s)
{
    if(!s->used)return 1;
    if(s->write(s->context,s->offset,s->workspace->block,s->used)!=(int)s->used)return -1;
    s->offset+=s->used;s->used=0;return 1;
}
static int byte(struct stream *s,uint8_t c)
{
    if(!s->write)return 1;
    s->workspace->block[s->used++]=c;
    return s->used==512?flush(s):1;
}
static int text(struct stream *s,const char *p)
{
    while(*p)if(byte(s,(uint8_t)*p++)<0)return -1;
    return 1;
}
/* Validate before encoding; unpaired surrogates and path syntax cannot enter a
 * generated relative line. Prefix ./ prevents a leading # becoming a comment. */
static int name(struct stream *s,uint32_t *bytes,uint32_t *hash,uint32_t max_units)
{
    const uint16_t *p=s->workspace->name;
    if(!p[0] || (p[0]=='.' && (!p[1] || (p[1]=='.' && !p[2]))))return -1;
    uint32_t i=0;
    for(;i<127 && p[i];++i){
        uint32_t c=p[i];*hash=(*hash^c)*16777619u;
        if(c<32 || c=='/' || c=='\\' || c==':' || c=='*' || c=='?' ||
           c=='"' || c=='<' || c=='>' || c=='|')return -1;
        if(c>=0xd800 && c<=0xdbff){
            if(i+1>=127 || p[i+1]<0xdc00 || p[i+1]>0xdfff)return -1;
            *hash=(*hash^p[i+1])*16777619u;
            c=0x10000+((c-0xd800)<<10)+(p[++i]-0xdc00);
        }else if(c>=0xdc00 && c<=0xdfff)return -1;
        unsigned n=c<0x80?1:c<0x800?2:c<0x10000?3:4;
        *bytes+=n;
        if(n>1 && byte(s,(uint8_t)((n==2?0xc0:n==3?0xe0:0xf0)|(c>>(6*(n-1)))))<0)return -1;
        for(unsigned k=n-1;k;k--)if(byte(s,(uint8_t)(0x80|((c>>(6*(k-1)))&63)))<0)return -1;
        if(n==1 && byte(s,(uint8_t)c)<0)return -1;
    }
    if((i==127 && p[i]) || i>max_units)return -1;
    *hash=(*hash^0u)*16777619u;return 1;
}
static int scan(const struct book_playlist_source *source,struct stream *s,struct book_playlist_plan *plan)
{
    uint32_t bytes=sizeof header-1+sizeof footer-1,hash=2166136261u;
    if(!source || !source->name || !source->count || source->count>256 ||
       !source->prefix_units || source->prefix_units>247)return -1;
    hash=(hash^source->prefix_units)*16777619u;
    if(text(s,header)<0)return -1;
    for(uint32_t i=0;i<source->count;i++){
        if(source->name(source->context,i,s->workspace->name)!=1 || text(s,"./")<0 || name(s,&bytes,&hash,255-source->prefix_units)<0 || byte(s,'\n')<0)return -1;
        bytes+=3;
    }
    if(text(s,footer)<0 || flush(s)<0)return -1;
    *plan=(struct book_playlist_plan){bytes,hash,source->count};return 1;
}
int book_playlist_plan(const struct book_playlist_source *source,struct book_playlist_workspace *workspace,struct book_playlist_plan *plan)
{
    *plan=(struct book_playlist_plan){0};
    struct stream stream={.workspace=workspace};return scan(source,&stream,plan);
}
static int same(const struct book_playlist_plan *a,const struct book_playlist_plan *b)
{ return a->bytes==b->bytes && a->fingerprint==b->fingerprint && a->count==b->count; }
int book_playlist_emit(const struct book_playlist_source *source,struct book_playlist_workspace *workspace,const struct book_playlist_plan *plan,book_write_fn write,void *context)
{
    struct book_playlist_plan checked;
    if(!write || book_playlist_plan(source,workspace,&checked)<0 || !same(plan,&checked))return -1;
    struct stream stream={.workspace=workspace,.write=write,.context=context};
    return scan(source,&stream,&checked)>0 && same(plan,&checked)?1:-1;
}
void book_prepare_sector(void *output,uint32_t magic,book_crc_fn crc)
{
    uint8_t *p=output;
    for(unsigned i=0;i<512;i++)p[i]=0;
    for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(magic>>(8*i));
    uint32_t sum=crc(output,508);
    for(unsigned i=0;i<4;i++)p[508+i]=(uint8_t)(sum>>(8*i));
}
