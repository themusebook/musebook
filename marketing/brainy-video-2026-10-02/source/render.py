from pathlib import Path
import subprocess,json,shutil,math
from PIL import Image,ImageDraw,ImageFont,ImageFilter
R=Path(__file__).resolve().parent.parent
OLD=R.parent/'video-2026-10-02'
(R/'source/fonts').mkdir(exist_ok=True)
for p in (OLD/'source/fonts').iterdir():shutil.copy2(p,R/'source/fonts'/p.name)
shutil.copy2(OLD/'source/beats.json',R/'source/beats.json')
for name in ['clawd-builder-320.webp','clawd-mascot-dark.png']:
 shutil.copy2(Path('/Users/8bit/Downloads/clawd-webmcp-starter/musebook-private/web-react/public/brand')/name,R/'source/assets'/name)
b=json.load(open(R/'source/beats.json'));origin=b['beats'][0];idx=[0,8,20,32,40,48,56,64,72,80,88,96,104];ts=[round((b['beats'][n]-origin)*30)/30 for n in idx]+[60.0]
scenes=[
(None,0,'MUSEBOOK / CLAWD','Follow the\nconnections.','Explore. Create. Build together.','mascot'),
('brainy.mov',1,'CONNECTED IDEAS','Start with a connection.','Look closer. Find the pattern.',None),
('brainy.mov',10,'EXPLORE THE GRAPH','See the bigger picture.','Follow the links between ideas.',None),
('brainy.mov',23,'A WORLD OF SIGNALS','Find your own path.','From a single node to a wider view.',None),
(None,0,'CLAWD IS ONLINE','Big ideas.\nSmall claws.','Meet your curious companion.','mascot'),
('brainy34.mov',1,'THE LAUNCH TANK','Explore what is building.','A closer look inside Musebook.',None),
('brainy34.mov',5,'LOOK A LITTLE CLOSER','Discover something new.','Explore the launch tank.',None),
('brainy34.mov',11,'MUSEBOOK TOWN','Enter the Town.','An island of places to explore.',None),
('brainy34.mov',18,'A PLACE TO EXPLORE','Take a look around.','Follow your curiosity through the Town.',None),
(None,0,'BUILD WITH CLAWD','Make your\nnext move.','Curiosity looks good on you.','builder'),
('brainy34.mov',25,'PLACES TO DISCOVER','Choose your next stop.','Look around. Open something new.',None),
('brainy.mov',18,'BACK TO THE BIG PICTURE','Keep connecting.','The next idea starts with a closer look.',None),
(None,0,'YOUR NEXT STOP','musebook.trade','Explore. Create. Build together.','mascot')]

