"""Read saved routing hints only; preferences are not proof of current master audio."""
import os
from pathlib import Path
import xml.etree.ElementTree as ET
from ..core.models import PlanningError


def saved_route(devices, appdata=None):
    base=Path(appdata or os.environ.get('APPDATA', ''))/'Pioneer/rekordbox6'
    names=[]
    try:
        path=base/'rekordbox3.settings'
        if path.stat().st_size>4*1024**2:raise ValueError('Settings too large')
        raw=path.read_bytes()
        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('XML declarations rejected')
        root=ET.fromstring(raw)
        for row in root.findall('VALUE'):
            if row.get('name')=='audioDeviceManager':
                setup=row.find('DEVICESETUP')
                if setup is not None and setup.get('audioOutputDeviceName'):names.append(setup.get('audioOutputDeviceName'))
        pc=base/'pcmasterout_device_v2.txt'
        if pc.is_file() and pc.stat().st_size<4096:
            name=pc.read_text(encoding='utf-8-sig').strip()
            if name:names.append(name)
    except (OSError,ValueError,ET.ParseError):pass
    matches=[d for d in devices if d['name'].removesuffix(' [Loopback]').casefold() in {n.casefold() for n in names}]
    return {'saved_outputs':list(dict.fromkeys(names)),
            'suggested_device_index':matches[0]['index'] if len(matches)==1 else None,
            'master_confirmed':False,
            'reason':'Salida sugerida por configuración guardada; comprobá la señal y la salida actual de Rekordbox.'}


def probe_signal(device, consent):
    if consent is not True:raise PlanningError('Confirmá el análisis local de la salida seleccionada')
    if type(device) is not int:raise PlanningError('Elegí una salida de audio')
    from .audio_match import devices, capture
    if device not in {d['index'] for d in devices()}:raise PlanningError('Salida no disponible; detectá dispositivos otra vez')
    import numpy as np
    samples=capture(device,seconds=3)
    rms=float(np.sqrt(np.mean(samples**2)))
    signal=bool(np.isfinite(rms) and rms>=.001)
    return {'signal_detected':signal,'rms':rms,'master_confirmed':False,
            'reason':'Hay señal en esta salida. Confirmá que corresponde al master; aún falta identificar la pista.' if signal else
            'No se detecta señal suficiente. Revisá Master Output en Rekordbox. Si usás ASIO/exclusivo, una salida compartida mediante PC MASTER OUT puede permitir la captura.'}
