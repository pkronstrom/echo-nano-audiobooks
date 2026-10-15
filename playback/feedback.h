#ifndef ECHO_FEEDBACK_H
#define ECHO_FEEDBACK_H
#include "fw.h"
/* Capture at gesture time; a canceled session cannot publish a late result. */
u32 feedback_token(void);
void feedback_result(u32 token,int success);
void feedback_cancel(void);
/* Only called from the guarded MusicWin service epilogue, on the UI task. */
void feedback_poll(u32 transition);
#endif
