"""Read-only Pro DJ Link receiver. Protocol facts: Deep Symmetry DJ Link Analysis.

Discovers devices, negotiates an observer number and receives live status.
Only presence packets are transmitted; track IDs retain their media namespace.
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
        raise PlanningError('Cabecera Pro DJ Link invÃ¡lida')
    player = data[0x21]
    if not 1 <= player <= 16: raise PlanningError('NÃºmero de dispositivo invÃ¡lido')
    name = data[12:32].split(b'\0')[0].decode('ascii', errors='replace')
    if port == 50002 and data[10] == 0x0a:
        if len(data) < 0xcc or int.from_bytes(data[0x22:0x24], 'big') + 0x24 != len(data):
            raise PlanningError('Longitud de estado invÃ¡lida')
        bpm = int.from_bytes(data[0x92:0x94], 'big')
        pitch = int.from_bytes(data[0x8c:0x90], 'big') / 0x100000
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
        if len(data) != 0x3c: raise PlanningError('Longitud de posiciÃ³n invÃ¡lida')
        return {'kind':'position', 'player':player, 'name':name,
                'position_seconds':int.from_bytes(data[0x28:0x2c], 'big') / 1000,
                'bpm':int.from_bytes(data[0x38:0x3c], 'big') / 10}
    raise PlanningError('Paquete Pro DJ Link no soportado')


class ProDjLink:
    def __init__(self, clock=time.monotonic, interface_provider=None):
        self.clock=clock;self.lock=threading.RLock();self.decks={};self.devices={};self.sockets=[];self.thread=None
        self.stopping=threading.Event();self.mode='stopped';self.rejected=0;self.error=None
        self.interface_provider=interface_provider or network_interfaces
        self.selected=None;self.requested='auto';self.number=None;self.blocked_numbers=set()
        self.join_packets=[];self.next_send=0;self.discovery_at=0;self.sent_packets=0
        self.interface_cache=None;self.interface_at=0

    def interfaces(self):
        now=self.clock()
        if self.interface_cache is None or now-self.interface_at>5:
            self.interface_cache=self.interface_provider();self.interface_at=now
        return [dict(row) for row in self.interface_cache]

    def ingest(self, data, port, address):
        now=self.clock()
        if port==50000:
            update=decode_announcement(data,address)
            with self.lock:
                if update['kind']=='conflict':
                    if self.number==update['player']:
                        self.blocked_numbers.add(self.number);self.number=None;self.join_packets=[]
                        self.mode='discovering';self.discovery_at=now
                    return
                if update['kind']!='device':return
                if self.selected and address==self.selected['address']:return
                key=(address,update['player'])
                if len(self.devices)>=64 and key not in self.devices:raise PlanningError('Demasiados equipos en la red')
                update['seen_at']=now;self.devices[key]=update
                if update['player']==self.number:
                    self.blocked_numbers.add(self.number);self.number=None;self.join_packets=[]
                    self.mode='discovering';self.discovery_at=now
            return
        update=decode(data,port);key=(address,update['player'])
        with self.lock:
            if self.selected and ipaddress.IPv4Address(address) not in ipaddress.IPv4Network(self.selected['network']):return
            if key not in self.decks and len(self.decks)>=32:raise PlanningError('Demasiados dispositivos')
            previous=self.decks.get(key,{})
            if update['kind']=='position':
                if not previous or now-previous['status_at']>2:return
                previous.update(position_seconds=update['position_seconds'],position_at=now)
                return
            identity=(update['source_player'],update['source_slot'],update['external_track_id'])
            same=previous.get('media_identity')==list(identity)
            self.decks[key]={**update,'address':address,'media_identity':list(identity),'status_at':now,
                'position_at':previous.get('position_at') if same else None,
                'position_seconds':previous.get('position_seconds') if same else None}

    def snapshot(self):
        with self.lock:
            now=self.clock();rows=[]
            for key,row in list(self.decks.items()):
                if now-row['status_at']>30:self.decks.pop(key);continue
                data={k:v for k,v in row.items() if k not in ('status_at','position_at')}
                data.update(fresh=now-row['status_at']<=2,age_seconds=round(now-row['status_at'],2))
                if row.get('position_at') is None or now-row['position_at']>1:data['position_seconds']=None
                rows.append(data)
            devices=[{k:v for k,v in row.items() if k!='seen_at'} for row in self.devices.values() if now-row['seen_at']<=10]
            active=[r for r in rows if r['fresh'] and r.get('on_air_reported') and r.get('playing')]
            messages={'stopped':'Conectá la PC y los reproductores a la misma red y activá la conexión.',
                      'discovering':'Buscando equipos Pro DJ Link en las interfaces de red disponibles.',
                      'joining':'Registrando Rekord AI en la red de los reproductores.',
                      'receiving':'Conexión de red activa. Esperando el estado de los reproductores.',
                      'interface_required':'Se detectaron equipos en varias redes. Elegí la interfaz de tu cabina.',
                      'number_unavailable':'No hay un número libre para conectar Rekord AI a esta red.',
                      'failed':'La conexión necesita atención. Revisá el detalle y volvé a conectar.'}
            message='Recibiendo estados de los reproductores.' if any(r['fresh'] for r in rows) else messages.get(self.mode,'')
            return {'mode':self.mode,'decks':rows,'devices':devices,'on_air_count':len(active),'ambiguous':len(active)>1,
                    'rejected_packets':self.rejected,'error':self.error,'message':message,
                    'interface':self.selected,'observer_number':self.number,'sent_presence_packets':self.sent_packets,
                    'requires_action':self.mode in ('interface_required','number_unavailable','failed'),
                    'note':'Los estados y canales On-Air son informados por los equipos. La identidad de cada pista incluye reproductor y soporte de origen.'}

    def start(self, bind_address='auto'):
        self.interface_cache=None
        interfaces=self.interfaces()
        if bind_address not in ('auto','127.0.0.1') and bind_address not in {r['address'] for r in interfaces}:
            raise PlanningError('Elegí una interfaz activa de esta PC o usá detección automática')
        self.stop();opened=[]
        try:
            for port in (50000,50001,50002):
                sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);opened.append(sock)
                if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
                sock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
                sock.bind(('127.0.0.1' if bind_address=='127.0.0.1' else '0.0.0.0',port));sock.setblocking(False)
        except OSError:
            for sock in opened:sock.close()
            raise PlanningError('No se pudieron abrir los puertos UDP 50000–50002. Otra app puede estar usando Pro DJ Link; detené su conexión de red y reintentá. No hace falta cerrar Rekordbox para consultar su colección.') from None
        with self.lock:
            self.sockets=opened;self.decks={};self.devices={};self.mode='discovering';self.error=None
            self.selected=None;self.number=None;self.requested=bind_address;self.blocked_numbers=set()
            self.join_packets=[];self.sent_packets=0;self.discovery_at=self.clock();self.stopping=threading.Event()
            self.thread=threading.Thread(target=self._run,args=(opened,self.stopping),daemon=True);self.thread.start()
        return self.snapshot()

    def _presence(self, sock):
        with self.lock:
            now=self.clock()
            peers=[d for d in self.devices.values() if now-d['seen_at']<=10 and 1<=d['player']<=16 and d['device_type']==1]
            if self.requested=='127.0.0.1' or not peers:return
            interfaces=self.interfaces()
            matches=[i for i in interfaces if (self.requested=='auto' or i['address']==self.requested)
                     and any(ipaddress.IPv4Address(d['address']) in ipaddress.IPv4Network(i['network']) for d in peers)]
            if not matches:return
            if len(matches)!=1:
                self.mode='interface_required';self.number=None;self.join_packets=[];return
            chosen=matches[0]
            if self.selected and chosen['address']!=self.selected['address']:
                self.number=None;self.join_packets=[];self.discovery_at=now
            self.selected=chosen
            if self.number is None:
                if now-self.discovery_at<3:return
                used={d['player'] for d in self.devices.values() if now-d['seen_at']<=10} | self.blocked_numbers
                self.number=next((n for n in range(7,16) if n not in used),None)
                if self.number is None:self.mode='number_unavailable';return
                self.join_packets=presence_sequence(chosen,self.number);self.next_send=now;self.mode='joining'
            if now<self.next_send:return
            packet=self.join_packets[0] if self.join_packets else keepalive(chosen,self.number,min(255,len(peers)+1))
            # Check routing without sending; never advertise an IP on another adapter.
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as probe:
                probe.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1);probe.connect((chosen['broadcast'],50000))
                if probe.getsockname()[0]!=chosen['address']:
                    self.mode='failed';self.error='La ruta de red no coincide con la interfaz elegida. Revisá VPN y adaptadores de red.';return
            sock.sendto(packet,(chosen['broadcast'],50000));self.sent_packets+=1
            if self.join_packets:self.join_packets.pop(0);self.next_send=now+.3
            else:self.next_send=now+1.5;self.mode='receiving'

    def _run(self,sockets,event):
        while not event.is_set():
            try:
                ready,_,_=select.select(sockets,[],[],.1)
                for sock in ready:
                    # Bounded burst: noisy peers cannot starve discovery/keepalives.
                    for _ in range(32):
                        try:data,source=sock.recvfrom(2049)
                        except BlockingIOError:break
                        try:self.ingest(data,sock.getsockname()[1],source[0])
                        except (PlanningError,ValueError):
                            with self.lock:self.rejected+=1
                self._presence(sockets[0])
            except (OSError,ValueError):
                if not event.is_set():
                    with self.lock:self.error='Se interrumpió la conexión UDP. Revisá la interfaz y volvé a conectar.';self.mode='failed'
                return

    def stop(self):
        self.stopping.set()
        if self.thread and self.thread is not threading.current_thread():self.thread.join(timeout=1)
        with self.lock:
            for sock in self.sockets:sock.close()
            self.sockets=[];self.thread=None;self.mode='stopped';self.decks={};self.devices={};self.number=None;self.selected=None
        return self.snapshot()


def network_interfaces():
    """Read active IPv4/mask/MAC tuples; no scan, installation or global firewall edits."""
    try:import psutil
    except ImportError:raise PlanningError('Falta el componente de red local. Repará la instalación de Rekord AI.') from None
    result=[];stats=psutil.net_if_stats()
    for name,addresses in psutil.net_if_addrs().items():
        if not stats.get(name) or not stats[name].isup:continue
        mac=next((a.address for a in addresses if a.family==psutil.AF_LINK),'').replace('-',':')
        try:mac_bytes=bytes.fromhex(mac.replace(':',''))
        except ValueError:continue
        if len(mac_bytes)!=6 or not any(mac_bytes) or mac_bytes[0]&1:continue
        for addr in addresses:
            if addr.family!=socket.AF_INET or not addr.netmask:continue
            try:
                local=ipaddress.IPv4Interface(addr.address+'/'+addr.netmask)
                if local.ip.is_loopback or local.ip.is_unspecified or local.network.prefixlen>30:continue
            except ValueError:continue
            result.append({'name':name,'address':str(local.ip),'network':str(local.network),
                           'broadcast':str(local.network.broadcast_address),'mac':mac})
    return result


def decode_announcement(data,address):
    if not isinstance(data,bytes) or not 37<=len(data)<=2048 or data[:10]!=MAGIC:
        raise PlanningError('Anuncio Pro DJ Link inválido')
    ip=ipaddress.IPv4Address(address)
    if ip.is_multicast or ip.is_unspecified:raise PlanningError('Origen de red inválido')
    kind=data[10]
    if kind not in (6,8):return {'kind':'ignored'}
    expected=54 if kind==6 else 41
    if len(data)!=expected or data[0x20]!=1 or int.from_bytes(data[0x22:0x24],'big')!=expected:
        raise PlanningError('Longitud de anuncio inválida')
    player=data[0x24]
    if not 1<=player<=255:raise PlanningError('Identidad de equipo inválida')
    if kind==8:return {'kind':'conflict','player':player}
    if data[0x2c:0x30]!=ip.packed:raise PlanningError('La dirección anunciada no coincide con el origen')
    return {'kind':'device','player':player,'address':str(ip),'name':data[12:32].split(b'\0')[0].decode('ascii',errors='replace'),
            'device_type':data[0x34]}


def presence_packet(kind,size):
    data=bytearray(size);data[:10]=MAGIC;data[10]=kind;data[12:21]=b'Rekord AI'
    data[0x20]=1;data[0x21]=3;data[0x22:0x24]=size.to_bytes(2,'big');return data


def keepalive(interface,number,peers=1):
    data=presence_packet(6,54);data[0x21]=2;data[0x24]=number;data[0x25]=1
    data[0x26:0x2c]=bytes.fromhex(interface['mac'].replace(':',''))
    data[0x2c:0x30]=ipaddress.IPv4Address(interface['address']).packed
    data[0x30]=peers;data[0x34]=1;data[0x35]=0x64;return bytes(data)


def presence_sequence(interface,number):
    result=[];mac=bytes.fromhex(interface['mac'].replace(':',''));ip=ipaddress.IPv4Address(interface['address']).packed
    for kind,size in ((10,38),(0,44),(2,50),(4,42)):
        for count in range(1,4):
            data=presence_packet(kind,size)
            if kind==10:data[0x21]=4;data[0x24:0x26]=b'\x01\x40'
            elif kind==0:data[0x24]=count;data[0x25]=1;data[0x26:0x2c]=mac
            elif kind==2:data[0x24:0x28]=ip;data[0x28:0x2e]=mac;data[0x2e]=number;data[0x2f]=count;data[0x30]=1;data[0x31]=1
            else:data[0x24]=number;data[0x25]=count
            result.append(bytes(data))
    return result
