"""Explicit, isolated presentation sessions with synthetic fixtures only."""
from pathlib import Path
from datetime import date,timedelta
import os,uuid,json,hashlib
from PIL import Image,ImageDraw,ImageFont

def create_session(parent=None):
    # A new directory for each rehearsal: no existing material is overwritten.
    parent=Path(parent or (Path.home()/'MVR-Presentation'))
    if parent.exists() and (parent.is_symlink() or getattr(parent.lstat(),'st_file_attributes',0)&0x400):
        raise PermissionError('Presentation directory may not be a link')
    parent.mkdir(parents=True,exist_ok=True)
    session=parent/('session-'+uuid.uuid4().hex[:12]);session.mkdir()
    data=session/'state';data.mkdir()
    files=session/'DemoFiles';files.mkdir()
    pics=files/'Pictures';pics.mkdir();docs=files/'Documents';docs.mkdir();downloads=files/'Downloads';downloads.mkdir()
    def picture(name,background,subject):
        im=Image.new('RGB',(768,512),background);d=ImageDraw.Draw(im)
        if subject=='car':
            d.rounded_rectangle((95,254,675,388),radius=42,fill='#2364cf')
            d.polygon([(180,256),(265,155),(485,155),(580,256)],fill='#2364cf')
            d.polygon([(276,172),(473,172),(544,246),(211,246)],fill='#cce6fa')
            for x in (180,520):d.ellipse((x,337,x+105,442),fill='#252833')
        elif subject=='bottle':
            d.rounded_rectangle((295,145,473,420),radius=30,fill='#faf7eb')
            d.rectangle((330,97,438,145),fill='#24252a')
            d.rectangle((310,239,458,312),fill='#c5b8a6')
        else:
            d.rectangle((374,220,394,445),fill='#38623f')
            for x,y in ((322,110),(392,110),(282,180),(432,180),(355,235)):
                d.ellipse((x,y,x+100,y+100),fill='#f2c32d')
            d.ellipse((344,177,427,260),fill='#7d4b22')
        im.save(pics/name,quality=94)
    # Opaque filenames deliberately omit subjects, so a visual search cannot pass by guessing filenames.
    picture('IMG_4128.jpg','#e9edf3','car')
    picture('IMG_0631.jpg','#bf2635','bottle')
    picture('IMG_0987.jpg','#edf2e7','flower')
    (docs/'春季活動_社群文案.txt').write_text('春季新品活動｜第二件九折\n活動主題：讓日常煥然一新。\n展示用合成文案，非真實客戶資料。',encoding='utf-8')
    (docs/'春季活動_成效.csv').write_text('metric,value\nimpressions,12000\nclicks,480\n',encoding='utf-8')
    # Minimal valid one-page PDF with ASCII content; no external dependency.
    stream=b'BT /F1 18 Tf 48 720 Td (MarVoiReflex - Synthetic campaign proposal) Tj ET'
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    pdf=bytearray(b'%PDF-1.4\n');offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(pdf));pdf.extend(str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n')
    xref=len(pdf);pdf.extend(b'xref\n0 6\n0000000000 65535 f \n')
    for off in offsets[1:]:pdf.extend(f'{off:010d} 00000 n \n'.encode())
    pdf.extend(f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    proposal=downloads/'春季活動_提案.pdf';proposal.write_bytes(pdf)
    from datetime import datetime
    yesterday=(datetime.now()-timedelta(days=1)).timestamp();os.utime(proposal,(yesterday,yesterday))
    manifest={f.relative_to(files).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(files.rglob('*')) if f.is_file()}
    (session/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return data,files

def roots_for(files):
    files=Path(files)
    return [(files/'Pictures','pictures'),(files/'Documents','documents'),(files/'Downloads','downloads')]
