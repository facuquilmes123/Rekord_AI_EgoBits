"""Lectura de snapshots SQLite descifrados, no de la colección SQLCipher activa."""
from __future__ import annotations
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any
from ..core.models import PlanningError

class NativeReadOnlyAdapter:
    def __init__(self, db_path: Path):
        self.db_path = db_path.resolve()
        if not self.db_path.is_file():
            raise PlanningError('Snapshot de base de datos no encontrado')
        with self.db_path.open('rb') as stream:
            if stream.read(16) != b'SQLite format 3\x00':
                raise PlanningError('Se requiere snapshot SQLite descifrado. SQLCipher no implementado; usá XML.')

    def read_tracks_snapshot(self, limit: int = 100) -> list[dict[str, Any]]:
        if type(limit) is not int or not 1 <= limit <= 10000:
            raise PlanningError('Límite inválido: 1..10000')
        try:
            with closing(sqlite3.connect(self.db_path.as_uri() + '?mode=ro', uri=True)) as conn:
                conn.execute('PRAGMA query_only=ON')
                required = {'djmdContent': {'ID','Title','ArtistID','BPM','KeyID'},
                            'djmdArtist': {'ID','Name'}, 'djmdKey': {'ID','ScaleName'}}
                for table, columns in required.items():
                    actual = {row[1] for row in conn.execute(f'PRAGMA table_info({table})')}
                    if not columns <= actual:
                        raise PlanningError(f'Esquema no compatible: {table}')
                rows = conn.execute("""SELECT c.ID,c.Title,a.Name,c.BPM,k.ScaleName
                    FROM djmdContent AS c LEFT JOIN djmdArtist AS a ON a.ID=c.ArtistID
                    LEFT JOIN djmdKey AS k ON k.ID=c.KeyID ORDER BY c.ID LIMIT ?""",(limit,)).fetchall()
                return [{'id':str(r[0]),'title':r[1] or '', 'artist':r[2] or '',
                         'bpm':r[3]/100.0 if r[3] else None,'key':r[4] or ''} for r in rows]
        except sqlite3.Error as exc:
            raise PlanningError(f'Snapshot no legible: {exc}') from exc
