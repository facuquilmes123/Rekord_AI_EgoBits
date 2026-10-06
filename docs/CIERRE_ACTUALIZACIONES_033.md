# Cierre seguro y contrato de actualización — Rekord AI 0.3.3

Fecha: 2026-10-01. Mejoras locales verificadas antes de generar el instalador.

## Cierre asistido de Rekordbox

Configuración → Colección de Rekordbox → **Cerrar Rekordbox y sus agentes**. El botón se habilita al comprobar procesos abiertos y se bloquea durante una operación nativa. Primero identifica los procesos, luego pide confirmación porque terminará la sesión musical.

El backend verifica nombre exacto (rekordbox.exe / rekordboxAgent.exe), ruta dentro de una instalación detectada, propietario de Windows y fecha de creación/PID. La confirmación usa un ticket de 90 segundos, de un solo uso. Cambios de identidad, estado desconocido o una operación nativa bloquean el cierre. No recibe PIDs ni rutas arbitrarias desde el cliente.

Solicita WM_CLOSE a ventanas principales habilitadas, incluidas ventanas ocultas de agentes. Espera hasta 15 segundos y consulta de nuevo los procesos. No usa TerminateProcess, taskkill /F ni inyección. Una ventana de guardado, un agente sin ventana o que ignore el cierre puede requerir intervención del DJ; se informa y la escritura sigue bloqueada. Enviar WM_CLOSE nunca equivale a afirmar que el proceso terminó.

QA sobre la instalación real 7.2.19: identificó cinco procesos (aplicación + cuatro agentes); el diálogo se revisó y se canceló. No se cerró Rekordbox, no se detuvo música ni se cambió su configuración. Falta validar el cierre real cuando el DJ decida terminar su sesión. Captura: `output/playwright/rekordbox-close-033.png`.

## Correcciones adicionales

- Estados de los respaldos en español y avisos de operación en curso.
- Después de cancelar/completar el cierre o una propuesta se refresca inmediatamente la disponibilidad.
- Demostración no permite crear playlists nativas, tanto en UI como backend.
- La preparación ahora verifica que todos los registros de playlists y membresías existentes se conserven, además de contenido/cues/análisis.
- Se rechazan recibos de backup con archivos inesperados.
- Salir desde la bandeja solicita shutdown bajo el mismo bloqueo usado para modificar la colección. Si hay trabajo activo, se cancela la salida. Después de aceptar el cierre, un flag impide que una petición encolada comience una escritura.
- Corregido el endpoint de shutdown para consumir/validar el cuerpo JSON antes de responder: evitó la interrupción de conexiones en Windows observada por la suite.

## Un Setup para instalar o actualizar

- AppId estable: `F57C7090-73DC-453B-96DF-8D9F3E215E10`; identifier `com.egobits.rekordai`. Instalación por usuario, x64, conservados.
- `UsePreviousAppDir`, `UsePreviousGroup` y `UsePreviousTasks`: reutilizan carpeta y elecciones de la instalación anterior, incluso si el nombre visible cambió.
- Reemplaza los binarios/recursos registrados sin desinstalar previamente. Configuración en `%LOCALAPPDATA%/Rekord AI EgoBits` y respaldos en `%LOCALAPPDATA%/Rekord AI/native-operations` quedan fuera de la carpeta de programa y no se eliminan por el instalador.
- Rechazo de downgrade según DisplayVersion; reinstalar la misma versión es válido. Los mensajes de versión son compatibles con ejecución silenciosa.
- Mutex `Local\RekordAIApp` creado por la app y observado por Inno: actualización/desinstalación exige salir de la bandeja. Minimizar la ventana no basta. Para releases antiguas sin mutex, un chequeo oculto de procesos del directorio instalado impide sobrescribir app/backend activos. El usuario no abre PowerShell; el asistente realiza el chequeo internamente.
- `SetupMutex` impide instaladores concurrentes. El watcher nuevo pausa el lanzamiento automático mientras un Setup está en curso.
- `release.json` centraliza versión/identidad y carpetas persistentes. `installer/release_contract.py` rechaza versiones inconsistentes antes de construir; package_single_installer genera versión/nombre de Setup desde ese contrato. Reglas permanentes en `AGENTS.md` del proyecto.

## Verificaciones

