"""Run two persistent Apple Vision scorers while the JPEG scan progresses."""
import concurrent.futures,json,subprocess,threading,time
from photos import LOCAL

state=threading.local()
processes=[]
def score(row):
    if row.get('error'):return {'id':row['id'],'error':row['error'],'sha256':row.get('sha256')}
    if not hasattr(state,'process'):
        state.process=subprocess.Popen([str(LOCAL/'vision-score')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=open(LOCAL/'vision-stderr.log','a'),text=True,bufsize=1)
        processes.append(state.process)
    p=state.process
    p.stdin.write(json.dumps({'id':row['id'],'path':str(LOCAL/'previews'/f'{row["id"]}.jpg')})+'\n');p.stdin.flush()
    line=p.stdout.readline()
    if not line:raise RuntimeError('Native Vision scorer exited unexpectedly')
    return {**json.loads(line),'sha256':row['sha256']}

def main():
    path=LOCAL/'vision.jsonl';done={}
    if path.exists():
        for line in path.read_text().splitlines():
            try:r=json.loads(line);done[r['id']]=r
            except ValueError:pass
    total=len(json.loads((LOCAL/'inventory.json').read_text())['photos'])
    started=time.time()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool,path.open('a') as output:
            while True:
                available={}
                if (LOCAL/'analysis.jsonl').exists():
                    for line in (LOCAL/'analysis.jsonl').read_text().splitlines():
                        try:r=json.loads(line);available[r['id']]=r
                        except ValueError:pass
                todo=[r for r in available.values() if r['id'] not in done or done[r['id']].get('sha256')!=r.get('sha256')]
                for result in pool.map(score,todo):
                    done[result['id']]=result;output.write(json.dumps(result)+'\n');output.flush()
                    if len(done)%100==0:print(f'Vision {len(done)}/{total} ({time.time()-started:.0f}s)',flush=True)
                if len(done)>=total:break
                time.sleep(2)
    finally:
        for p in processes:p.stdin.close();p.wait()
    print('On-device scoring complete',flush=True)

if __name__=='__main__':main()
