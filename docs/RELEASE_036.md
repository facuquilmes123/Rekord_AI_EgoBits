# Rekord AI 0.3.6 — corrección del instalador

## Causa y corrección

Se reprodujo exactamente el error `(at 6:59)` mostrado por el usuario. El callback AfterInstall pasaba CurrentFileName directamente a GetSHA256OfFile, aunque ese nombre puede contener constantes del instalador. La ruta no existía literalmente.

El generador ahora pasa el destino explícito y el callback ejecuta ExpandConstant antes de leerlo. Mantiene la comprobación SHA-256 y registra cada componente verificado. Inno documenta que [CurrentFileName puede contener constantes](https://jrsoftware.org/ishelp/topic_isxfunc_currentfilename.htm).

La aprobación previa de la fixture 0.3.5 fue incorrecta: el modo silencioso suprimió el diálogo interno y terminó con código 0. Su log sí contiene el mismo error. El validador ahora rechaza excepciones/Runtime error en logs y exige todos los callbacks SHA. Esta regresión se incorpora al pipeline de build antes de compilar la app.

0.3.5 se archivó en `output/closure/release-035/withdrawn/` como evidencia histórica y no se debe distribuir. 0.3.6 conserva AppId, identifier, modo por usuario, directorio y ubicaciones de configuración/respaldos. Permite instalación inicial, actualización y reparación sobre una instalación incompleta sin desinstalar previamente.

## Verificación

- Suite host: 205/205 aprobadas. Suite de build: 205 ejecutadas, 204 aprobadas y 1 omitida (SDK MCP opcional).
- Rust: 2/2 aprobadas, offline/locked.
- Fixture aislada: instalación inicial, upgrade 0.3.5 → 0.3.6, carpeta/datos conservados, bloqueo por mutex y anti-downgrade aprobados. Log sin errores internos y SHA callback ejecutado. Evidencia: `output/closure/upgrade-lab-1790955064694427000/result.json`.
- PyInstaller, Tauri e Inno completos con código 0. Metadatos Windows y contrato: 0.3.6.
- Defender local: payload y Setup sin detecciones; protección intacta, sin exclusiones.
- Smoke backend congelado: 11 controles aprobados, incluido modelo local/conversación, comparación exacta, XML Unicode nuevo/original preservado y cierre limpio. Evidencia: `output/closure/release-036/egobits-qa-b5a03691c0634889aaff9f2501005205/evidence.json`.
- Primer smoke durante compilaciones simultáneas: controles de IA no aprobados (141,23 s). Se conserva evidencia del fallo. Repetición sin compilaciones aprobada (85,53 s); esto no certifica rendimiento bajo carga.
- Extracción completa aislada: instalación inicial y actualización 0.3.5 → 0.3.6 aprobadas; 22 callbacks SHA, shell/backend/modelo verificados, carpeta y sentinelas conservados, mutex/anti-downgrade y desinstalación QA aprobados; sin excepciones internas. Evidencia: `output/closure/upgrade-lab-1790955316731400900/result.json`. Ambos paquetes QA usan binarios actuales con versiones de Setup distintas; la fixture liviana comprueba además reemplazo efectivo del backend. No se ensayó el Setup retirado sobre la instalación personal.

## Artefacto

`dist/Rekord_AI_Setup_0.3.6_x64.exe`, 3.030.705.473 bytes. SHA-256 vuelto a comprobar:

```text
a8213029451b42162e5d075567e3f3b7cc0fc27b27b8f583b2573fde59cc3852
```

Logs de build y antivirus archivados en `output/closure/release-036/`. Ejecutar este Setup para actualizar/reparar; cerrar Rekord AI desde su bandeja antes de comenzar, sin desinstalar ni borrar datos.

## Límites

El ensayo usa AppId, mutex y accesos directos de QA. No modifica la instalación personal ni colección/música real, no cierra Rekordbox. El modo full-payload usa shell/backend/DLL/modelo reales y verifica extracción/hash, pero omite instalación del prerrequisito WebView2 y ejecución automática de la app. No equivale a una VM limpia sin red. Los binarios no están firmados; Defender local sin detecciones no garantiza reputación en otros equipos.
