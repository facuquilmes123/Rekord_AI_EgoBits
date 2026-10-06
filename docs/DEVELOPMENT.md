# Desarrollo y registro de cambios

## Fuente de verdad

- `release.json` fija versión, identidad, mutex y rutas persistentes. Ejecutar `python installer/release_contract.py` antes de compilar.
- `AGENTS.md` establece las reglas de preservación, QA y actualización. Leerlo antes de cambiar la app.
- `prototype/egobits/desktop/service.py` sirve la API local y enruta el chat. `opportunities.py` responde consultas de metadatos desde la colección completa; `assistant_context.py` acota los datos enviados al modelo.
- `prototype/egobits/desktop/ui/` contiene la interfaz. `desktop/src-tauri/` contiene el shell Windows y la firma de aprobaciones nativas.
- `docs/RELEASE_039.md` conserva la evidencia del último Setup completo; la versión actual 0.4.0 es una actualización directa del host, sin nuevo Setup. `docs/ASISTENTE_CAPACIDADES_0311.md` detalla capacidades, ejemplos y niveles de evidencia; `docs/RENDIMIENTO_0312.md` registra las optimizaciones y evaluación de propuestas.

## Para cada cambio

1. Crear una rama desde `main` y describir el problema, el alcance y la prueba que lo reproduce en un issue o PR.
2. Cambiar el mínimo de archivos necesarios. No incluir XML de colección, bases, música, modelos, binarios compilados, configuraciones locales, tokens ni logs.
3. Ejecutar desde la raíz con Python y dependencias fijadas: `python installer/release_contract.py` y `$env:PYTHONPATH='prototype'; python -m unittest discover -s prototype/tests -q`.
4. Registrar en el PR el resultado de pruebas, la versión, los límites de validación y cualquier cambio de seguridad o datos. Revisar el diff y pedir revisión antes de fusionar.
5. Para un nuevo Setup, seguir `docs/CIERRE_ACTUALIZACIONES_033.md` y validar instalación inicial, actualización, datos conservados y rechazo de downgrade en entorno aislado. No asumir que una actualización directa del host certifica ese Setup.

## Colección y respuestas

El chat requiere una colección real: XML exportado o base viva de sólo lectura. Si falta, solicita conectar desde Laboratorio DJ o cargar XML en Configuración. Los conteos cubren toda la colección conectada; las muestras son sólo ejemplos. La base viva refresca cambios de DB/WAL con caché de tres segundos; el XML puede quedar desactualizado. Ninguna fuente certifica el master audible. Ver `docs/COLECCION_INTELIGENTE_040.md` para herramientas, pruebas, límites de modelo, USB y simulación.

## Actualización directa de este host

Compilar backend y shell con la versión de `release.json`, comprobar hashes y hacer copia de los dos ejecutables instalados. Cerrar sólo Rekord AI cuando no haya operaciones nativas activas; no cerrar Rekordbox. Copiar únicamente los ejecutables y recursos nuevos necesarios, verificar hashes y arrancar la app. Confirmar `/api/status`, la colección cargada y una consulta real. Conservar `settings.json`, la colección, modelos y respaldos. Si falla, restaurar los ejecutables anteriores desde la copia verificada. El registro de Windows del Setup previo no sustituye la verificación de los binarios instalados.

## Verificación de 0.3.10 en este host (2026-10-06)

- `python installer/release_contract.py`: contrato 0.3.10 verificado.
- `PYTHONPATH=prototype python -m unittest discover -s prototype/tests -q`: 251 pruebas, 11 omitidas, código 0.
- PyInstaller backend y `cargo build --release --locked --target x86_64-pc-windows-msvc`: completados con código 0. No se generó Setup.
- Smoke de backend congelado con XML fixture aislado: arranque, comparación, conversación real local, cierre limpio y sin huérfanos aprobados. La primera conversación abierta tardó 88,8 s; el modelo local sigue siendo el límite de esa ruta.
- Actualización directa: respaldo SHA-256 verificado de ambos ejecutables previos; cierre limpio del backend y del shell de Rekord AI; copia y hashes nuevos verificados; `settings.json` conservado byte por byte. Rekordbox no se cerró.
- Instalación reiniciada: `/api/status` informó 0.3.10, colección real de 23.482 pistas y sin operación nativa activa. `/api/chat` respondió una consulta de faltantes en 0,081 s, con 14.215 pistas en la unión de género/BPM/tonalidad y enlaces a los tres listados.
- Estos ensayos no certifican instalación nueva, actualización por Setup, Windows limpio, audio master ni hardware DJ. El registro de desinstalación del Setup previo puede conservar su versión anterior hasta publicar un nuevo instalador.

## Verificación de 0.3.11 en este host (2026-10-06)

