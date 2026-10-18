import pathlib,json,shutil,zipfile
from PIL import Image,ImageDraw,ImageFont
R=pathlib.Path(__file__).resolve().parent
records=json.loads((R/'manifest.json').read_text())
out=R/'screenshots';out.mkdir(exist_ok=True)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',18)
for v in records:
    name=v['video'];t=round(v['target_seconds'],2)
    source=R/'frames'/name/f'{name}__t{t:07.2f}.jpg'
    if not source.exists():
        source=min((R/'frames'/name).glob('*.jpg'),key=lambda p:abs(float(p.stem.split('__t')[1])-t))
    im=Image.open(source)
    panel=Image.new('RGB',(max(im.width,560),im.height+100),'white')
    panel.paste(im,((panel.width-im.width)//2,0))
    d=ImageDraw.Draw(panel)
    for i,text in enumerate([f'{name}.mov — {t:.2f} с — исходный кадр',f"Метка таблицы: {v['label']}",'Момент из таблицы' if v['source_timestamp'] else 'Обзорный кадр: середина видео']):
        d.text((12,im.height+10+i*27),text,font=font,fill='black')
    dest=out/f'{name}__REAL__t{t:07.2f}.jpg';panel.save(dest,quality=95)
    v['screenshot']=str(dest.relative_to(R))
    v['reference_frame']=str(source.relative_to(R))
    v['review_status']='overview_sequence_reviewed; violation_definition_pending'
    v['selection_status']='source_timestamp' if v['source_timestamp'] else 'provisional_midpoint'
    v['generation_status']='awaiting_violation_definition'
(R/'manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
with zipfile.ZipFile(R/'real_screenshots_42.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(out.glob('*.jpg')):z.write(p,p.relative_to(R))
    for p in sorted((R/'contact_sheets').glob('*.jpg')):
        if not p.name.startswith('batch_'):z.write(p,p.relative_to(R))
    z.write(R/'manifest.json','manifest.json')
assert len(list(out.glob('*.jpg')))==42
print('42 labeled screenshots, 42 contact sheets; generated images: 0')
