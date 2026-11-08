"""Resumable all-JPEG analysis. NAS is read-only; private previews and metrics stay local."""
import concurrent.futures, hashlib, io, json, os, subprocess, time
from pathlib import Path
import numpy as np
import imagehash
from PIL import Image, ImageOps, ImageCms
from photos import ROOT, LOCAL, save_json

def process(row):
    try:
        source = Path(INVENTORY['root']) / row['source']
        raw = source.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        with Image.open(io.BytesIO(raw)) as im:
            exif = im.getexif()
            width, height = im.size
            # Read the EXIF sub-IFD; filenames/mtime are only a fallback.
            detail = exif.get_ifd(34665) if 34665 in exif else {}
            captured = detail.get(36867) or exif.get(36867) or exif.get(306)
            im.draft('RGB',(1600,1600))
            im = ImageOps.exif_transpose(im)
            profile = im.info.get('icc_profile')
            if profile:
                im = ImageCms.profileToProfile(im,ImageCms.ImageCmsProfile(io.BytesIO(profile)),ImageCms.createProfile('sRGB'),outputMode='RGB')
            else: im = im.convert('RGB')
            if exif.get(274) in (5,6,7,8):width,height=height,width
            im.thumbnail((1600,1600),Image.Resampling.LANCZOS)
            clean = Image.frombytes('RGB',im.size,im.tobytes())
            clean.save(LOCAL/'previews'/f'{row["id"]}.jpg',quality=87)
            small=clean.copy();small.thumbnail((640,640));small.save(LOCAL/'thumbs'/f'{row["id"]}.jpg',quality=82)
            gray=small.convert('L');a=np.array(gray,dtype=np.float32)
            lap=-4*a[1:-1,1:-1]+a[:-2,1:-1]+a[2:,1:-1]+a[1:-1,:-2]+a[1:-1,2:]
            result={**row,'sha256':sha,'width':width,'height':height,'previewWidth':clean.width,'previewHeight':clean.height,'phash':str(imagehash.phash(small)),'dhash':str(imagehash.dhash(small)),'sharpness':round(float(lap.var()),3),'darkFraction':round(float((a<8).mean()),4),'brightFraction':round(float((a>249).mean()),4),'contrast':round(float(a.std()),3),'captured':str(captured) if captured else None,'camera':str(exif.get(272,''))}
            return result
    except Exception as error:return {**row,'error':str(error)}

def main():
    global INVENTORY
    INVENTORY=json.loads((LOCAL/'inventory.json').read_text())
    for folder in ['previews','thumbs']:(LOCAL/folder).mkdir(exist_ok=True)
    path=LOCAL/'analysis.jsonl';done={}
    if path.exists():
        for line in path.read_text().splitlines():
            try:r=json.loads(line);done[r['id']]=r
            except ValueError:pass
    todo=[r for r in INVENTORY['photos'] if r['id'] not in done or done[r['id']].get('mtime')!=r['mtime'] or done[r['id']].get('error')]
    start=time.time()
    with path.open('a') as log,concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for i,r in enumerate(pool.map(process,todo)):
            log.write(json.dumps(r,ensure_ascii=False)+'\n');log.flush()
            if (i+1)%100==0:print(f'JPEG analysis {i+1}/{len(todo)} ({time.time()-start:.0f}s)',flush=True)
    print('JPEG analysis complete',flush=True)

if __name__=='__main__':main()
