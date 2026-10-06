from __future__ import annotations
import re
import unicodedata
from typing import Any
from .intents import (
    Intent,
    PlanPlaylistIntent,
    SearchTracksIntent,
    ComparePlaylistsIntent,
    AuditLibraryIntent,
    ExplainTransitionIntent,
    RecommendManualIntent,
    RecommendLiveIntent,
    SystemStatusIntent,
    UnknownIntent, ListPlaylistsIntent, DuplicatesIntent, DescribeTrackIntent,
    SimilarTracksIntent, MultiSearchIntent, CollectionSummaryIntent, InspectPlaylistIntent, AuditSetlistIntent,
)
from ..core.models import PlanningError

def _matched_playlists(text: str, available: list[str]) -> list[str]:
    full = [p for p in available if re.search(rf'(?<!\w){re.escape(p.casefold())}(?!\w)', text)]
    resolved_shorts = {p.split('/')[-1].casefold() for p in full}
    return [p for p in available if p in full or (p.split('/')[-1].casefold() not in resolved_shorts
            and re.search(rf'(?<!\w){re.escape(p.split("/")[-1].casefold())}(?!\w)', text))]

def sanitize_user_input(raw: str, max_length: int = 500) -> str:
    """Normaliza y limita texto. No es una defensa suficiente contra prompt injection."""
    if not isinstance(raw, str):
        return ''
    # Normalizar Unicode a forma NFC
    cleaned = unicodedata.normalize('NFC', raw)
    # Eliminar caracteres de control no imprimibles
    cleaned = ''.join(ch for ch in cleaned if unicodedata.category(ch)[0] != 'C' or ch in '\n\t ')
    # Limitar longitud para prevenir desbordes y denegación de servicio en memoria
    return cleaned[:max_length].strip()


def _search_intent(query):
    """Extract supported filters instead of searching for the whole sentence."""
    text = ''.join(c for c in unicodedata.normalize('NFD', query) if unicodedata.category(c) != 'Mn')
    params = {}
    number = r'([0-9]+(?:[.,][0-9]+)?)'
    span = re.search(r'(?:entre|de)\s+' + number + r'\s*(?:y|a|-)\s*' + number + r'\s*bpm\b', text)
    bpm = span or re.search(r'(?:de\s+)?' + number + r'\s*bpm\b', text)
    if bpm:
        first = float(bpm.group(1).replace(',', '.'))
        if span:
            params.update(bpm_min=first, bpm_max=float(span.group(2).replace(',', '.')))
        else:
            params.update(bpm_min=max(0, first - .1), bpm_max=first + .1)
        text = text[:bpm.start()] + ' ' + text[bpm.end():]
    key = re.search(r'\b(?:en\s+)?(?:tonalidad|camelot|clave|key)\s*(?:(?:de|en)\s+)?([0-9]{1,2}\s*[ab])\b', text)
    if not key and params:
        key = re.search(r'\b([0-9]{1,2}\s*[ab])\b',text)
    if key:
        params['key'] = re.sub(r'\s', '', key.group(1)).upper()
        text = text[:key.start()] + ' ' + text[key.end():]
    energy = re.search(r'\b(?:buena|alta|mucha|baja|media)\s+energia\b|\benergia\s+(?:buena|alta|baja|media)\b', text)
    if energy:
        if 'baja' in energy.group(): params.update(energy_min=0, energy_max=3.9)
        elif 'media' in energy.group(): params.update(energy_min=4, energy_max=6.9)
        else: params['energy_min'] = 7
        text = text[:energy.start()] + ' ' + text[energy.end():]
    else:
        numeric_energy = re.search(r'\benergia\s+(?:minima\s+|de\s+|al menos\s+)?' + number + r'\b', text)
        if numeric_energy:
            params['energy_min'] = float(numeric_energy.group(1).replace(',', '.'))
            text = text[:numeric_energy.start()] + ' ' + text[numeric_energy.end():]
    aliases = {'techhouse': 'tech house', 'techno': 'techno', 'house': 'house', 'deephouse': 'deep house',
               'progressivehouse': 'progressive house', 'melodictechno': 'melodic techno',
               'afrohouse': 'afro house', 'drumandbass': 'drum and bass', 'minimal': 'minimal'}
    for alias in sorted(aliases, key=len, reverse=True):
        # Match joined/spaced/hyphenated genre names, preserving remaining text.
        pattern = r'(?<!\w)' + r'[\s-]*'.join(alias) + r'(?!\w)'
        match = re.search(pattern, text)
        if match:
            params['genre'] = aliases[alias]
            text = (text[:match.start()] + ' ' + text[match.end():]).strip()
            break
    if not params:
        return SearchTracksIntent(query=re.sub(r'^de\s+', '', query).strip())
    # Remove request scaffolding, retaining artist/title text as a real filter.
    text = re.sub(r'\b(?:en|de|dentro de)\s+(?:(?:mi|la)\s+)?(?:coleccion|biblioteca)\b', ' ', text)
    text = re.sub(r'\b(?:una?|pistas?|tracks?|temas?|canciones?|con|y|de|del|genero)\b', ' ', text)
    text = re.sub(r'\b(?:que|cuales|tengo|tenemos|hay|disponibles?|mi|la|coleccion|biblioteca)\b',' ',text)
    text = ' '.join(text.split()).strip(' ,;?.¿¡!')
    from ..core.search import validate_search
    intent = SearchTracksIntent(query=' '.join(text.split()), **params)
    try: validate_search(intent)
    except PlanningError as error: return UnknownIntent(reason=str(error))
    return intent

