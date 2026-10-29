from pathlib import Path
import glob,json,subprocess,shutil
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent.parent
FONTROOT=Path('/Users/8bit/Downloads/clawd-webmcp-starter/musebook-private/marketing/campaign-2026-09-27/fonts')
(ROOT/'source/fonts').mkdir(exist_ok=True)
for p in FONTROOT.iterdir():shutil.copy2(p,ROOT/'source/fonts'/p.name)
paths=[glob.glob('/Users/8bit/Downloads/Screen Recording 2026-10-02 at '+t+'*.mov')[0] for t in ['1.17.02','2.07.00','1.14.51']]
beat=json.load(open(ROOT/'source/beats.json'))
b=beat['beats'];origin=b[0]
indices=[0,4,12,20,28,32,36,44,52,56,64]
times=[round((b[n]-origin)*30)/30 for n in indices]
scenes=[
(None,0,'MUSEBOOK','Catch the first signal.','Explore the market. Find your next move.'),
(2,11,'MARKET DISCOVERY','Catch the first signal.','A closer look at the Musebook feed.'),
(2,1,'LIVE ACTIVITY','Follow the live feed.','Watch market activity unfold.'),
(1,0,'TOKEN DISCOVERY','Explore tokens.','Inspect the details that matter.'),
(1,2.5,'WALLET REVIEW','Review before signing.','See the amount. Set your slippage.'),
(1,6,'WALLET REVIEW','Stay in control.','Review a fresh quote before signing.'),
(0,11,'SOLGPT WORKSPACE','Meet your workspace.','Markets, tools, and Clawd in one view.'),
(1,20,'AGENT TOKENS','Discover agent tokens.','Explore what is moving.'),
(2,12,'MUSEBOOK','Find your next signal.','Explore at musebook.trade'),
(None,0,'EXPLORE MUSEBOOK','musebook.trade','Catch the first signal.')]
timeline={'bpm_detected':beat['bpm'],'music': '/Users/8bit/Downloads/SOLGPT Night - Track 2 - Treblo.mp3','music_start':origin,'fps':30,'duration':times[-1],'scenes':[]}
for i,(src,start,label,title,sub) in enumerate(scenes):timeline['scenes'].append({'index':i,'recording':None if src is None else paths[src],'source_in':start,'timeline_in':times[i],'duration':times[i+1]-times[i],'label':label,'title':title,'subtitle':sub,'beat_index':indices[i]})
json.dump(timeline,open(ROOT/'source/timeline.json','w'),indent=2)
def run(args):subprocess.run(['ffmpeg','-v','error','-y']+args,check=True)
def font(size,mono=False):return ImageFont.truetype(str(ROOT/'source/fonts'/('DMMono-Regular.ttf' if mono else 'BricolageGrotesque-Bold.ttf')),size)
def render(fmt,w,h):
 folder=ROOT/'source'/fmt;folder.mkdir(exist_ok=True)
 vertical=h>w
 if vertical:box=(60,570,w-60,1410);heady=270;title_size=64
 else:box=(110,260,w-110,940);heady=90;title_size=64
 for s in timeline['scenes']:
  i=s['index'];dur=s['duration'];src=s['recording'];im=Image.new('RGBA',(w,h),(10,8,20,255));d=ImageDraw.Draw(im)
  # Subtle ruled frame and coral/mint signal marks.
  d.line((60,54,w-60,54),fill='#302941',width=2);d.rectangle((60,54,150,59),fill='#F34C3F');d.rectangle((150,54,240,59),fill='#C8F0DC')
  d.text((60,78),'musebook',font=font(30),fill='#F6F7F5');d.text((w-205,85),f'{i+1:02d} / 10',font=font(19,True),fill='#C8F0DC')
  if src:
   d.text((box[0],heady+50 if not vertical else heady),s['label'],font=font(19,True),fill='#C8F0DC')
   d.text((box[0],heady+83 if not vertical else heady+45),s['title'],font=font(title_size),fill='#F6F7F5')
   d.rectangle((box[0]-3,box[1]-3,box[2]+3,box[3]+3),fill='#40354E')
   d.rectangle(box,fill=(0,0,0,0))
   d.text((box[0],box[3]+32),s['subtitle'],font=font(25 if not vertical else 27),fill='#D8D1E2')
  else:
   y=620 if vertical else 350
   d.text((90,y-65),s['label'],font=font(24,True),fill='#C8F0DC')
   title=s['title'];lines=['Catch the','first signal.'] if i==0 else ['musebook.trade']
   if vertical and i==9:lines=['musebook','.trade']
   for j,line in enumerate(lines):d.text((85,y+j*115),line,font=font(100 if vertical else 108),fill='#F34C3F' if j==1 or i==9 else '#F6F7F5')
   d.text((90,y+len(lines)*115+30),s['subtitle'],font=font(29),fill='#D8D1E2')
   d.line((90,y+len(lines)*115+100,w-90,y+len(lines)*115+100),fill='#40354E',width=2)
  d.text((60,h-65),'MUSEBOOK.TRADE',font=font(20,True),fill='#C8F0DC')
  d.text((w-335,h-65),'CAPTURED 02 OCT 2026',font=font(17,True),fill='#8B829D')
  png=folder/f'layer-{i:02d}.png';im.save(png)
  output=folder/f'scene-{i:02d}.mp4'
  enc=['-t',str(dur),'-r','30','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-ar','48000',str(output)]
  if src:
   bw,bh=box[2]-box[0],box[3]-box[1]
   graph=f'[0:v]fps=30,scale={bw}:{bh}:force_original_aspect_ratio=decrease,pad={bw}:{bh}:(ow-iw)/2:(oh-ih)/2:color=0x0A0814,setsar=1[v];color=c=0x0A0814:s={w}x{h}:r=30[bg];[bg][v]overlay={box[0]}:{box[1]}[base];[base][1:v]overlay=0:0,fade=t=in:st=0:d=0.10[out];[0:a]atrim=duration={dur},asetpts=PTS-STARTPTS,afade=t=in:d=0.04,afade=t=out:st={max(0,dur-.06)}:d=0.06[a]'
   run(['-ss',str(s['source_in']),'-i',src,'-loop','1','-i',str(png),'-filter_complex',graph,'-map','[out]','-map','[a]']+enc)
  else:run(['-loop','1','-i',str(png),'-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-vf','fade=t=in:d=0.2','-map','0:v','-map','1:a']+enc)
  print(fmt,'scene',i,'done',flush=True)
 concat=folder/'concat.txt';concat.write_text(''.join(f"file '{folder/f'scene-{i:02d}.mp4'}'\n" for i in range(len(scenes))))
 joined=folder/'joined.mp4';run(['-f','concat','-safe','0','-i',str(concat),'-c','copy',str(joined)])
 duration=timeline['duration'];out=ROOT/'exports'/f'musebook-beatsync-{fmt}.mp4'
 graph=f'[0:a]volume=2.0[s];[1:a]atrim=duration={duration},asetpts=PTS-STARTPTS,afade=t=in:d=0.12,afade=t=out:st={duration-1.1}:d=1.1,volume=0.85[m];[s][m]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]'
 run(['-i',str(joined),'-ss',str(origin),'-i',timeline['music'],'-filter_complex',graph,'-map','0:v','-map','[a]','-c:v','copy','-c:a','aac','-b:a','256k','-t',str(duration),'-movflags','+faststart',str(out)])
 print('EXPORT',out,flush=True)
render('landscape',1920,1080)
render('vertical',1080,1920)
