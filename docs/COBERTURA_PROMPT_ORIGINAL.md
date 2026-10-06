# Cobertura del pedido original

## Estado vigente — 2026-10-02

La tabla histórica inferior corresponde al 23/09 y no representa la versión actual. Ver [auditoría consolidada](AUDITORIA_DIRECTOR_20261002.md) y [recomendaciones/popup](RECOMENDACIONES_POPUP_20261002.md).

| Área | Estado actual | Validación pendiente |
|---|---|---|
| Windows e instalación | Shell Tauri, tray, iconos y Setup Inno único; identidad estable y upgrades | Windows 10/11 limpios, firma y nuevo Setup con fuente posterior a 0.3.4 |
| Chat y colección | Consultas, filtros, @, múltiples búsquedas, contexto y LLM local; búsqueda MCP comparte filtros | Corpus real amplio y calidad semántica de orientación del modelo |
| Escritura nativa | Playlist en copia, respaldo SHA, revisión, confirmación nativa firmada, exclusión Windows, rollback/restauración con esquema compatible | Ensayo humano de publicación/reapertura en Rekordbox; borrado conjunto de audio/base aún bloqueado |
| Recomendaciones | Ranking por BPM, Camelot, género y energía registrada; popup de historial provisional y piloto WASAPI optativo | Proveedor master fiable, ASIO y mezcla real; arrastre hacia deck real |
| Offline | Pesos/runtime locales, hashes, loopback, IA autenticada con PID/puerto verificado | Instalador completo sin red y sin WebView2 previo en VM limpia |

## Evidencia histórica del 23/09

Fecha: 2026-09-23. Evaluación por evidencia, sin porcentaje global artificial.

| Requisito | Estado comprobable | Falta para completarlo |
|---|---|---|
| Investigación MCP y código público | Inventario previo más actualización de fuentes primarias, licencias y límites | Investigación continua; no se puede garantizar inventario universal |
| Asistente Windows con chat | UI web y API local implementadas y probadas | Ejecutable Tauri e instalación limpia |
| Pedidos en español | Parser determinista + modelo local con respuesta estructurada validada | Corpus amplio de consultas reales y aclaraciones conversacionales |
| Unir playlists por BPM/energía | Planificador, preview, revisión y XML nuevo | Importación humana en Rekordbox objetivo; energía requiere fuente externa explícita |
| Diccionario de consultas | `DICCIONARIO_CONSULTAS.md` | Ampliar sólo junto con implementación/tests |
| Cero APIs pagas y operación offline | Binarios/pesos locales verificados, loopback autenticado, sin descargas en runtime | Smoke de instalador sin red |
| Inicio con Rekordbox | Scripts de watcher/registro y detección de proceso implementados | Prueba tras instalación; no se activó globalmente |
| Icono junto al reloj y controles | Código Tauri con Mostrar/Ocultar, Silencio, push, Salir | Compilar y probar en Windows |
| Sugerencias BPM/género/armonía/energía | Recomendador manual compartido con ruta live; preferencias guardadas | Fuente real y fiable de pista audible |
| Lectura completa de colección | XML propio soportado | SQLCipher/live no integrado; lector auxiliar sólo para snapshots SQLite descifrados |
| Opciones deshabilitadas según estado | API de capacidades, UI con motivo, fail-closed | Certificación de adaptador antes de cualquier escritura nativa |
| ZIP de traspaso | Script y kit fuente con hashes | ZIP de instalador sólo después del build |

## Correcciones de esta revisión

1. Biblioteca real ya no hereda energías demo por IDs coincidentes ni cae silenciosamente a demo ante ruta inválida.
2. Peticiones desconocidas ya no generan planes ni eligen dos playlists arbitrariamente. Parámetros del modelo se validan y no incluyen escrituras.
3. Chat ejecuta búsqueda, comparación, auditoría, duplicados, descripción, transición y recomendación; muestra la propuesta en el planificador.
4. MCP usa el estado real del watcher, registra 13 herramientas y tiene prueba de protocolo stdio, no sólo llamadas directas de Python.
5. Recomendador no inventa BPM 120 ante ausencia de dato. Energía/género ausentes se excluyen cuando el filtro los necesita.
6. Preferencias y biblioteca seleccionada son persistentes; carga inválida conserva el estado anterior.
7. Exportar una propuesta antigua o un XML cuyo origen cambió queda bloqueado. Se preservan cues/grids y caracteres Unicode.
8. El lector auxiliar SQLite usa joins sobre columnas reales; SQLCipher se declara no soportado en este adaptador.
9. Se corrigieron importaciones circulares ocultas por el orden previo de tests.
10. Backend Tauri obtiene el puerto efectivamente asignado por Python; se corrigieron id de bandeja, CSP de IPC y persistencia de avisos.
11. Se incorporaron activos reales; el GGUF de más de 2 GB se separó del MSI/NSIS.

## Prioridad siguiente

Primero toolchain y build nativo, luego instalación offline y prueba Bridge. La telemetría FLX4 sigue siendo investigación independiente: no confundir un deck cargado, historial o proceso abierto con audio audible. No abrir ni modificar `master.db` del DJ para suplir esa evidencia.
