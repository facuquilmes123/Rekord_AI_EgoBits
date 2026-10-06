"""Visual QA only: isolated settings, fake native receipts and cancelled bridge."""
import os
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
os.environ['LOCALAPPDATA']=str(root/'output/closure/release-039/ui-recovery-fixture')
sys.path.insert(0,str(root/'prototype'))
from egobits.desktop import service
from egobits.adapters.xml_adapter import Library
from http.server import ThreadingHTTPServer
service._GLOBAL_LIB=Library(root/'prototype/examples/library.xml')
service._MONITOR.check_state=lambda:'closed'
service._MONITOR.check_native_state=lambda:'closed'
service._MONITOR.native_status=lambda:{'state':'closed','reason':'Prueba aislada: procesos simulados cerrados.','processes':[]}
service._HISTORY.process_state=lambda:'closed'
service.discover=lambda:{'databases':[],'installations':[],'xml_files':[]}
service._NATIVE.backups=lambda:[{'id':'a'*32,'name':'Playlist de prueba','state':'applied','created_at':1,'verified':True}]
service._TRANSACTIONS.backups=lambda:[{'id':'b'*32,'name':'Recuperación de transacciones','state':'restoring','created_at':2,'verified':True}]
class Handler(service.EgoBitsRequestHandler):
    prepares=0
    def do_GET(self):
        if self.path in ('/','/index.html'):
            content=(service.UI_DIR/'index.html').read_text(encoding='utf-8')
            bridge="""<script>window.__TAURI__={core:{invoke:async(name)=>name==='backend_info'?{port:location.port,token:'fixture'}:{state:'cancelled'}},event:{listen:async()=>()=>{}}};</script>"""
            content=content.replace('<head>','<head>'+bridge).replace('<body>','<body><p style="margin:0;padding:8px;background:#fff4ce">Prueba aislada · confirmaciones nativas simuladas · sin datos reales</p>')
            data=content.encode('utf-8');self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
        super().do_GET()
    def do_POST(self):
        if self.path in ('/api/transactions/prepare','/api/transactions/restore/prepare','/api/native/restore/prepare'):
            self.read_json_body()
            if self.path=='/api/transactions/prepare':
                type(self).prepares+=1
                if type(self).prepares>1:self.send_error_json('Error simulado: la colección cambió; volvé a preparar el respaldo.',400);return
            self.send_json({'token':'c'*32,'backup_directory':'Fixture aislada'});return
        super().do_POST()
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
print(f'UI_FIXTURE:{server.server_port}',flush=True)
try:server.serve_forever()
finally:server.server_close()