t={'bpm_detected':b['bpm'],'music':'/Users/8bit/Downloads/SOLGPT Night - Track 2 - Treblo.mp3','music_start':origin,'duration':ts[-1],'fps':30,'scenes':[]}
for i,(p,st,label,title,sub,mascot) in enumerate(scenes):t['scenes'].append(dict(index=i,recording='/Users/8bit/Downloads/'+p if p else None,source_in=st,timeline_in=ts[i],duration=ts[i+1]-ts[i],label=label,title=title,subtitle=sub,mascot=mascot,beat_index=idx[i]))
json.dump(t,open(R/'source/timeline.json','w'),indent=2)
def font(n,mono=False):return ImageFont.truetype(str(R/'source/fonts'/('DMMono-Regular.ttf' if mono else 'BricolageGrotesque-Bold.ttf')),n)
def run(a):subprocess.run(['ffmpeg','-v','error','-y']+a,check=True)
def render(fmt,w,h):
 folder=R/'source'/fmt;folder.mkdir(exist_ok=True);vert=h>w
 for s in t['scenes']:
  i=s['index'];dur=s['duration'];hero=s['recording'] is None
  base=Image.new('RGBA',(w,h),'#080711');d=ImageDraw.Draw(base)
  # Fine orbital grid provides movement cues without obscuring the recordings.
  cx,cy=int(w*.75),int(h*.45)
  for rad in [160,270,400,570,760]:d.ellipse((cx-rad,cy-rad,cx+rad,cy+rad),outline='#161326',width=2)
  d.line((60,60,w-60,60),fill='#3B2F4B',width=2);d.rectangle((60,60,190,65),fill='#F34C3F');d.rectangle((190,60,290,65),fill='#C8F0DC')
  d.text((60,85),'musebook',font=font(34),fill='#F6F7F5');d.text((w-255,95),'CLAWD / ONLINE',font=font(18,True),fill='#C8F0DC')
  d.text((60,h-65),'MUSEBOOK.TRADE',font=font(22,True),fill='#C8F0DC')
  d.text((w-195,h-65),f'{i+1:02d} / 13',font=font(20,True),fill='#827990')
  title=Image.new('RGBA',(w,h));td=ImageDraw.Draw(title)
  if hero:
   tx,ty=(70,270) if vert else (100,300)
   td.text((tx,ty),s['label'],font=font(22,True),fill='#C8F0DC')
   lines=s['title'].split('\n')
   if vert and i==12:lines=['musebook','.trade']
   size=100 if i!=9 else (100 if vert else 82)
   for j,line in enumerate(lines):td.text((tx-5,ty+58+j*114),line,font=font(size),fill='#F34C3F' if j==1 or i==12 else '#F6F7F5')
   td.text((tx,ty+75+len(lines)*114),s['subtitle'],font=font(27),fill='#DAD4E7')
   mw=820 if vert else 760;mx=(w-mw)//2 if vert else w-mw-40;my=850 if vert else 195
   img=Image.open(R/'source/assets'/('clawd-mascot-dark.png' if s['mascot']=='mascot' else 'clawd-builder-320.webp')).convert('RGBA')
   img=img.resize((mw,mw),Image.Resampling.LANCZOS);img.save(folder/f'character-{i}.png')
  else:
   box=(60,560,w-60,1420) if vert else (90,280,w-90,940)
   tx,ty=(60,285) if vert else (90,155)
   td.text((tx,ty),s['label'],font=font(20,True),fill='#C8F0DC')
   headline_size=62 if vert else 66
   # Fit headline to safe width.
   while td.textbbox((0,0),s['title'],font=font(headline_size))[2]>w-120:headline_size-=1
   td.text((tx,ty+40),s['title'],font=font(headline_size),fill='#F6F7F5')
   d.rounded_rectangle((box[0]-3,box[1]-3,box[2]+3,box[3]+3),radius=4,outline='#514064',width=3)
   td.text((tx,box[3]+30),s['subtitle'],font=font(27),fill='#DAD4E7')
   # Small builder badge sits with the section label, away from the UI.
   badge=Image.open(R/'source/assets/clawd-builder-320.webp').convert('RGBA');badge.thumbnail((100,100));base.alpha_composite(badge,(w-175,155 if not vert else 430))
  base.save(folder/f'base-{i}.png');title.save(folder/f'title-{i}.png')
  inputs=['-loop','1','-framerate','30','-i',str(folder/f'base-{i}.png')]
  if hero:
   inputs+=['-loop','1','-framerate','30','-i',str(folder/f'character-{i}.png'),'-loop','1','-framerate','30','-i',str(folder/f'title-{i}.png')]
   graph=f"[1:v]format=rgba,fade=t=in:st=0:d=0.25:alpha=1[c];[0:v][c]overlay=x='{mx}+20*sin(2*PI*t/4.1)':y='{my}+14*sin(2*PI*t/2.04)+65*exp(-7*t)'[v];[2:v]format=rgba,fade=t=in:st=0.10:d=0.25:alpha=1[txt];[v][txt]overlay=x='-90*exp(-9*t)':y=0,fade=t=out:st={dur-.14}:d=0.14[out]"
  else:
   bw,bh=box[2]-box[0],box[3]-box[1]
   inputs+=['-ss',str(s['source_in']),'-i',s['recording'],'-loop','1','-framerate','30','-i',str(folder/f'title-{i}.png')]
   graph=f"[1:v]fps=30,eq=brightness=0.025:contrast=1.04,scale={bw}:{bh}:force_original_aspect_ratio=decrease,pad={bw}:{bh}:(ow-iw)/2:(oh-ih)/2:color=0x080711,zoompan=z='1.01+0.00006*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={bw}x{bh}:fps=30,setsar=1[v];[0:v][v]overlay=x={box[0]}:y='{box[1]}+30*exp(-8*t)'[canvas];[2:v]format=rgba,fade=t=in:st=0.05:d=0.22:alpha=1[txt];[canvas][txt]overlay=x='-65*exp(-10*t)':y=0,fade=t=in:d=0.1[out]"
  run(inputs+['-filter_complex',graph,'-map','[out]','-an','-t',str(dur),'-r','30','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(folder/f'scene-{i:02d}.mp4')])
  print(fmt,'scene',i,'done',flush=True)
 concat=folder/'concat.txt';concat.write_text(''.join(f"file '{folder/f'scene-{i:02d}.mp4'}'\n" for i in range(len(scenes))))
 run(['-f','concat','-safe','0','-i',str(concat),'-c','copy',str(folder/'joined.mp4')])
 run(['-i',str(folder/'joined.mp4'),'-ss',str(origin),'-i',t['music'],'-map','0:v','-map','1:a','-af',f"afade=t=in:d=0.10,afade=t=out:st={t['duration']-1.0}:d=1.0,volume=1.2,alimiter=limit=0.95",'-c:v','copy','-c:a','aac','-b:a','256k','-ar','48000','-t',str(t['duration']),'-movflags','+faststart',str(R/'exports'/f'musebook-brainy-60s-{fmt}.mp4')])
 print('EXPORT',fmt,flush=True)
render('landscape',1920,1080)
render('vertical',1080,1920)
