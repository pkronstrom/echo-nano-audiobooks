#!/usr/bin/env python3
"""Prepare an Echo Nano book without changing or renaming its audio files."""
import argparse
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

AUDIO={'.mp1','.mp2','.mp3','.wma','.wav','.ape','.fla','.flac','.aac','.m4a','.ogg','.mp4','.3gp','.dff','.dsf'}
CONVERTIBLE=AUDIO|{'.m4b','.aiff','.aif','.opus','.mka'}

def natural_key(path):
    # Keep disc folder components before track components; 01 and 1 tie by name.
    return tuple(tuple((1,int(x)) if x.isdecimal() else (0,x.casefold())
                       for x in re.split(r'([0-9]+)',part)) for part in Path(path).parts)

def resume_bytes():
    sector=bytearray(512)
    struct.pack_into('<I',sector,0,0x31524e45)
    struct.pack_into('<I',sector,508,zlib.crc32(sector[:508]))
    return bytes(sector)*2

def valid_resume(data):
    return len(data)==1024 and any(struct.unpack_from('<I',data,n)[0]==0x31524e45 and
        struct.unpack_from('<I',data,n+508)[0]==zlib.crc32(data[n:n+508]) for n in (0,512))

def checked_path(path):
    text=path.as_posix()
    if len(text.encode('utf-16le'))//2>255 or len(text.encode('utf-8'))>1023:
        raise ValueError(f'Path exceeds player limits: {text}')
    if any(ord(c)<32 or c in ':*?"<>|\\' for c in text):
        raise ValueError(f'Unsupported player filename: {text}')
    # Portable across FAT and exFAT: stock exFAT indexed-open has a smaller buffer.
    if len(path.name.encode('utf-16le'))//2>127:
        raise ValueError(f'Filename exceeds the stock exFAT limit: {path.name}')
    return text

def require_copyable_audio(path):
    raw=subprocess.check_output(['ffprobe','-v','error','-select_streams','a:0',
        '-show_entries','stream=codec_name','-of','json',str(path)])
    streams=json.loads(raw).get('streams',[])
    if not streams or streams[0].get('codec_name') not in ('aac','alac'):
        raise ValueError(f'M4A remux requires AAC or ALAC audio: {path}; use explicit MP3 conversion instead')

def write_metadata(destination,stem,body,marker):
    playlist=destination/(stem+'.M3U');resume=destination/(stem+'.RSM')
    if not playlist.exists():
        with playlist.open('xb') as f:f.write(body)
    if not resume.exists():
        with resume.open('xb') as f:f.write(resume_bytes())
    if marker:(destination/'.nomusic').touch(exist_ok=True)

