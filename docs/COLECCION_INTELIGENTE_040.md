# Colección inteligente — 0.4.0

## Alcance y uso

Implementación del adjunto del 6 de octubre de 2026. Se conserva la identidad de actualización y se reemplazan los ejecutables instalados, **sin generar Setup**. Equipo del usuario: DDJ-FLX4. Las pruebas USB y Pro DJ Link son simulaciones documentadas, no certificación de reproductores físicos.

En **Laboratorio DJ**:

1. **Conectar colección de Rekordbox** abre `master.db` en modo de sólo lectura. No hace falta cerrar Rekordbox. La lectura usa una transacción coherente y revisa cambios de DB/WAL, con caché de tres segundos. XML continúa disponible en Configuración.
2. **Explorar** permite estrellas, contador de reproducciones, fecha y varios MyTags. Los conteos cubren la colección completa; los resultados se paginan. Se pueden pasar pistas marcadas al planificador. `DJPlayCount=0` sólo describe el contador de esa colección, no toda la vida de una canción.
3. **Estructura y ensayo** muestra cues/loops, presencia de beatgrid y frases que realmente existen en ANLZ. La transición por frases necesita Outro saliente y Hot Cue A entrante; calcula segundos y duración asumiendo 4/4. No garantiza sincronización de drops ni beatgrid correcto.
4. **Audio offline** analiza selección, playlist o colección en segundo plano. Se puede cancelar y conservar resultados parciales. Los archivos originales no se modifican. Las mediciones se invalidan si cambian ruta, tamaño, fecha o identidad del archivo. El planificador usa la energía calculada automáticamente.
5. **Key Shift** es optativo, apagado inicialmente, con máximo ±1/2 semitonos. La recomendación indica tonalidad resultante y acción manual. No envía órdenes al FLX4 ni presupone botones/modos disponibles en cada software.
6. **USB DeviceSQL** detecta exportaciones existentes, comprueba páginas, archivos/análisis y referencias de playlists. Puede preparar una playlist con pistas ya presentes o copiar pistas de la colección junto con su audio y ANLZ. La publicación requiere cierre de Rekordbox/agentes, respaldo verificado y confirmación nativa. Hay restauración con otro respaldo del estado actual; no borra música adicional.
7. **Pro DJ Link** ofrece dos modos separados: simulación de paquetes y receptor UDP pasivo. Los datos envejecen y no se convierten en notificaciones de master audible. El FLX4 no utiliza este protocolo. Los estados dirigidos de equipos compatibles necesitan un espejo/relay de paquetes hacia la IPv4 seleccionada; esta versión no anuncia un CDJ virtual.

### Consultas directas

- «Mostrame pistas sin reproducir con 5 estrellas».
- «Buscá pistas con etiqueta \"Peak Time\" desde 2026-01-01».
- «Armame un set de 10 pistas sin reproducir con 4 estrellas».
- «Listar MyTags».

Las combinaciones habituales de filtros y planificación usan código determinista. La búsqueda cuenta todas las coincidencias; la planificación automática toma hasta 200 candidatas e informa esa preselección. El planificador existente de toda la colección conserva sus propios límites y avisos.

## Arquitectura y contratos

| Superficie | Responsabilidad |
| --- | --- |
| `adapters/native_collection.py` | Lectura SQLCipher coherente, metadata, cues, playlists y snapshot privado por DB. Sustituye controles XML ilegales sólo en el snapshot; no edita la base. |
| `core/intelligence.py` | Filtros, paginación, archivos, estructura, Key Shift y transiciones. |
| `adapters/analysis_structure.py` | PQTZ/PSSI, tiempos reales del beatgrid, frases por mood; ausencias explícitas. |
| `core/acoustic.py` | Decoder PyAV, K-weighting, gating, espectro y transientes. |
| `desktop/analysis_jobs.py` | Un trabajo cancelable, persistencia atómica e invalidación de resultados. |
| `core/toolbox.py` | Doce operaciones compartidas de lectura/planificación, firma validada y ciclo de modelo acotado. |
| `adapters/device_library.py` | DeviceSQL, propuestas, respaldo, publicación exclusiva y restauración. |
| `adapters/anlz_relocate.py` | Reemplaza PPTH; conserva todas las demás secciones ANLZ byte por byte, incluso desconocidas u ofuscadas. |
| `telemetry/prodj_link.py` | Decodificación de estado/posición, receptor, caducidad, namespaces y simulador. |
| `desktop/ui/intelligence.js` | Controles del Laboratorio DJ y presentación sin ejecutar metadata como HTML. |

### Herramientas compartidas

MCP registra **15** herramientas. Se agregan `collection.tools` (catálogo) y `collection.execute` (invocación validada). El catálogo compartido incluye:

