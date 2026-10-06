"""Windows Explorer file dialogs, Unicode, no shell or additional dependency."""
import ctypes
from ctypes import wintypes as W
import os
import threading
from pathlib import Path
from ..core.models import PlanningError

_LOCK = threading.Lock()

class OpenFileName(ctypes.Structure):
    _fields_ = [('lStructSize', W.DWORD), ('hwndOwner', W.HWND), ('hInstance', W.HINSTANCE),
                ('lpstrFilter', W.LPCWSTR), ('lpstrCustomFilter', W.LPWSTR),
                ('nMaxCustFilter', W.DWORD), ('nFilterIndex', W.DWORD), ('lpstrFile', W.LPWSTR),
                ('nMaxFile', W.DWORD), ('lpstrFileTitle', W.LPWSTR), ('nMaxFileTitle', W.DWORD),
                ('lpstrInitialDir', W.LPCWSTR), ('lpstrTitle', W.LPCWSTR), ('Flags', W.DWORD),
                ('nFileOffset', W.WORD), ('nFileExtension', W.WORD), ('lpstrDefExt', W.LPCWSTR),
                ('lCustData', ctypes.c_ssize_t), ('lpfnHook', ctypes.c_void_p),
                ('lpTemplateName', W.LPCWSTR), ('pvReserved', ctypes.c_void_p),
                ('dwReserved', W.DWORD), ('FlagsEx', W.DWORD)]

def choose_file(kind, suggested=''):
    choices = {'library': ('xml', False), 'energies': ('json', False),
               'export_xml': ('xml', True), 'export_m3u8': ('m3u8', True)}
    if kind not in choices:
        raise PlanningError('Selector de archivo no admitido')
    if os.name != 'nt':
        raise PlanningError('El explorador de archivos requiere Windows')
    if not _LOCK.acquire(blocking=False):
        raise PlanningError('Ya hay un selector de archivos abierto')
    try:
        ext, save = choices[kind]
        filename = ctypes.create_unicode_buffer(32768)
        filename.value = Path(str(suggested)).name[:200] if save else ''
        config = OpenFileName()
        config.lStructSize = ctypes.sizeof(config)
        config.lpstrFilter = f'Archivos {ext.upper()}\0*.{ext}\0\0'
        config.nFilterIndex = 1
        config.lpstrFile = ctypes.cast(filename, W.LPWSTR)
        config.nMaxFile = len(filename)
        config.lpstrTitle = 'Rekord AI · ' + ('Guardar playlist' if save else 'Seleccionar archivo')
        config.lpstrDefExt = ext
        config.Flags = 0x00080000 | 0x00000008 | 0x00000800 | 0x02000000
        if not save: config.Flags |= 0x00001000
        # The backend is a separate process. An unrelated foreground owner can
        # hide the dialog when the host browser/app is in the background.
        config.hwndOwner = None
        dll = ctypes.WinDLL('comdlg32')
        func = dll.GetSaveFileNameW if save else dll.GetOpenFileNameW
        func.argtypes = [ctypes.POINTER(OpenFileName)]
        func.restype = W.BOOL
        if func(ctypes.byref(config)): return filename.value
        dll.CommDlgExtendedError.restype = W.DWORD
        error = dll.CommDlgExtendedError()
        if error: raise PlanningError(f'Windows no pudo abrir el selector ({error})')
        return None
    finally:
        _LOCK.release()
