import argparse
import json
import os
import sys
from pathlib import Path
from .core import (
    Library,
    PlanOptions,
    plan,
    export_xml,
    audit_library,
    find_duplicates,
    compare_playlists
)

def main():
    # The frozen CLI also emits Unicode when redirected by Windows PowerShell.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
    p = argparse.ArgumentParser(description='Rekord AI: asistente de DJ y planificador determinista offline')
    p.add_argument('--xml', type=Path, help='Ruta al archivo XML exportado desde Rekordbox')
    p.add_argument('--list', action='store_true', help='Listar playlists disponibles y cantidad de tracks')
    p.add_argument('--playlist', action='append', default=[], help='Playlist a incluir (repetible, ej. --playlist ROOT/X --playlist ROOT/Y)')
    p.add_argument('--count', type=int, default=4, help='Cantidad de tracks requeridos en la propuesta (1..100)')
    p.add_argument('--mode', choices=['bpm', 'energy'], default='bpm', help='Modo de optimización (bpm o energy)')
    p.add_argument('--energies', type=Path, help='Ruta a JSON de energías con procedencia declarada')
    p.add_argument('--max-bpm-step', type=float, default=3.0, help='Salto máximo de BPM admisible por transición')
    p.add_argument('--same-genre', action='store_true', help='Exigir que todas las pistas mantengan el mismo género')
    p.add_argument('--allow-key-clash', action='store_true', help='Permitir saltos armónicos no adyacentes en Camelot')
    p.add_argument('--name', default='Rekord AI - propuesta', help='Nombre de la playlist a exportar en el nuevo XML')
    p.add_argument('--out', type=Path, help='Ruta de destino para el nuevo archivo XML (ej. propuesta.xml)')
    p.add_argument('--audit', action='store_true', help='Auditar metadatos de la colección (tracks sin BPM, sin Key, etc.)')
    p.add_argument('--duplicates', action='store_true', help='Buscar pistas duplicadas por título y artista')
    p.add_argument('--compare', nargs=2, metavar=('PLAYLIST_A', 'PLAYLIST_B'), help='Comparar dos playlists')
    p.add_argument('--serve', action='store_true', help='Iniciar servidor local de UI y API desktop')
    p.add_argument('--port', type=int, default=8765, help='Puerto para el servidor desktop (def: 8765)')

    a = p.parse_args()

    if a.serve:
        from .desktop.service import run_server
        print(f"Iniciando servicio Desktop Rekord AI en http://127.0.0.1:{a.port}")
        run_server(port=a.port, default_xml=a.xml, default_energies=a.energies,
                   session_token=os.environ.get('EGB_SESSION_TOKEN'))
        return

    if not a.xml:
        p.print_help()
        sys.exit(1)

    energy = json.loads(a.energies.read_text(encoding='utf-8')) if a.energies else None
    lib = Library(a.xml, energy)

    if a.list:
        print(json.dumps({'revision': lib.revision, 'playlists': {k: len(v) for k, v in lib.playlists.items()}}, ensure_ascii=False, indent=2))
        return

    if a.audit:
        report = audit_library(list(lib.tracks.values()))
        report['source_revision'] = lib.revision
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    if a.duplicates:
        dups = find_duplicates(list(lib.tracks.values()))
        print(json.dumps({'source_revision': lib.revision, 'duplicates_count': len(dups), 'groups': dups}, ensure_ascii=False, indent=2))
        return

    if a.compare:
        p1, p2 = a.compare
        cmp_result = compare_playlists(lib.pool([p1]), lib.pool([p2]), p1, p2)
        cmp_result['source_revision'] = lib.revision
        print(json.dumps(cmp_result, ensure_ascii=False, indent=2))
        return

    if not a.playlist:
        print("Error: Seleccioná al menos una playlist con --playlist o usá --list para ver las disponibles.", file=sys.stderr)
        sys.exit(1)

    result = plan(
        lib.pool(a.playlist),
        PlanOptions(
            count=a.count,
            mode=a.mode,
            max_bpm_step=a.max_bpm_step,
            harmonic=not a.allow_key_clash,
            same_genre=a.same_genre
        )
    )
    result['source_revision'] = lib.revision
    if a.out:
        export_xml(lib, result, a.name, a.out)
        result['exported_xml'] = str(a.out)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
