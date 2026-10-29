from pathlib import Path
import subprocess,json,csv,zipfile,hashlib
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent.parent
t=json.load(open(root/'source/timeline.json'));beats=json.load(open(root/'source/beats.json'))['beats']
report={'duration_target':t['duration'],'bpm_detected':t['bpm_detected'],'beat_alignment_max_error_seconds':max(abs(s['timeline_in']-(beats[s['beat_index']]-t['music_start'])) for s in t['scenes']),'exports':[]}
for fmt in ['landscape','vertical']:
 p=root/'exports'/f'musebook-beatsync-{fmt}.mp4'
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
 subprocess.run(['ffmpeg','-v','error','-i',str(p),'-f','null','-'],check=True)
 loud=subprocess.run(['ffmpeg','-hide_banner','-i',str(p),'-af','volumedetect','-f','null','-'],capture_output=True,text=True,check=True)
 report['exports'].append({'file':p.name,'duration':float(probe['format']['duration']),'streams':[{k:s.get(k) for k in ['codec_type','codec_name','width','height','sample_rate']} for s in probe['streams']],'full_decode':'passed','volume':[x.strip() for x in loud.stderr.splitlines() if 'mean_volume:' in x or 'max_volume:' in x],'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 # Inspect a middle frame from every scene.
 sheet=Image.new('RGB',(1000,680),'#0A0814');d=ImageDraw.Draw(sheet)
 for s in t['scenes']:
  frame=root/'review'/f'{fmt}-{s["index"]:02d}.jpg'
  subprocess.run(['ffmpeg','-v','error','-ss',str(s['timeline_in']+s['duration']/2),'-i',str(p),'-frames:v','1','-vf','scale=200:300:force_original_aspect_ratio=decrease','-y',str(frame)],check=True)
  im=Image.open(frame);x=(s['index']%5)*200;y=(s['index']//5)*340
  sheet.paste(im,(x,y));d.text((x+4,y+305),s['label'],fill='white')
 sheet.save(root/'review'/f'{fmt}-contact.jpg')
json.dump(report,open(root/'review/qa.json','w'),indent=2)
with open(root/'source/timeline.csv','w') as f:
 writer=csv.DictWriter(f,fieldnames=list(t['scenes'][0]));writer.writeheader();writer.writerows(t['scenes'])
(root/'README.md').write_text(f'''# Musebook beat-synced marketing video — 2 October 2026

Duration: {t['duration']:.2f}s. Ten scenes; 30 fps. Landscape 1920×1080 and vertical 1080×1920. H.264/AAC with faststart.

Music: supplied SOLGPT Night - Track 2 - Treblo.mp3, starting at {t['music_start']:.3f}s. Detected tempo {t['bpm_detected']:.2f} BPM. Cuts follow detected beats, rounded to the nearest video frame. Recording audio is retained underneath the music with short edge fades; no generated narration.

## Extracted audio
- recording-1.m4a / .wav: Screen Recording 2026-10-02 at 1.17.02 PM.mov
- recording-2.m4a / .wav: Screen Recording 2026-10-02 at 2.07.00 PM.mov
- recording-3.m4a / .wav: Screen Recording 2026-10-02 at 1.14.51 PM.mov

M4A files retain the original AAC audio without re-encoding. WAV files are PCM editing copies. The second recording is particularly quiet.

## Editing and reproduction
The editable shot list is source/timeline.json and source/timeline.csv. All title layers are PNGs in source/landscape and source/vertical. Fonts and their licenses are included. source/render.py defines typography, layouts, clips, titles, music timing, and audio mix. It recreates the timeline when run; edit that script for changes.

From the campaign folder:
```sh
python3 -m venv source/.venv
source/.venv/bin/pip install pillow numpy scipy librosa
source/.venv/bin/python source/render.py
source/.venv/bin/python source/package_and_verify.py
```
Requires ffmpeg/ffprobe and original source recordings and music at the absolute paths in render.py/timeline.json. Original videos and full music are not duplicated in the package. Update paths when moving machines. Beat analysis was performed by source/analyze_media.py; beats.json is included.

## Validation
Both exports fully decoded without errors. Frame contact sheets and stream/audio measurements are in review/. Cuts are within one half-frame of the detected beat timestamps. Music beat detection is automated, not a manually transcribed musical score.

Nothing published. Source recordings and music are preserved unchanged.
''')
(root/'preview.html').write_text('''<!doctype html><meta charset="utf-8"><title>Musebook — Catch the first signal</title><style>body{background:#0a0814;color:#f6f7f5;font:18px system-ui;margin:40px}h1{color:#f34c3f}video{width:100%;max-width:1100px;display:block;margin:24px 0}.vertical{max-width:400px}a{color:#c8f0dc}</style><h1>Catch the first signal.</h1><p>Musebook · Treblo beat-synced edit · 2 October 2026</p><video controls src="exports/musebook-beatsync-landscape.mp4"></video><video class="vertical" controls src="exports/musebook-beatsync-vertical.mp4"></video><p><a href="audio/recording-1.m4a">Recording 1 audio</a> · <a href="audio/recording-2.m4a">Recording 2 audio</a> · <a href="audio/recording-3.m4a">Recording 3 audio</a></p>''')
archive=root.parent/'musebook-video-2026-10-02.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in root.rglob('*'):
  if not p.is_file() or '.venv' in p.parts or '__pycache__' in p.parts or p.name=='music.wav' or (p.suffix=='.mp4' and 'source' in p.parts):continue
  z.write(p,p.relative_to(root.parent))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
print(json.dumps(report,indent=2));print('Archive:',archive)
