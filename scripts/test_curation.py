import functools,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import curation,studio
from upload import upload_plan

class CurationTests(unittest.TestCase):
    def test_manual_decision_survives_automatic_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'library.json').write_text(json.dumps([dict(id='a',autoIncluded=True,album='one',fileName='a.jpg')]))
            (root/'overrides.json').write_text(json.dumps({'a':dict(included=False,title='Mine',album='two')}))
            with patch.object(curation,'LOCAL',root):
                row=curation.effective_rows()[0]
                self.assertFalse(row['included']);self.assertEqual(row['title'],'Mine');self.assertEqual(row['album'],'two')
    def test_low_aesthetic_alone_is_not_junk(self):
        self.assertIsNone(curation.technical_rejection(dict(width=3000,height=2000,darkFraction=.5,brightFraction=0,contrast=40,sharpness=50,aesthetic=-.8)))
        self.assertEqual(curation.technical_rejection({'error':'bad JPEG'}),'文件无法解码')
    def test_upload_uses_only_included_actual_variants(self):
        row=dict(key='yes',included=True,variants=[{'bound':480},{'bound':1600}],formats=['jpg'])
        self.assertEqual(upload_plan([row,{**row,'key':'no','included':False}]),['yes/1600.jpg','yes/480.jpg'])
    def test_local_api_rejects_cross_origin_unknown_ids_and_restores(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);identity='a'*20
            (root/'library.json').write_text(json.dumps([dict(id=identity,autoIncluded=True,album='one',fileName='a.jpg')]))
            with patch.object(curation,'LOCAL',root),patch.object(studio,'LOCAL',root),patch.object(studio,'JOB',dict(running=False,error=None,dirty=False)):
                server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(studio.Handler,directory=directory))
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_port}'
                def post(body,origin=base):
                    return urlopen(Request(base+'/api/decision',data=json.dumps(body).encode(),headers={'Origin':origin,'Content-Type':'application/json'}))
                try:
                    with self.assertRaises(HTTPError) as error:post({'ids':[identity],'included':False},'https://example.com')
                    self.assertEqual(error.exception.code,403)
                    with self.assertRaises(HTTPError) as error:post({'ids':['unknown'],'included':False})
                    self.assertEqual(error.exception.code,400)
                    with post({'ids':[identity],'included':False}) as response:self.assertEqual(response.status,200)
                    self.assertFalse(curation.effective_rows()[0]['included'])
                    with post({'ids':[identity],'reset':True}) as response:self.assertEqual(response.status,200)
                    self.assertTrue(curation.effective_rows()[0]['included'])
                finally:server.shutdown();server.server_close();thread.join()
