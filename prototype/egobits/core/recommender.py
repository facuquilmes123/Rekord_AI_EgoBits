"""Selección determinista configurable; no infiere metadatos ausentes."""
from dataclasses import dataclass
from collections import Counter
import math
from .models import Track, PlanningError
from .planner import harmonic_score
from .search import normalized_genre


def compact_recommendation(result):
    """Keep ranking evidence while bounding transport independent of library size."""
    excluded=result.get('excluded',{})
    return {**{k:v for k,v in result.items() if k!='excluded'},
            'excluded_count':len(excluded),'excluded_reasons':dict(Counter(excluded.values()))}


@dataclass(frozen=True)
class RecommendationOptions:
    count: int = 5
    max_bpm_delta: float = 4.0
    match_bpm: bool = True
    harmonic: bool = True
    same_genre: bool = True
    key_mode: str = 'compatible'
    min_duration_seconds: float | None = None
    max_energy_delta: float | None = None
    avoid_same_artist: bool = True
    max_key_shift: int = 0

    def __post_init__(self):
        if type(self.max_key_shift) is not int or not 0<=self.max_key_shift<=2:raise PlanningError('Key Shift: 0..2 semitonos')
        if type(self.count) is not int or not 1 <= self.count <= 50:
            raise PlanningError('Cantidad de recomendaciones: 1..50')
        if self.key_mode not in ('compatible','same'):raise PlanningError('Modo tonal: compatible o same')
        if self.min_duration_seconds is not None and (type(self.min_duration_seconds) not in (int,float) or not math.isfinite(self.min_duration_seconds) or not 0<=self.min_duration_seconds<=7200):raise PlanningError('Duración mínima: 0..7200 segundos')
        for name in ('max_bpm_delta', 'max_energy_delta'):
            value = getattr(self, name)
            if value is None and name == 'max_energy_delta':
                continue
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 30:
                raise PlanningError(f'{name}: número finito entre 0 y 30')
        for name in ('match_bpm','harmonic', 'same_genre', 'avoid_same_artist'):
            if type(getattr(self, name)) is not bool:
                raise PlanningError(f'{name}: debe ser booleano')


def recommend(current: Track, tracks: list[Track], options: RecommendationOptions) -> dict:
    if options.match_bpm and current.bpm is None:
        raise PlanningError('La pista de referencia no tiene BPM; no se inventa un valor')
    if options.harmonic and current.key is None:
        raise PlanningError('La pista de referencia no tiene tonalidad')
    if options.same_genre and not current.genre:
        raise PlanningError('La pista de referencia no tiene género')
    if options.max_energy_delta is not None and (current.energy is None or not current.energy_source):
        raise PlanningError('La pista de referencia no tiene energía con procedencia')
    candidates, excluded = [], {}
    for track in tracks:
        if track.id == current.id:
            continue
        delta = None if track.bpm is None or current.bpm is None else abs(track.bpm - current.bpm)
        hs = harmonic_score(current.key, track.key)
        shift=0;resulting_key=track.key
        if options.harmonic and options.max_key_shift:
            from .intelligence import key_shift_options
            shifts=key_shift_options(current.key,track.key,options.max_key_shift)
            if options.key_mode=='same':shifts=[s for s in shifts if s['resulting_key']==current.key]
            if shifts:
                selected=shifts[0];shift=selected['semitones'];resulting_key=selected['resulting_key'];hs=selected['harmonic_score']
        energy = None if track.energy is None or current.energy is None or not track.energy_source or not current.energy_source else abs(track.energy - current.energy)
        same_genre=bool(current.genre and track.genre and normalized_genre(track.genre)==normalized_genre(current.genre))
        reason = None
        if options.match_bpm and (delta is None or delta > options.max_bpm_delta):
            reason = 'BPM ausente o fuera del margen'
        elif options.harmonic and (hs is None or hs < 0.85):
            reason = 'Tonalidad ausente o incompatible'
        elif options.harmonic and options.key_mode=='same' and resulting_key!=current.key:
            reason = 'Tonalidad distinta'
        elif options.same_genre and not same_genre:
            reason = 'Género diferente o ausente'
        elif options.max_energy_delta is not None and (energy is None or energy > options.max_energy_delta):
            reason = 'Energía ausente o fuera del margen'
        elif options.avoid_same_artist and current.artist and track.artist.casefold() == current.artist.casefold():
            reason = 'Mismo artista'
        elif options.min_duration_seconds is not None and (track.duration is None or track.duration<options.min_duration_seconds):
            reason = 'Duración ausente o menor al mínimo'
        if reason:
            excluded[track.id] = reason
            continue
        components=[];reasons=[]
        if options.match_bpm:
            components.append((40,1 if options.max_bpm_delta==0 else 1-delta/options.max_bpm_delta))
            reasons.append(f'BPM: diferencia {delta:g}')
        if options.harmonic:
            components.append((35,hs));reasons.append('Misma tonalidad' if track.key==current.key else 'Tonalidad Camelot compatible')
        if options.same_genre:
            components.append((15,1 if same_genre else 0))
            reasons.append('Mismo género' if same_genre else 'Género diferente o sin registrar')
        if options.max_energy_delta is not None:
            components.append((10,1 if options.max_energy_delta==0 else 1-energy/options.max_energy_delta))
            reasons.append(f'Energía: diferencia {energy:g}/10 (con fuente)')
        score=sum(weight*value for weight,value in components)/sum(weight for weight,_ in components) if components else 0
        if shift:
            score*=1-.03*abs(shift)
            reasons.append(f'Key Shift manual {shift:+d} semitonos: {track.key} → {resulting_key}. Ensayá el resultado audible.')
        if options.min_duration_seconds is not None:reasons.append(f'Duración: {track.duration:g} s')
        if not components:reasons.append('Sin filtros de BPM, tonalidad, género o energía; no se calcula compatibilidad')
        row={**vars(track),'compatibility_score':round(score*100,1) if components else None,'match_reasons':reasons,
             'match_details':{'bpm_delta':delta,'harmonic_score':hs,'same_genre':same_genre,'energy_delta':energy,'key_shift_semitones':shift,'resulting_key':resulting_key}}
        candidates.append((-score,(delta or 0) if options.match_bpm else 0,-(hs or 0) if options.harmonic else 0,track.id,row))
    candidates.sort(key=lambda row: row[:4])
    chosen = [row[-1] for row in candidates[:options.count]]
    return {'reference_track': vars(current), 'recommendations': chosen,
            'excluded': excluded, 'options': vars(options),
            'warning': 'Puntaje de compatibilidad por metadatos, no probabilidad ni similitud sonora; no garantiza el resultado perceptual de la mezcla.'}
