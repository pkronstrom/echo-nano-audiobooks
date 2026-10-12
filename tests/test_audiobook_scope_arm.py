"""Run the P1b playback containment regression matrix on the audiobook image."""
import test_playback_scope_arm as scope
import test_playback_runtime_arm as runtime

class AudiobookScopeTests(scope.PlaybackScopeTests):
    def setUp(self):
        super().setUp()
        image=scope.Image((scope.ROOT/'out/audiobook/NANOV170.IMG').read_bytes())
        for index in (0,33):
            m=image.modules[index]
            for kind in ('code','data'):
                off=image.l2f(m[kind+'_load'])
                self.cpu.mem_write(m[kind+'_exec'],bytes(image.d[off:off+m[kind+'_len']]))
        self.cpu.mem_write(0x0309b694,(scope.ROOT/'out/playback/playback.bin').read_bytes())
        symbols={n:int(v,16) for v,t,n in (line.split() for line in (scope.ROOT/'out/playback/playback.nm').read_text().splitlines())}
        self.call(symbols['playback_init'])
