#include "natural.h"
static unsigned peek(const unsigned short *s,unsigned i){return i<256?s[i]:0;}
static int digit(unsigned c){return c>='0' && c<='9';}
static unsigned fold(unsigned c)
{
    if((c>='A' && c<='Z') || (c>=0xc0 && c<=0xde && c!=0xd7))c+=32;
    return c;
}
int browser_natural_compare(const unsigned short *a,const unsigned short *b)
{
    unsigned i=0,j=0;
    for(;;){
        unsigned x=peek(a,i),y=peek(b,j);
        if(digit(x) && digit(y)){
            while(peek(a,i)=='0')i++;
            while(peek(b,j)=='0')j++;
            unsigned ae=i,be=j;
            while(digit(peek(a,ae)))ae++;
            while(digit(peek(b,be)))be++;
            if(ae-i!=be-j)return ae-i<be-j?-1:1;
            while(i<ae){x=peek(a,i++);y=peek(b,j++);if(x!=y)return x<y?-1:1;}
            continue;
        }
        x=fold(x);y=fold(y);
        if(x!=y)return x<y?-1:1;
        if(!x)return 0;
        i++;j++;
    }
}
