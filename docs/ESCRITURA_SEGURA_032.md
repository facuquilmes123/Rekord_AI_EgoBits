# Escritura segura y restauración — Rekord AI 0.3.2

Fecha: 2026-10-01. Implementación local. La colección real del DJ no fue modificada.

## Flujo disponible

1. Selección manual de 1–100 pistas y nombre de playlist desde Preparar un set.
2. La UI pide cerrar Rekordbox y sus agentes de sincronización. Abierto o estado desconocido bloquean el backend; el botón aparece grisado.
3. Confirmación de respaldo obligatorio: copia cifrada de master.db y masterPlaylists6.xml, SHA-256 e integridad SQLCipher. El XML del DJ y el audio original permanecen intactos.
4. La playlist se prepara en una copia, usando métodos nativos pyrekordbox, USN y archivo auxiliar; correspondencia por ruta única, orden validado y tablas de contenido/cues/análisis sin cambios lógicos.
5. Revisión y segunda confirmación para aplicar. Ticket de uso único, diez minutos; XML y ambos archivos nativos deben conservar la revisión. No se aceptan destinos arbitrarios por HTTP.
6. Publicación con dos handles Windows CreateFileW share=0 mantenidos hasta completar y verificar ambos archivos. Escritura y FlushFileBuffers a través de esos handles. Si Rekordbox se inicia durante el cambio, se cancela y recupera bajo los mismos bloqueos.
7. Registro persistente de operación, backups conservados y rollback automático verificado ante falla. Una escritura interrumpida bloquea nuevas publicaciones y exige recuperación.
8. Configuración → Respaldos y recuperación: listado persistente, validación SHA-256, restauración con revisión y confirmación. Se crea automáticamente un respaldo del estado actual antes de restaurar. Restaurar deshace cambios posteriores del conjunto completo de base + playlists; no incluye archivos de audio.

## Evidencia

- `output/closure/verify-native-restore-final.log`: 119 pruebas ejecutadas, 118 aprobadas, una omitida (extra MCP ausente); 29 archivos upstream con hash verificado. Código 0.
- Nueve pruebas nuevas de publicación Windows: exclusión real de lectura concurrente, truncamiento correcto, publicación/restauración, respaldo anterior a restaurar, tickets de un uso, revisiones obsoletas, alteración de backup/propuesta, falla parcial con rollback, inicio concurrente de proceso y recuperación persistente.
- `output/closure/native-lab-1790873850487098400/result.json`: base cifrada aislada derivada de lectura real; playlist de tres pistas aplicada a esa copia y restaurada byte por byte. Nunca se publicó sobre la base del DJ.
- Lectura real: Rekordbox 7.2.19, 23.683 pistas, 21 playlists, quick_check OK. Rekordbox y agentes seguían abiertos durante QA. Endpoint de preparación rechazó la escritura con instrucción de cierre.
- Interfaz sin errores de JavaScript observados, diálogo propio y sección de respaldos. Captura `output/playwright/backup-confirmation-032.png`.
- Dependencias nativas/audio fijadas con 13 wheels SHA-256; pip offline y recursos del instalador incluidos. Véase `docs/NATIVE_LIVE_PILOT.md` para procedencia, licencias y piloto de audio.

## Límites y validación pendiente

- Soporte de escritura limitado a creación de playlists y restauración de nuestros respaldos con esquema 6/7 validado en staging. No supone compatibilidad universal ni certificación de AlphaTheta. Falta la prueba con Rekordbox cerrado, aplicación revisada y comprobación al reabrir la versión instalada del DJ.
- Dos archivos no forman una transacción atómica ante corte eléctrico. Los locks evitan acceso simultáneo; backup duradero y registro permiten recuperación, pero no pueden garantizar éxito de disco o sistema operativo fallando. Tras interrupción, mantener Rekordbox cerrado y restaurar desde la app antes de abrirlo.
- No eliminar duplicados ni archivos de música con este flujo. Sigue pendiente un protocolo específico de referencias, cues y recuperación de audio.
- Recomendaciones manuales e historial nuevo disponibles; historial no prueba master audible. El piloto WASAPI continúa sin validación del ruteo físico, mezclas/pitch y certeza audible. No habilita Toast ni presenta una similitud como probabilidad calibrada.
- App instalada del usuario conservada. Nuevo Setup generado para instalar manualmente cuando no esté usando Rekordbox.

## Fuentes

- Exclusión Windows: https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
- Métodos de playlist/USN: https://pyrekordbox.readthedocs.io/en/latest/tutorial/db6.html
- Captura loopback y límites: https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording

## Artefacto de entrega

- `dist/Rekord_AI_Setup_0.3.2_x64.exe`: 3.030.577.868 bytes, instalador único offline. Build completo código 0 (`output/closure/build-032-native-restore.log`); Rust release 0.3.2 finalizado.
- SHA-256: `eb000945a4649e018c272ab0598038c4c500c3f8629126991c879025f5c720db`.
- Backend EXE smoke: `output/closure/native032-frozen-smoke.json`: 23.683 pistas y 22 playlists en la lectura final (Rekordbox permanece abierto y puede actualizar su propia colección). Preparación rechazada por proceso abierto; ningún respaldo real ni escritura creada por nuestra prueba.
- Captura final del EXE servido en loopback: `output/playwright/native-backups-032.png`; confirma botón grisado, instrucción de cierre y sección de respaldos. Servidores de QA detenidos.
- Instalación nueva no ejecutada sobre el usuario; Authenticode aún sin firma. Instalador anterior y aplicación instalada conservados.
