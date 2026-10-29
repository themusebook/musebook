from pathlib import Path
from PIL import Image,ImageDraw
import subprocess,json,hashlib,csv,zipfile
R=Path(__file__).resolve().parent.parent
t=json.load(open(R/'source/timeline.json'));b=json.load(open(R/'source/beats.json'))['beats']
report={'duration_target':60,'scenes':len(t['scenes']),'cut_alignment_max_error_seconds':max(abs(s['timeline_in']-(b[s['beat_index']]-t['music_start'])) for s in t['scenes']),'source_audio':'Neither input recording contains an audio stream; soundtrack is the supplied Treblo song.','exports':[]}
for fmt in ['landscape','vertical']:
 p=R/'exports'/f'musebook-brainy-60s-{fmt}.mp4'
 d=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)]))
 subprocess.run(['ffmpeg','-v','error','-i',str(p),'-f','null','-'],check=True)
 v=next(s for s in d['streams'] if s['codec_type']=='video');assert int(v['nb_frames'])==1800
 assert abs(float(d['format']['duration'])-60)<.05
 vol=subprocess.run(['ffmpeg','-hide_banner','-i',str(p),'-af','volumedetect','-f','null','-'],capture_output=True,text=True,check=True)
 report['exports'].append({'file':p.name,'duration':d['format']['duration'],'frames':v['nb_frames'],'width':v['width'],'height':v['height'],'full_decode':'passed','volume':[x.strip() for x in vol.stderr.splitlines() if 'mean_volume:' in x or 'max_volume:' in x],'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 tw,th=(384,216) if fmt=='landscape' else (216,384)
 sheet=Image.new('RGB',(tw*4,(th+34)*4),'#080711');draw=ImageDraw.Draw(sheet)
 for s in t['scenes']:
  frame=R/'review'/f'{fmt}-{s["index"]:02d}.jpg'
  subprocess.run(['ffmpeg','-v','error','-ss',str(s['timeline_in']+s['duration']/2),'-i',str(p),'-frames:v','1','-vf',f'scale={tw}:{th}','-y',str(frame)],check=True)
  x=s['index']%4*tw;y=s['index']//4*(th+34);sheet.paste(Image.open(frame),(x,y));draw.text((x+8,y+th+8),f'{s["timeline_in"]:.2f}s / '+s['label'],fill='white')
 sheet.save(R/'review'/f'{fmt}-contact.jpg')
 # Poster at native resolution.
 subprocess.run(['ffmpeg','-v','error','-ss','1.5','-i',str(p),'-frames:v','1','-y',str(R/'exports'/f'poster-{fmt}.jpg')],check=True)
json.dump(report,open(R/'review/qa.json','w'),indent=2)
with open(R/'source/timeline.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=list(t['scenes'][0]));w.writeheader();w.writerows(t['scenes'])
(R/'README.md').write_text('''# Musebook / Clawd — Follow the connections

One-minute marketing video, 2 October 2026. 13 scenes at 30 fps; landscape 1920×1080 and vertical 1080×1920. Both exports contain exactly 1,800 video frames.

Uses brainy.mov, brainy34.mov, clawd-builder-320.webp, and clawd-mascot-dark.png. The two recordings have no audio streams. Soundtrack: supplied SOLGPT Night - Track 2 - Treblo.mp3, starting at 0.603719 seconds. Automated beat analysis found approximately 117.45 BPM; every scene entrance follows the measured beat grid, rounded to the nearest frame. The ending is intentionally fixed at 60 seconds rather than a beat beyond one minute.

Motion: staggered title fades with eased horizontal entrances, floating Clawd hero cards, eased footage entrances, gentle footage push-ins, and beat-aligned scene cuts. Original assets are preserved. The montage shows the supplied graph, launch tank, and Town footage without adding simulated activity.

## Editable sources
source/render.py controls clips, typography, framing, character motion, music, and shot order. source/timeline.json and timeline.csv document the edit. PNG layers and supplied character images are included with fonts and their licenses. Original MOVs and full MP3 remain at their original absolute paths and are not duplicated in the package.

Reproduce from this directory with ffmpeg/ffprobe installed:
```sh
python3 -m venv source/.venv
source/.venv/bin/pip install pillow
source/.venv/bin/python source/render.py
source/.venv/bin/python source/package_and_verify.py
```
Update the source paths in render.py when moving machines. beats.json contains the measured music beats, so reanalysis is unnecessary.

## QA and publication
review/qa.json contains full-decode checks, duration/frame count, volume peaks, beat timing error, and export hashes. Contact sheets show every scene. Nothing published.
''')
(R/'preview.html').write_text('''<!doctype html><meta charset="utf-8"><title>Musebook / Clawd — Follow the connections</title><style>body{margin:40px;background:#080711;color:#f6f7f5;font:18px system-ui}h1{color:#f34c3f}video{display:block;width:100%;max-width:1100px;margin:24px 0}.vertical{max-width:400px}</style><h1>Follow the connections.</h1><p>Musebook / Clawd · 60 seconds · Treblo</p><video controls poster="exports/poster-landscape.jpg" src="exports/musebook-brainy-60s-landscape.mp4"></video><video class="vertical" controls poster="exports/poster-vertical.jpg" src="exports/musebook-brainy-60s-vertical.mp4"></video>''')
archive=R.parent/'musebook-brainy-60s-2026-10-02.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in R.rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts or (p.suffix=='.mp4' and ('source' in p.parts or '60s' not in p.name)):continue
  z.write(p,p.relative_to(R.parent))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
print(json.dumps(report,indent=2));print('PACKAGE',archive)
