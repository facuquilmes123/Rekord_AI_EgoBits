"""API desktop loopback. Los errores y el modo demostración son explícitos."""
from __future__ import annotations
import atexit
from contextlib import contextmanager
import hmac
import hashlib
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from ..adapters.xml_adapter import Library, export_xml
from ..adapters.m3u8 import export_m3u8, local_path
from .file_dialog import choose_file
from .collection_tools import insights, verify_duplicates, draft, answer_help
from .assistant_context import collection_context, validate_answer, fallback_answer
from .duplicate_scan import DuplicateScan
from ..ai.parser import parse_natural_language_intent, sanitize_user_input
from ..ai.intents import UnknownIntent, SystemStatusIntent, RecommendLiveIntent
from ..ai.sidecar_client import LocalLlamaRuntime
from ..core.analysis import audit_library, find_duplicates, compare_playlists
from ..core.models import PlanOptions, PlanningError
from ..core.planner import plan
from ..core.recommender import recommend, RecommendationOptions
from ..policy import capability, State
from .chat import execute_chat, enrich_chat
from ..core.mentions import mention_candidates, resolve_followup, extract_mentions
from .live_suggestion import live_suggestion
from .settings import SettingsStore
from .tray_watcher import ProcessMonitor
from .discovery import discover, cached_discover
from ..adapters.sqlcipher_read import inspect as inspect_native
from ..adapters.native_write import NativePlaylistWriter, digest
from .process_close import RekordboxCloser
from ..adapters.transaction_recovery import TransactionRecovery
from ..telemetry.history import HistoryObserver
from ..telemetry.audio_watch import AudioWatch
from .track_handoff import drag_file

UI_DIR = Path(__file__).resolve().parent / 'ui'
EXAMPLES_DIR = (Path(sys._MEIPASS) / 'examples' if getattr(sys, 'frozen', False)
                else Path(__file__).resolve().parents[2] / 'examples')
