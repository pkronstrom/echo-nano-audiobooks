#include "speed.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef SPEED_TEST_METRICS
extern uint32_t speed_test_peak_comparisons;
#endif
static uint32_t random_state = 1;
static uint32_t rnd(void) { random_state ^= random_state << 13; random_state ^= random_state >> 17; random_state ^= random_state << 5; return random_state; }
static size_t run(unsigned fs, unsigned channels, unsigned q, const int16_t *src,
                  size_t frames, size_t chunk, size_t room, int16_t *dst) {
    struct { uint64_t a; speed_state s; uint64_t b; } guard = {0};
    guard.a = guard.b = UINT64_C(0x0123456789abcdef);
    assert(speed_init(&guard.s, fs, channels, q) == 0);
    size_t used = 0, made = 0, iterations = 0;
    uint64_t mapped=0;
    for (;;) {
        size_t n = frames - used; if (n > chunk) n = chunk;
        int16_t block[4098 * 2];
        for (size_t j=0;j<sizeof block/sizeof *block;j++) block[j]=12345;
        speed_result r;
        assert(speed_process(&guard.s, n ? src + used * channels : NULL, n,
               used+n == frames, block+2, room, &r) == 0);
        assert(r.consumed <= n && r.produced <= room);
        assert(block[0] == 12345 && block[1] == 12345);
        assert(block[2 + room*channels] == 12345);
        assert(guard.a == UINT64_C(0x0123456789abcdef) && guard.b == guard.a);
        used += r.consumed;
        assert(r.source_begin==mapped && r.source_end>=mapped);
        assert(r.source_end-r.source_begin>=r.produced);
        assert(r.source_end-r.source_begin<=2*r.produced);
        assert(r.source_end<=guard.s.retired && r.source_end<=used);
        if(q==4) assert(r.source_begin==made && r.source_end==made+r.produced);
        speed_packet packet; uint64_t position;
        assert(speed_packet_init(&packet,&r)==0);
        assert(speed_packet_position(&packet,0,&position)==0 && position==mapped);
        assert(speed_packet_position(&packet,(uint32_t)r.produced,&position)==0 && position==r.source_end);
        mapped=r.source_end;
        memcpy(dst + made*channels, block+2, r.produced*channels*sizeof *dst);
        made += r.produced;
        assert(used <= frames && made <= frames);
        if (r.done) break;
        assert(++iterations < frames*4 + 10000);
        assert(r.consumed || r.produced);
    }
    assert(used == frames && mapped == frames && guard.s.emitted_source == frames);
    assert(guard.s.accepted == frames && guard.s.retired == frames);
    assert(guard.s.produced == made && guard.s.dropped + made == frames);
    long target = (long)(frames*4/q);
    assert(labs((long)made-target) <= (long)(fs/65 + 1));
    return made;
}
static void format_matrix(void) {
    const unsigned rates[] = {8000,11025,11999,16000,22050,24000,44100,48000};
    const size_t lengths[] = {0,1,7,122,255,738,1475,1476,2049,10000};
    int16_t src[20000],a[20000],b[20000];
    for(size_t i=0;i<20000;i++) src[i]=(int16_t)rnd();
    for(size_t f=0;f<sizeof rates/sizeof *rates;f++)
      for(unsigned c=1;c<=2;c++) for(unsigned q=4;q<=8;q++)
       for(size_t k=0;k<sizeof lengths/sizeof *lengths;k++) {
        size_t n=lengths[k];
        size_t na=run(rates[f],c,q,src,n,7,1,a);
        size_t nb=run(rates[f],c,q,src,n,2048,4096,b);
        assert(na == nb && !memcmp(a,b,na*c*sizeof *a));
        if(q==4) assert(na==n && !memcmp(src,a,n*c*sizeof *a));
       }
}
static void pitch_and_stereo(void) {
    const unsigned fs=48000; const size_t n=96000;
    int16_t *src=malloc(n*2*sizeof *src), *out=malloc(n*2*sizeof *out);
    assert(src && out);
    for(size_t i=0;i<n;i++) { src[2*i]=(int16_t)(12000*sin(6.283185307179586*125*i/fs)); src[2*i+1]=-src[2*i]; }
    for(unsigned layout=0;layout<2;layout++) {
      if(layout) for(size_t i=0;i<n;i++) src[2*i]=0;
      for(unsigned q=5;q<=8;q++) {
        size_t made=run(fs,2,q,src,n,256,97,out); size_t crosses=0;
        for(size_t i=1;i<made;i++) {
            if(!layout) assert(abs(out[2*i]+out[2*i+1])<=1);
            else assert(out[2*i]==0);
            if(out[2*(i-1)+1]<=0 && out[2*i+1]>0) crosses++;
        }
        double hz=(double)crosses*fs/made;
        assert(fabs(hz-125)<2);
      }
    }
    free(src);free(out);
}
static void pitch_matrix(void) {
    const unsigned rates[]={8000,22050,44100,48000};
    const unsigned frequencies[]={65,73,85,98,110,125,147,173,211,257,311,347,400};
    int16_t *src=malloc(96000*sizeof *src),*out=malloc(96000*sizeof *out);
    assert(src && out);
    double worst_relative=0;
    for(unsigned f=0;f<sizeof rates/sizeof *rates;f++)
      for(unsigned h=0;h<sizeof frequencies/sizeof *frequencies;h++)
       for(unsigned shape=0;shape<2;shape++) {
        unsigned fs=rates[f],hz=frequencies[h];size_t n=2*fs;
        for(size_t i=0;i<n;i++) {
            double phase=6.283185307179586*hz*i/fs;
            double signal=sin(phase);
            if(shape) signal=(signal+0.35*sin(2*phase)+0.2*sin(3*phase))*(0.6+0.4*sin(6.283185307179586*3*i/fs));
            src[i]=(int16_t)(15000*signal);
        }
        for(unsigned q=5;q<=8;q++) {
            size_t made=run(fs,1,q,src,n,256,128,out),crosses=0;
            for(size_t i=1;i<made;i++) if(out[i-1]<=0 && out[i]>0) crosses++;
            double measured=(double)crosses*fs/made,relative=fabs(measured-hz)/hz;
            if(relative>worst_relative) worst_relative=relative;
            if(fabs(measured-hz)>fmax(2.0,0.03*hz)) {
                fprintf(stderr,"pitch regression fs=%u hz=%u shape=%u quarters=%u measured=%.3f\n",fs,hz,shape,q,measured);
                abort();
            }
        }
       }
    printf("416 pitch cases passed; worst crossing-rate error %.2f%%\n",100*worst_relative);
    free(src);free(out);
}
static void reset_invalid_and_backpressure(void) {
    speed_state s,copy; speed_result r;
    int16_t in[4096]={0},out[4096];
    assert(speed_init(&s,0,1,4)==-1);
    assert(speed_init(&s,48000,3,4)==-1);
    assert(speed_init(&s,48000,1,9)==-1);
    assert(speed_init(&s,48000,2,5)==0);
    copy=s;
    assert(speed_process(&s,NULL,1,0,out,1,&r)==-1);
    assert(!memcmp(&s,&copy,sizeof s));
    assert(speed_process(&s,in,2048,0,NULL,0,&r)==0);
    assert(r.produced==0 && r.consumed<=2048);
    speed_reset(&s);
    assert(!s.accepted && !s.retired && !s.produced && !s.input_frames && !s.output_frames);
    assert(s.sample_rate==48000 && s.channels==2 && s.quarters==5);
    assert(speed_process(&s,NULL,0,1,out,1,&r)==0 && r.done);
    copy=s;
    assert(speed_process(&s,in,1,1,out,1,&r)==-1 && !memcmp(&s,&copy,sizeof s));
    assert(speed_process(&s,NULL,0,1,out,1,&r)==0 && r.done);
    /* Reproduces the upstream-lite problematic EOF shape without overrun. */
    int16_t *silence=calloc(5120,sizeof *silence),*result=calloc(5120,sizeof *result);
    assert(silence && result);
    size_t n=run(48000,1,5,silence,5120,256,4096,result);
    for(size_t i=0;i<n;i++) assert(result[i]==0);
    free(silence);free(result);
}
static void extremes(void) {
    int16_t src[8192],dst[8192];
    for(unsigned shape=0;shape<4;shape++) {
        for(size_t i=0;i<8192;i++) src[i]=shape==0?0:shape==1?-32768:shape==2?32767:(i/2%2?-32768:32767);
        for(unsigned q=4;q<=8;q++) {
            size_t made=run(48000,2,q,src,4096,64,3,dst);
            if(shape<3) for(size_t i=0;i<made*2;i++) assert(dst[i]==src[0]);
        }
    }
}
static void search_work_bound(void) {
    unsigned worst=0;
    for(unsigned fs=8000;fs<=48000;fs++) {
        unsigned skip=fs/4000,lo=fs/400,hi=fs/65;
        unsigned first=lo/skip,last=hi/skip;
        unsigned coarse=(first+last)*(last-first+1)/2;
        unsigned fine=(2*skip+1)*((hi+1)/2);
        unsigned bound=coarse+fine;
        if(bound>worst) worst=bound;
        assert(bound<=11071);
    }
    assert(worst==11071);
    printf("all supported sample-rate search bounds <=%u comparisons\n",worst);
}
static void mapping(void) {
    speed_state s; speed_result r;
    int16_t input[4096]={0},output[256];
    assert(speed_init(&s,48000,2,5)==0);
    assert(speed_process(&s,input,2048,0,output,128,&r)==0);
    /* Silence chooses a 120-frame period: 120 output frames represent240
     * source frames, followed by8 unchanged source frames. */
    assert(r.produced==128 && r.source_begin==0 && r.source_end==248);
    speed_packet packet; uint64_t position=999;
    assert(speed_packet_init(&packet,&r)==0);
    uint64_t previous=0;
    for(unsigned i=0;i<=128;i++) {
        assert(speed_packet_position(&packet,i,&position)==0);
        assert(position>=previous && position<=248);
        /* Interpolation may differ from the exact piecewise map, bounded
         * by this packet's size; endpoints stay exact. */
        uint64_t exact=i<=120?2*i:240+i-120;
        assert(labs((long)position-(long)exact)<=128);
        previous=position;
    }
    assert(speed_process(&s,NULL,0,0,NULL,0,&r)==0);
    assert(!r.produced && r.source_begin==248 && r.source_end==248);
    assert(speed_process(&s,NULL,0,0,output,1,&r)==0);
    assert(r.source_begin==248 && r.source_end==249);
    speed_reset(&s);
    assert(!s.emitted_source);
    assert(speed_process(&s,input,1,1,output,1,&r)==0 && r.done);
    assert(r.source_begin==0 && r.source_end==1);
    /* Errors leave caller-owned metadata/output unchanged. */
    speed_packet before=packet; r.produced=SPEED_PACKET_MAX_FRAMES+1u;
    assert(speed_packet_init(&packet,&r)==-1 && !memcmp(&packet,&before,sizeof packet));
    position=999;
    assert(speed_packet_position(&packet,129,&position)==-1 && position==999);
    r.produced=1;r.source_begin=9;r.source_end=8;
    assert(speed_packet_init(&packet,&r)==-1);
    r.source_end=12;
    assert(speed_packet_init(&packet,&r)==-1);
    r.source_end=9;
    assert(speed_packet_init(&packet,&r)==-1);
    r.produced=0;
    assert(speed_packet_init(&packet,&r)==0);
    assert(speed_packet_position(&packet,0,&position)==0 && position==9);
    assert(speed_packet_position(&packet,1,&position)==-1);
    /* Near-maximum absolute source offsets do not wrap interpolation. */
    r.produced=SPEED_PACKET_MAX_FRAMES;r.source_end=UINT64_MAX;
    r.source_begin=UINT64_MAX-2*SPEED_PACKET_MAX_FRAMES;
    assert(speed_packet_init(&packet,&r)==0);
    assert(speed_packet_position(&packet,SPEED_PACKET_MAX_FRAMES,&position)==0 && position==UINT64_MAX);
    assert(speed_packet_position(&packet,SPEED_PACKET_MAX_FRAMES-1,&position)==0 && position==UINT64_MAX-2);
}
int main(void) {
    format_matrix();
#ifdef SPEED_TEST_METRICS
    printf("peak pitch-search comparisons: %u\n",speed_test_peak_comparisons);
    fflush(stdout);
    assert(speed_test_peak_comparisons<=15000);
#endif
    pitch_and_stereo();pitch_matrix();reset_invalid_and_backpressure();extremes();mapping();search_work_bound();
#ifdef SPEED_TEST_METRICS
    assert(speed_test_peak_comparisons<=11071);
    printf("final observed peak pitch-search comparisons: %u\n",speed_test_peak_comparisons);
#endif
    printf("speed prototype: all checks passed; state %zu bytes\n",sizeof(speed_state));
}
