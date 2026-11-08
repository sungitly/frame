"""Import the local review export, validating IDs and avoiding accidental cross-site import."""
import argparse, json, re
from photos import ROOT, save_json

def validate(payload, current, site):
    if payload.get('site') != site or payload.get('version') != 1:
        raise ValueError('清单不属于此网站，或版本不受支持')
    known = {row['id']: row for row in current}
    result, seen = [], set()
    for row in payload['selections']:
        identity = row.get('id')
        if identity not in known or identity in seen: raise ValueError('未知或重复的照片 ID')
        seen.add(identity)
        if not isinstance(row.get('approved'), bool): raise ValueError('approved 必须是布尔值')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,60}', row.get('album','')): raise ValueError('相册标识只允许字母、数字、下划线、短横线')
        title = row.get('title','').strip()
        if not title or len(title)>120: raise ValueError('标题必须为 1–120 字符')
        result.append({**known[identity], 'title':title, 'album':row['album'], 'approved':row['approved']})
    return result

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('file');args=parser.parse_args()
    current=json.loads((ROOT/'content/selections.json').read_text())
    site=json.loads((ROOT/'site.json').read_text())['kind']
    rows=validate(json.loads(open(args.file).read()),current,site)
    save_json(ROOT/'.local/selections-before-import.json',current)
    save_json(ROOT/'content/selections.json',rows)
    catalog={r['id']:r for r in json.loads((ROOT/'content/catalog.json').read_text())}
    save_json(ROOT/'content/catalog.json',[{**catalog[r['id']],**r} for r in rows])
    print(f'导入 {len(rows)} 张，其中 {sum(r["approved"] for r in rows)} 张确认入选。没有上传或发布。')
