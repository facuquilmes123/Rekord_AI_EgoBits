# Auditoría integral y correcciones — 2026-10-02

## Resultado y alcance

Ejecución `$director`: `rekord-audit-20261002-7f3c0244`. Se revisaron arquitectura, colección/backups, chat/MCP, IA local, recomendaciones, shell Windows y empaquetado. El principal integró los cambios; tres especialistas auditaron en sólo lectura y un cuarto realizó revisión independiente.

Esto es una auditoría de la fuente posterior a 0.3.4. No se generó ni instaló un Setup nuevo. No se publicó en la colección original, no se borró música ni se cerró la sesión de Rekordbox. Las pruebas de escritura y de instalación usan entornos aislados.

| Participante | Modelo del rol | Responsabilidad |
|---|---|---|
| security-reviewer | Sol, alto | Integridad, escritura, recuperación, autenticación |
| windows-engineer | Terra, alto | Tray, popup, seguimiento y arrastre |
| researcher | Terra, medio | Chat/MCP, sidecar, contrato de release y dependencias |
| reviewer | Sol, alto | Gate independiente de seguridad y consistencia |

La coordinación conserva el modelo de la sesión. Registro local en `output/director/runs/rekord-audit-20261002-7f3c0244.jsonl`; no se modificó memoria global.

## Correcciones aplicadas

| Hallazgo | Corrección |
|---|---|
| Versiones 16/17 podían pasar por coincidencia de texto “6.”/“7.” | Validación anclada de versiones 6/7. Datos desconocidos o varias versiones incompatibles siguen bloqueados; no se inventa asociación entre instalación y base |
| Confirmación de escritura sólo en HTML | Diálogo nativo Windows con opción inicial No; HMAC SHA-256 separado del token HTTP, vinculado a operación/token/digest canónico. Clave sólo en shell/backend, nunca en `backend_info`. Backend rechaza confirmaciones inexistentes, modificadas o de otra operación; tickets se consumen al aplicar |
| APIs nativas disponibles en modo servidor sin token | Preparación, aplicación, restauración y cierre bloqueados sin sesión autenticada del shell |
| Restaurar un respaldo de otro esquema | Firma de esquema SQLite + user_version, guardada en recibo y comprobada antes de restaurar/publicar. Respaldos antiguos sólo admitidos si su esquema real coincide |
| Espacio insuficiente para copias/recuperación | Preflight de espacio en origen y destino con margen. Journal temprano; etapas aplicadas se eliminan conservando respaldos verificados |
| Delta de playlists demasiado amplio | Exige exactamente una nueva playlist y el número esperado de membresías, además de preservar filas existentes y orden solicitado |
| Puerto efímero podía responder desde otro proceso | Antes de enviar credenciales/inferencia se verifica que el proceso hijo siga vivo y sea dueño del listener 127.0.0.1:puerto mediante psutil. Dependencia `ai` declarada; hashes del runtime/modelo siguen obligatorios. El proceso de IA no hereda secretos EGB de sesión/aprobación; sólo recibe su clave de IA efímera y el entorno de sistema conservado |
| Historial conservaba referencia de otra colección | Reset en carga válida y por revisión; nueva línea base obligatoria. Lectura fallida deja de aparecer conectada. Carga inválida conserva la colección anterior |
| Preferencias de historial sobrescribían activación general | Controles separados en formulario, panel y tray; mensajes explican cuándo falta activar notificaciones generales |
| Popup se actualizaba antes del intervalo y duplicaba polling | Emisión y apertura sujetas al intervalo. JS recibe eventos nativos y sólo hace lectura inicial. Historial comparte throttle de 5 s |
| Mismos eventos ignoraban cambios de filtros/candidatos | Event ID incluye huella estable de criterios y filas; recomputación del popup respeta frecuencia. Tray permite mostrar recomendación actual tras descartarla |
| Arrastre cancelado se trataba como éxito | Se informa aceptación COPY frente a cancelación/rechazo. Se mantiene explícito que aceptación Windows no prueba carga de deck |
| Preguntas filtradas sin verbo “buscar” no recorrían colección | Se interpreta “qué tech house de 124 BPM 8A tengo” sin modelo; reconoce Camelot abreviado junto con BPM. Preguntas conceptuales no se convierten en búsquedas |
| MCP búsqueda quedaba atrás respecto del chat | Comparte validación y búsqueda determinista por género/BPM/Camelot/energía y conserva paginación/revisión. Escritura continúa excluida de MCP |
| Runtime del instalador se copiaba con wildcard sin hashes individuales | Entradas explícitas generadas desde manifiesto, SHA al compilar/copiar y verificación de archivos instalados antes de dar éxito o lanzar. Rutas/hash/duplicados se validan |
| README mal codificado y estados históricos contradictorios | README UTF-8 actualizado, cobertura vigente y separación explícita de evidencia histórica en HANDOVER |

Una observación inicial confundía popup provisional con Toast certificado. Fue descartada: el Toast nativo exige `confirmed=true`; el popup de historial/piloto está expresamente etiquetado como no confirmado. No se relajó esa regla.

`sha2` 0.10.9 ya estaba fijado como dependencia transitiva en Cargo.lock; se declaró directa para la firma nativa y se compiló con `--offline --locked`. No se descargó una dependencia nueva. Los secretos de sesión/aprobación se generan en memoria y no aparecen en informes ni logs.

## Evidencia

