#!/usr/bin/env python3
"""Encode original chase RGB frames and trace-derived captions into a viewing MP4."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess


def srt_time(seconds):
    ms = round(seconds * 1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'


def encode(directory, output):
    if output.exists():
        raise FileExistsError(output)
    metadata = json.loads((directory/'sensors.json').read_text())
    frames = metadata['streams']['rgb']
    if metadata['errors'] or metadata['dropped'] or not frames:
        raise ValueError('Incomplete original camera capture')
    width, height = frames[0]['width'], frames[0]['height']
    size = width*height*4
    raw = directory/'rgb-video.bgra'
    if raw.stat().st_size != len(frames)*size:
        raise ValueError('Raw frame count/size mismatch')
    with raw.open('rb') as stream:
        for i, frame in enumerate(frames):
            if ((frame['width'], frame['height'], frame['format']) != (width, height, 'BGRA8') or
                    frame['validity'] != 'VALID' or
                    (i and frame['frame'] != frames[i-1]['frame']+5) or
                    abs(frame['timestamp']-frames[0]['timestamp']-i*.05) > 1e-5 or
                    hashlib.sha256(stream.read(size)).hexdigest() != frame['sha256']):
                raise ValueError('Original frame identity/hash/time mismatch')
    indices = {frame['frame'] for frame in frames}
    states = {}
    with gzip.open(directory/'trace.jsonl.gz', 'rt') as stream:
        for line in stream:
            row = json.loads(line)
            if row['frame'] in indices:
                states[row['frame']] = row
    if set(states) != indices:
        raise ValueError('Camera frame missing from physical trace')
    captions = []
    for i in range(0, len(frames), 10):
        frame = frames[i]
        row = states[frame['frame']]
        if abs(row['simulation_seconds']-frame['timestamp']) > 1e-6:
            raise ValueError('Camera/physics source timestamp mismatch')
        terminal = row['native']['speed_terminal']
        speed = row['physics']['body_forward_velocity_m_s']*3.6
        if terminal['power_off']:
            phase = 'Stopped | HV off'
        elif terminal['trigger_ns']:
            phase = 'Braking' if abs(speed) > .01 else 'Stopped | Hold'
        else:
            phase = 'Accelerating' if speed < 29 else 'Cruising'
        captions.append(f'{len(captions)+1}\n{srt_time(i*.05)} --> {srt_time(min(i+10,len(frames))*.05)}\n'
                        f'StrataDrive | 30 km/h NormalStop\n'
                        f'Sim {i*.05:04.1f}s | {speed:05.2f} km/h | {phase}\n\n')
    output.parent.mkdir(parents=True, exist_ok=True)
    subtitles = directory/'video-status.srt'
    subtitles.write_text(''.join(captions))
    # Separate raw encoding from caption muxing so paths need no filter escaping.
    base = directory/'camera-original.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-f','rawvideo',
                    '-pixel_format','bgra','-video_size',f'{width}x{height}','-framerate','20',
                    '-i',str(raw),'-an','-c:v','libx264','-preset','fast','-crf','20',
                    '-pix_fmt','yuv420p','-movflags','+faststart',str(base)],check=True)
    # ffmpeg filter uses a fixed relative filename in the capture directory.
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-i','camera-original.mp4',
                    '-vf',"subtitles=video-status.srt:force_style='FontName=DejaVu Sans,FontSize=17,Alignment=7,MarginL=16,MarginV=14,Outline=1,BorderStyle=3'",
                    '-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',
                    '-movflags','+faststart',str(output.resolve())],cwd=directory,check=True)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                    '-show_entries','stream=width,height,nb_read_frames,r_frame_rate,duration','-of','json',str(output)]))['streams'][0]
    if (int(info['nb_read_frames'])!=len(frames) or info['r_frame_rate']!='20/1' or
            abs(float(info['duration'])-len(frames)*.05)>.001):
        raise ValueError('Encoded video duration/frame count mismatch')
    result=dict(status='PASS_VIEWING_VIDEO',video=str(output),frames=len(frames),
                width=width,height=height,fps=20,duration_s=len(frames)*.05,
                original_frames_hash_verified=True,caption_source='Original matching frame/physics/native terminal',
                new_control_acceptance=False,run_status=json.loads((directory/'result.json').read_text())['status'])
    (directory/'video.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    encode(args.directory,args.output)
