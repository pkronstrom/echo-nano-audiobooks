/* Shared with the sanitizer-tested host prototype. */
#include "../experiments/audiobook_speed/speed.c"
/* Freestanding overlap-safe copy; no allocator or hosted libc dependency. */
void *memmove(void *destination,const void *source,size_t length)
{
    unsigned char *d=destination;const unsigned char *s=source;
    if((uintptr_t)d<(uintptr_t)s){for(size_t i=0;i<length;i++)d[i]=s[i];}
    else if(d!=s){while(length){length--;d[length]=s[length];}}
    return destination;
}
