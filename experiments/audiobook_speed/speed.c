/* Experimental bounded pitch-period speedup.
 * Algorithm/reference: Sonic, Copyright 2010 Bill Cox, Apache-2.0.
 * This adaptation replaces stream allocation, buffering, EOF and rate math;
 * it does not use upstream sonic_lite's unchecked write/flush routines.
 * See LICENSE and README.md. */
#include "speed.h"
#include <string.h>
#ifdef SPEED_TEST_METRICS
/* Host-only instrumentation; excluded from normal/firmware builds. */
uint32_t speed_test_peak_comparisons;
static uint32_t speed_test_current_comparisons;
#define COUNT_COMPARISON() (++speed_test_current_comparisons)
#else
#define COUNT_COMPARISON() ((void)0)
#endif
#define READY UINT32_C(0x53504544)
static size_t smaller(size_t a,size_t b) { return a<b?a:b; }
int speed_init(speed_state *s,unsigned rate,unsigned channels,unsigned quarters) {
    if(!s || rate<8000 || rate>48000 || (channels!=1 && channels!=2) || quarters<4 || quarters>8) return -1;
    memset(s,0,sizeof *s); s->sample_rate=rate; s->channels=channels; s->quarters=quarters; s->ready=READY;
    return 0;
}
void speed_reset(speed_state *s) {
    if(s && s->ready==READY) (void)speed_init(s,s->sample_rate,s->channels,s->quarters);
}
/* Mean absolute difference: use 64-bit cross products when comparing means.
 * At 48k and full-scale opposing samples, a 32-bit product can overflow. */
