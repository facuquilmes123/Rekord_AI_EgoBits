"""Offline stereo/mono BS.1770 gated loudness and an explicit energy heuristic."""
import math
from pathlib import Path
import time
from .models import PlanningError

RATE=48000


class AcousticMeter:
    """Streaming 48 kHz input. K weighting uses FFmpeg's fixed biquad filters."""
    def __init__(self,channels):
        import av
        import numpy as np
        if channels not in (1,2):raise PlanningError('Análisis acústico admite audio mono o estéreo')
        self.channels=channels;self.graph=av.filter.Graph()
        source=self.graph.add_abuffer(sample_rate=RATE,format='fltp',layout='mono' if channels==1 else 'stereo',time_base='1/48000')
        shelf=self.graph.add('biquad','b0=1.53512485958697:b1=-2.69169618940638:b2=1.19839281085285:a0=1:a1=-1.69065929318241:a2=0.73248077421585')
        highpass=self.graph.add('biquad','b0=1:b1=-2:b2=1:a0=1:a1=-1.99004745483398:a2=0.99007225036621')
        sink=self.graph.add('abuffersink');source.link_to(shelf);shelf.link_to(highpass);highpass.link_to(sink);self.graph.configure()
        self.source=source;self.sink=sink;self.buffer=np.empty((channels,0));self.raw=np.empty(0)
        self.blocks=[];self.frames=0;self.bass=0.;self.middle=0.;self.onsets=0;self.last_onset=-RATE;self.previous_rms=0.;self.raw_position=0

    def feed(self,samples):
        import av
        import numpy as np
        samples=np.asarray(samples,dtype=np.float32)
        if samples.ndim!=2 or samples.shape[0]!=self.channels or not np.isfinite(samples).all():raise PlanningError('PCM inválido')
        self.frames+=samples.shape[1]
        frame=av.AudioFrame.from_ndarray(np.ascontiguousarray(samples),format='fltp',layout='mono' if self.channels==1 else 'stereo');frame.sample_rate=RATE
        self.source.push(frame)
        while True:
            try:weighted=self.sink.pull().to_ndarray()
            except (av.error.BlockingIOError,av.error.EOFError):break
            self.buffer=np.concatenate((self.buffer,weighted),axis=1)
            while self.buffer.shape[1]>=19200:
                self.blocks.append(float(np.mean(self.buffer[:,:19200].astype(np.float64)**2,axis=1).sum()))
                self.buffer=self.buffer[:,4800:]
        self.raw=np.concatenate((self.raw,samples.mean(axis=0)))
        window=np.hanning(2048);freq=np.fft.rfftfreq(2048,1/RATE)
        while len(self.raw)>=2048:
            chunk=self.raw[:2048];power=abs(np.fft.rfft(chunk*window))**2
            self.bass+=float(power[(freq>=20)&(freq<100)].sum());self.middle+=float(power[(freq>=100)&(freq<8000)].sum())
            rms=float(np.sqrt(np.mean(chunk.astype(np.float64)**2)))
            if rms>max(.005,self.previous_rms*1.8) and self.raw_position-self.last_onset>=4800:
                self.onsets+=1;self.last_onset=self.raw_position
            self.previous_rms=rms;self.raw=self.raw[1024:];self.raw_position+=1024

    def result(self):
        import numpy as np
        if not self.blocks:raise PlanningError('Se necesitan al menos 400 ms de audio')
        power=np.array(self.blocks);absolute=power[power>10**((-70+.691)/10)]
        if not len(absolute):lufs=None
        else:
            relative=absolute.mean()/10
            gated=absolute[absolute>relative];lufs=round(-.691+10*math.log10(float(gated.mean())),3)
        duration=self.frames/RATE;ratio=self.bass/max(self.bass+self.middle,1e-20);density=self.onsets/max(duration,1e-9)
        loudness=0 if lufs is None else min(1,max(0,(lufs+30)/25))
        energy=0 if lufs is None else round(10*(.65*loudness+.2*min(1,ratio/.5)+.15*min(1,density/5)),2)
        return {'integrated_lufs':lufs,'sub_bass_ratio':round(ratio,5),'transients_per_second':round(density,4),'duration_seconds':round(duration,3),
                'value':energy,'source':'acoustic-v1: K-weighted gated LUFS + sub100Hz + onset density',
                'energy_kind':'estimated','algorithm':'acoustic-v1','measurement':'BS.1770 K weighting; 400 ms / 75% overlap; gates -70 LUFS and -10 LU',
                'limitations':'Índice heurístico de energía musical; no sustituye escucha. Sólo mono/estéreo. No modifica audio ni mide true peak.'}


def analyze_file(path,cancelled=None):
    import av
    path=Path(path).resolve(strict=True);before=path.stat()
    if before.st_size>2*1024**3:raise PlanningError('Archivo supera 2 GiB')
    started=time.monotonic();meter=None
    with av.open(str(path)) as media:
        if not media.streams.audio:raise PlanningError('Archivo sin audio')
        channels=len(media.streams.audio[0].codec_context.layout.channels)
        meter=AcousticMeter(channels)
        resampler=av.AudioResampler(format='fltp',layout='mono' if channels==1 else 'stereo',rate=RATE)
        for decoded in media.decode(audio=0):
            if cancelled and cancelled.is_set():raise InterruptedError('Análisis cancelado')
            if time.monotonic()-started>600 or meter.frames>RATE*7200:raise PlanningError('Límite por pista: 2 h de audio / 10 min de cálculo')
            for frame in resampler.resample(decoded):meter.feed(frame.to_ndarray())
        for frame in resampler.resample(None):meter.feed(frame.to_ndarray())
    after=path.stat()
    if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise PlanningError('El audio cambió durante el análisis')
    return {**meter.result(),'file_identity':{'path':str(path),'size':after.st_size,'mtime_ns':after.st_mtime_ns,'inode':after.st_ino}}
