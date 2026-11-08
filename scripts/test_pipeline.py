import tempfile, unittest
from pathlib import Path
from PIL import Image
from photos import srgb_image
from review import validate
from upload import upload_plan

class PipelineTests(unittest.TestCase):
    def test_orientation_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'original.jpg'
            exif=Image.Exif();exif[274]=6;exif[315]='Private name'
            Image.new('RGB',(80,40),'green').save(source,exif=exif)
            before=source.read_bytes()
            result=srgb_image(source)
            self.assertEqual(result.size,(40,80))
            clean=Image.frombytes('RGB',result.size,result.tobytes());out=Path(directory)/'web.jpg';clean.save(out)
            with Image.open(out) as image:self.assertEqual(len(image.getexif()),0)
            self.assertEqual(source.read_bytes(),before)

    def test_cross_site_import_rejected(self):
        with self.assertRaises(ValueError):validate({'site':'photo','version':1,'selections':[]},[],'frame')

    def test_unknown_and_duplicate_ids_rejected(self):
        row={'id':'a','album':'water','title':'A','approved':True}
        for rows in [[{**row,'id':'other'}],[row,row]]:
            with self.assertRaises(ValueError):validate({'site':'frame','version':1,'selections':rows},[row],'frame')

    def test_import_cannot_replace_source_metadata(self):
        original={'id':'a','album':'water','title':'A','approved':False,'date':'2024-01-01'}
        changed={**original,'approved':True,'date':'1900-01-01'}
        result=validate({'site':'frame','version':1,'selections':[changed]},[original],'frame')
        self.assertEqual(result[0]['date'],original['date']);self.assertTrue(result[0]['approved'])

    def test_only_approved_images_can_upload(self):
        plan=upload_plan([{'key':'yes','approved':True},{'key':'no','approved':False}])
        self.assertEqual(len(plan),8);self.assertTrue(all(p.startswith('yes/') for p in plan))

if __name__=='__main__':unittest.main()
