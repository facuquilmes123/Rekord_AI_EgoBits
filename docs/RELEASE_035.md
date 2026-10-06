# Rekord AI 0.3.5 — 2026-10-02

> **RETIRADO por fallo de instalación:** se reprodujo el error interno `(at 6:59)` al verificar una ruta con constantes sin expandir. La fixture anterior también registró este error, aunque devolvió código 0; su aprobación fue incorrecta. No usar este Setup. La corrección y el ensayo de extracción se documentan en `RELEASE_036.md`. Los resultados inferiores se conservan como evidencia histórica.

## Entrega

Setup único Inno x64, con instalación inicial y actualización sobre versiones anteriores, sin desinstalar previamente. Identidad estable, modo por usuario y carpetas persistentes conservados. Modelo GGUF, llama.cpp y WebView2 incluidos; el usuario no necesita PowerShell ni herramientas de desarrollo.

Se reconstruyeron backend Python y shell Tauri. La versión coincide en release.json, Python, HTTP/XML, Cargo/config/lock, metadatos Windows y Setup. Updater web continúa deshabilitado.

## Mejoras incluidas

- Todas las correcciones de [la auditoría director](AUDITORIA_DIRECTOR_20261002.md): confirmación nativa firmada de escritura/restauración, esquema/espacio/backups, identidad del sidecar y aislamiento de secretos, historial, filtros/popup, preferencias independientes, arrastre y hashes del runtime instalado.
- Búsquedas del chat por género/BPM/Camelot/energía, @, consultas múltiples y conversación local con contexto; clasificación de duplicados y regla de revisión.
- Preguntas “hay canciones en común”, “qué pistas comparten” y “canciones compartidas” comparan playlists completas de forma determinista; no dependen de muestras ni de la elección de herramienta del modelo.
- Ayuda de audio distingue popup provisional optativo de Toast certificado.
- QA del ejecutable carga explícitamente una colección sintética en una carpeta temporal, verifica versión y archivos UI congelados, separa comparación exacta de conversación real e inspecciona exportación/cierre/preservación.

## Verificación

- Suite host: **205/205 aprobadas**; 29 archivos upstream íntegros. Entorno de build: 205 ejecutadas, 204 aprobadas y 1 omitida por SDK MCP opcional; el MCP stdio sí se prueba en el host.
- Rust: 2 pruebas aprobadas offline/locked (HMAC RFC4231 y payload Windows Unicode).
- Tauri release optimizado y PyInstaller: compilación completa con código 0.
- Inno fixture aislada: instalación inicial, actualización **0.3.4 → 0.3.5**, conservación de datos/carpeta, bloqueo por mutex y rechazo de downgrade aprobados. AppId QA distinto y limpieza QA aprobada. `output/closure/upgrade-lab-1790953416719763100/result.json`.
- Defender: análisis local obligatorio de payload y Setup, sin exclusiones ni cambios de protección. Resultado y hashes finales en `output/closure/single-installer.json`.
- El primer smoke detectó que una respuesta conversacional no equivalía a comparación exacta: se corrigió el parser y se reconstruyó el paquete. Primer candidato conservado en `output/closure/release-035/first-build/`; no es el artefacto de entrega.

**Smoke final aprobado**, código 0, sobre backend EXE reconstruido: colección/revisión/versiones, interfaz congelada de confirmación/popup, comparación exacta, conversación con IA real, XML nuevo, original intacto, live no certificado bloqueado y cierre limpio. Evidencia `output/closure/release-035/egobits-qa-c5299bd4918b44a68d72dbd54ae65508/evidence.json`. El hash del backend probado coincide con el incluido en el Setup.

**Artefacto final:** `dist/Rekord_AI_Setup_0.3.5_x64.exe`, 3.030.703.468 bytes (~3,03 GB). Inno código 0 y Defender sin detecciones en payload/Setup. SHA-256 comprobado nuevamente:

```text
107138c389c5277119a035ca154d2c4137a5c46b660a0ffd569122158e10efd9
```

Archivo SHA junto al EXE. Reporte de build `output/closure/release-035/final-installer.json`; logs de esta corrida en la misma carpeta. El Setup de 0.3.4 se conservó.

## Límites

No se instaló ni actualizó la aplicación personal del DJ, no se cerró Rekordbox y no se modificaron colección ni música reales. El ensayo de upgrade es una fixture, no el instalador completo en Windows limpio. Red del host habilitada: no certifica VM sin red ni ausencia previa de WebView2.

El master audible sigue sin certificar; historial/piloto son referencias provisionales. Arrastre al deck real, publicación/reapertura en Rekordbox y borrado recuperable de audio/base pendientes. El Setup no tiene firma Authenticode; el análisis local de Defender no garantiza reputación en otros equipos.

Para actualizar, cerrar **Rekord AI** antes de ejecutar el Setup. El instalador conserva la configuración y los respaldos y no requiere cerrar la sesión DJ de Rekordbox por sí mismo.
