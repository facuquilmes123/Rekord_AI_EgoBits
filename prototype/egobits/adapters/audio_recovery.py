"""Reversible local audio moves; verified identities remain locked throughout."""
from contextlib import ExitStack
from pathlib import Path
from .windows_exclusive import WindowsExclusiveFiles
from ..core.models import PlanningError


class AudioRecovery:
    def __init__(self,manifest):
        self.manifest=manifest;self.stack=ExitStack();self.held={};self.moved=[]

    def __enter__(self):
        try:
            for source,sha in self.manifest.get('audio_checks',{}).items():
                path=Path(source)
                if path.resolve(strict=True)!=path or path.stat().st_nlink!=1:
                    raise PlanningError('Cambió la identidad o ubicación de un archivo de música')
                held=self.stack.enter_context(WindowsExclusiveFiles([path],allow_rename=True))
                if held.digest(path.name)!=sha:raise PlanningError('La música cambió; operación cancelada')
                self.held[source]=held
            for move in self.manifest.get('audio_moves',[]):
                source=Path(move['source']);target=Path(move['target'])
                if str(source) not in self.held or target.exists() or target.parent.resolve(strict=True)!=target.parent:
                    raise PlanningError('Destino de recuperación ocupado o alterado')
                if source.anchor.casefold()!=target.anchor.casefold():raise PlanningError('La recuperación debe estar en el mismo volumen')
            return self
        except Exception:self.stack.close();raise

    def move(self):
        for item in self.manifest.get('audio_moves',[]):
            self.held[item['source']].rename(Path(item['source']).name,item['target'])
            self.moved.append(item)

    def rollback(self):
        for item in reversed(self.moved):
            self.held[item['source']].rename(Path(item['source']).name,item['source'])
        self.moved=[]

    def __exit__(self,*args):self.stack.close()


def restore_plan(origin):
    """Locate moved identities after a crash, never overwrite an occupied path."""
    from .native_write import digest
    checks={};moves=[]
    for item in origin.get('audio_moves',[]):
        source=Path(item['source']);target=Path(item['target'])
        if source.exists() and target.exists():raise PlanningError('Ambas rutas de música existen: restauración manual requerida')
        existing=source if source.exists() else target
        if not existing.is_file() or digest(existing)!=item['sha256']:
            raise PlanningError('Falta música recuperable o su contenido cambió')
        checks[str(existing)]=item['sha256']
        if existing==target:moves.append({'source':str(target),'target':str(source),'sha256':item['sha256']})
    return checks,moves
