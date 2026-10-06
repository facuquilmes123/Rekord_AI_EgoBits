# Plan de implementación: colección e inteligencia DJ

Solicitud: implementar las funciones del adjunto del 2026-10-06, actualizando la app instalada sin Setup. Equipo del usuario: DDJ-FLX4. Se autorizaron simulaciones basadas en fuentes públicas; ninguna simulación certifica hardware real.

## Diseño y criterios de aceptación

Un registro de herramientas validadas alimentará MCP, HTTP y el asistente. Los adaptadores de lectura de base viva, XML, DeviceSQL y telemetría conservan su procedencia y sus IDs; no se mezclan IDs entre colecciones. Las escrituras requieren propuesta, respaldo y confirmación nativa. El modelo no recibe SQL, shell ni rutas arbitrarias de escritura.

1. **Colección viva:** conexión SQLCipher de lectura, snapshots coherentes, refresco, pistas/playlists, rating, conteo y fecha; consultas de joyas olvidadas, estrellas, MyTags y archivos ausentes. Prueba de cambios visibles y base original intacta.
2. **Estructura musical:** cues/loops, beatgrid y frases cuando existan; auditoría pre-show y propuesta temporal de transición con evidencia. Datos ausentes son desconocidos, no inventados ni certificados como correctos.
3. **Herramientas y asistente:** catálogo compartido y ciclo acotado de lectura/planificación de varios pasos; argumentos tipados, cancelación/límites y traza visible. Rutas directas siguen rápidas. Sin mutaciones autónomas.
4. **Audio y armonía:** análisis offline cancelable con progreso, LUFS y características acústicas; índice de energía estimado con fórmula/procedencia, persistencia y uso en planificación. Key Shift optativo ±1/2 semitonos, tonalidad resultante y costo explícitos.
5. **USB DeviceSQL:** detectar/leer/auditar export.pdb, verificar archivos/análisis/referencias, preparar y aplicar playlists sobre pistas presentes con backup/validación/rollback. Exportar pistas nuevas exige incluir audio y análisis compatibles, no sólo una fila de playlist. Diferenciar exportaciones DeviceSQL y Device Library Plus.
6. **Pro DJ Link:** recibir/interpretar estado de equipos compatibles, decks, IDs, tempo/posición cuando disponibles y On-Air; frescura, origen y ambigüedad explícitos. FLX4 no se presenta como dispositivo Pro DJ Link. Pruebas con paquetes documentados y datos malformados.
7. **Integración y entrega:** controles y resultados utilizables en UI, MCP y chat; regresión, fixtures realistas, builds, smoke y actualización instalada; documentación y PR privado. Sin cerrar Rekordbox, borrar música ni modificar automáticamente USB/base real.

## Correcciones de la propuesta

- El porcentaje «25–30 % del potencial» no tiene una métrica verificable.
- LUFS mide sonoridad; un índice de energía DJ combina características mediante una heurística documentada, no una verdad científica de 0 a 10.
- Un semitono cambia 7 posiciones Camelot módulo 12, pero 10A no es vecino armónico de 8A. Las sugerencias se calculan y prueban sobre notas, sin copiar ese ejemplo incorrecto.
- On-Air depende de mixer, cableado y ajustes; no demuestra por sí mismo sonido audible ni latencia universal <10 ms.
- `mode=ro` y `query_only` protegen la base viva; `immutable` no se usa sobre una base que Rekordbox sigue modificando.

## Seguimiento

Bloques 1–6 implementados con pruebas locales/simuladas y controles de UI. Bloque 7: versión 0.4.0 instalada y verificada; publicación privada registrada mediante PR. Evidencia y límites detallados en `COLECCION_INTELIGENTE_040.md`; los límites de hardware y del modelo local permanecen explícitos.
