"""Offline spectral matching pilot. Similarity is a score, not a probability.

Only explicitly selected local files are decoded. Audio stays in RAM. No automatic
master confirmation: device routing and real mixer tests must be validated first.
"""
from pathlib import Path
import time
from ..core.models import PlanningError

RATE = 11025
HOP = 1024
SIZE = 2048


def features(samples, hop=HOP):
    import numpy as np
    samples=np.asarray(samples,dtype=np.float32)
    if samples.ndim!=1 or len(samples)<SIZE or not np.isfinite(samples).all():
        raise PlanningError('Audio insuficiente o inválido')
    if type(hop) is not int or not 1<=hop<=HOP:raise PlanningError('Paso de análisis inválido')
    frames=np.lib.stride_tricks.sliding_window_view(samples,SIZE)[::hop]
    spectrum=np.abs(np.fft.rfft(frames*np.hanning(SIZE),axis=1))
    edges=np.unique(np.geomspace(8,SIZE//2,65).astype(int))
    bands=np.stack([np.log1p(spectrum[:,a:b].mean(axis=1)) for a,b in zip(edges,edges[1:])],axis=1)
    bands-=bands.mean(axis=1,keepdims=True)
    norms=np.linalg.norm(bands,axis=1,keepdims=True)
    return (bands/np.maximum(norms,1e-8)).astype(np.float32)


def similarity(reference,query):
    import numpy as np
    if len(reference)<len(query): return 0.0
    # FFT convolution evaluates every possible reference offset in bounded RAM.
    size=1 << (len(reference)+len(query)-1).bit_length()
    product=np.fft.rfft(reference,size,axis=0)*np.fft.rfft(query[::-1],size,axis=0)
    score=np.fft.irfft(product,size,axis=0).sum(axis=1)[len(query)-1:len(reference)]/len(query)
    return float(np.clip(score.max(),0,1))


def decode(path):
    import av
    import numpy as np
    path=Path(path).resolve(strict=True)
    if not path.is_file() or path.stat().st_size>512*1024**2: raise PlanningError('Archivo no elegible para ensayo de audio')
    chunks=[]; frames=0; deadline=time.monotonic()+30
    with av.open(str(path)) as media:
        resampler=av.AudioResampler(format='fltp',layout='mono',rate=RATE)
        for frame in media.decode(audio=0):
            for item in resampler.resample(frame):
                chunk=item.to_ndarray().reshape(-1);chunks.append(chunk);frames+=len(chunk)
            if frames>RATE*900 or time.monotonic()>deadline: raise PlanningError('Audio supera el límite de 15 minutos/30 segundos de decodificación')
        for item in resampler.resample(None): chunks.append(item.to_ndarray().reshape(-1))
    if not chunks: raise PlanningError('No hay audio decodificable')
    return np.concatenate(chunks)


def devices():
    import pyaudiowpatch as pa
    audio=pa.PyAudio()
    try:
        return [{'index':int(d['index']),'name':d['name'],'rate':int(d['defaultSampleRate']),
                 'channels':int(d['maxInputChannels'])} for d in audio.get_loopback_device_info_generator()]
    finally: audio.terminate()


def capture(index,seconds=6):
    import pyaudiowpatch as pa
    import numpy as np
    audio=pa.PyAudio(); stream=None
    try:
        device=audio.get_device_info_by_index(index)
        if not device.get('isLoopbackDevice') or not 1<=device['maxInputChannels']<=8:
            raise PlanningError('Sólo se admiten salidas WASAPI loopback, no micrófonos')
        rate=int(device['defaultSampleRate']);channels=int(device['maxInputChannels'])
        chunks=[]
        stream=audio.open(format=pa.paFloat32,channels=channels,rate=rate,input=True,input_device_index=index,frames_per_buffer=1024)
        for _ in range(int(rate*seconds/1024)):
            chunks.append(np.frombuffer(stream.read(1024,exception_on_overflow=True),dtype=np.float32).reshape(-1,channels).mean(axis=1))
        raw=np.concatenate(chunks)
        return np.interp(np.arange(0,len(raw),rate/RATE),np.arange(len(raw)),raw).astype(np.float32)
    except OSError:
        raise PlanningError('La salida no permite captura compartida WASAPI; revisar ASIO/salida master') from None
    finally:
        if stream: stream.close()
        audio.terminate()


def identify(samples,references):
    import numpy as np
    rms=float(np.sqrt(np.mean(np.asarray(samples,dtype=np.float32)**2)))
    if rms<0.001: return {'matched':False,'reason':'Silencio o nivel insuficiente','rms':rms}
    if len(references)<2: raise PlanningError('Compará al menos dos pistas para evaluar ambigüedad')
    # Capture starts at arbitrary sample positions. Search eight query phases
    # without weakening the score/margin gates or expanding reference memory.
    dense=features(samples,hop=HOP//8)
    phases=[dense[offset::8] for offset in range(8)]
    scores=sorted(((max(similarity(value,query) for query in phases if len(query)),tid) for tid,value in references.items()),reverse=True)
    best,runner=scores[0][0],scores[1][0]
    matched=best>=0.94 and best-runner>=0.10
    return {'matched':matched,'track_id':scores[0][1] if matched else None,'similarity':round(best,4),
            'margin':round(best-runner,4),'rms':rms,'master_confirmed':False,'confirmed':False,
            'reason':'Coincidencia experimental de audio; falta validar ruta master y casos reales' if matched else 'Audio desconocido, mezcla o identificación ambigua',
            'note':'No reconoce con fiabilidad pitch/time-stretch, EQ extrema o todas las mezclas; no habilita Toast.'}
