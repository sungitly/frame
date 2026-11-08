"""Upload selected derivatives only. Dry-run by default; uses Wrangler OAuth, no stored API secret."""
import argparse, json, subprocess
from pathlib import Path
from photos import ROOT, save_json

def upload_plan(catalog):
    return sorted({f'{p["key"]}/{size}.{ext}' for p in catalog if p.get('included',p.get('approved',False)) for size in [v['bound'] for v in p.get('variants',[{'bound':n} for n in (480,960,1600,2560)])] for ext in p.get('formats',['jpg','webp'])})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    config=json.loads((ROOT/'wrangler.json').read_text())
    bucket=config['r2_buckets'][0]['bucket_name']
    keys=upload_plan(json.loads((ROOT/'content/catalog.json').read_text()))
    if not keys:raise SystemExit('没有入选照片，请先整理影集。')
    missing=[key for key in keys if not (ROOT/'public/media'/key).is_file()]
    if missing:raise SystemExit('缺少展示图，请先运行 curation.py materialize')
    total=sum((ROOT/'public/media'/key).stat().st_size for key in keys)
    print(f'{bucket}: {len(keys)} 个文件，{total/1024**2:.1f} MiB；'+('开始上传' if args.execute else '仅预览，未上传'),flush=True)
    if args.execute:
        ledger_path=ROOT/'content/uploaded.json'
        ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else {'bucket':bucket,'keys':[]}
        if ledger['bucket']!=bucket:raise SystemExit('上传记录的 bucket 不匹配')
        uploaded=set(ledger['keys'])
        for key in keys:
            if key in uploaded:continue
            subprocess.run(['node',str(ROOT/'node_modules/wrangler/bin/wrangler.js'),'r2','object','put',bucket+'/'+key,'--file',str(ROOT/'public/media'/key),'--content-type','image/webp' if key.endswith('.webp') else 'image/jpeg','--remote'],cwd=ROOT,check=True)
            uploaded.add(key);save_json(ledger_path,dict(bucket=bucket,keys=sorted(uploaded)))
        print('上传完成；清单已保存。现在可以构建正式网站。')
