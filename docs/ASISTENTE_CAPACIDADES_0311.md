# Asistente: capacidades verificadas y ampliación 0.3.11

Fecha: 2026-10-06. El chat consulta el XML seleccionado en Configuración. La biblioteca de demostración o un XML ilegible no autorizan respuestas sobre la colección del usuario: se solicita conectar una colección real. El XML refleja una exportación; no prueba sincronización continua con Rekordbox.

## Funciones anunciadas

| Función | Implementación y evidencia | Condiciones y límites |
| --- | --- | --- |
| Buscar pistas y aplicar BPM/género/tonalidad/energía | `core/search.py`, parser y chat; pruebas `test_chat_search_filters.py` y consultas sobre el XML real | Conteo completo y resultados limitados/paginados. Energía exige valor y fuente. Los filtros no se relajan silenciosamente. |
| Listar y comparar playlists | `playlist.list`, `playlist.compare`; `test_analysis.py`, `test_ai_intents.py` y comparación real | Comparación de pertenencia por ID; no similitud sonora. |
| Planificar por BPM o energía | `core/planner.py`; `test_core.py`, `test_assistant_capabilities.py` y propuesta de 10 pistas sobre el XML real | Búsqueda determinista acotada, hasta 100 pistas en la propuesta. Más de 1.000 candidatas válidas: preselección de 1.000 posiciones representativas por BPM/energía e ID. Puede omitir una secuencia posible, no garantiza un óptimo global. Nunca relaja BPM, armonía, género o artista. |
| Asistente del planificador y orden manual | `ui/workspace.js`, `/api/draft`, `collection_tools.draft`; `test_collection_workflows.py` y orden inverso real | Orden manual explícito, hasta 100 pistas distintas. La duración suma temas enteros; no calcula solapamientos. |
| Explicar transiciones | `core/analysis.py`, `transition.explain`; `test_analysis.py` y consulta real | BPM/Camelot/energía son orientación por metadatos, no una garantía perceptual ni análisis del audio. |
| Auditar metadatos y abrir listas completas | `opportunities.py`, `library.audit`; `test_opportunities.py` y resumen real | Los conteos cubren todo el XML. Corregir en Rekordbox y volver a exportar. Estado nativo de análisis se consulta en lectura; faltantes de BPM/clave no prueban `Analysed=0`. |
| Recomendar temas compatibles y usar referencias @ | `core/recommender.py`, `core/mentions.py`; pruebas de filtros, menciones y ranking; cinco recomendaciones verificadas sobre XML real | Todas las pistas pertenecen a la colección; respetan filtros. Historial es una referencia con posible demora, no escucha del master. |
| Exportar XML y M3U8 | Adaptadores, `/api/export`; `test_core.py`, `test_xml_extended.py`, `test_collection_workflows.py`; exportaciones reales a carpeta temporal | Exportación confirmada desde la propuesta. XML conserva cues y beatgrids; M3U8 conserva orden/rutas. No sobrescribe el XML fuente ni archivos existentes. La importación y carga en decks requiere validación del DJ. |
| Crear una playlist nativa | `adapters/native_write.py`; pruebas de publicación/recuperación y `scripts/validate_native_staging.py` | Shell Windows autenticado, base/version/esquema admitidos, procesos y agentes cerrados, respaldo verificado y confirmación. En esta iteración se creó/restauró únicamente sobre una copia cifrada aislada de la base; no se escribió en la base musical real. |
| Verificar duplicados y todos los archivos | `desktop/duplicate_scan.py`, `collection_tools.verify_duplicates`; `test_duplicate_scan.py`, `test_collection_workflows.py` | Hash SHA-256 completo de archivos locales accesibles. Reporta faltantes, cambios, cancelación y archivos no verificables. Metadatos parecidos no prueban duplicado. No se ejecutó un escaneo de toda la música real durante este QA. |
| Eliminación recuperable y restauración | `duplicate_native.py`, `audio_recovery.py`, `native_write.py`; `test_duplicate_publication.py`, `test_transaction_recovery.py`, `test_native_publication.py` | Sólo idénticos seguros, consolidación de referencias, cues/ANLZ protegidos, respaldo y confirmación; bloquea con Rekordbox/agentes abiertos. Ensayos de esquema, archivos y bloqueos Windows aislados, sin borrar música real. |

La ayuda anterior omitía condiciones de energía y archivos no disponibles. Además, el planificador rechazaba más de 1.000 candidatas pese a ofrecer toda la colección; ahora admite esa fuente y explica la preselección. Se corrigió el mensaje de estado que describía la eliminación recuperable como pendiente.

## Nuevas funciones en el chat

- `resumí mi colección` / `¿cuántas pistas tengo?`: conteos completos, horas conocidas, duración faltante, BPM, géneros/artistas frecuentes, faltantes, energía con fuente y pistas fuera de playlists.
- `revisá la playlist ROOT/NOMBRE`: conserva su orden original y referencias repetidas; revisa transiciones, BPM, duración, presencia de cues/beatgrid y observaciones. No certifica la precisión musical de los cues.
- `auditá set con IDs 123,456,789`: audita ese orden, hasta 1.000 referencias existentes. Esta operación ya existía por MCP; ahora se puede usar desde el chat.
- `armá un set de 10 pistas desde toda mi colección`: produce una propuesta revisable en Preparar un set y exportable desde esa pantalla.

Las acciones `library.summary`, `playlist.inspect`, `setlist.audit` y `playlist.plan` se validan también cuando las propone el modelo. No exponen escrituras nativas, comandos, borrado ni exportación automática al LLM. Las consultas comunes anteriores responden directamente sin inferencia; las preguntas abiertas siguen usando el modelo local y pueden tardar más.

## Evidencia y reproducción

```powershell
python installer/release_contract.py
$env:PYTHONPATH='prototype'
python -m unittest discover -s prototype/tests -q
& build/venv/Scripts/python.exe scripts/verify_assistant_readonly.py
# Ensayo cifrado aislado: requiere dependencias nativas y una base detectada.
& build/venv/Scripts/python.exe scripts/validate_native_staging.py
# Después de compilar el backend; perfil temporal, sin modificar la configuración del DJ.
& build/venv/Scripts/python.exe scripts/smoke_frozen_backend.py
```

- Contrato 0.3.11 aprobado. Suite: 261 pruebas, 11 omitidas, código 0. Los omitidos se deben a dependencias opcionales del Python de la suite; la prueba cifrada utiliza el entorno de build con dependencias nativas.
- XML real seleccionado: 24.140 pistas, 22 playlists; 24.129 candidatas válidas para BPM/armonía, 1.000 preseleccionadas. Propuesta de 10 pistas aprobada; cinco recomendaciones cumplen pertenencia, BPM, género y armonía. Resumen 0,047–0,094 s; planificación 0,313–0,969 s durante compilación. Son mediciones locales, no un SLA.
- No hay energía con fuente registrada en el XML/perfil actual: planificar por energía exige cargarla; no se estima a partir del BPM ni de la tonalidad.
- Exportaciones XML/M3U8 en carpeta temporal y verificación de cues/beatgrid/orden aprobadas. Hash del XML fuente conservado.
- Copia cifrada aislada: creación, integridad `ok` y restauración byte por byte aprobadas. Rekordbox permaneció abierto. No se certifica reapertura ni carga en decks reales, audio master, hardware o Windows limpio.

La evidencia del EXE y la actualización directa de este host se registra en `DEVELOPMENT.md`. Se mantiene el último Setup 0.3.9; esta entrega 0.3.11 no genera un instalador.
