import sys, pathlib, json, re, hashlib, subprocess
sys.path.insert(0, '/private/tmp/video_angles_deps')
import imageio_ffmpeg, openpyxl
from PIL import Image, ImageDraw
ROOT = pathlib.Path(__file__).resolve().parent
ff = imageio_ffmpeg.get_ffmpeg_exe()
rows = list(openpyxl.load_workbook(ROOT/'source/open/open_labels.xlsx', data_only=True).active.values)[1:]
records=[]
seen={}
for name,stamp,label in rows:
    src=ROOT/'source/open/videos'/f'{name}.mov'
    digest=hashlib.sha256(src.read_bytes()).hexdigest()
    info=subprocess.run([ff,'-i',str(src)],capture_output=True,text=True).stderr
    h,m,s=re.search(r'Duration: (\d+):(\d+):([\d.]+)',info).groups()
    duration=int(h)*3600+int(m)*60+float(s)
    nums=[int(n) for n in re.findall(r'\d+',stamp or '')]
    target=(nums[0]*60+nums[1] if len(nums)==2 else nums[0]) if nums else duration*.5
    out=ROOT/'frames'/name
    out.mkdir(parents=True,exist_ok=True)
    times=sorted(set([round(duration*f,2) for f in [.08,.25,.5,.75,.92]]+[max(0,min(duration-.1,target+delta)) for delta in [-1,0,1]]))
    canvas=Image.new('RGB',(1280,((len(times)+3)//4)*220),'white')
    draw=ImageDraw.Draw(canvas)
    for i,t in enumerate(times):
        p=out/f'{name}__t{t:07.2f}.jpg'
        subprocess.run([ff,'-v','error','-ss',str(t),'-i',str(src),'-frames:v','1','-q:v','2','-y',str(p)],check=True)
        im=Image.open(p); im.thumbnail((320,190))
        x=(i%4)*320;y=(i//4)*220
        canvas.paste(im,(x+(320-im.width)//2,y))
        draw.text((x+5,y+195),f'{name} | {t:.2f}s',fill='black')
    sheets=ROOT/'contact_sheets';sheets.mkdir(exist_ok=True)
    canvas.save(sheets/f'{name}.jpg')
    records.append(dict(video=name,source=str(src.relative_to(ROOT)),label=label,source_timestamp=stamp,target_seconds=target,duration=duration,sha256=digest,duplicate_of=seen.get(digest),review_status='pending',generated=[]))
    seen.setdefault(digest,name)
    (ROOT/'manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
    print(name,label,duration,'duplicate:',records[-1]['duplicate_of'],flush=True)
