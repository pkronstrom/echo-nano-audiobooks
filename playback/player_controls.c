#include "session.h"
/* Decode first: native double-Previous already invokes our bookmark hook.
 * Consume all directional phases for books so stock release/restart/skip
 * handling cannot undo a bounded seek. Music and folder playback pass through. */
u32 playback_player_key(u32 argument)
{
    u32 message=FW(0x03063242,u32,u32)(argument);
    u32 key=message&0x0fffffffu,phase=message>>28;
    if(playback_active==1 && (key==4 || key==8) && phase>=1 && phase<=5){
        if(phase>=2 && phase<=4)playback_seek_request(key==4?1:-1);
        return 0;
    }
    return message;
}
/* Every window exit cancels an uncommitted seek. A committed relaunch (status2)
 * survives this callback, just as it does the settings-menu cancel path. */
void playback_player_uninit(void)
{
    playback_rate_cancel();
    FW(0x03079512,void,void)();
}