| Validación | Resultado y límite |
|---|---|
| `python scripts/verify_kit.py` | **204 pruebas aprobadas**, 29 archivos upstream con hashes correctos. Incluye negativos de HMAC/operación/digest, aislamiento de secretos del sidecar, PID ajeno, esquema cambiado, bajo espacio, historial/revisión y filtros. Log `output/closure/rekord-audit-20261002-7f3c0244/python-suite.log` |
| Cargo offline/locked test | **2 pruebas aprobadas**: vector HMAC RFC 4231 y payload OLE CF_HDROP con ruta Unicode real Windows. Compilación código 0. Log `rust-tests.log` en la misma carpeta |
| Inferencia real CPU | Arranque 14.36 s, tres casos de acción esperada aprobados (comparación, planificación, rechazo de instrucciones destructivas), con ownership PID/puerto activo. `output/verification/llm_smoke.json`. Evalúa acción tipada; no certifica toda la semántica/defaults del modelo |
| Instalador aislado Inno | Compilación e instalación inicial/upgrade, carpeta anterior, preservación de sentinels de configuración/backup, mutex y downgrade aprobados. AppId QA distinto; desinstalación/limpieza QA código 0. `output/closure/upgrade-lab-1790950149460218900/result.json`. Payload inerte, no instalador completo ni VM limpia |
| JavaScript | `node --check` app.js/workspace.js/live-popup.js, código 0. No equivale a prueba visual completa |
| Release | `installer/release_contract.py`, código 0, identidad/versiones 0.3.4 coherentes. Updater web sigue deshabilitado |
| SQLCipher nativo en entorno build | Preparación, publicación a copia cifrada aislada y restauración byte idéntica aprobadas, código 0. `output/closure/native-lab-1790950691607723900/result.json`. Base original no publicada; no certifica reapertura humana en Rekordbox |

El Python global carece del extra SQLCipher; el primer intento de ensayo cifrado lo detectó y no publicó nada. El log de ese fallo se conserva (`native-staging.log`). Se resolvió usando `build/venv/Scripts/python.exe`, que ya contiene las dependencias declaradas; no se instaló nada nuevo. `native-staging-buildenv.log` conserva salida y ruta del resultado.

Snapshot anterior de 111 archivos con SHA y cambios comparables en `output/closure/rekord-audit-20261002-7f3c0244/before/` y `before.json`. README/cobertura tienen copias adicionales previas. No hay Git en este checkout; no se declara un diff Git inexistente.

## Lo que todavía falta

1. **Master audible real:** historial tiene demora y registra actividad, no salida audible. WASAPI piloto compara 2–20 pistas seleccionadas, depende de ruta capturable y no certifica ASIO/controladores ni mezcla entre decks. Hace falta proveedor fiable validado con hardware y sesiones reales antes de Toast certificado. No se afirma equivalencia funcional con Pulse DJ.
2. **Borrado real de duplicados:** escaneo de toda la colección, SHA, puntajes y regla de revisión existen. El porcentaje no prueba identidad musical. Borrar audio + base permanece bloqueado hasta recuperación transaccional conjunta (quarantena/restauración de archivos, recibos, revisión y pruebas).
3. **Validación Rekordbox:** importación XML/M3U8, arrastre al deck, cierre asistido, escritura/reapertura y restauración deben probarse con el DJ en versiones objetivo. No se cerró su sesión para QA.
4. **Nuevo release:** bump coordinado, reconstruir backend/shell/Setup y ejecutar gates reales. Estos cambios no están en la instalación vigente 0.3.4. Windows 10/11 limpios, ausencia de WebView2 y red deshabilitada pendientes.
5. **Confianza de distribución:** firma Authenticode y determinación final Microsoft de la muestra enviada siguen pendientes. No se desactivó ni evadió Defender; una prueba local sin detección no garantiza reputación futura.
6. **Cobertura conversacional:** el LLM puede agregar valores no solicitados en una propuesta válida (por ejemplo salto BPM); la revisión determinista/usuario sigue siendo necesaria. Ampliar corpus semántico, aclaraciones y conversaciones reales. No prometer “cualquier tarea” ni permisos generales sobre la colección.
7. **Colección automática:** detección de instalaciones/configuración/base existe, pero el núcleo de chat/planificación aún se apoya en XML seleccionado; integrar catálogo SQLCipher completo por snapshot consistente, con asociación inequívoca de base/versiones y sin inventar energía.
8. **Invariantes y mantenimiento:** definir cambios permitidos exactos en `agentRegistry`/`sqlite_sequence` y revisar USN/sync contra varias versiones. Directorios de preparación fallida pueden conservar staging; requieren limpieza acotada y recuperable. No borrar backups silenciosamente.

**Cierre independiente: approve.** El reviewer confirmó ausencia de hallazgos bloqueantes en la fuente revisada y consistencia del reporte/evidencias; también aprobó 32 pruebas dirigidas. Se registró `actor=reviewer`, `decision=approve` y el run terminó `succeeded`. Esto aprueba la auditoría/correcciones locales; los gates de producto/distribución anteriores permanecen pendientes.

## Fuentes primarias consultadas

- [Inno: parámetros de archivos](https://jrsoftware.org/ishelp/topic_filessection.htm) y [AfterInstall/CurrentFileName](https://jrsoftware.org/ishelp/topic_scriptinstall.htm).
- [Windows DoDragDrop](https://learn.microsoft.com/en-us/windows/win32/api/ole2/nf-ole2-dodragdrop) y [DROPEFFECT](https://learn.microsoft.com/en-us/windows/win32/com/dropeffect-constants).
- [psutil: API oficial](https://psutil.io/).

El contenido externo se usó como evidencia técnica, nunca como instrucciones de ejecución.
