# Rekord AI 0.4.1: conexión productiva

La app conecta una colección real. Un perfil nuevo detecta la base de Rekordbox y la abre en modo lectura; no carga una biblioteca de ejemplo. XML queda como alternativa explícita y como respaldo de lectura cuando no hay base local y existe una exportación configurada o detectada de forma única.

## Uso y automatización

- La detección consulta configuraciones de Pioneer/AlphaTheta, Rekordbox Agent, ubicaciones conocidas e instalaciones de Windows. Resuelve las rutas y prioriza la base configurada por Rekordbox frente a una base antigua en su ubicación original.
- La ruta se guarda después de completar la lectura. Los perfiles anteriores sin un modo explícito migran a `auto`, conservando preferencias. Una selección explícita de XML sigue siendo válida; «Detectar y conectar automáticamente» cambia al modo de base viva.
- Varias bases sin una preferencia inequívoca requieren una elección. Configuración muestra las candidatas y permite indicar `master.db` en otra ubicación.
- Las consultas de colección son compatibles con Rekordbox abierto o cerrado. SQLCipher usa `mode=ro`, `query_only` y una transacción de lectura coherente. Los cambios en DB/WAL invalidan el snapshot con TTL de tres segundos. El snapshot XML interno es una copia de trabajo generada por la app: no exige exportar XML ni modifica la base original.
- Un bloqueo, migración o componente ausente se muestra como error de conexión con acciones para reintentar o usar XML. No se cierran procesos para resolver una lectura. Una colección ausente no se sustituye por datos ficticios.
- Crear playlists, consolidar duplicados y restaurar una base exige Rekordbox y sus agentes cerrados, respaldo verificado, propuesta vigente y confirmación nativa ligada por HMAC a la operación. La app permite solicitar cierre normal con confirmación. No automatiza un cierre durante una sesión del DJ.
- Las escrituras usan la base elegida aunque se detecten varias; antes de preparar se comprueba que siga registrada en la configuración real de Rekordbox. Tras una operación nativa la colección se vuelve a leer inmediatamente, conservando modo automático/nativo y sin cambiar al XML de recuperación.
- El seguimiento del historial usa la base seleccionada cuando la colección es nativa, evitando ambigüedad por instalaciones antiguas.

## Pro DJ Link

La interfaz «Herramientas DJ → Pro DJ Link» conecta equipos reales. Detecta interfaces IPv4 activas con MAC/máscara, escucha anuncios UDP 50000 y estados/posición en 50001–50002, selecciona la red que contiene reproductores y negocia un número de observador libre del 7 al 15. Envía secuencias de presencia compatibles con CDJ-3000 y keep-alives; no exige un espejo o relay UDP para la conexión habitual.

Si detecta reproductores en varias redes, solicita elegir la interfaz. Si recibe un conflicto de número, abandona ese número y busca otro. Comprueba la ruta de salida antes de anunciar su dirección. La recepción mantiene frescura de los estados, posición y nombres; conserva la posición entre actualizaciones de la misma pista. Los IDs incluyen reproductor y soporte de origen y no se equiparan a IDs de la colección local.

El registro sólo transmite presencia. No envía carga de pistas, Play, Sync, fader-start ni control de tempo. On-Air es un estado informado por los equipos, no una medición del sonido. La conexión puede fallar si otra aplicación ocupa estos puertos, una VPN dirige el tráfico por otra interfaz o el firewall impide UDP. Se debe conectar la PC y los reproductores a la misma red y permitir Rekord AI en la red de la cabina.

El DDJ-FLX4 usa USB y no implementa Pro DJ Link. Las herramientas de colección, planificación, audio e historial funcionan independientemente de esa red. La validación de CDJ/XDJ físicos permanece pendiente por falta de equipos; la implementación se entrega operativa con pruebas de protocolo y sockets. No se afirma compatibilidad universal con todas las variantes de hardware.

## Ausencia de simulación en producción

Se retiraron el botón, la ruta HTTP y el método que creaban decks sintéticos. Los generadores de paquetes y el proveedor de telemetría de prueba están exclusivamente en `prototype/tests`; no forman parte del paquete Python productivo. El backend congelado tampoco incluye el directorio de ejemplos. Se revisaron interfaz, ayuda del asistente y catálogo de herramientas para describir capacidades operativas y requisitos reales.