def prepare(source,write=False,output=None,convert=False,name=None,remux=False):
    if convert and remux:raise ValueError('Choose either MP3 conversion or M4A remux')
    transform=convert or remux
    source=Path(source)
    if source.is_symlink():raise ValueError('Source must not be a symlink')
    source=source.resolve(strict=True)
    root=source if source.is_dir() else source.parent
    allowed=CONVERTIBLE if transform else AUDIO
    candidates=list(root.rglob('*')) if source.is_dir() else [source]
    audio=[];unsupported=[]
    for p in candidates:
        if p.is_symlink():
            if p.suffix.lower() in CONVERTIBLE:raise ValueError(f'Audio symlinks are not supported: {p}')
            continue
        if not p.is_file():continue
        if p.suffix.lower() in allowed:audio.append(p)
        elif p.suffix.lower() in CONVERTIBLE:unsupported.append(str(p))
    if unsupported:raise ValueError('Prepare these with --remux-to m4a (AAC/ALAC) or --convert-to mp3, plus --output DIR: '+', '.join(unsupported))
    audio.sort(key=lambda p:(natural_key(p.relative_to(root)),p.relative_to(root).as_posix()))
    if not audio:raise ValueError('No supported audio files found')
    if len(audio)>256:raise ValueError('A book can contain at most 256 audio files')
    stem=name or ('BOOK' if source.is_dir() else source.stem)
    if Path(stem).name!=stem or stem in ('','.','..'):raise ValueError('--name must be a filename stem')
    if output and Path(output).is_symlink():raise ValueError('Output must not be a symlink')
    destination=Path(output).resolve() if output else root
    if transform:
        if not output:raise ValueError('Audio processing requires --output DIR')
        if destination==root or root in destination.parents:raise ValueError('Output must be outside the source book folder')
        if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
            raise ValueError('Output must be an empty directory')
        if not shutil.which('ffmpeg'):raise ValueError('ffmpeg is required for audio processing')
        if remux:
            if not shutil.which('ffprobe'):raise ValueError('ffprobe is required for --remux-to m4a')
            for p in audio:require_copyable_audio(p)
        extension='m4a' if remux else 'mp3'
        names=[Path(f'{i:03d} {p.stem}.{extension}') for i,p in enumerate(audio)]
    else:
        if output:raise ValueError('--output is only used with --convert-to or --remux-to')
        names=[p.relative_to(root) for p in audio]
    lines=[checked_path(p) for p in names]
    lines=['./'+line if line.startswith('#') else line for line in lines]
    if any(len(line.encode('utf-8'))>1024 for line in lines):
        raise ValueError('Playlist line exceeds player limit')
    playlist=destination/(stem+'.M3U');resume=destination/(stem+'.RSM')
    checked_path(Path(playlist.name));checked_path(Path(resume.name))
    body=('#EXTM3U\n'+'\n'.join(lines)+'\n').encode('utf-8')
    # Existing user-edited playlist order is authoritative. Validate its companion
    # but leave it intact, including on repeated preparation.
    playlist_exists=playlist.exists()
    if playlist_exists and not playlist.is_file():raise ValueError(f'Playlist is not a regular file: {playlist}')
    if playlist.is_symlink() or resume.is_symlink() or (destination/'.nomusic').is_symlink():
        raise ValueError('Metadata targets must not be symlinks')
    if resume.exists() and not valid_resume(resume.read_bytes()):
        raise ValueError(f'Existing resume file has an unknown/corrupt format; preserved: {resume}')
    marker=destination/'.nomusic' if source.is_dir() or transform else None
    result={'status':'prepared' if write else 'preview','playlist':str(playlist),'resume':str(resume),
            'tracks':([line for line in playlist.read_text(encoding='utf-8-sig').splitlines() if line and not line.startswith('#')] if playlist_exists else lines),'order':'existing playlist preserved' if playlist_exists else 'natural filename order',
            'conversion':'mp3' if convert else None,'remux':'m4a' if remux else None,
            'marker':str(marker) if marker else None}
    if write:
        if transform:
            # Publish one complete book. Failed processing leaves an existing
            # empty destination untouched; staging is on the same filesystem.
            destination.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.nano-prepare-',dir=destination.parent) as tmp:
                stage=Path(tmp)/'book';stage.mkdir()
                for original,relative in zip(audio,names):
                    codec=['-c:a','copy'] if remux else ['-c:a','libmp3lame','-q:a','2']
                    subprocess.run(['ffmpeg','-nostdin','-v','error','-n','-i',str(original),'-map','0:a:0',
                        '-map_metadata','0','-map_chapters','-1',*codec,str(stage/relative)],check=True)
                write_metadata(stage,stem,body,True)
                if destination.is_symlink():raise ValueError('Output must not be a symlink')
                # Windows cannot rename over even an empty directory. Remove
                # only the empty destination after all processing has succeeded.
                removed_empty=False
                if destination.exists():
                    destination.rmdir();removed_empty=True
                try:
                    stage.rename(destination)
                except OSError:
                    if removed_empty and not destination.exists():destination.mkdir()
                    raise
        else:
            write_metadata(destination,stem,body,marker is not None)
    return result

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,epilog='Examples:\n  %(prog)s /Volumes/NANO/Audiobooks/Book\n  %(prog)s /Volumes/NANO/Audiobooks/Book --write\n  %(prog)s /Downloads/Book.m4b --convert-to mp3 --output /Volumes/NANO/Audiobooks/Book --write',formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source',type=Path,help='One book folder, or one long audio file')
    parser.add_argument('--write',action='store_true',help='Write playlist, resume companion and .nomusic; default is preview')
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--convert-to',choices=['mp3'],help='Re-encode audio using ffmpeg; originals remain untouched')
    modes.add_argument('--remux-to',choices=['m4a'],help='Copy AAC/ALAC audio without re-encoding using ffmpeg/ffprobe; Nano compatibility needs a device test')
    parser.add_argument('--output',type=Path,help='Empty destination directory for processed files')
    parser.add_argument('--name',help='Playlist/resume filename stem (default BOOK for folders, file stem for one file)')
    args=parser.parse_args(argv)
    try:result=prepare(args.source,args.write,args.output,bool(args.convert_to),args.name,bool(args.remux_to))
    except (ValueError,OSError,subprocess.CalledProcessError) as exc:
        print(f'prepare-book: {exc}',file=sys.stderr);return 2
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':sys.exit(main())
