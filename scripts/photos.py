"""Read-only NAS inventory and reproducible JPEG derivatives. All private state is ignored by Git."""
import argparse, hashlib, io, json, os
from pathlib import Path
from PIL import Image, ImageOps, ImageCms, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local'
PIPELINE = 'srgb-v1'

def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    tmp.replace(path)

def scan(source):
    source = Path(source).resolve()
    rows = []
    for directory, dirs, files in os.walk(source):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d not in ('@eaDir', '#recycle'))
        for filename in sorted(files):
            p = Path(directory) / filename
            if p.suffix.lower() not in ('.jpg', '.jpeg') or p.name.startswith('.') or p.is_symlink():
                continue
            rel = p.relative_to(source).as_posix()
            stat = p.stat()
            rows.append(dict(id=hashlib.sha256(rel.encode()).hexdigest()[:20], source=rel,
                             event=rel.split('/')[0], bytes=stat.st_size, mtime=stat.st_mtime_ns))
    save_json(LOCAL / 'inventory.json', dict(root=str(source), photos=rows))
    print(f'Indexed {len(rows)} JPEGs; {sum(r["bytes"] for r in rows)/1024**3:.2f} GiB', flush=True)

def sample(per_event):
    inventory = json.loads((LOCAL / 'inventory.json').read_text())
    groups = {}
    for p in inventory['photos']:
        groups.setdefault(p['event'], []).append(p)
    samples = []
    for event, rows in groups.items():
        n = min(per_event, len(rows))
        samples.extend(rows[round(i * (len(rows)-1) / max(1, n-1))] for i in range(n))
    cache = LOCAL / 'thumbnails'; cache.mkdir(parents=True, exist_ok=True)
    for i, row in enumerate(samples):
        out = cache / (row['id'] + '.jpg')
        if not out.exists():
            with Image.open(Path(inventory['root']) / row['source']) as image:
                image.draft('RGB', (800, 800))
                image = ImageOps.exif_transpose(image).convert('RGB')
                image.thumbnail((600, 440))
                image.save(out, quality=85)
        row['sample'] = i + 1
    save_json(LOCAL / 'samples.json', samples)
    for start in range(0, len(samples), 40):
        sheet = Image.new('RGB', (1400, 1900), '#f5f3ee')
        draw = ImageDraw.Draw(sheet)
        for offset, row in enumerate(samples[start:start+40]):
            with Image.open(cache / (row['id'] + '.jpg')) as im:
                im.thumbnail((270, 205))
                x, y = (offset % 5) * 280, (offset // 5) * 237
                sheet.paste(im, (x+(280-im.width)//2, y))
                draw.text((x+6, y+210), f'{row["sample"]}  {Path(row["source"]).name}', fill='#222222')
        sheet.save(LOCAL / f'contact-{start//40+1}.jpg', quality=90)
    print(f'{len(samples)} samples; {(len(samples)+39)//40} contact sheets', flush=True)

def srgb_image(path):
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source)
        profile = source.info.get('icc_profile')
        if profile:
            image = ImageCms.profileToProfile(image, ImageCms.ImageCmsProfile(io.BytesIO(profile)),
                                             ImageCms.createProfile('sRGB'), outputMode='RGB')
        else:
            image = image.convert('RGB')
        return image.copy()

def prepare():
    inventory = json.loads((LOCAL / 'inventory.json').read_text())
    indexed = {row['id']: row for row in inventory['photos']}
    selected = json.loads((ROOT / 'content/selections.json').read_text())
    result = []
    for choice in selected:
        row = indexed[choice['id']]
        path = Path(inventory['root']) / row['source']
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        key = f'{digest[:24]}-{PIPELINE}'
        destination = ROOT / 'public/media' / key
        info = destination / 'info.json'
        if not info.exists():
            im = srgb_image(path)
            destination.mkdir(parents=True, exist_ok=True)
            variants = []
            for bound in (480, 960, 1600, 2560):
                small = im.copy(); small.thumbnail((bound, bound), Image.Resampling.LANCZOS)
                # Recreate pixel-only image so inherited EXIF/XMP/IPTC cannot survive encoding.
                clean = Image.frombytes('RGB', small.size, small.tobytes())
                clean.save(destination / f'{bound}.jpg', quality=88, optimize=True, progressive=True)
                clean.save(destination / f'{bound}.webp', quality=85, method=6)
                variants.append(dict(bound=bound, width=small.width, height=small.height))
            save_json(info, dict(width=im.width, height=im.height, variants=variants))
        dimensions = json.loads(info.read_text())
        result.append(dict(**choice, key=key, **dimensions))
        print(f'Prepared {choice["id"]}', flush=True)
    save_json(ROOT / 'content/catalog.json', result)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    scan_p = sub.add_parser('scan'); scan_p.add_argument('source')
    sample_p = sub.add_parser('sample'); sample_p.add_argument('--per-event', type=int, default=6)
    sub.add_parser('prepare')
    args = parser.parse_args()
    if args.command == 'scan': scan(args.source)
    elif args.command == 'sample': sample(args.per_event)
    else: prepare()
