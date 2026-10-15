#ifndef ECHO_SPEED_EXPERIMENT_H
#define ECHO_SPEED_EXPERIMENT_H
#include <stddef.h>
#include <stdint.h>
#define SPEED_INPUT_FRAMES 1536u
#define SPEED_MAX_PERIOD 738u
#define SPEED_ANALYSIS_FRAMES 256u
/* Experimental state: caller owns it; no shared state or heap allocation. */
typedef struct {
    int16_t input[SPEED_INPUT_FRAMES * 2];
    int16_t output[SPEED_MAX_PERIOD * 2];
    int16_t analysis[SPEED_ANALYSIS_FRAMES];
    uint32_t sample_rate, channels, quarters;
    uint32_t input_frames, output_frames, output_offset;
    uint32_t copy_frames, copy_fraction;
    uint32_t ended, ready;
    uint64_t accepted, retired, produced, dropped, emitted_source;
} speed_state;
typedef struct {
    size_t consumed, produced;
    int done;
    /* Source-frame interval represented by returned output, relative to reset.
     * Endpoints are exact; interior mapping may mix 1:1 and 2:1 segments. */
    uint64_t source_begin, source_end;
} speed_result;
#define SPEED_PACKET_MAX_FRAMES 65535u
typedef struct {
    uint64_t source_begin, source_end;
    uint32_t output_frames;
} speed_packet;
/* Compact descriptor for a caller-owned native output slot. No queue or clock.
 * Source position is interpolated inside a packet, exact at either endpoint.
 * consumed_frames is absolute within this packet, NOT a delta. */
int speed_packet_init(speed_packet *packet, const speed_result *result);
int speed_packet_position(const speed_packet *packet, uint32_t consumed_frames,
                          uint64_t *source_frame);
/* Valid rates: 8000..48000; channels 1/2; quarters 4,5,6,7,8. */
int speed_init(speed_state *s, unsigned sample_rate, unsigned channels, unsigned quarters);
/* Discard all queued PCM/accounting, retaining the existing format and speed. */
void speed_reset(speed_state *s);
/* Input/output must not alias each other or state. Counts are frames, not samples.
 * eof means no source follows the offered input; retry unconsumed input with eof.
 * Passing zero output capacity is legal. Once done, reset before another stream.
 * Returns -1 on invalid arguments or input after EOF, without changing state. */
int speed_process(speed_state *s, const int16_t *input, size_t input_frames,
                  int eof, int16_t *output, size_t output_capacity, speed_result *result);
#endif