`collection.query`, `collection.tags`, `collection.missing_files`, `track.structure`, `set.preshow`, `transition.phrase`, `set.plan_selection`, `recommend.key_shift`, `audio.measurement`, `device.list`, `device.audit`, `link.state`.

HTTP usa `POST /api/toolbox/catalog` y `/api/toolbox/execute`. La UI y el asistente llaman a la misma implementación. No se necesita iniciar un servidor MCP adicional para el chat. Los trabajos acústicos, selección de fuente, receptor y escrituras tienen endpoints de UI explícitos; no son acciones autónomas del modelo.

El agente permite hasta tres pasos, evita repetir llamadas, reduce el catálogo según la consulta, limita el contexto y termina al producir una propuesta. El paso de inferencia tiene límite de 30 s; el presupuesto entre pasos es 65 s (una llamada iniciada antes del límite puede concluir después). Se puede cancelar entre pasos. La carga inicial del modelo es independiente de esos límites. Las respuestas del modelo no autorizan SQL, shell, borrado, exportaciones o escrituras.

**Limitación observada:** dos intentos con el modelo CPU de este host agotaron límites de 15/30 s. La composición fue verificada con un cliente controlado; no se certifica resolución general de consultas compuestas por el modelo real. Los flujos equivalentes están disponibles en controles deterministas y las combinaciones habituales de filtros tienen ruta directa.

### Seguridad USB

- Sólo DeviceSQL existente; no crea una exportación completa desde un pendrive vacío.
- Si existe `exportLibrary.db` (Device Library Plus), se bloquea la escritura directa para no desincronizar ambas bases; se debe exportar desde Rekordbox.
- Hasta 100 pistas por propuesta; caducidad de diez minutos; bloqueo de escritores concurrentes; hash de DB original, DB propuesta y cada archivo copiado.
- Audio nuevo: MP3, AAC en M4A, WAV/AIFF PCM entero 16/24 bits; frecuencias 44,1/48/88,2/96 kHz. Es un límite de implementación, no garantía de compatibilidad universal con cada CDJ.
- Se requiere ANLZ original con PPTH válido. Conserva DAT/EXT/2EX y cambia sólo la ruta. No inventa análisis ni replica artwork adicional.
- Ante una excepción durante publicación se restaura la DB original. Ante corte eléctrico se conserva respaldo para restauración posterior. Pueden quedar archivos nuevos sin referencia; no se eliminan automáticamente.
- Firma de confirmación HMAC ligada a operación/token/digest, generada únicamente por el shell después del diálogo de Windows. Un booleano enviado por chat/HTTP no habilita la escritura.

### Sonoridad y energía

Medición mono/estéreo a 48 kHz: filtros K, bloques de 400 ms con 75% de solapamiento, puerta absoluta −70 LUFS y relativa −10 LU. El silencio se representa sin valor LUFS, no como infinito JSON. No mide true peak.

Índice `acoustic-v1`: 65% sonoridad normalizada entre −30 y −5 LUFS, 20% proporción de subgrave y 15% densidad de transientes; salida 0..10. Es una **heurística de energía**, no una escala musical científica ni una certificación de sonoridad. Límite por archivo: 2 GiB, dos horas de audio y diez minutos de cálculo.

Persistencia privada: `%LOCALAPPDATA%/Rekord AI EgoBits/collection-cache`, `acoustic-analysis` y `usb-backups`. No subir esos directorios, bases, audio, configuración, rutas de música ni credenciales al repositorio.

## Evidencia

