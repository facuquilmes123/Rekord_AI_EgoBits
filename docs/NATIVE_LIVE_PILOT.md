> Actualización 0.3.2: `docs/ESCRITURA_SEGURA_032.md` sustituye el bloqueo de publicación descripto abajo. La lectura master sigue sin validación real.

# Escritura nativa y lectura de reproducción — piloto local

2026-10-01. Estos cambios son posteriores al Setup 0.3.0 existente. No equivalen a release certificada, escritura real habilitada ni lectura master validada.

## Estado comprobado

- Rekordbox 7.2.19 detectado, abierto durante QA. No se cerró ni se modificó su configuración de audio.
- Base real leída mediante conexión SQLCipher `mode=ro` y `query_only=ON`: 23.683 pistas, 21 playlists, `quick_check=ok`. No se cambió la colección real ni se borró audio.
- Copia coherente cifrada obtenida con SQLite Backup desde lectura de la base. En laboratorio se creó una nueva playlist de tres pistas usando métodos pyrekordbox, su registro USN y `masterPlaylists6.xml`. Orden validado, integridad correcta y huellas lógicas iguales en todas las tablas ajenas a playlists/agentRegistry. Archivo original del laboratorio sin cambios.
- Ensayo en `output/closure/native-lab-1790871232030856600/result.json`; sólo modifica `operations/*/stage/` dentro del laboratorio. No se publicó sobre `master.db` real.
- 110 pruebas: 109 aprobadas, una omitida por extra MCP ausente. Log `output/closure/verify-native-live-pilot-final.log`. Tests nuevos incluyen bloqueo abierto/desconocido, WAL activo, publicación no habilitada, historial inicial ignorado, evento nuevo nunca presentado como master, señal desplazada identificada en prueba controlada, candidatos idénticos ambiguos y silencio.
- UI: dispositivos detectados y acceso nativo comprobados; historial conectado, esperando una entrada nueva; sin errores de consola. Captura `output/playwright/native-live-pilot.png`.

## Escritura: alcance y bloqueo

`NativePlaylistWriter.prepare` exige estado cerrado, base detectada, versión 6/7, ausencia de WAL/SHM/journal, XML fresco y correspondencia única por rutas. Rechaza nombres de playlist repetidos, sin mezclar por título/artista. Crea respaldos SHA-256 y una propuesta aislada; verifica integridad y orden y evita modificaciones de cues, contenido, análisis y otras tablas.

`apply` y el endpoint HTTP de publicación continúan bloqueados. Falta implementar y verificar exclusión frente al arranque concurrente de Rekordbox, recuperación persistente de un cambio multiarchivo y reapertura real en Rekordbox. Reemplazar dos archivos con dos renames no constituye una transacción atómica; esa publicación experimental se retiró. Ningún token o booleano de frontend salta el bloqueo.

No se habilitó eliminar contenido/audio. La primera operación objetivo es crear una playlist nueva; borrar duplicados tendrá un protocolo adicional de conservación de referencias/cues y retirada recuperable del archivo.

## Recomendaciones actuales

1. **Manual:** toma una pista de la colección XML; filtra por diferencia máxima de BPM, armonía Camelot, género, energía con procedencia y artista. Ordena por menor diferencia de BPM, mejor compatibilidad armónica y menor diferencia de energía. Son criterios por metadatos; no una garantía perceptual.
2. **Historial automático, opt-in en Configuración:** consulta entradas nuevas de `djmdSongHistory` en modo de sólo lectura, cada cinco segundos en la UI (mínimo dos en backend). No reutiliza el historial al conectarse. La ruta del archivo debe corresponder a una pista única de la colección cargada. Cambios múltiples, entradas viejas o identidad ambigua no generan referencia. La referencia expira tras 120 segundos sin otra entrada. Usa los filtros guardados y presenta sugerencias en pantalla, sin Toast. No demuestra play/pause, volumen, fader, auriculares o canal master; puede llegar tarde según cuándo Rekordbox registre el historial.
3. **Audio WASAPI, piloto explícito:** enumera sólo salidas loopback. Decodifica 2–20 archivos seleccionados localmente y compara seis segundos de la salida con características espectrales de esos archivos, incluyendo búsqueda de desplazamiento. No guarda audio ni lo transmite. La similitud es un puntaje, no una probabilidad ni certeza calibrada. Silencio, ambigüedad y falta de coincidencia se rechazan. Pitch/time-stretch, mezcla, EQ y versiones similares todavía requieren pruebas; el piloto no identifica toda la biblioteca. `master_confirmed=False`, `confirmed=False`: jamás habilita Toast.

En esta PC sólo se detectó `Speakers (Realtek(R) Audio) [Loopback]`, 48 kHz, dos canales. Falta confirmar si recibe el master de Rekordbox. No se tomó una muestra del audio del usuario durante QA: enumeración y pruebas con señal sintetizada, exclusivamente.

## Dependencias y build offline

- Extra `native`: pyrekordbox 0.4.4 (MIT), sqlcipher3-wheels 0.5.7.
- Extra `audio`: PyAudioWPatch 0.2.12.8 (Apache-2.0), PyAV 18.0.0 (BSD), NumPy 2.5.3. La DLL FFmpeg incluida declara LGPL v3 o posterior; cumplir su redistribución/source offer antes de una entrega pública. Bidict 0.24.1 declara MPL-2.0 y tampoco debe presentarse como MIT. Avisos de paquetes en `assets/licenses/native` y `assets/licenses/audio`.
- Trece wheels fijados, revisados y hashes contrastados con PyPI. Manifiestos `installer/native-wheels.lock.json`, `audio-wheels.lock.json`; procedencia `output/closure/native-audio-provenance.json`.
- `installer/install_local_components.py --install` verifica SHA-256 y usa pip `--no-index --require-hashes` con wheels locales. `build_backend.ps1` lo ejecuta antes de congelar. No instala componentes globales ni descarga durante el runtime.
- Backend de desarrollo recompilado; logs `native-audio-backend-build.log` y `pyinstaller.log`. El instalador 0.3.0 y la aplicación instalada del usuario se conservaron. Falta generar la próxima entrega tras los gates pendientes.

## Prueba necesaria con el equipo real

Confirmar salida master (FLX4 USB/ASIO, parlantes Windows u otra interfaz). Si es ASIO/exclusivo, una salida WASAPI puede no recibirlo. Con música propia de ensayo: pista A audible, pausa/silencio, B sólo en auriculares, crossfader/faders cerrados, mezcla A+B y cambio a B; medir errores/latencia con pitch, EQ y efectos. No inferir master a partir del botón MASTER de sincronización. Sólo habilitar notificaciones después de verificar esa evidencia.

Para escritura real: cerrar Rekordbox de forma normal, completar exclusión y rollback, ensayar en copia, aplicar una playlist nueva revisada con respaldo y verificar al reabrir. No ejecutar durante una sesión DJ.

## Fuentes primarias

- Pulse DJ describe lectura de historial para sus sugerencias: https://blog.pulsedj.com/what-djs-use
- Métodos de playlists/USN y advertencia de dependencias: https://pyrekordbox.readthedocs.io/en/latest/tutorial/db6.html
- WASAPI captura audio del endpoint compartido, no identifica por sí solo el master de una app ni soporta modo exclusivo: https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording
- Algunos proyectos Windows exportan track/deck master mediante inyección/hook específico de versión: https://github.com/Unreal-Dan/RekordBoxSongExporter . No se incorporó inyección en Rekordbox.

La referencia Pulse permite justificar seguimiento del historial; no certifica su capacidad para identificar audio master ni nuestra implementación.
