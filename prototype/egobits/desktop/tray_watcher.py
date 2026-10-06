from __future__ import annotations
import os
import csv
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

@dataclass
class NotificationConfig:
    enabled: bool = True
    opt_in: bool = True
    min_frequency_seconds: int = 30
    silenced: bool = False
    allowed_genres: list[str] = field(default_factory=list)
    show_key_compatibility: bool = True
    show_energy_delta: bool = True

class ProcessMonitor:
    """Monitor del proceso de Rekordbox en Windows."""
    def __init__(self, process_name: str = 'rekordbox.exe'):
        self.process_name = process_name.lower()
        self._forced_state: Literal['open', 'closed', 'unknown'] | None = None

    def force_state(self, state: Literal['open', 'closed', 'unknown'] | None):
        """Permite inyectar estado para pruebas o entornos simulados."""
        self._forced_state = state

    def check_state(self) -> Literal['open', 'closed', 'unknown']:
        return self._check(native=False)

    def check_native_state(self) -> Literal['open', 'closed', 'unknown']:
        """Native writes also require agent/synchronization processes to be gone."""
        return self._check(native=True)

    def native_status(self):
        return self._assessment(native=True)

    def _check(self, native=False):
        return self._assessment(native)['state']

    def _assessment(self, native=False):
        if self._forced_state is not None:
            return {'state':self._forced_state,'processes':[],'reason':'Estado simulado para pruebas.'}
        unknown={'state':'unknown','processes':[],'reason':'Windows no pudo comprobar los procesos. Volvé a verificar; no se autoriza escritura por un estado desconocido.'}
        if sys.platform!='win32':return unknown
        try:
            rows=None
            try:
                import psutil
                if hasattr(psutil.process_iter,'cache_clear'):psutil.process_iter.cache_clear()
                snapshot=list(psutil.process_iter(['pid','name']))
                if snapshot and all(row.info['name'] and type(row.info['pid']) is int for row in snapshot):
                    rows=[[row.info['name'],str(row.info['pid'])] for row in snapshot]
            except Exception:pass
            if rows is None:
                output=subprocess.check_output(['tasklist','/FO','CSV','/NH'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),text=True,stderr=subprocess.DEVNULL,timeout=10.0)
                rows=list(csv.reader(output.splitlines()))
            if not rows or any(len(row)<2 or not row[1].isdigit() for row in rows):return unknown
            processes=[{'name':row[0],'pid':int(row[1])} for row in rows if row[0].casefold()==self.process_name or (native and row[0].casefold().startswith('rekordbox'))]
            state='open' if processes else 'closed'
            reason=('Siguen activos: '+', '.join(f"{row['name']} (PID {row['pid']})" for row in processes)+'. Revisá las ventanas de guardado y los agentes de la bandeja.' if processes else 'No se detectan procesos de Rekordbox ni sus agentes. La escritura volverá a comprobarlo antes de preparar el respaldo.')
            return {'state':state,'processes':processes,'reason':reason}
        except Exception:return unknown

class TrayStateManager:
    """Administra el estado de la bandeja del sistema y despacho de alertas."""
    def __init__(self, monitor: ProcessMonitor, config: NotificationConfig | None = None):
        self.monitor = monitor
        self.config = config or NotificationConfig()
        self.last_notification_time: datetime | None = None
        self.notifications_history: list[dict] = []

    def can_dispatch_notification(self) -> bool:
        if not self.config.enabled or not self.config.opt_in or self.config.silenced:
            return False
        if self.monitor.check_state() != 'open':
            return False
        if self.last_notification_time is not None:
            delta = (datetime.now(timezone.utc) - self.last_notification_time).total_seconds()
            if delta < self.config.min_frequency_seconds:
                return False
        return True

    def dispatch_suggestion(self, suggestion_text: str, track_info: dict) -> bool:
        if not self.can_dispatch_notification():
            return False
        self.last_notification_time = datetime.now(timezone.utc)
        record = {
            'timestamp': self.last_notification_time.isoformat(),
            'text': suggestion_text,
            'track': track_info
        }
        self.notifications_history.append(record)
        return True
