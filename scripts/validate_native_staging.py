"""Exercise native writer on an encrypted isolated copy, never publish to source."""
import json
from pathlib import Path
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'prototype'))
from egobits.adapters.sqlcipher_read import connection,driver_and_key,inspect
from egobits.adapters.native_write import NativePlaylistWriter,digest
from egobits.adapters.xml_adapter import Library
from egobits.desktop.discovery import discover

lab=ROOT/'output/closure'/('native-lab-'+str(time.time_ns()))
lab.mkdir()
db=Path(discover()['databases'][0])
copy=lab/'master.db'
driver,key=driver_and_key()
dest=driver.connect(str(copy));dest.execute("PRAGMA key='"+key.replace("'","''")+"'");del key
with connection(db) as source: source.backup(dest)
dest.execute('PRAGMA journal_mode=DELETE')
dest.close()
shutil.copy2(db.parent/'masterPlaylists6.xml',lab/'masterPlaylists6.xml')
root=ET.Element('DJ_PLAYLISTS',Version='1.0.0');coll=ET.SubElement(root,'COLLECTION',Entries='3')
with connection(copy) as conn:
    rows=conn.execute("SELECT ID,Title,FolderPath FROM djmdContent WHERE FolderPath IS NOT NULL AND FolderPath<>'' LIMIT 3").fetchall()
for tid,title,path in rows:
    ET.SubElement(coll,'TRACK',TrackID=str(tid),Name=title or '',Location=Path(path).as_uri().replace('file://','file://localhost',1),AverageBpm='124')
xml=lab/'library.xml';ET.ElementTree(root).write(xml,encoding='utf-8',xml_declaration=True)
lib=Library(xml);before=digest(copy)
writer=NativePlaylistWriter(lab/'operations',lambda:'closed',lambda:{'databases':[str(copy)],'installations':[{'version':'7.2.19'}]})
with patch('pyrekordbox.db6.database.get_rekordbox_pid',return_value=0):
    result=writer.prepare(lib,list(lib.tracks),'Rekord AI — ensayo aislado',copy)
assert digest(copy)==before
applied=writer.apply(result['token'],lib.revision)
assert inspect(copy)['integrity']=='ok'
restore=writer.prepare_restore(result['token'])
writer.restore(restore['token'])
assert digest(copy)==before
(lab/'result.json').write_text(json.dumps({'prepared':True,'applied_to_isolated_copy':applied['state']=='applied','restored_byte_identical':True,'tracks':result['tracks'],'integrity':'ok','published_to_real_database':False},indent=2))
print(lab/'result.json')

