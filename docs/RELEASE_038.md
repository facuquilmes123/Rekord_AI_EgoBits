# 0.3.8 · Duplicados en lote y recomendaciones sin captura

## Entrega

`dist/Rekord_AI_Setup_0.3.8_x64.exe`, 3.030.735.850 bytes. Un instalador gráfico offline para instalación inicial y actualización; mantiene AppId, identifier, mutex, configuración y respaldos. No se activa el updater online.

SHA-256: `e35fe3047d2695237866bc759ae6765c9321d965d40f94b9a42a2af175ed0598`.

## Cambios

- Mi colección: selector de umbral con **50% hacia arriba** y botón **Eliminar duplicados desde este porcentaje…**. Respaldo automático, consolidación de registros seguros, conservación de playlists/historial, retirada recuperable de archivos y restauración conjunta. Ver `DUPLICADOS_SEGUROS_038.md` para protecciones y límites.
- Las referencias al mismo archivo conservan su audio. Metadatos parecidos no bastan para eliminar; análisis ANLZ, cues o vínculos no certificados quedan protegidos.
- XML consolidado nuevo; nunca se sobrescribe el XML fuente. La vista carga esa colección y conserva preferencias de energía.
- Recomendaciones sin captura con activación única, última referencia registrada en historial y filtros BPM/género/tonalidad por defecto en preferencias nuevas. También se configuran tonalidad exacta/compatible, duración, energía verificada y artista. No se afirma identificar el master audible.
- Tray: una recomendación no disponible abre Configuración con explicación. Se corrigieron símbolos de avisos y disponibilidad.
- Empaquetado: verifica equivalencia de 46 módulos Python congelados y todos los recursos de la interfaz respecto de la fuente; rechaza binarios o UI desactualizados.

## Verificación

- Suite del entorno de build: **226 pruebas, 225 aprobadas y 1 omitida** por SDK MCP opcional. Incluye 12 pruebas específicas de duplicados y recuperación en Windows/SQLCipher. Upstream y activos offline verificados por hash.
- Tauri 0.3.8 y backend EXE: builds completos código 0. El primer intento de empaquetado se rechazó correctamente por fuente posterior al congelado; se recompiló el backend y la pipeline final terminó código 0.
- Backend congelado: interfaz nueva, rechazo de eliminación sin aprobación nativa y recomendaciones sobre copia del XML real aprobados. Sin capturar audio, modificar configuración personal ni cerrar Rekordbox. Referencia Gata Only: 3 pistas locales con 100 BPM, 12A y reggaeton.
- Defender del host: payload y Setup sin amenazas. **Sin firma Authenticode**; no es certificación universal de antivirus.
- Regresión ligera de Inno: instalación inicial, actualización 0.3.7→0.3.8, conservación de sentinelas y bloqueo de downgrade/mutex aprobados bajo identidad QA aislada.
- Ensayo **full-payload aislado aprobado**: instalación inicial y actualización, 22 callbacks SHA, shell/backend/modelo/runtime extraídos e íntegros, sentinelas conservados, sin errores internos, downgrade/mutex bloqueados y desinstalación/registro QA limpiados. Evidencia: `output/closure/upgrade-lab-1790967660424881900/result.json`. Usa identidad QA y mismo backend actual en ambas versiones de fixture; la fixture ligera verifica reemplazo de backend. No ejecuta el prerrequisito WebView2 ni modifica la instalación personal.

Evidencia: `output/closure/release-038/installer.json`, `final-pipeline.log`, `final-source-suite.log`, `metadata-qa-b3fa2dde38674b3bb7966e22712c2a88/evidence.json` y `output/closure/upgrade-lab-1790967516798867200/result.json`.

## Límites

No se eliminó música ni se modificó la base real. Consolidación y recuperación se ensayaron con una base cifrada y archivos de prueba; no certifican reapertura de la colección personal en Rekordbox. No se certifican el master audible, el arrastre a deck real ni una VM limpia. La recuperación retiene archivos y no libera su espacio; ANLZ/cues nativos diferentes e identidad entre formatos requieren una ampliación independiente.
