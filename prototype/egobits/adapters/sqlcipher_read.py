"""Explicit read-only SQLCipher access. Never logs or persists the runtime key."""
from contextlib import contextmanager
from pathlib import Path
import logging
from ..core.models import PlanningError


def driver_and_key():
    logging.getLogger('pyrekordbox').disabled = True
    try:
        from sqlcipher3 import dbapi2
        from pyrekordbox.db6.database import BLOB, deobfuscate
        from pyrekordbox.logger import logger
        logger.disabled = True
        return dbapi2, deobfuscate(BLOB)
    except ImportError:
        raise PlanningError('Falta el componente local SQLCipher declarado en el extra native') from None


@contextmanager
def connection(path, *, readonly=True):
    driver, key = driver_and_key()
    path = Path(path).resolve(strict=True)
    uri = path.as_uri() + ('?mode=ro' if readonly else '?mode=rw')
    conn = driver.connect(uri, uri=True, timeout=2)
    try:
        conn.execute("PRAGMA key='" + key.replace("'", "''") + "'")
        del key
        if readonly: conn.execute('PRAGMA query_only=ON')
        conn.execute('SELECT count(*) FROM sqlite_master').fetchone()
        yield conn
    except driver.Error:
        raise PlanningError('Base SQLCipher no legible o bloqueada; no se modificó la colección') from None
    finally:
        conn.close()


def inspect(path):
    with connection(path) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {'djmdContent', 'djmdPlaylist', 'djmdSongPlaylist', 'agentRegistry'}
        if not required <= tables: raise PlanningError('Esquema nativo no compatible')
        return {'readable': True, 'tracks': conn.execute('SELECT count(*) FROM djmdContent').fetchone()[0],
                'playlists': conn.execute('SELECT count(*) FROM djmdPlaylist').fetchone()[0],
                'integrity': conn.execute('PRAGMA quick_check').fetchone()[0]}
