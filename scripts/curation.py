"""Automatic decisions and non-destructive manual overrides shared by both sites."""
import datetime, hashlib, json, os, re, shutil
from pathlib import Path
from PIL import Image
from photos import ROOT, LOCAL, save_json

def data_root():
    config=LOCAL/'library-config.json'
    return Path(json.loads(config.read_text())['dataRoot']) if config.exists() else LOCAL

def read_jsonl(path):
    result={}
    if path.exists():
        for line in path.read_text().splitlines():
            try:r=json.loads(line);result[r['id']]=r
            except (ValueError,KeyError):pass
    return result

def capture_time(row):
    if row.get('captured'):
        try:return datetime.datetime.strptime(row['captured'][:19],'%Y:%m:%d %H:%M:%S')
        except ValueError:pass
    return None

def hamming(a,b):return (int(a,16)^int(b,16)).bit_count()

def technical_rejection(row):
    if row.get('error'):return '文件无法解码'
    if min(row['width'],row['height'])<240:return '分辨率过低'
    if row['darkFraction']>.985 and row['contrast']<7:return '画面近乎全黑'
    if row['brightFraction']>.985 and row['contrast']<7:return '画面近乎全白'
    if row['sharpness']<3 and row['contrast']<12 and row.get('aesthetic',0)<0:return '细节和对比度均严重不足'
    return None

def rank(row):
    return row.get('aesthetic',0)+min(row.get('sharpness',0),1000)/10000+max(row.get('faceQuality',[]) or [0])*.15

def build_library():
    root=data_root();analysis=read_jsonl(root/'analysis.jsonl');vision=read_jsonl(root/'vision.jsonl')
    inventory=json.loads((root/'inventory.json').read_text())
    if len(analysis)!=len(inventory['photos']) or len(vision)!=len(analysis):raise RuntimeError('全量分析尚未完成，不覆盖现有选片结果')
    rows=[]
    for source in inventory['photos']:
        row={**analysis[source['id']],**vision[source['id']]}
        date=capture_time(row);event=source['event'];fallback=event[:8]
        row.update(date=date.strftime('%Y-%m-%d') if date else f'{fallback[:4]}-{fallback[4:6]}-{fallback[6:8]}',dateSource='exif' if date else 'folder',eventTitle=event[9:],album=event[:8],fileName=Path(source['source']).name,autoIncluded=True,reason='自动保留：未检测到严重技术缺陷或高度重复。',decision='keep',duplicateOf=None)
        rejected=technical_rejection(row)
        if rejected:row.update(autoIncluded=False,reason=rejected,decision='reject')
        rows.append(row)
    # Greedy representative matching avoids collapsing a chain of distinct moments.
    keep_by_event={};hashes={}
    for row in sorted(rows,key=rank,reverse=True):
        if not row['autoIncluded']:continue
        exact=hashes.get(row['sha256'])
        duplicate=exact
        if not duplicate:
            time=capture_time(row)
            if time:
                for other in keep_by_event.get(row['event'],[]):
                    other_time=capture_time(other)
                    if not other_time or abs((time-other_time).total_seconds())>3:continue
                    if row.get('faces')!=other.get('faces'):continue
                    if hamming(row['phash'],other['phash'])<=3 and hamming(row['dhash'],other['dhash'])<=4:
                        duplicate=other;break
        if duplicate:
            row.update(autoIncluded=False,decision='duplicate',duplicateOf=duplicate['id'],reason='完全重复文件，保留另一份。' if exact else '同一事件 3 秒内的高度相似画面，保留综合表现较好的一张。')
        else:
            hashes[row['sha256']]=row;keep_by_event.setdefault(row['event'],[]).append(row)
    editorial_path=ROOT/'content/editorial.json'
    editorial=json.loads(editorial_path.read_text()) if editorial_path.exists() else {}
    for row in rows:
        if json.loads((ROOT/'site.json').read_text())['kind']=='frame':
            row.update(autoIncluded=False,album='water',reason='未进入本次摄影书精选；可以从照片库补充。')
        if row['id'] in editorial:
            row.update(editorial[row['id']])
    save_json(LOCAL/'library.json',rows)
    print(f'{len(rows)} analyzed; {sum(r["autoIncluded"] for r in rows)} retained; {sum(r["decision"]=="duplicate" for r in rows)} duplicates; {sum(r["decision"]=="reject" for r in rows)} technical rejects',flush=True)
    return rows

def effective_rows():
    rows=json.loads((LOCAL/'library.json').read_text())
    override_file=LOCAL/'overrides.json'
    overrides=json.loads(override_file.read_text()) if override_file.exists() else {}
    result=[]
    for row in rows:
        change=overrides.get(row['id'],{})
        result.append({**row,'included':change.get('included',row['autoIncluded']),'album':change.get('album',row['album']),'title':change.get('title',row.get('title',row['fileName'])),'manual':bool(change)})
    return result

def materialize():
    kind=json.loads((ROOT/'site.json').read_text())['kind'];data=data_root();output=[];selections=[]
    rows=effective_rows()
    for row in rows:
        if not row['included']:continue
        if row.get('error'):raise ValueError('无法加入损坏的文件：'+row['id'])
        key=row['sha256'][:24]+'-jpeg-v2'
        folder=ROOT/'public/media'/key;folder.mkdir(parents=True,exist_ok=True)
        preview=data/'previews'/f'{row["id"]}.jpg'
        if not (folder/'1600.jpg').exists():shutil.copy2(preview,folder/'1600.jpg')
        if not (folder/'480.jpg').exists():
            with Image.open(data/'thumbs'/f'{row["id"]}.jpg') as image:
                image.thumbnail((480,480));clean=Image.frombytes('RGB',image.size,image.tobytes());clean.save(folder/'480.jpg',quality=84)
        with Image.open(folder/'480.jpg') as small:small_size=small.size
        with Image.open(folder/'1600.jpg') as large:large_size=large.size
        variants=[{'bound':480,'width':small_size[0],'height':small_size[1]},{'bound':1600,'width':large_size[0],'height':large_size[1]}]
        # A photography book gets a larger, original-JPEG-derived display master.
        if kind=='frame':
            if not (folder/'2560.jpg').exists():
                from photos import srgb_image
                inventory=json.loads((data/'inventory.json').read_text())
                image=srgb_image(Path(inventory['root'])/row['source']);image.thumbnail((2560,2560),Image.Resampling.LANCZOS)
                clean=Image.frombytes('RGB',image.size,image.tobytes());clean.save(folder/'2560.jpg',quality=91)
            with Image.open(folder/'2560.jpg') as full:variants.append({'bound':2560,'width':full.width,'height':full.height})
        title=row.get('title') or row['fileName']
        item=dict(id=row['id'],title=title,caption=row.get('caption') or title,album=row['album'],event=row['eventTitle'],date=row['date'],dateSource=row['dateSource'],included=True,decisionSource='manual' if row['manual'] else ('editorial' if kind=='frame' else 'automatic'),reason=row['reason'],key=key,width=row['width'],height=row['height'],variants=variants,formats=['jpg'])
        output.append(item);selections.append({k:v for k,v in item.items() if k not in ['key','width','height','variants','formats']})
    save_json(ROOT/'content/catalog.json',output);save_json(ROOT/'content/selections.json',selections)
    print(f'{kind}: {len(output)} photos prepared',flush=True)
    return len(output)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['classify','materialize']);args=parser.parse_args()
    build_library() if args.action=='classify' else materialize()
