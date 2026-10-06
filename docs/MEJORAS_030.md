# Rekord AI 0.3.0 — cambios y verificación

Fecha: 2026-10-01. El nombre visible sigue la última indicación del usuario: Rekord AI. El logo y la bandeja nativa se conservan.

## Implementado

- Configuración destacada con pulso cuando falta colección propia; respeta movimiento reducido.
- Explorador nativo de Windows para XML, energía JSON y destino de exportación. Unicode, sin dependencia adicional. Un selector simultáneo; cancelar no modifica ajustes.
- Avisos propios con marca, tilde, animación y cierre; se retiraron alert/prompt del navegador.
- Disponibilidad por función y motivos concretos: biblioteca, escritura y telemetría se evalúan por separado.
- KPIs de pistas, playlists, artistas, horas, energía y géneros faltantes; gráficos de género, BPM y tonalidad; acciones sugeridas basadas en metadatos.
- Sets desde playlists, colección o selección manual. Asistente de cuatro pasos, filtro de género, búsqueda paginada, agregado de pistas, arrastre desde la lista, orden manual y revisión de transiciones.
- Exportación exclusiva XML y M3U8 UTF-8. XML conserva cues/beatgrids; M3U8 conserva rutas locales y orden, sin cues/beatgrids. No se sobrescriben destinos ni XML fuente.
- Duplicados: título/artista son candidatos; SHA-256 verifica archivos idénticos. Distingue referencias a un mismo archivo y diferencias de cues. Archivos faltantes, cambios y límites de recursos producen incertidumbre, nunca autorización para borrar.
- Recomendaciones desde una pista elegida de la colección con los filtros guardados; selección de referencia sin escribir IDs.
- Chat responde de forma explícita sobre escucha en tiempo real, capacidades, duplicados y formatos sin inventar capacidades del dispositivo.

## Pendientes reales

1. **Eliminación de duplicados de la colección real y Windows:** bloqueada. El XML es un snapshot; falta un adaptador certificado para retirar referencias de la base real, respaldo verificable y revisión. El endpoint rechaza la acción; no elimina archivos sueltos. Hashes distintos tampoco prueban que sean canciones distintas. El detector no identifica todas las versiones con otra codificación ni nombres diferentes.
2. **Sugerencias push automáticas mientras suena música:** falta un proveedor real de pista audible. El watcher sólo detecta Rekordbox abierto. Guardar filtros o activar push no conecta telemetría. La referencia manual sí permite recomendar desde la biblioteca.
3. **Chat general:** las tareas musicales mantienen intents validados y fallback determinista. Las respuestas informativas incorporadas no representan un chat general con memoria conversacional.
4. **Colecciones grandes:** el planificador conserva el límite de 1000 pistas elegibles; usar género/playlists/selección para reducir el pool. La selección manual admite hasta 100 pistas. No se certifica compatibilidad universal con toda versión de Rekordbox.
5. Instalador sin firma comercial; instalación limpia Windows 10/11 e importación real en Rekordbox requieren pruebas separadas. No se reinstaló sobre la app del usuario durante esta revisión.

## Evidencia local

- `python scripts/verify_kit.py`: **103 pruebas, sin fallos**, código 0; 29 archivos upstream verificados. Log: `output/closure/verify-030-final.log`.
- JavaScript: `node --check` en app.js y workspace.js.
- Pruebas nuevas: UTF-8/Unicode y orden M3U8, no sobrescritura, revisión obsoleta, rutas inválidas, mismos nombres/diferentes bytes, bytes idénticos/cues distintos, referencias al mismo archivo, archivos faltantes, selección y KPIs, respuesta de escucha.
- QA con seis pistas de ejemplo y ajustes temporales: asistente genera cuatro pistas 124–128 BPM; gráficos y recomendaciones; exportación desde la UI mediante Guardar de Windows a `output/closure/Ensayo Unicode selección.m3u8`, aviso propio con tilde y marca. Archivo inspeccionado como UTF-8; selección Abrir de Windows devuelve el XML de ensayo.
- Captura: `output/playwright/rekord-ai-030.png`. No se usó la biblioteca real para escrituras ni eliminación.
- QA adicional: selección manual de dos pistas produce orden y transiciones revisables; el chat responde a la pregunta de escucha con el límite real del proveedor. Consola sin errores/advertencias. Arrastre implementado, sin prueba UI automatizada de drag.
- Backend EXE final iniciado aisladamente en puerto 8884: nombre Rekord AI, versión 0.3.0, seis pistas y distribución de géneros correctos. Evidencia: `output/closure/frozen-030-smoke.json`. No equivale a instalación del Setup.
- Build final: `output/closure/build-030-final.log`, `tauri-single-build.log`, `pyinstaller.log`, `inno-build.log`. El resultado final, hashes y límite de validación de instalación están en `output/closure/single-installer.json`.

## Fuentes oficiales

- Windows OPENFILENAMEW: https://learn.microsoft.com/en-us/windows/win32/api/commdlg/ns-commdlg-openfilenamew
- Windows GetOpenFileNameW: https://learn.microsoft.com/en-us/windows/win32/api/commdlg/nf-commdlg-getopenfilenamew
- Manual Rekordbox 7 (importación M3U8): https://cdn.rekordbox.com/files/20260409151936/rekordbox7.214_manual_EN.pdf

El manual acredita el formato soportado; no equivale a una prueba de importación real del archivo generado.

## Compilación local

`powershell -NoProfile -File installer/build_single_installer.ps1`

Requiere el entorno de desarrollo fijado ya preparado. Verifica SHA-256 de modelo, runtime, upstream y WebView2, congela Python, compila Tauri y genera un único instalador Inno offline. Si ya existe el instalador, conservarlo en `dist/archive/` antes de compilar. El usuario final abre el EXE y sigue el asistente; no usa PowerShell.