def parse_natural_language_intent(text: str, available_playlists: list[str] | None = None) -> Intent:
    """Interpreta solicitudes comunes en lenguaje natural (español) en un Intent tipado.
    Funciona de forma determinista offline sin depender del LLM si éste no está activo.
    """
    text = sanitize_user_input(text)
    s = text.casefold()

    if not s:
        return UnknownIntent()

    # Multiple read-only searches, separated outside quoted song names.
    parts = re.split(r'[;\n]+(?=(?:[^"\x27]*["\x27][^"\x27]*["\x27])*[^"\x27]*$)', text)
    parts = [part.strip() for part in parts if part.strip()]
    if len(parts) > 1:
        if len(parts) > 5: return UnknownIntent(reason='Separá hasta cinco búsquedas por mensaje.')
        parsed = [parse_natural_language_intent(part, available_playlists) for part in parts]
        if all(isinstance(item, (SearchTracksIntent, SimilarTracksIntent)) for item in parsed):
            return MultiSearchIntent(queries=tuple(parts))
        return UnknownIntent(reason='Las consultas separadas por punto y coma deben ser búsquedas o similitudes. Pedí las otras acciones en mensajes separados.')

    from ..core.mentions import extract_mentions, MENTION
    references = extract_mentions(text)
    # Remove reference names before recognizing verbs: song titles are inert data.
    request = MENTION.sub('', s)
    plain = ''.join(c for c in unicodedata.normalize('NFD', request) if unicodedata.category(c) != 'Mn')
    if references and re.search(r'\b(similar\w*|parecid\w*|compatible\w*|recom\w*|decime|dime|busc\w*|mostr\w*|sugeri\w*)\b', plain):
        count = re.search(r'\b(\d+)\s*(?:canciones|pistas|temas|tracks)\b', plain)
        amount = int(count.group(1)) if count else 10
        if not 1 <= amount <= 50 or len(references) > 5:
            return UnknownIntent(reason='Pedí de 1 a 50 resultados y hasta cinco referencias @.')
        by_key = bool(re.search(r'tonalidad|armonic|camelot|clave|key', plain))
        by_genre = bool(re.search(r'genero|estilo', plain))
        by_bpm = bool(re.search(r'bpm|tempo|velocidad', plain))
        by_energy = 'energia' in plain
        specified = by_key or by_genre or by_bpm or by_energy
        exact = bool(re.search(r'(?:misma|igual|exacta)\s+(?:tonalidad|clave)|tonalidad\s+(?:igual|exacta)', plain))
        return SimilarTracksIntent(references=tuple(references), count=amount,
            same_genre=by_genre if specified else True,
            key_mode=('exact' if exact else 'compatible') if by_key or not specified else 'none',
            match_bpm=by_bpm, match_energy=by_energy)

    if references:
        return UnknownIntent(reason='Para invocar una pista usá, por ejemplo: canciones similares en género y tonalidad a @id:123. Los nombres con espacios van entre comillas.')

    if (re.search(r'\b(resum\w*|panorama|estadisticas)\b',plain) and re.search(r'coleccion|biblioteca',plain)) or re.search(r'cuantas\s+(?:pistas|canciones|playlists)\s+(?:tengo|hay)',plain):
        return CollectionSummaryIntent()
    if re.search(r'\b(revis\w*|audit\w*|inspeccion\w*|detalle\w*|analiz\w*)\b',plain) and re.search(r'\bplaylist\b',plain):
        found=_matched_playlists(s,available_playlists or [])
        if len(found)==1:return InspectPlaylistIntent(playlist=found[0])
        return UnknownIntent(reason='Indicá una playlist por su ruta completa para revisar su orden.')
    ids=re.search(r'\b(?:ids|pistas)\s+([0-9][0-9,\s]*)[.!?]?$',plain)
    if ids and re.search(r'\b(?:audit\w*|revis\w*)\b.*\b(?:set|setlist|orden)\b',plain):
        selected=tuple(re.findall(r'\d+',ids.group(1)))
        if len(selected)>1000:return UnknownIntent(reason='La auditoría de orden admite hasta 1000 pistas.')
        return AuditSetlistIntent(track_ids=selected)

    if any(k in s for k in ['duplicad', 'repetidos']):
        return DuplicatesIntent()
    if re.search(r'(listar|mostr[aá]|ver|cu[aá]les).*playlists', s):
        return ListPlaylistsIntent()
    described = re.search(r'(?:describ[ií]|describe|detalle(?:s)? de)\s+(?:pista|track|id)?\s*(\d+)', s)
    if described:
        return DescribeTrackIntent(track_id=described.group(1))

    # Intención: Estado del sistema
    if any(k in s for k in ['estado', 'status', 'cómo está', 'versión', 'como esta']):
        return SystemStatusIntent()

    # Intención: Auditar colección
    if any(k in s for k in ['auditar', 'auditoría', 'auditoria', 'auditá', 'audita', 'revisar biblioteca', 'problemas en coleccion']):
        return AuditLibraryIntent()

    # Intención: Recomendar en vivo
    if any(k in s for k in ['en vivo', 'live', 'qué está sonando', 'que esta sonando', 'ahora sonando']):
        return RecommendLiveIntent()

    # Intención: Recomendar manual
    m_rec = re.search(r'recom(?:endar|endá|enda)(?:\s+desde)?\s+(?:track|id|pista)?\s*([0-9]+)', s)
    if m_rec:
        return RecommendManualIntent(current_track_id=m_rec.group(1))

    # Intención: Explicar transición
    m_trans = re.search(r'transici[oó]n\s+(?:entre|de)?\s*([0-9]+)\s*(?:a|y)?\s*([0-9]+)', s)
    if m_trans:
        return ExplainTransitionIntent(track_a_id=m_trans.group(1), track_b_id=m_trans.group(2))

    # Intención: Comparar playlists
    common_request = re.search(r'\b(?:comparten|compartidas?|en com[uú]n)\b', s)
    pls = _matched_playlists(s, available_playlists or [])
    if 'compar' in s or (common_request and len(pls) >= 2):
        if len(pls) >= 2:
            if len(pls) != 2:
                return UnknownIntent(reason='Indicá exactamente dos playlists por su ruta completa para comparar.')
            return ComparePlaylistsIntent(playlist_a=pls[0], playlist_b=pls[1])
        return UnknownIntent(reason='Indicá las dos playlists que querés comparar.')

    # Intención: Buscar pistas
    if re.search(r'\b(?:que|qué|cuales|cuáles)\b',s) and re.search(r'\b(?:tengo|tenemos|hay)\b',s) and (re.search(r'\d+(?:[.,]\d+)?\s*bpm\b',s) or re.search(r'\b(?:pistas?|temas?|canciones?|tracks?)\b',s)):
        return _search_intent(s)
    m_search = re.search(r'(?:buscar?|busc[aá]|encontr[aá]r?|mostr[aá]r?|dame)(?:\s+(?:tracks?|pistas?|temas?|cancion(?:es)?))?(?:\s+de)?\s*(.+)', s)
    if m_search and not ('playlist' in s or 'unir' in s or 'combinar' in s or 'recorr' in s):
        query = m_search.group(1).strip()
        return _search_intent(query)

    if not re.search(r'\b(recorr\w*|un[ií]|unir|combin\w*|cre[aá]\w*|arm[aá]\w*|gener\w*|planific\w*|orden\w*)\b', s):
        return UnknownIntent()

    # Intención: Planificar playlist (recorrer, unir, crear)
    # Detectar playlists candidatas
    pls_found = _matched_playlists(s, available_playlists or [])
    whole_collection=bool(re.search(r'\b(?:toda\s+(?:mi\s+|la\s+)?|desde\s+(?:mi\s+|la\s+)?)?(?:coleccion|biblioteca)\b',plain))

    if not pls_found and not whole_collection:
        return UnknownIntent(reason='Indicá las playlists por su nombre o ruta; no voy a elegirlas por vos.')
    shorts = [p.split('/')[-1].casefold() for p in pls_found]
    if len(shorts) != len(set(shorts)) and not all(p.casefold() in s for p in pls_found):
        return UnknownIntent(reason='Hay playlists con el mismo nombre. Usá sus rutas completas.')

    # Modo: bpm o energía
    mode = 'energy' if any(k in s for k in ['energía', 'energia', 'energy']) else 'bpm'

    # Cantidad
    m_count = re.search(r'\b([0-9]+)\s*(?:tracks?|pistas?|temas?|canciones)', s)
    count = int(m_count.group(1)) if m_count else 10
    if not 1 <= count <= 100:
        return UnknownIntent(reason='La cantidad debe estar entre 1 y 100; no se modificó tu pedido.')

    # Salto BPM
    m_step = re.search(r'(?:salto|paso|step)\s*(?:de\s+)?([0-9]+(?:\.[0-9]+)?)\s*bpm', s)
    max_bpm_step = float(m_step.group(1)) if m_step else 3.0

    # Restricciones
    same_genre = any(k in s for k in ['mismo género', 'mismo genero', 'un solo género', 'un solo genero'])
    avoid_artist = not any(k in s for k in ['permitir mismo artista', 'permitir repetir artista'])

    out_name = 'Selección Generada'
    m_name = re.search(r'llamada\s+["\']?([^"\'\n]+)["\']?', text, re.IGNORECASE)
    if m_name:
        out_name = sanitize_user_input(m_name.group(1), 50)

    return PlanPlaylistIntent(
        playlists=tuple(pls_found),
        count=count,
        mode=mode,
        max_bpm_step=max_bpm_step,
        same_genre=same_genre,
        avoid_adjacent_artist=avoid_artist,
        out_name=out_name,source='collection' if whole_collection and not pls_found else 'playlists'
    )
