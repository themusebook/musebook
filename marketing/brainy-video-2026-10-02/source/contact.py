from PIL import Image,ImageDraw
import subprocess
from pathlib import Path
r=Path(__file__).resolve().parent.parent
out=Image.new('RGB',(1600,540),'#0a0814');d=ImageDraw.Draw(out)
for i,p in enumerate(['/Users/8bit/Downloads/brainy.mov','/Users/8bit/Downloads/brainy34.mov']):
 for j,t in enumerate([2,10,18,26]):
  f=r/'review'/f'input-{i}-{j}.jpg';subprocess.run(['ffmpeg','-v','error','-ss',str(t),'-i',p,'-frames:v','1','-vf','scale=400:240:force_original_aspect_ratio=decrease,pad=400:240:(ow-iw)/2:(oh-ih)/2','-y',str(f)],check=True)
  out.paste(Image.open(f),(j*400,i*270));d.text((j*400+10,i*270+245),f'{Path(p).name} / {t}s',fill='white')
out.save(r/'review/inputs.jpg')
