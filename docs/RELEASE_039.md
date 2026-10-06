# Rekord AI 0.3.9 — estado de verificación

Fecha: 2026-10-02. Setup 0.3.9 generado y verificado; instalación inicial y actualización completas aisladas aprobadas. La instalación real del DJ no se modificó.

## Correcciones

- El aviso de duplicados abre el cierre de Rekordbox desde la app. Primero solicita cierre normal; si quedan procesos, ofrece finalización con confirmación explícita. Revalida PID, hora de creación, ejecutable y propietario. No se finalizaron procesos reales durante QA.
- La detección conserva `7.2.19.0342`; el nombre de carpeta ya no sustituye una versión válida del registro. La escritura conserva el guard de esquema 6/7.
- Recuperación de WAL con copia verificada de DB/WAL/SHM/XML presentes, checkpoint SQLCipher exclusivo y confirmación HMAC nativa. No se borran manualmente las transacciones. Falla de precondiciones conserva datos nuevos; fallo posterior usa rollback o deja recuperación visible.
- Respaldos de recuperación y restauración interrumpida visibles y restaurables después de reiniciar. Se bloquean escrituras ante estados incompletos. Un rollback journal requiere revisión específica; no se trata como WAL.
- Consulta sobre pistas pendientes de análisis: lectura nativa `Analysed=0`, paginación y acciones; el XML se etiqueta como evidencia incompleta y no certifica análisis nativo.
- Modelo local automático para conversación, cola limitada, timeout, reinicio de su propio sidecar si falla y respuesta alternativa con datos comprobados. Guardas contra contradicciones observadas e instrucciones externas; no certifican universalmente toda respuesta del modelo.
- Configuración en cinco pestañas, avisos con acciones, oportunidades que abren sus detalles, mejor feedback de cancelación y recuperación.

## Evidencia

- `output/closure/release-039/verify-kit-final.log`: **247 tests, 246 aprobados, 1 omitido**, exit 0; 29 archivos upstream verificados. Omisión: SDK MCP opcional ausente. Las pruebas SQLCipher y HANDLE sí se ejecutaron.
- Suite específica de recuperación: **5/5**, incluida restauración tras reinicio y guard de escritura después del checkpoint. El log `transaction-tests.log` corresponde a una corrida previa con un fallo ya corregido; no representa el estado final.
- `installer/release_contract.py`: contrato 0.3.9 válido.
- `output/closure/release-039/source-manifest.json`: SHA-256 del snapshot de aplicación, tests y scripts. No existe checkout Git; no se afirma commit/autoría verificable.
- `analysis-source.json`: consulta real de sólo lectura, cinco pendientes, 8.281 s, sin LLM ni cambios en XML fuente.
- `conversation-source.json`: conversación local real y fallback verificado. Un caso tardó 203.11 s; no se promete latencia instantánea en CPU.
- `ui-qa.json`: cinco pestañas, teclado y guardado de preferencias verificados previamente en copia aislada. Los controles nuevos de recuperación también pasaron en Playwright CLI: `ui-recovery-qa.json`. Cancelación, error, botón reactivado, listado conjunto y restauración cancelada comprobados en fixture; confirmación nativa simulada, sin escribir datos reales.

## Instalador y límites de certificación

El usuario autorizó Playwright después de los timeouts de CUA. QA visual completado en navegador temporal y fixture aislada; sólo el HTTP 400 deliberado de la prueba apareció en consola. La PC funciona normalmente según el usuario.

Compilación final de backend y shell: exit 0. Smoke final del EXE: todos los checks aprobados, conversación local real 84 s, salida limpia sin huérfanos. La primera corrida falló por comprobar el LLM antes de su activación; se corrigió el helper, no la aplicación. Tauri sólo normalizó CRLF a LF en Cargo.toml; cambios posteriores al freeze limitados a helpers QA, snapshot original conservado. Suite obligatoria de prebuild: 247 tests en 57.721 s, exit 0, 1 omitido. Setup: 3.030.771.690 bytes; SHA-256 `c242512397df3d4b7ea3f7185722e021df17f8711d3c01553952cfe2045fe7b5`. ISCC y pipeline: exit 0. Defender del payload y Setup: sin amenazas en este host. 48 módulos congelados y todos los archivos UI comparados con fuentes. Snapshot final: 146 archivos, 0 diferencias; incluye salidas generadas del empaquetado. Instalación inicial, actualización 0.3.8 → 0.3.9, directorio reutilizado, configuración/respaldos sentinel conservados, hashes completos, 22 callbacks de runtime, bloqueo con app abierta, rechazo de downgrade y limpieza QA aprobados: `installer-full-qa.json`, proceso exit 0. La fixture usa AppId separado y la lógica Inno de producción; ambas versiones empaquetan los binarios actuales. No certifica migraciones de datos históricos. WebView ya estaba instalado, su primera instalación no se ensayó. No se certifica Windows limpio ni firma comercial.

La eliminación automática sigue limitada a identidad SHA-256 completa y ausencia de conflictos nativos. El porcentaje selecciona candidatos de revisión; no autoriza borrar pistas diferentes. La música retirada por ese flujo se conserva en recuperación. El backup transaccional contiene la base y sidecars, no un respaldo de todos los archivos musicales.

Las recomendaciones por historial no certifican el master audible. No se activó captura de audio ni actualización online.

El smoke empleó únicamente servicios locales y activos empaquetados, pero la red del host no fue deshabilitada. No se certifica una prueba con Windows físicamente desconectado. El modo online de actualización sigue desactivado.

## Uso de las correcciones

1. Ejecutar `dist/Rekord_AI_Setup_0.3.9_x64.exe` sobre la instalación anterior, después de salir de Rekord AI desde la bandeja. No requiere PowerShell ni desinstalar.
2. Ante el aviso de duplicados, usar su acción de cierre: cierre normal primero; si persisten agentes, finalización con confirmación expresa.
3. Si hay transacciones pendientes, Configuración → Base y procesos → Respaldar y recuperar transacciones. Preparar copia, revisar y confirmar.
4. Volver a Mi colección y preparar la propuesta de duplicados. El porcentaje no sustituye la verificación SHA ni resuelve conflictos de cues/metadata. La confirmación muestra exactamente qué se retirará y preserva recuperación.

Ejecución director `20261002-rekord-039`: recuperación transaccional especializada y revisión independiente. Código/UX aprobado; gates de empaquetado completos con las limitaciones explícitas anteriores. No se realizaron cambios en configuración global ni memoria, ni se cerró la sesión real del DJ.

Revisión independiente final: **approve**, confianza 0,98; sin nuevos bloqueadores dentro del alcance y límites declarados.
