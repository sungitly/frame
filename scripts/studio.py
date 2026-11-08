"""Local-only curation server. All writes require same-origin JSON; source paths are never served."""
import argparse, functools, json, re, subprocess, threading
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from curation import data_root,effective_rows,materialize
from photos import ROOT,LOCAL,save_json

LOCK=threading.RLock()
def overrides():
    path=LOCAL/'overrides.json'
    return json.loads(path.read_text()) if path.exists() else {}
def is_dirty():
    applied=LOCAL/'applied-overrides.json'
    return overrides() != (json.loads(applied.read_text()) if applied.exists() else {})
JOB={'running':False,'error':None,'dirty':is_dirty()}

def rebuild():
    try:
        materialize()
        result=subprocess.run(['npm','run','build'],cwd=ROOT,capture_output=True,text=True)
        (LOCAL/'studio-build.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('构建失败，请查看 .local/studio-build.log；你的增删记录已经保存。')
        with LOCK:
            save_json(LOCAL/'applied-overrides.json',overrides())
            JOB.update(dirty=False,error=None)
    except Exception as error:
        with LOCK:JOB['error']=str(error)
    finally:
        with LOCK:JOB['running']=False

class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
    def json(self,data,status=200):
        body=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def valid_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
    def do_GET(self):
        if not self.valid_host():return self.json({'error':'Invalid host'},403)
        parsed=urlparse(self.path);query=parse_qs(parsed.query)
        if parsed.path=='/api/status':return self.json(JOB)
        if parsed.path in ('/api/library','/api/export'):
            try:
                rows=effective_rows()
                if parsed.path=='/api/export':return self.json({'site':json.loads((ROOT/'site.json').read_text())['kind'],'version':2,'selections':[{k:r.get(k) for k in ('id','included','album','title','manual')} for r in rows]})
                events={r['event']:r['eventTitle'] for r in rows}
                counts={'all':len(rows),'included':sum(r['included'] for r in rows),'excluded':sum(not r['included'] for r in rows),'duplicates':sum(r['decision']=='duplicate' for r in rows)}
                state=query.get('state',['included'])[0];event=query.get('event',[''])[0];needle=query.get('q',[''])[0].lower().strip()
                filtered=[r for r in rows if (state=='all' or (state=='included' and r['included']) or (state=='excluded' and not r['included']) or (state=='duplicates' and r['decision']=='duplicate')) and (not event or r['event']==event) and (not needle or needle in ' '.join([r['title'],r['fileName'],r['eventTitle'],str(r.get('labels',[]))]).lower())]
                page=max(0,int(query.get('page',['0'])[0]));size=60
                output=[{k:r.get(k) for k in ('id','title','fileName','date','eventTitle','album','included','autoIncluded','manual','reason','decision','duplicateOf','aesthetic','width','height','error')} for r in filtered[page*size:(page+1)*size]]
                return self.json({'photos':output,'total':len(filtered),'page':page,'pageSize':size,'counts':counts,'events':events,'job':JOB})
            except (ValueError,FileNotFoundError) as error:return self.json({'error':'照片索引尚未准备好。'+str(error)},503)
        match=re.fullmatch(r'/library-media/([a-f0-9]{20})\.jpg',parsed.path)
        if match:
            folder='previews' if query.get('large')==['1'] else 'thumbs'
            path=data_root()/folder/(match.group(1)+'.jpg')
            if not path.is_file():return self.send_error(404)
            body=path.read_bytes();self.send_response(200);self.send_header('Content-Type','image/jpeg');self.send_header('Cache-Control','private, max-age=300');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        if parsed.path.startswith('/api/'):return self.send_error(404)
        super().do_GET()
    def do_POST(self):
        if not self.valid_host() or self.headers.get('Origin') != 'http://'+self.headers.get('Host','') or self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.json({'error':'拒绝跨站修改请求'},403)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<0 or length>100000:return self.json({'error':'请求过大'},413)
            payload=json.loads(self.rfile.read(length))
            with LOCK:
                if JOB['running']:return self.json({'error':'正在更新影集，请稍后再修改。'},409)
                if self.path=='/api/apply':
                    JOB.update(running=True,error=None);threading.Thread(target=rebuild,daemon=True).start();return self.json(JOB,202)
                if self.path!='/api/decision':return self.json({'error':'未知操作'},404)
                ids=payload.get('ids',[])
                if not isinstance(ids,list) or not 1<=len(ids)<=200:raise ValueError('一次可修改 1–200 张照片')
                rows={r['id']:r for r in effective_rows()}
                if any(identity not in rows for identity in ids):raise ValueError('未知照片')
                file=LOCAL/'overrides.json';overrides=json.loads(file.read_text()) if file.exists() else {}
                if payload.get('reset') is True:
                    for identity in ids:overrides.pop(identity,None)
                else:
                    change={}
                    if 'included' in payload:
                        if type(payload['included']) is not bool:raise ValueError('无效入选状态')
                        if payload['included'] and any(rows[i].get('error') for i in ids):raise ValueError('无法加入损坏的照片文件')
                        change['included']=payload['included']
                    if 'album' in payload:
                        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,60}',payload['album']):raise ValueError('相册标识无效')
                        change['album']=payload['album']
                    if 'title' in payload:
                        if not isinstance(payload['title'],str) or not 1<=len(payload['title'].strip())<=120:raise ValueError('标题长度应为 1–120 字符')
                        change['title']=payload['title'].strip()
                    if not change:raise ValueError('没有修改内容')
                    for identity in ids:overrides[identity]={**overrides.get(identity,{}),**change}
                if file.exists():save_json(LOCAL/'overrides.previous.json',json.loads(file.read_text()))
                save_json(file,overrides);JOB.update(dirty=True,error=None)
                return self.json({'saved':len(ids),'job':JOB})
        except (ValueError,KeyError,TypeError) as error:return self.json({'error':str(error)},400)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=4322);args=parser.parse_args()
    LOCAL.mkdir(exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),functools.partial(Handler,directory=str(ROOT/'dist/preview')))
    print(f'Local photo studio: http://127.0.0.1:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