- Suite completa: 127 pruebas ejecutadas; 126 aprobadas y una omitida por extra MCP ausente. Código 0, 29 archivos upstream verificados: `output/closure/verify-033-final-fixed.log`. Los logs `verify-033-final.log` y `verify-033-final-retry.log` conservan el fallo de conexión previo a la corrección.
- Pruebas específicas nuevas: confirmación/expiración, PID reutilizado, propietario/ruta no confiable, proceso que ignora cierre, exclusión mutua con operación nativa, shutdown activo, bloqueo de peticiones nuevas y drift de versión/identidad.
- Inno real, fixture de payload pequeño e identidad QA separada: `output/closure/upgrade-lab-1790876466030856000/result.json`. Instalación 0.3.2 → actualización 0.3.3, carpeta previa reutilizada, binario reemplazado, sentinelas de configuración/backup preservados, upgrade con mutex bloqueado y downgrade rechazado. Desinstalación QA código 0; entrada QA del registro eliminada. No modifica la instalación real del usuario. Este ensayo prueba la lógica del instalador, no el paquete completo ni Windows limpio/VM.
- Laboratorio cifrado: `output/closure/native-lab-1790876476562366600/result.json`: aplicación y restauración en una copia aislada, byte por byte; preservación de playlists existentes validada. No escribe sobre la base real del DJ.
- UI propia: diálogo de cierre, escritura grisada con Rekordbox abierto, cancelación sin cerrar procesos, sin errores de consola observados. Sintaxis de app.js/workspace.js verificada con Node.

## Actualizaciones web futuras

No se habilita ninguna búsqueda ni descarga online ahora. El instalador manual ya comparte identidad y mecanismo de upgrade, pero esto no constituye un updater automático activo.

Antes de activar el sitio/updater: definir canal/URL HTTPS y manifest con versión, compatibilidad mínima, tamaño y SHA-256 del Setup; firma criptográfica del manifest/artefacto verificada contra una clave pública incluida en la app; Authenticode del ejecutable; rechazo de rollback/replay y respuestas fuera de esquema. Descargar a staging, verificar antes de ejecutar, posponer durante un set o una operación sobre la colección, cerrar la app de forma coordinada, confirmar éxito/versión y ofrecer recuperación si el upgrade falla. Cambios futuros de settings/esquema exigen migraciones versionadas con backup; no activar escritores antiguos sobre un esquema más nuevo. Conservar siempre la posibilidad de instalar/actualizar offline y usar IA/colección sin Internet ni APIs pagas.

## Fuentes oficiales

- WM_CLOSE permite a la aplicación guardar o pedir confirmación: https://learn.microsoft.com/en-us/windows/win32/learnwin32/closing-the-window
- Identidad de aplicación para upgrades Inno: https://jrsoftware.org/ishelp/topic_sameappnotes.htm
- Reutilizar directorio anterior: https://jrsoftware.org/ishelp/topic_setup_usepreviousappdir.htm
- AppMutex requiere un mutex creado por la app: https://jrsoftware.org/ishelp/topic_setup_appmutex.htm

## Instalador final

- `dist/Rekord_AI_Setup_0.3.3_x64.exe`: 3.030.579.581 bytes; build completo código 0 (`output/closure/build-033-safe-close-upgrade.log`). Rust release 0.3.3 compilado en 3 min 16 s.
- SHA-256 contrastado después de finalizar: `fb6166ce201b17eab2e1112646b8324902a53d9aad7af9138da9cb31fcbe6be2`.
- Backend EXE: smoke exitoso (`output/closure/frozen033-smoke.json`), cinco procesos detectados, cierre sin confirmación rechazado, escritura desde demo rechazada y estado de operación consultable. Captura final del EXE: `output/playwright/rekordbox-close-033-exe.png`.
- Contrato de release/mutex y sus dos pruebas específicas volvieron a verificarse después del build. El verificador de build se reforzó para detectar divergencia entre el nombre del mutex Inno y Rust; no cambia el payload compilado.
- Prueba de instalación/upgrade del payload completo pendiente; sólo se ejecutó el fixture aislado con la lógica Inno actual. Instalador sin Authenticode. No se instaló ni actualizó la app del usuario durante QA.
- Sesión Rekordbox intacta: los mismos cinco PIDs seguían activos al final. Base y audio reales sin escrituras por nuestra implementación en QA. Servidores/vistas temporales de QA detenidos.