static unsigned search(const int16_t *samples,unsigned stride,unsigned first,unsigned last,unsigned sample_step) {
    uint32_t best_diff=0; unsigned best=first,best_count=0;
    for(unsigned p=first;p<=last;p++) {
        uint32_t diff=0;
        for(unsigned i=0;i<p;i+=sample_step) {
            int32_t delta=(int32_t)samples[i*stride]-samples[(i+p)*stride];
            COUNT_COMPARISON();
            diff+=(uint32_t)(delta<0?-delta:delta);
        }
        /* Normalize by samples actually compared, including odd periods. */
        unsigned count=(p+sample_step-1)/sample_step;
        if(p==first || (uint64_t)diff*best_count < (uint64_t)best_diff*count) {
            best=p;best_diff=diff;best_count=count;
        }
    }
    return best;
}
static unsigned pitch(speed_state *s) {
#ifdef SPEED_TEST_METRICS
    speed_test_current_comparisons=0;
#endif
    unsigned lo=s->sample_rate/400,hi=s->sample_rate/65,skip=s->sample_rate/4000;
    unsigned frames=2*hi/skip,c=s->channels;
    /* One shared decision preserves stereo timing. Choose the stronger channel;
     * averaging opposite-phase stereo can cancel its pitch signal, while always
     * using the left channel fails when only the right channel carries speech. */
    unsigned channel=0;
    if(c==2) {
        uint32_t magnitude[2]={0,0};
        for(unsigned i=0;i<2*hi;i++) for(unsigned ch=0;ch<2;ch++) {
            int32_t sample=s->input[i*2+ch];
            magnitude[ch]+=(uint32_t)(sample<0?-sample:sample);
        }
        channel=magnitude[1]>magnitude[0];
    }
    for(unsigned i=0;i<frames;i++) {
        int32_t sum=0;
        for(unsigned k=0;k<skip;k++) sum+=s->input[(i*skip+k)*c+channel];
        s->analysis[i]=(int16_t)(sum/(int32_t)skip);
    }
    unsigned p=search(s->analysis,1,lo/skip,hi/skip,1)*skip;
    /* One coarse-bin radius and every-other-frame refinement bound work.
     * There are no runtime quality knobs or floating-point operations. */
    unsigned lower=p>skip?p-skip:lo,upper=p+skip;
    if(lower<lo) lower=lo;
    if(upper>hi) upper=hi;
    unsigned found=search(s->input+channel,c,lower,upper,2);
#ifdef SPEED_TEST_METRICS
    if(speed_test_current_comparisons>speed_test_peak_comparisons)
        speed_test_peak_comparisons=speed_test_current_comparisons;
#endif
    return found;
}
static void retire(speed_state *s,unsigned n) {
    s->input_frames-=n; s->retired+=n;
    memmove(s->input,s->input+n*s->channels,(size_t)s->input_frames*s->channels*sizeof(int16_t));
}
static void overlap(speed_state *s) {
    unsigned p=pitch(s),c=s->channels;
    for(unsigned i=0;i<p;i++) for(unsigned ch=0;ch<c;ch++) {
        int32_t value=(int32_t)s->input[i*c+ch]*(int32_t)(p-i)+(int32_t)s->input[(i+p)*c+ch]*(int32_t)i;
        s->output[i*c+ch]=(int16_t)(value/(int32_t)p);
    }
    s->output_frames=p;s->output_offset=0;
    /* n/4 speed: remove one period, then copy p*(8-n)/(n-4).
     * Carry the division remainder rather than accumulating rate rounding. */
    unsigned numerator=p*(8-s->quarters)+s->copy_fraction;
    s->copy_frames=numerator/(s->quarters-4);
    s->copy_fraction=numerator%(s->quarters-4);
    s->dropped+=p;
    retire(s,2*p);
}
int speed_process(speed_state *s,const int16_t *input,size_t input_frames,int eof,
                  int16_t *output,size_t capacity,speed_result *result) {
    if(!s || s->ready!=READY || !result || (!input && input_frames) || (!output && capacity) ||
       input_frames>SIZE_MAX/4 || capacity>SIZE_MAX/4 || (s->ended && input_frames)) return -1;
    speed_result r={0}; unsigned c=s->channels;
    r.source_begin=s->emitted_source;
    if(s->quarters==4) {
        size_t n=smaller(input_frames,capacity);
        if(n) memcpy(output,input,n*c*sizeof(int16_t));
        r.consumed=r.produced=n;s->accepted+=n;s->retired+=n;s->produced+=n;
        if(eof && n==input_frames) s->ended=1;
        s->emitted_source=s->retired;r.source_end=s->emitted_source;
        r.done=(int)s->ended;*result=r;return 0;
    }
    if(eof && !input_frames) s->ended=1;
    for(;;) {
        if(s->output_frames) {
            size_t n=smaller(s->output_frames,capacity-r.produced);
            if(!n) break;
            memcpy(output+r.produced*c,s->output+s->output_offset*c,n*c*sizeof(int16_t));
            s->output_frames-=(uint32_t)n;s->output_offset+=(uint32_t)n;
            s->emitted_source=s->retired-2*s->output_frames;
            r.produced+=n;s->produced+=n;
            continue;
        }
        if(s->copy_frames && s->input_frames) {
            size_t n=smaller(smaller(s->copy_frames,s->input_frames),capacity-r.produced);
            if(!n) break;
            memcpy(output+r.produced*c,s->input,n*c*sizeof(int16_t));
            s->copy_frames-=(uint32_t)n;retire(s,(unsigned)n);
            s->emitted_source=s->retired;
            r.produced+=n;s->produced+=n;
            continue;
        }
        if(s->input_frames>=2*(s->sample_rate/65)) {
            if(r.produced==capacity) break;
            overlap(s);continue;
        }
        if(!s->ended && r.consumed<input_frames) {
            size_t n=smaller(SPEED_INPUT_FRAMES-s->input_frames,input_frames-r.consumed);
            memcpy(s->input+s->input_frames*c,input+r.consumed*c,n*c*sizeof(int16_t));
            s->input_frames+=(uint32_t)n;r.consumed+=n;s->accepted+=n;
            if(eof && r.consumed==input_frames) s->ended=1;
            continue;
        }
        if(s->ended) {
            /* No synthetic padding: the final <2-period tail is copied once.
             * Duration differs from ideal by at most one maximum period. */
            size_t n=smaller(s->input_frames,capacity-r.produced);
            if(n) {
                memcpy(output+r.produced*c,s->input,n*c*sizeof(int16_t));
                retire(s,(unsigned)n);r.produced+=n;s->produced+=n;
                s->emitted_source=s->retired;
            }
            if(!s->input_frames) { s->copy_frames=0;r.done=1; }
            break;
        }
        break;
    }
    r.source_end=s->emitted_source;
    *result=r;return 0;
}

int speed_packet_init(speed_packet *packet,const speed_result *result) {
    if(!packet || !result || result->produced>SPEED_PACKET_MAX_FRAMES ||
       result->source_end<result->source_begin) return -1;
    uint64_t span=result->source_end-result->source_begin;
    if(span<result->produced || span>2*result->produced) return -1;
    packet->source_begin=result->source_begin;packet->source_end=result->source_end;
    packet->output_frames=(uint32_t)result->produced;return 0;
}
int speed_packet_position(const speed_packet *packet,uint32_t consumed_frames,uint64_t *source_frame) {
    if(!packet || !source_frame || packet->output_frames>SPEED_PACKET_MAX_FRAMES ||
       consumed_frames>packet->output_frames || packet->source_end<packet->source_begin) return -1;
    uint64_t span=packet->source_end-packet->source_begin;
    uint32_t frames=packet->output_frames;
    if(span<frames || span>2*frames) return -1;
    uint32_t extra=(uint32_t)span-frames;
    /* extra <=frames <=65535, so this product fits32 bits. Only integer
     * division is needed even when the absolute source position is64-bit. */
    uint32_t skipped=frames ? extra*consumed_frames/frames : 0;
    *source_frame=packet->source_begin+consumed_frames+skipped;
    return 0;
}