- Suite completa: 308 tests, 307 aprobados y uno omitido por SDK MCP opcional en el entorno de build. MCP stdio real ejecutado por separado con SDK instalado: aprobado (15 herramientas; invocación compartida y rechazo de escritura).
- Después de ajustes finales de contexto/caché: 34 tests dirigidos aprobados. Rust: dos tests aprobados (HMAC y rutas Unicode).
- Colección real en modo lectura: 24.140 pistas, 22 playlists, 28 MyTags. Carga inicial 4,829 s; consulta posterior 0,140 s. Se saneó un campo con control ilegal sólo en el XML temporal.
- Tres ANLZ reales: beatgrid presente; 20, 19 y 16 frases leídas respectivamente. Sin escribir esos archivos.
- Navegador real: filtros de cinco estrellas y contador cero devolvieron 148 coincidencias; controles, MyTags y simulación de dos decks visibles, sin errores de consola observados.
- LUFS: silencio, relación de +6,02 dB al duplicar amplitud y +3,01 dB estéreo frente a mono, usando tonos sintéticos.
- USB temporal: lectura de fixture público, playlist preservando pistas, respaldo, replay rechazado, restauración, exportación de WAV generado + ANLZ con sección desconocida preservada y rutas verificadas.
- HTTP: autenticación existente; HMAC ausente o correspondiente a otra operación rechazado; ruta de aplicación sólo con firma correcta en fixture. Ninguna escritura real en USB o master.db durante QA.
- Pro DJ Link: frames sintéticos documentados, bytes malformados, fuentes con mismo ID, caducidad/ambigüedad y recepción UDP real por loopback. Sin hardware físico certificado.
- Backend PyInstaller y shell Tauri sin bundle: código 0. Smoke del EXE congelado: diez comprobaciones aprobadas, incluyendo colección nativa real, ANLZ, planificación combinada, DeviceSQL y análisis del WAV sintético (−23,007 LUFS). Consulta filtrada: 0,047 s.
- Instalación activa: 0.4.0, colección nativa de 24.140 pistas, once comprobaciones API aprobadas. Resumen 0,219 s; planificación general 0,906 s; ayuda 0,032 s; faltantes 0,125 s; género 0,265 s; filtros + set 0,110 s. Mediciones puntuales, no garantías bajo carga musical.
- Respaldo previo: `%LOCALAPPDATA%/Rekord AI EgoBits/update-backups/before-0.4.0-20261006-185207`, con dos ejecutables y configuración anterior. Configuración conservada durante sustitución; luego sólo cambiaron `collection_mode` y `native_database` para conectar la base viva. Rekordbox continuó abierto.
- SHA-256 instalado backend: `99da1a7e84fcae9b0f31fdfc174164e88fe9dd04a942d3611bfdf3f7c007c88c`. Shell: `f3454d93e033212a72624118d80577029b3ee17637f778d3b21a82a9d13f872b`. Se agregó el aviso MIT del parser a los recursos instalados.
- No se generó Setup ni se certificaron instalación limpia, hardware DJ físico, master audible o funcionamiento universal en todos los CDJ. El registro del instalador anterior puede conservar su versión previa.

## Fuentes y licencias

- [DDJ-FLX4, Pioneer DJ](https://www.pioneerdj.com/en/product/dj-controllers/ddj-flx4/): conexión y características del equipo.
- [ITU-R BS.1770](https://www.itu.int/rec/r-rec-bs.1770/fr): medición de sonoridad; no define energía DJ 0..10.
- [DJ Link Ecosystem Analysis](https://djl-analysis.deepsymmetry.org/djl-analysis/vcdj.html) y [Beat Link](https://github.com/Deep-Symmetry/beat-link): hechos del protocolo utilizados en una implementación propia. No se copió código Java.
- [Crate Digger ANLZ schema](https://github.com/Deep-Symmetry/crate-digger/blob/main/src/main/kaitai/rekordbox_anlz.ksy): significado de frases y campos.
- [rekordbox-pdb](https://github.com/fragmede/rekordbox-pdb), MIT, commit `ee3bac2f22ca11a5ce61eea35f8cb951c246eaef`: tres módulos vendorizados tras revisión, sin ejecutar instalación. Licencia en `assets/licenses/rekordbox-pdb-MIT.txt`; hashes originales, hashes parcheados y fixture en `research/rekordbox-pdb.lock.json`.
- Pyrekordbox 0.4.4, PyAV 18.0.0 y NumPy 2.5.3 ya estaban fijados en los locks locales; no se agregaron dependencias de red.

## Continuidad para otro desarrollador

1. Leer `AGENTS.md`, `docs/DEVELOPMENT.md`, este documento y `release.json`.
2. Trabajar en una rama y PR; conservar resultados de validación y diferencias entre pruebas simuladas, host real y hardware.
3. Ejecutar `python installer/release_contract.py`, suite Python, MCP stdio, Rust y smoke del backend congelado. No afirmar build correcto sin código 0.
4. Actualizar backend con `installer/build_backend.ps1`; shell mediante Tauri `build --ci --no-bundle --target x86_64-pc-windows-msvc -- --locked`. No usar el workflow que genera Setup para una actualización directa.
5. Respaldar ejecutables/configuración, verificar jobs activos, cerrar sólo Rekord AI, reemplazar con hashes comprobados y verificar versión/API/configuración/colección. Rekordbox permanece abierto.
6. No habilitar updater online ni ampliar identidad, paths persistentes o permisos sin una tarea explícita.

### Reproducibilidad del repositorio

`.gitattributes` conserva los bytes fijados de referencias, vendor y fixture: Windows no debe cambiar sus saltos de línea. `scripts/verify_kit.py` verifica los 29 archivos de referencia, el parser parcheado y el fixture; ejecuta la suite con un perfil temporal para no depender de la colección/configuración personal del desarrollador.
