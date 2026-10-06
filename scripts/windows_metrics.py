"""Sample owned process tree with Windows APIs; no command lines or credentials."""
import ctypes as C
from ctypes import wintypes as W
import os
import threading
import time


class Entry(C.Structure):
    _fields_ = [('size', W.DWORD), ('usage', W.DWORD), ('pid', W.DWORD), ('heap', C.c_size_t),
                ('module', W.DWORD), ('threads', W.DWORD), ('parent', W.DWORD),
                ('priority', W.LONG), ('flags', W.DWORD), ('exe', W.WCHAR * 260)]


class Memory(C.Structure):
    _fields_ = [('size', W.DWORD), ('faults', W.DWORD)] + [(name, C.c_size_t) for name in
        ('peak_working', 'working', 'peak_paged', 'paged', 'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile', 'private')]


class ProcessMetrics:
    def __init__(self, pid):
        self.kernel = C.WinDLL('kernel32', use_last_error=True)
        self.psapi = C.WinDLL('psapi', use_last_error=True)
        self.kernel.CreateToolhelp32Snapshot.argtypes = [W.DWORD, W.DWORD]
        self.kernel.CreateToolhelp32Snapshot.restype = W.HANDLE
        self.kernel.Process32FirstW.argtypes = [W.HANDLE, C.POINTER(Entry)]
        self.kernel.Process32NextW.argtypes = [W.HANDLE, C.POINTER(Entry)]
        self.kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        self.kernel.OpenProcess.restype = W.HANDLE
        self.kernel.CloseHandle.argtypes = [W.HANDLE]
        self.kernel.GetProcessTimes.argtypes = [W.HANDLE] + [C.POINTER(W.FILETIME)] * 4
        self.kernel.GetExitCodeProcess.argtypes = [W.HANDLE, C.POINTER(W.DWORD)]
        self.psapi.GetProcessMemoryInfo.argtypes = [W.HANDLE, C.POINTER(Memory), W.DWORD]
        self.pids = {pid}
        self.handles = {}
        self.cpu = {}
        self.peak_working = self.peak_private = self.samples = 0
        self.stop_event = threading.Event()
        self.started = time.monotonic()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def sample(self):
        snapshot = self.kernel.CreateToolhelp32Snapshot(2, 0)
        parents = {}
        if snapshot != C.c_void_p(-1).value:
            try:
                entry = Entry(); entry.size = C.sizeof(entry)
                ok = self.kernel.Process32FirstW(snapshot, C.byref(entry))
                while ok:
                    parents[entry.pid] = entry.parent
                    ok = self.kernel.Process32NextW(snapshot, C.byref(entry))
            finally:
                self.kernel.CloseHandle(snapshot)
        while True:
            children = {pid for pid, parent in parents.items() if parent in self.pids} - self.pids
            if not children: break
            self.pids.update(children)
        working = private = 0
        for pid in self.pids:
            if pid not in self.handles:
                handle = self.kernel.OpenProcess(0x410, False, pid)
                if handle: self.handles[pid] = handle
            handle = self.handles.get(pid)
            if not handle: continue
            times = [W.FILETIME() for _ in range(4)]
            if self.kernel.GetProcessTimes(handle, *(C.byref(t) for t in times)):
                self.cpu[pid] = sum((t.dwHighDateTime << 32) + t.dwLowDateTime for t in times[2:]) / 10_000_000
            mem = Memory(); mem.size = C.sizeof(mem)
            if self.psapi.GetProcessMemoryInfo(handle, C.byref(mem), mem.size):
                working += mem.working; private += mem.private
        self.peak_working = max(working, self.peak_working)
        self.peak_private = max(private, self.peak_private)
        self.samples += 1

    def run(self):
        while not self.stop_event.is_set():
            self.sample()
            self.stop_event.wait(.25)

    def finish(self):
        self.stop_event.set(); self.thread.join(timeout=3)
        self.sample()
        alive = []
        for pid, handle in self.handles.items():
            code = W.DWORD()
            if self.kernel.GetExitCodeProcess(handle, C.byref(code)) and code.value == 259: alive.append(pid)
            self.kernel.CloseHandle(handle)
        elapsed = time.monotonic() - self.started
        cpu = sum(self.cpu.values())
        return {'sampling_ms': 250, 'samples': self.samples, 'elapsed_seconds': round(elapsed, 2),
                'peak_tree_working_set_mib': round(self.peak_working / 1048576, 1),
                'peak_tree_private_commit_mib': round(self.peak_private / 1048576, 1),
                'cpu_core_seconds': round(cpu, 2), 'logical_cpus': os.cpu_count(),
                'mean_host_cpu_percent': round(100 * cpu / elapsed / (os.cpu_count() or 1), 2),
                'observed_processes': len(self.handles), 'still_alive_pids': alive,
                'limitations': 'Sampled process tree; shared pages may count twice. No concurrent DJ/audio workload.'}
