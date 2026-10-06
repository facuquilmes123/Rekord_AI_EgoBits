"""User-confirmed, normal Windows close requests for discovered Rekordbox.

No termination, injection, arbitrary PID from HTTP or closing other users' apps.
"""
import ctypes
from ctypes import wintypes as W
from pathlib import Path
import os
import secrets
import threading
import time
from ..core.models import PlanningError

NAMES = {'rekordbox.exe', 'rekordboxagent.exe'}


def inventory(discovery):
    if os.name != 'nt': raise PlanningError('El cierre asistido requiere Windows')
    import psutil
    owner = psutil.Process().username().casefold()
    roots = [Path(row['path']).resolve().parent for row in discovery['installations']]
    result = []
    for proc in psutil.process_iter(['pid','name','exe','create_time','username']):
        info = proc.info
        if (info['name'] or '').casefold() not in NAMES: continue
        if not info['exe'] or not info['username'] or info['username'].casefold()!=owner:
            raise PlanningError('No se pudo verificar el propietario de un proceso de Rekordbox. Cerralo manualmente.')
        exe=Path(info['exe']).resolve()
        if exe.name.casefold() not in NAMES or not any(exe.is_relative_to(root) for root in roots):
            raise PlanningError('Un proceso no corresponde a la instalación detectada. Cerralo manualmente.')
        result.append({'pid':info['pid'],'name':info['name'],'path':str(exe),'started':info['create_time']})
    return sorted(result,key=lambda row:row['pid'])


def request_close(rows):
    user=ctypes.WinDLL('user32',use_last_error=True)
    callback_type=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    user.EnumWindows.argtypes=[callback_type,W.LPARAM];user.EnumWindows.restype=W.BOOL
    user.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
    user.GetWindow.argtypes=[W.HWND,W.UINT];user.GetWindow.restype=W.HWND
    user.IsWindowEnabled.argtypes=[W.HWND];user.IsWindowEnabled.restype=W.BOOL
    user.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM];user.PostMessageW.restype=W.BOOL
    pids={row['pid'] for row in rows};posted=set()
    def visit(hwnd,_):
        pid=W.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        # Top-level unowned, enabled windows, including hidden agent windows.
        if pid.value in pids and not user.GetWindow(hwnd,4) and user.IsWindowEnabled(hwnd):
            if user.PostMessageW(hwnd,0x0010,0,0): posted.add(pid.value)
        return True
    callback=callback_type(visit)
    if not user.EnumWindows(callback,0): raise PlanningError('Windows no pudo solicitar el cierre. Cerrá Rekordbox manualmente.')
    return posted


def terminate_owned(rows):
    """Explicit force option, restricted to fresh verified identities."""
    import psutil
    owner=psutil.Process().username().casefold();terminated=set()
    for row in sorted(rows,key=lambda r:r['name'].casefold()!='rekordbox.exe'):
        try:
            proc=psutil.Process(row['pid'])
            if proc.create_time()!=row['started'] or Path(proc.exe()).resolve()!=Path(row['path']).resolve() or proc.username().casefold()!=owner:
                raise PlanningError('Cambió la identidad de un proceso; finalización bloqueada.')
            proc.terminate();terminated.add(row['pid'])
        except psutil.NoSuchProcess:continue
        except psutil.AccessDenied:raise PlanningError('Windows denegó finalizar ese proceso. No se cambió la colección.') from None
    return terminated


class RekordboxCloser:
    def __init__(self, discover, monitor, writer):
        self.discover,self.monitor,self.writer=discover,monitor,writer
        self.tickets={};self.lock=threading.Lock()

    def prepare(self,mode="normal"):
        if mode not in ("normal","force"):raise PlanningError("Modo de cierre inválido")
        with self.lock:
            if self.writer.lock.locked(): raise PlanningError('Esperá a que finalice la operación sobre la colección.')
            if self.monitor.check_native_state()=='unknown': raise PlanningError('No se puede comprobar el estado de los procesos.')
            rows=inventory(self.discover())
            if not rows: return {'state':self.monitor.check_native_state(),'processes':[]}
            token=secrets.token_hex(16)
            self.tickets={token:(time.monotonic()+90,rows,mode)}
            return {'token':token,'mode':mode,'processes':[{'name':row['name'],'path':row['path']} for row in rows],'requires_confirmation':True}

    def close(self,token,confirmed):
        if confirmed is not True or not isinstance(token,str): raise PlanningError('Confirmá el cierre de tu sesión de Rekordbox.')
        with self.lock:
            ticket=self.tickets.pop(token,None)
            if not ticket or ticket[0]<time.monotonic(): raise PlanningError('La confirmación venció. Revisá los procesos nuevamente.')
            # Exclude native publication, restore and backup preparation throughout.
            if not self.writer.lock.acquire(blocking=False): raise PlanningError('Hay una operación sobre la colección en curso.')
            try:
                if inventory(self.discover())!=ticket[1]: raise PlanningError('Los procesos cambiaron. Revisá el cierre nuevamente.')
                force=len(ticket)>2 and ticket[2]=='force'
                close_method=terminate_owned if force else request_close
                primary=[row for row in ticket[1] if row['name'].casefold()=='rekordbox.exe']
                initial=ticket[1] if force else (primary or ticket[1])
                posted=close_method(initial)
                requested={(row['pid'],row['started']) for row in initial}
                deadline=time.monotonic()+15
                remaining=ticket[1]
                while remaining and time.monotonic()<deadline:
                    time.sleep(.25);remaining=inventory(self.discover())
                    if remaining and not any(row['name'].casefold()=='rekordbox.exe' for row in remaining):
                        agents=[row for row in remaining if (row['pid'],row['started']) not in requested]
                        if agents:
                            posted.update(close_method(agents));requested.update((row['pid'],row['started']) for row in agents)
                state=self.monitor.check_native_state()
                reason=('Rekordbox y sus agentes están cerrados. Ya podés preparar el respaldo.' if state=='closed' else
                        'El cierre sigue pendiente. Procesos verificados activos: '+', '.join(f"{row['name']} (PID {row['pid']})" for row in remaining)+'. Revisá las confirmaciones de guardado; si queda un agente, salí desde su icono en la bandeja. Volvé a verificar. La escritura permanece bloqueada.')
                return {'state':state,'reason':reason,'remaining':[row['name'] for row in remaining],'close_requested':len(posted),'forced':force}
            finally: self.writer.lock.release()
