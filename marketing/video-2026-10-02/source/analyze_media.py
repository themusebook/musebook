import subprocess,glob,json
from PIL import Image,ImageDraw
ps=[glob.glob('/Users/8bit/Downloads/Screen Recording 2026-10-02 at '+t+'*.mov')[0] for t in ['1.17.02','2.07.00','1.14.51']]
out=Image.new('RGB',(1600,840),'#101010');d=ImageDraw.Draw(out)
for r,p in enumerate(ps):
 for c,t in enumerate([1,7,13,17 if r==2 else 23]):
  dest=f'marketing/video-2026-10-02/review/frame-{r}-{c}.jpg'
  subprocess.run(['ffmpeg','-v','error','-ss',str(t),'-i',p,'-frames:v','1','-vf','scale=400:250:force_original_aspect_ratio=decrease,pad=400:250:(ow-iw)/2:(oh-ih)/2','-y',dest],check=True)
  out.paste(Image.open(dest),(400*c,280*r));d.text((400*c+8,280*r+252),f'{r+1} / {t}s',fill='white')
out.save('marketing/video-2026-10-02/review/contact.jpg')
subprocess.run(['ffmpeg','-v','error','-i','/Users/8bit/Downloads/SOLGPT Night - Track 2 - Treblo.mp3','-ac','1','-ar','22050','-y','marketing/video-2026-10-02/review/music.wav'],check=True)
import librosa,numpy as np
y,sr=librosa.load('marketing/video-2026-10-02/review/music.wav',sr=22050)
tempo,beats=librosa.beat.beat_track(y=y,sr=sr,trim=False)
ts=librosa.frames_to_time(beats,sr=sr)
json.dump({'bpm':float(np.asarray(tempo).flat[0]),'beats':ts.tolist()},open('marketing/video-2026-10-02/source/beats.json','w'),indent=2)
print('BPM',tempo,'first beats',ts[:24])
