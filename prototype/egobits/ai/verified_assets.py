"""Process-local integrity reuse under Windows handles that deny writes/deletion.

Never trusts persisted timestamps. Other platforms rehash on every verification.
"""
import ctypes
from ctypes import wintypes as W
import os
from pathlib import Path
from ..core.models import PlanningError


def locked_reader(path):
    if os.name!='nt':return None
    import msvcrt
    dll=ctypes.WinDLL('kernel32',use_last_error=True)
    dll.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE]
    dll.CreateFileW.restype=W.HANDLE
    # GENERIC_READ; FILE_SHARE_READ only. llama.cpp may read, nobody may replace/write.
    handle=dll.CreateFileW(str(path),0x80000000,1,None,3,0x80,None)
    if handle==ctypes.c_void_p(-1).value:raise PlanningError('No se pudo proteger el activo de IA: '+path.name)
    try:fd=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY)
    except Exception:
        dll.CloseHandle.argtypes=[W.HANDLE];dll.CloseHandle(handle);raise
    return os.fdopen(fd,'rb')


def identity(stat):return stat.st_dev,stat.st_ino,stat.st_size


class VerifiedAssets:
    def __init__(self):self.held={}

    def verify(self,path,expected,hash_function):
        path=Path(path).resolve();key=(path,expected)
        if len(expected)!=64 or not path.is_file():raise PlanningError('Activo offline ausente o SHA-256 inválido: '+path.name)
        existing=self.held.get(key)
        if existing and identity(os.fstat(existing.fileno()))==identity(path.stat()):return True
        reader=locked_reader(path)
        try:
            if reader and identity(os.fstat(reader.fileno()))!=identity(path.stat()):
                raise PlanningError('El activo de IA cambió de ubicación durante la verificación')
            if hash_function(path)!=expected:raise PlanningError('Activo offline con SHA-256 inválido: '+path.name)
            if reader:
                if identity(os.fstat(reader.fileno()))!=identity(path.stat()):
                    raise PlanningError('El activo de IA fue sustituido durante la verificación')
                if existing:existing.close()
                self.held[key]=reader;reader=None
            return False
        finally:
            if reader:reader.close()

    def close(self):
        for reader in self.held.values():reader.close()
        self.held.clear()