«Herramientas DJ» reemplaza el nombre «Laboratorio DJ». La identificación de audio conserva sus resultados, procedencia y ambigüedad, con lenguaje de uso. Ninguna advertencia de pruebas físicas pendientes se presenta como un modo simulado de la aplicación.

## Validación

- Suite local del entorno de build: 321 pruebas, 320 aprobadas y una omitida por SDK MCP opcional; fixtures cifrados, publicación/rollback, contratos de versión y audio incluidos.
- Suite sin dependencias opcionales de audio/base: 318 pruebas, 304 aprobadas (antes de las tres pruebas finales de destino nativo y refresco) y 14 omitidas.
- Pruebas nuevas de autodetección, persistencia sólo tras lectura válida, ausencia de colección, elección entre bases, bloqueo, XML explícito y migración de preferencias.
- Pruebas de registro Pro DJ Link, número libre/conflicto, redes ambiguas sin transmisión, frescura y posición conservada, recepción UDP loopback y eliminación de la ruta de simulación.
- Navegador: un perfil vacío detectó 24.140 pistas, 22 playlists y MyTags; configuración muestra conexión viva y XML como alternativa. Pro DJ Link abre puertos reales y espera equipos sin crear decks. Consola sin errores.

## Fuentes del protocolo

Implementación propia a partir de hechos documentados; no se añadió ni ejecutó código externo.

- [DJ Link Packet Analysis](https://djl-analysis.deepsymmetry.org/djl-analysis/packets.html)
- [Startup y conflictos](https://djl-analysis.deepsymmetry.org/djl-analysis/startup.html), incluida variante CDJ-3000 (último byte de keep-alive `0x64`).
- [Estados de reproductores](https://djl-analysis.deepsymmetry.org/djl-analysis/vcdj.html)
- [DDJ-FLX4 oficial](https://www.pioneerdj.com/en/product/dj-controllers/ddj-flx4/)

## Continuidad y recuperación

Conservar identidad, ubicaciones persistentes y contrato `release.json`. Ejecutar `scripts/verify_kit.py` en un perfil temporal y `installer/release_contract.py` antes del build. Los ejemplos se proporcionan explícitamente sólo a las pruebas. El backend se compila con `installer/build_backend.ps1`; el shell con Tauri `build --ci --no-bundle --target x86_64-pc-windows-msvc -- --locked`. Para actualizar, respaldar ambos ejecutables y configuración, comprobar jobs/operaciones, cerrar sólo Rekord AI y verificar los hashes copiados y el estado posterior. No generar Setup para esta entrega.

## Actualización instalada verificada

- Backend y shell 0.4.1 compilados con código 0, sin Setup. El backend congelado pasó 14 comprobaciones en un perfil temporal y la instalación pasó 13 comprobaciones de colección/asistente/configuración.
- Colección real: 24.140 pistas; resumen completo, filtros, planificación, comparación/inspección, recomendaciones y auditoría. Configuración conservada durante sustitución; posteriormente sólo cambió el modo de colección a `auto`.
- `master.db` conservó exactamente su SHA-256 durante la actualización final y consultas. No se ejecutaron escrituras reales de playlist, duplicados ni USB. Los procesos de Rekordbox conservaron su estado; en esta comprobación estaba cerrado.
- Primera conexión desde un perfil vacío: 7,375 s; consulta en caliente 0,062 s en el backend congelado. Son mediciones puntuales, no garantías bajo carga.
- SHA-256 backend instalado: `74f704732a94a436bdbfe493f0992c18f8c35a9b6c504b2a7fb486df4209ece8`. Shell: `719ea26632c76e03207c378aab5098d6d5b0c0c9bce2f30f3e323ada7b6fe52e`.
- Respaldo original de 0.4.0: `%LOCALAPPDATA%/Rekord AI EgoBits/update-backups/before-0.4.1-20261006-220859`. La revisión final conserva además un respaldo intermedio de la misma versión antes de ajustar destino nativo/refresco.