_SESSION_TOKEN = None
_NATIVE_APPROVAL_KEY = os.environ.get('EGB_NATIVE_APPROVAL_KEY')
_GLOBAL_LIB = None
_MONITOR = ProcessMonitor()
_LIVE_PROVIDER = None
_LLAMA_RUNTIME = None
_AI_LOCK = threading.Lock()
_AUDIO_LOCK = threading.Lock()
_AUDIO_WATCH = AudioWatch(_MONITOR.check_state)
atexit.register(_AUDIO_WATCH.stop)
_LIB_LOCK = threading.RLock()
_SERVER = None
_SETTINGS = SettingsStore()
_HISTORY = HistoryObserver(cached_discover, _MONITOR.check_state)
_NATIVE = NativePlaylistWriter(Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Rekord AI' / 'native-operations', _MONITOR.check_native_state, discover)
_TRANSACTIONS = TransactionRecovery(_NATIVE.root, _MONITOR.check_native_state, discover, _NATIVE)
_CLOSER = RekordboxCloser(discover, _MONITOR, _NATIVE)
_DUPLICATES = DuplicateScan()
_LLM_STATUS = {'state': 'not_started', 'reason': 'Se activa al interpretar consultas no reconocidas por el parser local'}
ALLOWED_ORIGINS = {'http://tauri.localhost', 'tauri://localhost'}
TOOL_NAMES = ('system.status', 'playlist.list', 'library.search', 'playlist.plan',
              'playlist.export_xml', 'playlist.compare', 'library.audit', 'library.duplicates',
              'track.describe', 'transition.explain', 'recommend.manual', 'recommend.live',
              'playlist.apply_native', 'device.export')


def get_or_load_library(default_xml=None, default_energies=None):
    global _GLOBAL_LIB
    with _LIB_LOCK:
        if _GLOBAL_LIB is not None:
            return _GLOBAL_LIB
        settings = _SETTINGS.snapshot()
        filename = default_xml or os.environ.get('EGB_LIBRARY_XML') or settings['library_xml']
        xml_path = Path(filename) if filename else EXAMPLES_DIR / 'library.xml'
        if not xml_path.is_file():
            raise PlanningError(f'XML configurado no encontrado: {xml_path}')
        energy_file = default_energies or os.environ.get('EGB_ENERGIES_JSON') or settings['energies_json']
        # Los IDs de otra colección nunca heredan las energías de la demostración.
        if not energy_file and xml_path.resolve() == (EXAMPLES_DIR / 'library.xml').resolve():
            energy_file = EXAMPLES_DIR / 'energies.json'
        energy = json.loads(Path(energy_file).read_text(encoding='utf-8')) if energy_file else None
        _GLOBAL_LIB = Library(xml_path, energy)
        return _GLOBAL_LIB


def current_library():
    try:
        return get_or_load_library(), None
    except (OSError, ValueError, TypeError) as exc:
        return None, str(exc)


def current_suggestion(lib, state):
    if state != 'open':
        return {'confirmed': False, 'reason': 'Requiere Rekordbox abierto'}
    if lib is None:
        return {'confirmed': False, 'reason': 'Requiere biblioteca cargada'}
    settings=_SETTINGS.snapshot()
    options = RecommendationOptions(**settings['recommendation'])
    result=live_suggestion(lib, _LIVE_PROVIDER, options)
    if not result.get('confirmed') and settings['notifications']['history_popup']:
        return _HISTORY.poll(lib,options,use_last_registered=settings['notifications']['history_reference_mode']=='last_registered')
    return result


def recommendation_popup():
    settings=_SETTINGS.snapshot()
    notifications=settings['notifications']
    if not notifications['enabled'] or notifications['silenced']:
        return {'display':False,'reason':'Avisos desactivados o modo silencio'}
    lib,error=current_library()
    if lib is None or lib.source==(EXAMPLES_DIR/'library.xml').resolve():
        return {'display':False,'reason':'Cargá tu colección real'}
    if _MONITOR.check_state()!='open':return {'display':False,'reason':'Requiere Rekordbox abierto'}
    options=RecommendationOptions(**settings['recommendation'])
    live=live_suggestion(lib,_LIVE_PROVIDER,options)
    if live.get('confirmed'):
        result={'recommendations':[vars(lib.tracks[live['track_id']])],**live,'source':'verified_telemetry'}
    else:
        audio=_AUDIO_WATCH.snapshot()
        if audio.get('popup_eligible') and audio.get('source_revision')==lib.revision and audio.get('track_id') in lib.tracks:
            result={**recommend(lib.tracks[audio['track_id']],list(lib.tracks.values()),options),
                    'source':'audio_pilot','confirmed':False,'reason':'Coincidencia repetida experimental; master sin certificar',
                    'event_id':f"{lib.revision}:audio:{audio['track_id']}"}
        elif notifications['history_popup']:
            result=_HISTORY.poll(lib,options,use_last_registered=notifications['history_reference_mode']=='last_registered')
            result['event_id']=f"{lib.revision}:history:{result.get('history_event_id','')}"
        else:return {'display':False,'reason':'No hay seguimiento conectado. Activá «Popup desde el historial» o configurá la salida de audio y el seguimiento experimental en Configuración.'}
    rows=[]
    for track in result.get('recommendations',[]):
        try:
            drag_file(lib,track['id'],lib.revision)
            rows.append({k:track.get(k) for k in ('id','artist','title','bpm','key','genre','compatibility_score','match_reasons')})
        except (OSError,ValueError):continue
        if len(rows)==3:break
    fingerprint=hashlib.sha256(json.dumps({'criteria':settings['recommendation'],'rows':rows},sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]
    if not rows and result.get('recommendations'):
        result['reason']='Hay sugerencias, pero sus archivos no están accesibles o la colección cambió. Revisá la colección cargada y las rutas de música.'
    elif not rows and result.get('reference_track'):
        result['reason']='No hay pistas que cumplan tus filtros. Ampliá BPM o revisá tonalidad, género y energía.'
    result.pop('excluded',None)
    return {**result,'event_id':f"{result.get('event_id','')}:{fingerprint}",'recommendations':rows,'display':bool(rows),'source_revision':lib.revision}


def status():
    lib, error = current_library()
    state = _MONITOR.check_state()
    native_state = state if state != 'closed' else _MONITOR.check_native_state()
    settings = _SETTINGS.snapshot()
    live = current_suggestion(lib, state)
    capabilities = {name: vars(capability(name, State(state), snapshot=lib is not None,
                    manual_track_id=True, live_fresh=live.get('confirmed', False),
                    opt_in=settings['notifications']['enabled'])) for name in TOOL_NAMES}
    return {'app': 'Rekord AI', 'version': '0.3.12', 'rekordbox_state': state,'native_process_state':native_state,
            'snapshot_revision': lib.revision if lib else None,
            'source_path': str(lib.source) if lib else None, 'library_error': error,
            'demo': bool(lib and lib.source == (EXAMPLES_DIR / 'library.xml').resolve()),
            'tracks_count': len(lib.tracks) if lib else 0, 'playlists_count': len(lib.playlists) if lib else 0,
            'energy_available': bool(lib and any(t.energy is not None for t in lib.tracks.values())),
            'telemetry_available': bool(_LIVE_PROVIDER and _LIVE_PROVIDER.is_available()),
            'telemetry_provider': _LIVE_PROVIDER.name() if _LIVE_PROVIDER else None,
            'live_reason': live.get('reason'), 'capabilities': capabilities,
            'notifications': settings['notifications'], 'llm': dict(_LLM_STATUS),
            'settings_error': _SETTINGS.load_error,'native_operation_active':_NATIVE.lock.locked(),
            'audio_watch':_AUDIO_WATCH.snapshot()}


def local_llama_client():
    global _LLAMA_RUNTIME, _LLM_STATUS
    root = Path(os.environ.get('EGB_RESOURCE_ROOT', Path(__file__).resolve().parents[3]))
    manifest = root / 'installer/offline_assets.json'
    if _LLAMA_RUNTIME is None:
        rows = json.loads(manifest.read_text(encoding='utf-8'))['assets']
        binary = next(row for row in rows if row['path'].endswith('/llama-server.exe'))
        model = next(row for row in rows if row['path'].endswith('.gguf'))
        model_path = root / model['path']
        if not model_path.is_file():
            model_path = _SETTINGS.path.parent / model['path']
        _LLAMA_RUNTIME = LocalLlamaRuntime(root / binary['path'], model_path,
                                           binary['sha256'], model['sha256'],
                                           [(root / row['path'], row['sha256']) for row in rows
                                            if row['path'].startswith('assets/bin/')])
        atexit.register(_LLAMA_RUNTIME.close)
    _LLM_STATUS = {'state': 'loading', 'reason': 'Cargando modelo local'}
    client = _LLAMA_RUNTIME.start()
    return client



@contextmanager
def ai_slot():
    if not _AI_LOCK.acquire(timeout=1):raise PlanningError('La IA local está atendiendo otra consulta. Podés usar las consultas directas de colección o intentar nuevamente cuando termine.')
    try:yield
    finally:_AI_LOCK.release()


def get_chat_intent(query, playlists):
    global _LLAMA_RUNTIME, _LLM_STATUS
    deterministic = parse_natural_language_intent(query, playlists)
    if not isinstance(deterministic, UnknownIntent) or not _SETTINGS.snapshot()['llm_enabled']:
        return deterministic
    if deterministic.reason != UnknownIntent().reason:
        return deterministic  # Una validación determinista fallida no se relaja mediante IA.
    root = Path(os.environ.get('EGB_RESOURCE_ROOT', Path(__file__).resolve().parents[3]))
    manifest = root / 'installer/offline_assets.json'
    if not manifest.is_file():
        _LLM_STATUS = {'state': 'not_configured', 'reason': 'Manifiesto local de IA ausente'}
        return deterministic
    with ai_slot():
        try:
            from ..ai.validation import intent_from_payload
            client = local_llama_client()
            payload = client.generate_intent(sanitize_user_input(query), playlists)
            intent = intent_from_payload(payload, playlists)
            _LLM_STATUS = {'state': 'ready', 'reason': 'Inferencia local verificada'}
            return intent
        except (OSError, ValueError, KeyError, StopIteration, RuntimeError) as exc:
            _LLM_STATUS = {'state': 'degraded', 'reason': f'Fallback determinista: {type(exc).__name__}'}
            return deterministic


def assistant_answer(query, lib, reference=None, history=None):
    global _LLM_STATUS
    if not _SETTINGS.snapshot()['llm_enabled']:
        return enrich_chat({'response':'La conversación abierta necesita la IA local, que está desactivada en Configuración. Las búsquedas, auditoría y planificación deterministas siguen disponibles.', 'applied':False},lib)
    context=collection_context(lib,query,reference)
    if history is not None:
        if not isinstance(history,list) or len(history)>4 or any(not isinstance(row,dict) or set(row)!={'role','text'} or row['role'] not in ('user','assistant') or not isinstance(row['text'],str) for row in history):
            raise PlanningError('Historial conversacional inválido.')
        context['recent_conversation']=[{'role':row['role'],'text':sanitize_user_input(row['text'],500)} for row in history]
    with ai_slot():
        try:
            client=local_llama_client()
            payload=client.generate_answer(sanitize_user_input(query),context)
            if isinstance(payload,dict) and set(payload)=={'action','params'}:
                from ..ai.validation import intent_from_payload
                intent=intent_from_payload(payload,list(lib.playlists) if lib else [])
                state=_MONITOR.check_state() if isinstance(intent,(SystemStatusIntent,RecommendLiveIntent)) else 'unknown'
                result=execute_chat(intent,lib,state,_SETTINGS.snapshot()['recommendation'],current_suggestion(lib,state))
            else:
                try:
                    answer=validate_answer(payload,context)
                except PlanningError:
                    # One corrective attempt; never relax grounding or execute a rejected response.
                    retry_context={**context,'response_requirements':'La respuesta anterior no pasó la validación. Devolvé una orientación breve, sin afirmar acciones, sin IDs fuera de la muestra y sin herramientas internas.'}
                    payload=client.generate_answer(sanitize_user_input(query),retry_context)
                    answer=validate_answer(payload,context)
                result=enrich_chat(answer,lib)
                result['source_revision']=lib.revision if lib else None
            _LLM_STATUS={'state':'ready','reason':'Conversación local basada en contexto de la colección'}
            return result
        except (OSError, ValueError, KeyError, StopIteration, RuntimeError) as exc:
            if isinstance(exc,(TimeoutError,ConnectionError)) and _LLAMA_RUNTIME is not None:
                _LLAMA_RUNTIME.stop()  # Cancel only our inference child; next question restarts it automatically.
            _LLM_STATUS={'state':'degraded','reason':f'Conversación local no disponible: {type(exc).__name__}'}
            return enrich_chat(fallback_answer(query,context,type(exc).__name__),lib)


def approval_preview(token):
    try: return _NATIVE.approval_preview(token)
    except PlanningError: return _TRANSACTIONS.approval_preview(token)


def verify_native_approval(body, operation):
    if not _SESSION_TOKEN or not _NATIVE_APPROVAL_KEY or body.get('confirmed') is not True:
        raise PlanningError('Falta la confirmación nativa de Rekord AI')
    preview = approval_preview(body.get('token'))
    if preview['operation'] != operation or body.get('approval_digest') != preview['digest']:
        raise PlanningError('La propuesta cambió; revisala nuevamente')
    message = f"{operation}:{preview['token']}:{preview['digest']}".encode()
    expected = hmac.new(_NATIVE_APPROVAL_KEY.encode(),message,'sha256').hexdigest()
    signature = body.get('approval_signature')
    if not isinstance(signature,str) or not hmac.compare_digest(signature,expected):
        raise PlanningError('Confirmación nativa inválida')


def activate_operation_collection(result, field):
    global _GLOBAL_LIB
    if not result.get(field):return
    try:
        with _LIB_LOCK:
            energy_path=_SETTINGS.snapshot()['energies_json']
            energies=json.loads(Path(energy_path).read_text(encoding='utf-8')) if energy_path else None
            library=Library(Path(result[field]),energies)
            _SETTINGS.update({'library_xml':result[field]})
            _GLOBAL_LIB=library;_HISTORY.reset();_AUDIO_WATCH.stop()
    except (OSError,ValueError):
        result['collection_reload_warning']='La operación nativa terminó. Cargá el XML indicado manualmente; no se pudo actualizar la vista o sus preferencias.'


class EgoBitsRequestHandler(BaseHTTPRequestHandler):
    def handle(self):
        try:
            super().handle()
        except (ConnectionError, TimeoutError):
            # Cerrar/recargar la ventana puede cancelar una respuesta en curso.
            pass

    def log_message(self, *args):
        pass

    def _allowed_origin(self):
        origin = self.headers.get('Origin')
        return not origin or origin in ALLOWED_ORIGINS or origin == f'http://127.0.0.1:{self.server.server_port}'

    def _authorized(self):
        if not self._allowed_origin():
            return False
        if self.headers.get('Host') not in ('127.0.0.1', f'127.0.0.1:{self.server.server_port}'):
            return False
        return _SESSION_TOKEN is None or hmac.compare_digest(self.headers.get('X-EgoBits-Token', ''), _SESSION_TOKEN)

    def _cors(self):
        origin = self.headers.get('Origin')
        if origin and self._allowed_origin():
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')

    def do_OPTIONS(self):
        if not self._allowed_origin():
            self.send_error(403)
            return
        self.send_response(204)
        self._cors()
        self.send_header('Access-Control-Allow-Methods', 'GET, POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-EgoBits-Token')
        self.end_headers()

    def send_json(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self._cors()
        self.end_headers()
        self.wfile.write(payload)

    def send_error_json(self, message, status=400):
        self.send_json({'error': message, 'response': message, 'status': status}, status)

    def read_json_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if self.headers.get('Transfer-Encoding') or not 0 <= length <= 65536:
            raise PlanningError('Solicitud demasiado grande o codificación no admitida')
        if self.headers.get_content_type() != 'application/json':
            raise PlanningError('Se requiere application/json')
        body = json.loads(self.rfile.read(length).decode('utf-8')) if length else {}
        if not isinstance(body, dict):
            raise PlanningError('Se requiere un objeto JSON')
        return body

    def do_GET(self):
        if not self._authorized():
            self.send_error_json('Acceso denegado', 403)
            return
        path = urlparse(self.path).path
        if path in ('/', '/index.html', '/app.js', '/style.css', '/workspace.js', '/settings-tabs.js', '/rekord-ia.png', '/favicon.png','/live-popup.html','/live-popup.js'):
            target = UI_DIR / ('index.html' if path == '/' else path[1:])
            data = target.read_bytes()
            mime = {'.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8',
                    '.css': 'text/css; charset=utf-8', '.png': 'image/png'}[target.suffix]
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        try:
            if path in ('/api/status', '/api/capabilities'):
                self.send_json(status())
            elif path == '/api/discovery':
                self.send_json(cached_discover(force=True))
            elif path == '/api/history-suggestion':
                lib, _ = current_library()
                settings=_SETTINGS.snapshot()
                self.send_json(_HISTORY.poll(lib, RecommendationOptions(**settings['recommendation']),use_last_registered=settings['notifications']['history_reference_mode']=='last_registered'))
            elif path == '/api/native/status':
                dbs = discover()['databases']
                if len(dbs) != 1: raise PlanningError('No se identificó una base única')
                reason = 'Disponible para crear una playlist con respaldo y revisión.'
                ready = True
                try: _NATIVE.guard(Path(dbs[0]).resolve())
                except PlanningError as error: ready=False; reason=str(error)
                self.send_json({**inspect_native(dbs[0]), 'database':dbs[0], 'write_enabled':ready,'reason':reason})
            elif path == '/api/transactions/backups':
                self.send_json({'backups': _TRANSACTIONS.backups()})
            elif path == '/api/native/backups':
                self.send_json({'backups':_NATIVE.backups()})
            elif path == '/api/native/activity':
                self.send_json({'active':_NATIVE.lock.locked()})
            elif path == '/api/audio/devices':
                from ..telemetry.audio_match import devices
                from ..telemetry.audio_route import saved_route
                available=devices()
                self.send_json({'devices':available,**saved_route(available)})
            elif path == '/api/audio/watch':
                self.send_json(_AUDIO_WATCH.snapshot())
            elif path == '/api/recommendation-popup':
                self.send_json(recommendation_popup())
            elif path == '/api/settings':
                self.send_json(_SETTINGS.snapshot())
            elif path == '/api/telemetry':
                event = _LIVE_PROVIDER.get_current_state() if _LIVE_PROVIDER else None
                self.send_json({'provider': _LIVE_PROVIDER.name() if _LIVE_PROVIDER else None,
                                'available': bool(_LIVE_PROVIDER and _LIVE_PROVIDER.is_available()),
                                'event': vars(event) if event else None})
            elif path == '/api/live-suggestion':
                lib, _ = current_library()
                self.send_json(current_suggestion(lib, _MONITOR.check_state()))
            elif path == '/api/playlists':
                lib = get_or_load_library()
                self.send_json({'revision': lib.revision, 'playlists': [{'path': p, 'count': len(ids)} for p, ids in lib.playlists.items()]})
            elif path == '/api/rekordbox/processes':
                self.send_json(_MONITOR.native_status())
            elif path == '/api/insights':
                self.send_json(insights(get_or_load_library()))
            elif path == '/api/opportunity':
                from urllib.parse import parse_qs
                from .opportunities import detail
                args=parse_qs(urlparse(self.path).query);lib=get_or_load_library()
                if args.get('revision',[''])[0]!=lib.revision:raise PlanningError('La colección cambió; actualizá las oportunidades')
                self.send_json(detail(lib,args.get('id',[''])[0],int(args.get('offset',['0'])[0]),discover=discover))
            elif path == '/api/tracks':
                from urllib.parse import parse_qs
                args = parse_qs(urlparse(self.path).query)
                query = args.get('q', [''])[0][:200].casefold()
                offset = max(0, int(args.get('offset', ['0'])[0]))
                lib = get_or_load_library()
                rows = [t for t in lib.tracks.values() if query in f'{t.title} {t.artist} {t.genre}'.casefold()]
                self.send_json({'tracks': [vars(t) for t in rows[offset:offset+100]], 'total': len(rows), 'offset': offset, 'source_revision': lib.revision})
            elif path == '/api/mentions':
                from urllib.parse import parse_qs
                query = parse_qs(urlparse(self.path).query).get('q', [''])[0]
                lib = get_or_load_library()
                self.send_json({'tracks':mention_candidates(lib,query), 'source_revision':lib.revision})
            elif path == '/api/audit':
                lib = get_or_load_library()
                self.send_json({**audit_library(list(lib.tracks.values())), 'source_revision': lib.revision})
            elif path == '/api/duplicates':
                lib = get_or_load_library()
                duplicates = find_duplicates(list(lib.tracks.values()))
                self.send_json({'duplicates': duplicates, 'duplicates_count': len(duplicates), 'source_revision': lib.revision})
            elif path == '/api/duplicates/scan':
                self.send_json(_DUPLICATES.snapshot())
            else:
                self.send_error_json('Endpoint no encontrado', 404)
        except (OSError, ValueError, TypeError, ImportError) as exc:
            self.send_error_json(str(exc))

    def do_POST(self):
        global _GLOBAL_LIB
        if not self._authorized():
            self.send_error_json('Acceso denegado', 403)
            return
        path = urlparse(self.path).path
        try:
            body = self.read_json_body()
            if path.startswith(('/api/native/', '/api/transactions/', '/api/rekordbox/close/','/api/duplicates/prepare','/api/duplicates/delete')) and not _SESSION_TOKEN:
                self.send_error_json('Esta operación requiere la aplicación Windows autenticada.',403)
                return
            if path in ('/api/native/apply','/api/native/restore/apply','/api/duplicates/delete'):
                verify_native_approval(body, 'consolidate_duplicates' if path=='/api/duplicates/delete' else 'restore' if '/restore/' in path else 'create_playlist')
            if path in ('/api/transactions/apply','/api/transactions/restore/apply'):
                verify_native_approval(body,'restore_transactions' if '/restore/' in path else 'recover_transactions')
            if path == '/api/native/approval-preview':
                self.send_json(approval_preview(body.get('token')))
                return
            if path == '/api/shutdown' and _SESSION_TOKEN and _SERVER:
                if not _NATIVE.lock.acquire(blocking=False):
                    self.send_error_json('Esperá a que termine la operación sobre la colección.',409)
                    return
                try: _NATIVE.stop_requested.set()
                finally: _NATIVE.lock.release()
                self.send_json({'status': 'closing'})
                threading.Thread(target=_SERVER.shutdown, daemon=True).start()
                return
            if _NATIVE.stop_requested.is_set(): raise PlanningError('Rekord AI se está cerrando. Volvé a abrirlo para continuar.')
            if path == '/api/transactions/prepare':
                self.send_json(_TRANSACTIONS.prepare());return
            if path == '/api/transactions/apply':
                self.send_json(_TRANSACTIONS.apply(body.get('token')));return
            if path == '/api/transactions/restore/prepare':
                self.send_json(_TRANSACTIONS.prepare_restore(body.get('operation_id')));return
            if path == '/api/transactions/restore/apply':
                self.send_json(_TRANSACTIONS.restore(body.get('token')));return
            if path == '/api/rekordbox/close/prepare':
                self.send_json(_CLOSER.prepare(body.get('mode','normal')));return
            if path == '/api/rekordbox/close/apply':
                self.send_json(_CLOSER.close(body.get('token'),body.get('confirmed')));return
            if path == '/api/native/restore/prepare':
                self.send_json(_NATIVE.prepare_restore(body.get('operation_id')))
                return
            if path == '/api/native/restore/apply':
                result=_NATIVE.restore(body.get('token'))
                activate_operation_collection(result,'source_xml')
                self.send_json(result)
                return
            if path == '/api/dialog':
                self.send_json({'path': choose_file(body.get('kind'), body.get('suggested', ''))})
                return
            if path == '/api/track/drag-file':
                self.send_json(drag_file(get_or_load_library(),body.get('track_id'),body.get('source_revision')));return
            if path == '/api/audio/watch/start':
                if _AUDIO_LOCK.locked():raise PlanningError('Esperá a que termine la prueba puntual de audio')
                lib=get_or_load_library()
                selector=None
                if body.get('automatic') is True:
                    from ..telemetry.audio_candidates import AudioCandidates
                    selector=AudioCandidates(lib,discover)
                self.send_json(_AUDIO_WATCH.start(lib,body.get('track_ids'),body.get('device_index'),body.get('accept_loopback'),body.get('allow_popup',False),selector));return
            if path == '/api/audio/watch/stop':
                self.send_json(_AUDIO_WATCH.stop());return
            if path == '/api/history/start':
                _AUDIO_WATCH.stop()
                _SETTINGS.update({'notifications':{'enabled':True,'silenced':False,'history_popup':True,'history_reference_mode':'last_registered'}})
                self.send_json(recommendation_popup());return
            if path == '/api/audio/signal':
                if _AUDIO_WATCH.snapshot().get('active'):raise PlanningError('Detené el seguimiento antes de comprobar la señal')
                if not _AUDIO_LOCK.acquire(blocking=False):raise PlanningError('Ya hay una prueba de audio en curso')
                try:
                    from ..telemetry.audio_route import probe_signal
                    self.send_json(probe_signal(body.get('device_index'),body.get('accept_loopback')))
                finally:_AUDIO_LOCK.release()
                return
            if path == '/api/audio/identify':
                if _AUDIO_WATCH.snapshot().get('active'):raise PlanningError('Detené el seguimiento continuo antes de hacer una prueba puntual')
                if body.get('accept_loopback') is not True: raise PlanningError('Confirmá el análisis local de la salida de audio')
                lib = get_or_load_library()
                ids = body.get('track_ids', [])
                if body.get('automatic') is True:
                    from ..telemetry.audio_candidates import AudioCandidates
                    ids=AudioCandidates(lib,discover)()
                if not isinstance(ids,list) or not 2<=len(ids)<=20 or any(type(i) is not str for i in ids) or len(set(ids))!=len(ids) or any(i not in lib.tracks for i in ids):
                    raise PlanningError('Seleccioná de 2 a 20 pistas de tu colección para comparar audio')
                index=body.get('device_index')
                if type(index) is not int or index<0: raise PlanningError('Elegí una salida WASAPI válida')
                if not _AUDIO_LOCK.acquire(blocking=False): raise PlanningError('Ya hay una prueba de audio en curso')
                try:
                    from ..telemetry.audio_match import devices,decode,features,capture,identify
                    if index not in {d['index'] for d in devices()}: raise PlanningError('La salida seleccionada cambió; actualizar dispositivos')
                    refs={tid:features(decode(local_path(lib.tracks[tid].location))) for tid in ids}
                    self.send_json(identify(capture(index),refs))
                finally: _AUDIO_LOCK.release()
                return
            if path == '/api/settings':
                if set(body) & {'library_xml', 'energies_json'}:
                    raise PlanningError('Cargá la biblioteca desde /api/library para validar antes de guardarla')
                self.send_json(_SETTINGS.update(body))
                return
            if path == '/api/library':
                if _NATIVE.lock.locked():raise PlanningError('Esperá a que termine la operación nativa antes de cambiar la colección')
                filename = body.get('path')
                if not isinstance(filename, str) or not filename.strip():
                    raise PlanningError('Indicá una ruta XML existente')
                source = Path(filename).resolve()
                energy_path = body.get('energies_path', '')
                if not isinstance(energy_path, str):
                    raise PlanningError('La ruta de energías debe ser texto')
                energy = json.loads(Path(energy_path).read_text(encoding='utf-8')) if energy_path else None
                library = Library(source, energy)
                with _LIB_LOCK:
                    _SETTINGS.update({'library_xml': str(source), 'energies_json': str(Path(energy_path).resolve()) if energy_path else ''})
                    _GLOBAL_LIB = library
                    _AUDIO_WATCH.stop()
                    _HISTORY.reset()
                self.send_json(status())
                return
            if path == '/api/chat':
                query = body.get('query')
                if not isinstance(query, str) or not query.strip():
                    raise PlanningError('Escribí una consulta')
                query=sanitize_user_input(query)
                lib, library_error = current_library()
                if lib is None or getattr(lib,'source',None) == (EXAMPLES_DIR / 'library.xml').resolve():
                    reason = library_error or 'Está cargada la biblioteca de demostración.'
                    self.send_json({'response':f'{reason} Para consultar tu colección, exportá el XML desde Rekordbox y cargalo en Configuración → Colección.',
                                    'applied':False,'answer_mode':'collection_required',
                                    'suggestions':[{'label':'Conectar mi colección','tab':'tab-config','target':'library-form'}]})
                    return
                if lib is not None: query = resolve_followup(query,lib,body.get('context_reference'))
                from .opportunities import analysis_query,answer_analysis,metadata_query,answer_metadata
                if lib is not None and analysis_query(query) and not extract_mentions(query):
                    self.send_json(enrich_chat(answer_analysis(lib,discover),lib));return
                fields=metadata_query(query) if not extract_mentions(query) else None
                if fields:
                    self.send_json(enrich_chat(answer_metadata(lib,fields),lib));return
                # Offline metadata queries do not wait for Windows process probes.
                # Reference names are inert and must not trigger unrelated help.
                help_text = None if extract_mentions(query) else answer_help(query, {'telemetry_available': bool(_LIVE_PROVIDER and _LIVE_PROVIDER.is_available())})
                if help_text:
                    self.send_json(enrich_chat({'response': help_text, 'applied': False, 'intent': {'action': 'help'}},lib))
                    return
                intent = parse_natural_language_intent(query, list(lib.playlists) if lib else [])
                if isinstance(intent,UnknownIntent) and intent.reason==UnknownIntent().reason:
                    self.send_json(assistant_answer(query,lib,body.get('context_reference'),body.get('history')))
                    return
                state = _MONITOR.check_state() if isinstance(intent,(SystemStatusIntent,RecommendLiveIntent)) else 'unknown'
                self.send_json(execute_chat(intent, lib, state, _SETTINGS.snapshot()['recommendation'], current_suggestion(lib, state)))
                return
            lib = get_or_load_library()
            if path == '/api/plan':
                options = PlanOptions(**{key: body[key] for key in ('count', 'mode', 'max_bpm_step', 'harmonic', 'same_genre', 'avoid_adjacent_artist') if key in body})
                if body.get('source') == 'collection':
                    pool = list(lib.tracks.values())
                elif body.get('source') == 'selected':
                    ids = body.get('track_ids', [])
                    if not isinstance(ids, list) or not 1 <= len(ids) <= 1000 or len(ids) != len(set(ids)) or any(i not in lib.tracks for i in ids):
                        raise PlanningError('Selección de pistas inválida')
                    pool = [lib.tracks[i] for i in ids]
                else:
                    pool = lib.pool(body.get('playlists', []))
                genre = body.get('genre', '')
                if not isinstance(genre, str): raise PlanningError('Género inválido')
                if genre: pool = [t for t in pool if t.genre.casefold() == genre.casefold()]
                result = plan(pool, options)
                self.send_json({**result, 'source_revision': lib.revision})
            elif path == '/api/draft':
                self.send_json(draft(lib, body.get('track_ids'), body.get('source_revision')))
            elif path == '/api/duplicates/verify':
                if body.get('source_revision') != lib.revision: raise PlanningError('La colección cambió; volvé a buscar duplicados')
                self.send_json(verify_duplicates(lib, body.get('track_ids')))
            elif path == '/api/duplicates/scan/start':
                if body.get('source_revision') != lib.revision:
                    raise PlanningError('La colección cambió; recargá antes de verificar.')
                self.send_json(_DUPLICATES.start(lib))
            elif path == '/api/duplicates/scan/cancel':
                self.send_json(_DUPLICATES.cancel(body.get('scan_id')))
            elif path == '/api/duplicates/rule':
                self.send_json(_DUPLICATES.rule(lib, body.get('scan_id'), body.get('threshold')))
            elif path == '/api/duplicates/prepare':
                if lib.source == (EXAMPLES_DIR/'library.xml').resolve():raise PlanningError('Cargá tu colección real; la demostración no permite cambios nativos')
                rule=_DUPLICATES.rule(lib,body.get('scan_id'),body.get('threshold'))
                dbs=discover()['databases']
                if len(dbs)!=1:raise PlanningError('No se identificó una base única')
                from ..adapters.duplicate_native import prepare
                self.send_json(prepare(_NATIVE,lib,rule,dbs[0]))
            elif path == '/api/native/prepare':
                if lib.source == (EXAMPLES_DIR/'library.xml').resolve(): raise PlanningError('Cargá tu colección real antes de crear una playlist en Rekordbox. La demostración no permite escritura nativa.')
                if body.get('source_revision') != lib.revision: raise PlanningError('La propuesta pertenece a otra revisión')
                dbs = discover()['databases']
                if len(dbs) != 1: raise PlanningError('No se identificó una base única')
                self.send_json(_NATIVE.prepare(lib,body.get('track_ids'),body.get('name'),dbs[0]))
            elif path == '/api/native/apply':
                if body.get('source_revision') != lib.revision or digest(lib.source) != lib.revision:
                    raise PlanningError('El XML cambió. Revisá nuevamente la propuesta.')
                self.send_json(_NATIVE.apply(body.get('token'),lib.revision))
            elif path == '/api/duplicates/delete':
                if body.get('source_revision')!=lib.revision or digest(lib.source)!=lib.revision:raise PlanningError('La colección cambió; repetí la revisión')
                result=_NATIVE.apply(body.get('token'),lib.revision)
                activate_operation_collection(result,'repaired_xml')
                self.send_json(result)
            elif path == '/api/export':
                result = body.get('result')
                if not isinstance(result, dict) or result.get('source_revision') != lib.revision:
                    raise PlanningError('La propuesta no pertenece a la biblioteca actual; recalculá')
                filename = body.get('target_path')
                if not isinstance(filename, str) or not filename:
                    raise PlanningError('Indicá el destino XML nuevo')
                target = Path(filename)
                if not target.is_absolute():
                    target = Path.home() / 'Documents' / 'Rekord AI' / target
                format_name = body.get('format', 'xml')
                if format_name not in ('xml', 'm3u8'): raise PlanningError('Formato de exportación inválido')
                exporter = export_xml if format_name == 'xml' else export_m3u8
                output = exporter(lib, result, body.get('name', 'Rekord AI Propuesta'), target)
                self.send_json({'status': 'ok', 'exported_file': str(output), 'track_count': len(result['track_ids'])})
            elif path == '/api/compare':
                self.send_json(compare_playlists(lib.pool([body.get('playlist_a')]), lib.pool([body.get('playlist_b')])))
            elif path == '/api/recommend':
                current = lib.tracks.get(body.get('current_track_id'))
                if current is None:
                    raise PlanningError('Seleccioná un ID de pista existente')
                from ..core.recommender import compact_recommendation
                self.send_json(compact_recommendation(recommend(current, list(lib.tracks.values()), RecommendationOptions(**_SETTINGS.snapshot()['recommendation']))))
            else:
                self.send_error_json('Endpoint no encontrado', 404)
        except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
            self.send_error_json(str(exc))


def run_server(host='127.0.0.1', port=8765, default_xml=None, default_energies=None, session_token=None):
    global _SESSION_TOKEN, _SERVER
    if host != '127.0.0.1':
        raise ValueError('El servidor Desktop sólo acepta 127.0.0.1')
    _SESSION_TOKEN = session_token
    if default_xml is not None:
        get_or_load_library(default_xml, default_energies)
    _SERVER = ThreadingHTTPServer((host, port), EgoBitsRequestHandler)
    print(f'EGB_READY:{_SERVER.server_port}', flush=True)
    try:
        _SERVER.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _SERVER.server_close()
        _SERVER = None
        if _LLAMA_RUNTIME:
            _LLAMA_RUNTIME.stop()