- Contrato de versión aprobado; suite completa: 261 pruebas, 11 omitidas por dependencias opcionales, código 0. Diez pruebas nuevas cubren consultas del chat, validación de acciones, referencias repetidas, colecciones grandes y energía sin fuente.
- Backend PyInstaller completado con código 0. Shell `cargo build --release --locked --target x86_64-pc-windows-msvc` completado con código 0. No se generó Setup.
- Smoke EXE con XML fixture seleccionado y perfil temporal: exportación, comparación, resumen, inspección, auditoría, planificación desde colección, conversación local real, bloqueo de master no confirmado, cierre limpio y ausencia de huérfanos aprobados. Arranque 4,25 s; comparación 0,03 s; primera conversación 177,36 s con compilación y escaneo simultáneos. El modelo local sigue limitando las preguntas abiertas; estos tiempos no son un SLA.
- XML real: 24.140 pistas y 22 playlists. Búsqueda, comparación, cinco recomendaciones compatibles, transiciones, propuesta de 10 pistas, orden manual y exportaciones temporales aprobadas; fuente preservada. Copia SQLCipher aislada: playlist creada, integridad `ok`, restauración byte por byte. Sin escritura en la base musical real.
- El DJ autorizó cancelar el escaneo activo para actualizar. Se confirmó `cancelled`, ausencia de operación nativa activa y cierre limpio del backend. Se cerró sólo el shell de Rekord AI.
- Respaldo de ejecutables en `%LOCALAPPDATA%\Rekord AI EgoBits\update-backups\before-0.3.11-20261006-172631`; hashes previos comprobados. Configuración conservada byte por byte. Hash SHA-256 del backend nuevo: `e9e31b91a0f45af36479458f6524cd4411aa045b1c8f185afbbfd96a96c169dd`; shell: `6a98e19e05daf95031e13ce23e765397c9ca6d153f2e46a62f6b5dc2ffb96187`.
- Instalación reiniciada: `/api/status` informó 0.3.11, colección real y ausencia de operación nativa activa. `/api/chat`: resumen 0,078 s; propuesta 0,297 s; faltantes 0,063 s. Ayuda, inspección y auditoría aprobadas; consultas directas sin inferencia. Rekordbox permaneció abierto.
- Revisión manual del agente principal: nuevos intents de lectura, validación de origen/IDs/opciones, propuesta sin aplicar, exportación por confirmación y preselección sin relajar restricciones. No se habilitaron escrituras al modelo/MCP. La matriz distingue pruebas aisladas de uso DJ real; no constituye revisión humana independiente ni certificación del último Setup en Windows limpio.

## Verificación de 0.3.12 en este host (2026-10-06)

- [Evaluación de propuestas, cambios y mediciones](RENDIMIENTO_0312.md). Contrato de versión aprobado. Suite del host: 274 pruebas, 11 omitidas; entorno con dependencias nativas/audio: 274 pruebas, 1 omitida (MCP). Ambos códigos 0. Rust: 2 pruebas aprobadas; JavaScript válido.
- Backend PyInstaller y shell Tauri completados con código 0. Smoke EXE real con perfil/XML aislados: 15 comprobaciones aprobadas, incluidas aliases de metadatos/género, recomendación compacta, conversación local y cierre sin huérfanos. Primera conversación abierta: 84,48 s; el modelo CPU continúa siendo el límite. No se generó Setup.
- Antes de actualizar: escaneo `idle`, ninguna operación nativa activa. Cierre limpio del backend y cierre de sólo el shell de Rekord AI. Rekordbox se mantuvo abierto. No se canceló un nuevo escaneo.
- Respaldo verificado de ambos ejecutables: `%LOCALAPPDATA%\Rekord AI EgoBits\update-backups\before-0.3.12-20261006-175359`. Configuración conservada byte por byte. SHA-256 instalado del backend: `017107187484783e7761d00fc54687af957ece97349a1d1f59f2304f02a2e119`; shell: `6026ffe9cb796b742e8f91f38c6cc629aea0be50f2b9d87ef5f5fbefd393f9fc`.
- Instalación reiniciada: `/api/status` 0.3.12, colección real de 24.140 pistas, ninguna operación nativa activa. Nueve verificaciones API aprobadas: resumen completo, propuesta de colección, ayuda, metadatos sin modelo, género directo, recomendaciones compactas, inspección, auditoría y Rekordbox abierto. Consulta «no tienen género»: 0,094 s; Tech House: 0,125 s; resumen: 0,250 s; propuesta de 10 pistas: 0,641 s. Tiempos puntuales, sin garantía bajo carga musical.
- No se escribió la colección musical real ni se inició un escaneo completo de toda la música para medir. Se conservan restricciones de respaldo/confirmación, identidad, rutas persistentes y updater deshabilitado. Arrastre físico, hardware DJ, master audible y Setup en Windows limpio siguen sin certificar.
- Se detectó otro trabajo de web en el checkout original; sus cambios se preservaron. Documentación y publicación de esta iteración se completaron en un worktree de la rama de rendimiento.


## Verificación de 0.4.0 en este host (2026-10-06)

- Colección viva, Laboratorio DJ y 12 operaciones compartidas: ver `docs/COLECCION_INTELIGENTE_040.md`.
- 308 tests de suite (307 aprobados, uno omitido); MCP stdio real aprobado aparte. Diez checks de EXE congelado y once checks de la instalación real aprobados.
- Backend y shell compilados con código 0, actualización sin Setup, respaldo verificado y Rekordbox abierto. Sólo se cambiaron dos preferencias para activar la lectura nativa.
- El modelo CPU agotó el límite de dos intentos de composición. Se mantienen controles deterministas equivalentes y rutas directas para filtros + plan. No confundir estos ensayos con certificación de CDJs, USB físico, Pro DJ Link o master audible.
- Revisión manual del agente principal: autenticación, firmas ligadas a operación, rutas USB contenidas, hashes, rollback, límites del parser, ausencia de escrituras autónomas y preservación de ANLZ desconocidos. No equivale a revisión humana independiente.
