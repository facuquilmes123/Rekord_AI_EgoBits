import unittest,tempfile,json
from pathlib import Path
from egobits.desktop.discovery import discover
class DiscoveryTests(unittest.TestCase):
 def test_missing(self):
  self.assertEqual(discover({},False)['installations'],[])
 def test_moved_and_future(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td); exe=root/'programs/rekordbox/rekordbox 99/rekordbox.exe';exe.parent.mkdir(parents=True);exe.write_bytes(b'fixture')
   db=root/'moved/master.db';db.parent.mkdir();db.write_bytes(b'untouched')
   options=root/'roaming/Pioneer/rekordboxAgent/storage/options.json';options.parent.mkdir(parents=True);options.write_text(json.dumps({'options':[['db-path',str(db)]]}))
   result=discover({'ProgramFiles':str(root/'programs'),'APPDATA':str(root/'roaming')},False)
   self.assertEqual(len(result['installations']),1);self.assertIn(str(db),result['databases']);self.assertEqual(db.read_bytes(),b'untouched');self.assertTrue(result['requires_xml'])
 def test_malformed(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'Pioneer/rekordbox6/bad.settings';p.parent.mkdir(parents=True);p.write_text('<broken')
   self.assertTrue(discover({'APPDATA':td},False)['warnings'])

 def test_version_folder_normalized_without_enabling_unknown_major(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);exe=root/'rekordbox/rekordbox 7.2.19/rekordbox.exe';exe.parent.mkdir(parents=True);exe.write_bytes(b'fixture')
   self.assertEqual(discover({'ProgramFiles':td},False)['installations'][0]['version'],'7.2.19')
   exe2=root/'rekordbox/rekordbox 99.1.0/rekordbox.exe';exe2.parent.mkdir();exe2.write_bytes(b'fixture')
   self.assertIn('99.1.0',[row['version'] for row in discover({'ProgramFiles':td},False)['installations']])
