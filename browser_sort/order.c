#include "order.h"
#include "natural.h"

static int compare(struct browser_order *w,const struct browser_order_provider *p,
                   uint32_t a,uint32_t b,int *error)
{
    unsigned da,db;
    int r;
    if(a==b)return 0;
    r=p->name(p->context,a,w->names[0],&da);
    if(r>=0)r=p->name(p->context,b,w->names[1],&db);
    if(r<0){*error=r;return 0;}
    if(da!=db)return da?-1:1;
    r=browser_natural_compare(w->names[0],w->names[1]);
    return r?r:(a>b?1:-1);
}
static void down(struct browser_order *w,const struct browser_order_provider *p,
                 unsigned n,unsigned at,int *error)
{
    uint32_t key=w->keys[at];
    unsigned child;
    while((child=at*2+1)<n){
        if(child+1<n && compare(w,p,w->keys[child],w->keys[child+1],error)<0)child++;
        if(*error || compare(w,p,key,w->keys[child],error)>=0)break;
        w->keys[at]=w->keys[child];at=child;
    }
    w->keys[at]=key;
}
int browser_order_window(struct browser_order *w,const struct browser_order_provider *p,
                         int has_after,uint32_t after)
{
    unsigned n=0,at,parent;
    uint32_t key,tmp;
    int error=p->reset(p->context),r;
    w->count=0;
    if(error<0)return error;
    error=0;
    while((r=p->next(p->context,&key))>0){
        if(has_after && compare(w,p,key,after,&error)<=0){if(error)break;continue;}
        if(error)break;
        if(n<BROWSER_ORDER_CAPACITY){
            at=n++;
            while(at){
                parent=(at-1)/2;
                if(compare(w,p,w->keys[parent],key,&error)>=0 || error)break;
                w->keys[at]=w->keys[parent];at=parent;
            }
            w->keys[at]=key;
        }else if(compare(w,p,key,w->keys[0],&error)<0){
            w->keys[0]=key;down(w,p,n,0,&error);
        }
        if(error)break;
    }
    if(r<0)error=r;
    for(at=n;!error && at>1;){
        tmp=w->keys[0];w->keys[0]=w->keys[--at];w->keys[at]=tmp;
        down(w,p,at,0,&error);
    }
    if(error)return error;
    w->count=n;return (int)n;
}
