"""Read-only Pro DJ Link receiver. Protocol facts: Deep Symmetry DJ Link Analysis.

No virtual player, deck control, load commands or automatic local-ID mapping.
Directed status requires a packet mirror/relay configured by the operator.
"""
import ipaddress
import select
import socket
import threading
import time
from ..core.models import PlanningError

MAGIC = b'Qspt1WmJOL'


def decode(data, port):
    if not isinstance(data, bytes) or not 36 <= len(data) <= 2048 or data[:10] != MAGIC:
        raise PlanningError('Cabecera Pro DJ Link inválida')
    player = data[0x21]
    if not 1 <= player <= 16: raise PlanningError('Número de dispositivo inválido')
    name = data[11:31].split(b'\0')[0].decode('ascii', errors='replace')
    if port == 50002 and data[10] == 0x0a:
        if len(data) < 0xcc or int.from_bytes(data[0x22:0x24], 'big') + 0x24 != len(data):
            raise PlanningError('Longitud de estado inválida')
        bpm = int.from_bytes(data[0x92:0x94], 'big')
        pitch = int.from_bytes(data[0x8d:0x90], 'big') / 0x100000
        beat = int.from_bytes(data[0xa0:0xa4], 'big')
        return {'kind':'status', 'player':player, 'name':name,
                'source_player':data[0x28], 'source_slot':data[0x29], 'track_type':data[0x2a],
                'external_track_id':str(int.from_bytes(data[0x2c:0x30], 'big')),
                'playing':data[0x7b] in (3,4,7,18), 'on_air_reported':bool(data[0x89] & 8),
                'tempo_master':bool(data[0x89] & 32), 'synced':bool(data[0x89] & 16),
                'bpm':None if bpm == 65535 else round(bpm / 100 * pitch, 3),
                'beat_number':None if beat == 0xffffffff else beat, 'beat_in_bar':data[0xa6],
                'position_seconds':None, 'local_track_id':None}
    if port == 50001 and data[10] == 0x0b:
        if len(data) != 0x3c: raise PlanningError('Longitud de posición inválida')
        return {'kind':'position', 'player':player, 'name':name,
                'position_seconds':int.from_bytes(data[0x28:0x2c], 'big') / 1000,
                'bpm':int.from_bytes(data[0x38:0x3c], 'big') / 10}
    raise PlanningError('Paquete Pro DJ Link no soportado')


def simulated_status(player=1, track_id=42, on_air=True):
    """Synthetic documented frame; never claims to be a recording of hardware."""
    data = bytearray(0xd4);data[:10]=MAGIC;data[10]=0x0a;data[11:19]=b'CDJ-SIM '
    data[0x21]=player;data[0x22:0x24]=(len(data)-0x24).to_bytes(2,'big')
    data[0x28]=player;data[0x29]=3;data[0x2a]=1;data[0x2c:0x30]=track_id.to_bytes(4,'big')
    data[0x7b]=3;data[0x89]=0x40 | (8 if on_air else 0);data[0x8d:0x90]=(0x100000).to_bytes(3,'big')
    data[0x92:0x94]=(12800).to_bytes(2,'big');data[0xa0:0xa4]=(129).to_bytes(4,'big');data[0xa6]=1
    return bytes(data)


class ProDjLink:
    def __init__(self, clock=time.monotonic):
        self.clock=clock;self.lock=threading.RLock();self.decks={};self.sockets=[];self.thread=None
        self.stopping=threading.Event();self.mode='stopped';self.rejected=0;self.error=None

    def ingest(self, data, port, address, simulated=False):
        update=decode(data,port);now=self.clock();key=(address,update['player'])
        with self.lock:
            if simulated != (self.mode == 'simulation'):raise PlanningError('Origen de telemetría distinto del modo activo')
            if key not in self.decks and len(self.decks)>=32:raise PlanningError('Demasiados dispositivos')
            previous=self.decks.get(key,{})
            if update['kind']=='position':
                if not previous or now-previous['status_at']>2:return
                previous.update(position_seconds=update['position_seconds'],position_at=now)
                return
            identity=(update['source_player'],update['source_slot'],update['external_track_id'])
            self.decks[key]={**update,'address':address,'media_identity':list(identity),'status_at':now,
                             'position_at':None,'simulated':simulated}

    def snapshot(self):
        with self.lock:
            now=self.clock();rows=[]
            for row in self.decks.values():
                fresh=now-row['status_at']<=2
                data={k:v for k,v in row.items() if k not in ('status_at','position_at')}
                data.update(fresh=fresh,age_seconds=round(now-row['status_at'],2))
                if row.get('position_at') is None or now-row['position_at']>1:data['position_seconds']=None
                rows.append(data)
            active=[r for r in rows if r['fresh'] and r.get('on_air_reported') and r.get('playing')]
            return {'mode':self.mode,'decks':rows,'on_air_count':len(active),'ambiguous':len(active)>1,
                    'rejected_packets':self.rejected,'error':self.error,'hardware_verified':False,
                    'note':'FLX4 no usa Pro DJ Link. Receptor pasivo: los estados dirigidos requieren espejo/relay UDP. On-Air no prueba audio audible. IDs USB no se equiparan a IDs locales.'}

    def simulate(self):
        self.stop()
        with self.lock:
            self.mode='simulation';self.decks={}
            self.ingest(simulated_status(),50002,'simulated-deck-1',True)
            self.ingest(simulated_status(2,42),50002,'simulated-deck-2',True)
            return self.snapshot()

    def start(self, bind_address='127.0.0.1'):
        try:
            address=ipaddress.IPv4Address(bind_address)
            if address.is_multicast or address.is_unspecified:raise ValueError()
        except (ValueError,TypeError):raise PlanningError('Elegí una dirección IPv4 concreta de esta PC') from None
        self.stop();opened=[]
        try:
            for port in (50001,50002):
                sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);opened.append(sock)
                if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
                sock.bind((str(address),port));sock.setblocking(False)
        except OSError:
            for sock in opened:sock.close()
            raise PlanningError('No se pudieron abrir los puertos 50001/50002 en esa interfaz; pueden estar ocupados') from None
        with self.lock:
            self.sockets=opened;self.decks={};self.mode='receiving';self.error=None;self.stopping=threading.Event()
            self.thread=threading.Thread(target=self._run,args=(opened,self.stopping),daemon=True);self.thread.start()
        return self.snapshot()

    def _run(self,sockets,event):
        while not event.is_set():
            try:
                ready,_,_=select.select(sockets,[],[],.2)
                for sock in ready:
                    data,source=sock.recvfrom(2049)
                    try:self.ingest(data,sock.getsockname()[1],source[0])
                    except PlanningError:
                        with self.lock:self.rejected+=1
            except OSError:
                if not event.is_set():
                    with self.lock:self.error='Se interrumpió la recepción UDP';self.mode='failed'
                return

    def stop(self):
        self.stopping.set()
        if self.thread and self.thread is not threading.current_thread():self.thread.join(timeout=1)
        with self.lock:
            for sock in self.sockets:sock.close()
            self.sockets=[];self.thread=None;self.mode='stopped';self.decks={}
        return self.snapshot()
