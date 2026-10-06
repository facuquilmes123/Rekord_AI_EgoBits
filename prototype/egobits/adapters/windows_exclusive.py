"""Windows file handles with share=0 protect BOTH native files during publication.

Bytes are written through the held handles, never via a new unlocked pathname.
Persistent verified backups are mandatory because multi-file writes are not atomic.
"""
import ctypes
from ctypes import wintypes as W
import hashlib
import os
from pathlib import Path
from ..core.models import PlanningError


class WindowsExclusiveFiles:
    def __init__(self, paths, *, allow_rename=False, create_missing=()):
        self.paths=[Path(p) for p in paths];self.handles={};self.allow_rename=allow_rename
        self.create_missing={Path(p).name for p in create_missing}

    def __enter__(self):
        if os.name!='nt': raise PlanningError('La publicación nativa requiere Windows')
        self.dll=ctypes.WinDLL('kernel32',use_last_error=True)
        self.dll.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE]
        self.dll.CreateFileW.restype=W.HANDLE
        self.dll.ReadFile.argtypes=[W.HANDLE,ctypes.c_void_p,W.DWORD,ctypes.POINTER(W.DWORD),ctypes.c_void_p]
        self.dll.WriteFile.argtypes=self.dll.ReadFile.argtypes
        self.dll.ReadFile.restype=self.dll.WriteFile.restype=W.BOOL
        self.dll.SetFilePointerEx.argtypes=[W.HANDLE,ctypes.c_longlong,ctypes.c_void_p,W.DWORD]
        self.dll.SetFilePointerEx.restype=W.BOOL
        for name in ('SetEndOfFile','FlushFileBuffers','CloseHandle'):
            func=getattr(self.dll,name);func.argtypes=[W.HANDLE];func.restype=W.BOOL
        try:
            for path in self.paths:
                # CREATE_NEW is intentionally opt-in.  Recovery uses it only for a
                # previously backed-up sidecar which SQLite removed after a checkpoint.
                disposition=1 if path.name in self.create_missing and not path.exists() else 3
                handle=self.dll.CreateFileW(str(path),0xC0000000 | (0x10000 if self.allow_rename else 0),0,None,disposition,0x80,None)
                if handle==ctypes.c_void_p(-1).value:
                    raise PlanningError('No se obtuvo acceso exclusivo: cerrá Rekordbox y sus procesos de sincronización')
                self.handles[path.name]=handle
            return self
        except Exception:
            self.__exit__(None,None,None);raise

    def seek(self,handle):
        if not self.dll.SetFilePointerEx(handle,0,None,0): raise PlanningError('No se pudo posicionar el archivo bloqueado')

    def digest(self,name):
        handle=self.handles[name];self.seek(handle)
        result=hashlib.sha256();buffer=ctypes.create_string_buffer(1024*1024);count=W.DWORD()
        while True:
            if not self.dll.ReadFile(handle,buffer,len(buffer),ctypes.byref(count),None): raise PlanningError('No se pudo verificar el archivo bloqueado')
            if not count.value: break
            result.update(buffer.raw[:count.value])
        return result.hexdigest()

    def write_from(self,name,source):
        handle=self.handles[name];self.seek(handle)
        with Path(source).open('rb') as stream:
            while chunk:=stream.read(1024*1024):
                buffer=ctypes.create_string_buffer(chunk);count=W.DWORD()
                if not self.dll.WriteFile(handle,buffer,len(chunk),ctypes.byref(count),None) or count.value!=len(chunk):
                    raise PlanningError('Error al escribir; se intentará restaurar el respaldo bajo bloqueo')
        if not self.dll.SetEndOfFile(handle) or not self.dll.FlushFileBuffers(handle):
            raise PlanningError('No se confirmó la escritura en disco')

    def copy_to(self,name,target):
        """Copy bytes from an already-exclusive source HANDLE and durably flush target."""
        handle=self.handles[name];self.seek(handle);target=Path(target)
        with target.open('xb') as stream:
            buffer=ctypes.create_string_buffer(1024*1024);count=W.DWORD()
            while True:
                if not self.dll.ReadFile(handle,buffer,len(buffer),ctypes.byref(count),None):
                    raise PlanningError('No se pudo copiar el archivo bloqueado')
                if not count.value: break
                stream.write(buffer.raw[:count.value])
            stream.flush();os.fsync(stream.fileno())

    def rename(self, name, target):
        """Rename the held identity, with no replacement and no unlocked path race."""
        if not self.allow_rename: raise PlanningError('Este bloqueo no permite mover archivos')
        target=Path(target).absolute()
        class RenameInfo(ctypes.Structure):
            _fields_=[('ReplaceIfExists',W.BOOLEAN),('RootDirectory',W.HANDLE),
                      ('FileNameLength',W.DWORD),('FileName',W.WCHAR * (len(str(target))+1))]
        info=RenameInfo();info.ReplaceIfExists=False;info.RootDirectory=None
        info.FileNameLength=len(str(target).encode('utf-16-le'))
        # Windows wchar count can exceed Python len for non-BMP Unicode.
        raw=str(target).encode('utf-16-le')
        size=RenameInfo.FileName.offset+len(raw)+2
        buffer=ctypes.create_string_buffer(max(size,ctypes.sizeof(info)))
        ctypes.memmove(buffer,ctypes.byref(info),RenameInfo.FileName.offset)
        ctypes.memmove(ctypes.addressof(buffer)+RenameInfo.FileName.offset,raw,len(raw))
        func=self.dll.SetFileInformationByHandle
        func.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD];func.restype=W.BOOL
        if not func(self.handles[name],3,buffer,size):
            raise PlanningError('No se pudo mover el archivo protegido; no se reemplazará ningún destino')

    def __exit__(self,*args):
        for handle in self.handles.values(): self.dll.CloseHandle(handle)
        self.handles.clear()
