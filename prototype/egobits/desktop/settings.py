"""Preferencias locales, validadas antes de reemplazar el archivo anterior."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
from ..core.models import PlanningError
from ..core.recommender import RecommendationOptions

DEFAULTS = {
    'library_xml': '', 'energies_json': '', 'llm_enabled': True,
    'collection_mode':'auto','native_database':'',
    'notifications': {'enabled': False, 'silenced': False, 'min_frequency_seconds': 30, 'history_popup':False,'history_reference_mode':'last_registered'},
    'recommendation': vars(RecommendationOptions()),
}


class SettingsStore:
    def __init__(self, path: Path | None = None):
        base = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Rekord AI EgoBits'
        self.path = path or base / 'settings.json'
        self.lock = RLock()
        self.data = deepcopy(DEFAULTS)
        self.load_error = None
        if self.path.exists():
            try:
                self.data = self.validate(json.loads(self.path.read_text(encoding='utf-8')))
            except (OSError, ValueError, TypeError) as exc:
                self.load_error = f'Preferencias no cargadas: {exc}'

    @staticmethod
    def validate(data):
        if isinstance(data,dict):
            data=deepcopy(data)
            data.setdefault('collection_mode','auto');data.setdefault('native_database','')
        if not isinstance(data, dict) or set(data) != set(DEFAULTS):
            raise PlanningError('Estructura de preferencias inválida')
        if data['collection_mode'] not in ('auto','xml','native'):raise PlanningError('Origen de colección inválido')
        for key in ('library_xml', 'energies_json','native_database'):
            if not isinstance(data[key], str) or len(data[key]) > 32768:
                raise PlanningError(f'{key} debe ser una ruta de texto')
        if type(data['llm_enabled']) is not bool:
            raise PlanningError('llm_enabled debe ser booleano')
        notification = data['notifications']
        if isinstance(notification,dict) and 'history_popup' not in notification:
            data=deepcopy(data)
            notification=data['notifications']
            notification['history_popup']=False
        if isinstance(notification,dict) and 'history_reference_mode' not in notification:
            data=deepcopy(data);notification=data['notifications'];notification['history_reference_mode']='new_entries'
        if not isinstance(notification, dict) or set(notification) != set(DEFAULTS['notifications']):
            raise PlanningError('Preferencias de avisos inválidas')
        if any(type(notification[k]) is not bool for k in ('enabled', 'silenced','history_popup')):
            raise PlanningError('Activación y silencio deben ser booleanos')
        if notification['history_reference_mode'] not in ('last_registered','new_entries'):raise PlanningError('Modo de referencia del historial inválido')
        interval = notification['min_frequency_seconds']
        if type(interval) is not int or not 10 <= interval <= 3600:
            raise PlanningError('Intervalo de avisos: 10..3600 segundos')
        try:
            options=RecommendationOptions(**data['recommendation'])
        except (TypeError, ValueError) as exc:
            raise PlanningError(f'Recomendador: {exc}') from exc
        data=deepcopy(data)
        data['recommendation']=vars(options)
        return data

    def snapshot(self):
        with self.lock:
            return deepcopy(self.data)

    def update(self, changes):
        with self.lock:
            if not isinstance(changes, dict) or set(changes) - set(DEFAULTS):
                raise PlanningError('Preferencias desconocidas')
            proposed = self.snapshot()
            for key, value in changes.items():
                if key in ('notifications', 'recommendation'):
                    if not isinstance(value, dict):
                        raise PlanningError(f'{key} debe ser un objeto')
                    proposed[key].update(value)
                else:
                    proposed[key] = value
            proposed = self.validate(proposed)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            name = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                                 prefix='settings-', suffix='.tmp', delete=False) as stream:
                    name = stream.name
                    json.dump(proposed, stream, ensure_ascii=False, indent=2)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(name, self.path)
                self.data = proposed
                self.load_error = None
            finally:
                if name and Path(name).exists():
                    Path(name).unlink()
            return self.snapshot()
