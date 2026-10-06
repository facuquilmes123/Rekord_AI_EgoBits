# Actualización de investigación: decisiones que afectan Fase 2

Fecha de contraste: 2026-09-23. Esta nota complementa `INVESTIGACION.md`; no afirma que se hayan encontrado todos los proyectos privados, desindexados o publicados después de esta consulta.

## Superficie oficial y servidores MCP

La página oficial [rekordbox for Developers](https://rekordbox.com/en/support/developer/) documenta el flujo Bridge: importar un XML UTF-8 y seleccionar el archivo desde **Preferences > Bridge > Imported Library**. También exige nombres únicos para carpetas o playlists en el mismo nivel. Su [formato XML oficial](https://cdn.rekordbox.com/files/20200410160904/xml_format_list.pdf) define `DJ_PLAYLISTS` v1.0.0 y marca los campos de texto como UTF-8. En los canales oficiales revisados no apareció un servidor MCP, ni una API pública general para controlar decks, consultar el master audible o editar la base nativa. Por lo tanto, XML Bridge sigue siendo la superficie oficial de escritura para la primera versión.

Los servidores no oficiales principales ya listados en `INVESTIGACION.md` no cambian esa decisión: `davehenke/rekordbox-mcp` y `interfluve-wav/rekordbox-smart-mcp` aportan patrones MIT para biblioteca y planificación; `y08416/rekordbox-mcp` tiene rutas macOS; `rekordbox-performer-mcp` no declara licencia y se limita a experimentos de MIDI/visión; y los proyectos AGPL o sin licencia siguen fuera del producto. MCP es útil como interfaz de herramientas y pruebas de conversación, pero la aplicación Windows puede exponer los mismos intents tipados localmente sin necesitar que Rekordbox ofrezca un MCP.

**Decisión:** conservar el núcleo determinista y los adaptadores XML propios. Cualquier escritura futura de `master.db` queda experimental, con matriz de versión, backup verificable y Rekordbox cerrado; no es condición para el instalador inicial.

## Base local y pyrekordbox en Windows

[pyrekordbox](https://github.com/dylanljones/pyrekordbox) declara compatibilidad con `master.db` de Rekordbox 6/7, XML, ANLZ, MySettings y Device Library Plus; su README indica que se prueba en Windows y macOS, con límites de CI que requieren una instalación real. Para abrir `master.db` usa SQLCipher; su [guía de instalación](https://github.com/dylanljones/pyrekordbox/blob/master/docs/source/installation.md) describe `sqlcipher3-wheels` y el camino de compilación con amalgamación SQLCipher para Windows.

Los nombres de entidades publicados por ese proyecto son `DjmdContent` (tracks), `DjmdPlaylist`, `DjmdSongPlaylist`, `DjmdAlbum`, `DjmdArtist`, `DjmdGenre` y `DjmdLabel`. Son nombres de un adaptador no oficial, no una especificación estable de AlphaTheta. La propia documentación advierte que el cifrado necesita una clave disponible en el equipo; no se deben extraer, registrar ni distribuir claves. El fallback correcto es: lectura SQLCipher sólo cuando la versión y la apertura son verificadas, luego XML exportado por el usuario, y por último deshabilitar las herramientas que necesitan biblioteca.

**Decisión:** tratar el lector SQLCipher como proveedor opcional de sólo lectura. Mantener el XML como canal de compatibilidad y no añadir automatismos que modifiquen `master.db` durante esta fase.

## Pista audible y DDJ-FLX4

El [listado MIDI oficial del DDJ-FLX4](https://downloads.support.alphatheta.com/software_info/dj-controllers/DDJ-FLX4/DDJ-FLX4_MIDI_message_List_J1.pdf) permite conocer acciones físicas que el controlador expone por MIDI. No prueba cuál deck queda audible: no contiene una señal certificada de master, nivel efectivo de canal, crossfader o audio de salida. La propia ayuda de AlphaTheta para FLX4 indica compatibilidad MIDI y recomienda no ejecutar varios programas DJ a la vez ([referencia](https://support.alphatheta.com/en-us/articles/12294087060377)).

[Beat Link](https://github.com/Deep-Symmetry/beat-link) puede informar pistas cargadas y estado en equipos Pro DJ Link compatibles, pero avisa que no se espera que funcione en la misma máquina que Rekordbox por competencia de puertos. Un FLX4 no ofrece Ethernet DJ Link, por lo que no es una fuente viable para él. Los repositorios que inspeccionan ventanas, usan OCR o inyectan/hookean procesos no entregan garantía de audio; hook/inyección queda excluido.

**Decisión:** el watcher de proceso sólo alimenta los estados de elegibilidad. El modo de sugerencias automáticas empieza apagado y sólo puede emitir avisos si recibe un `NowPlayingEvent` de un proveedor explícitamente calibrado que cumpla el contrato local (<5 s y certeza >85 %). Para FLX4 no hay proveedor no intrusivo verificado todavía. Agregar una integración futura requiere una prueba de cabina con versión de Rekordbox, firmware, latencia, casos de crossfader/auriculares y falsos positivos, antes de activar notificaciones por defecto.

## Runtime local y modelo empaquetable

`llama.cpp` publica [binarios Windows x64 CPU en sus releases](https://github.com/ggml-org/llama.cpp/releases) y sus releases enlazan attestations de GitHub. La documentación del [servidor](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) confirma `llama-server.exe`, el binding por defecto en `127.0.0.1` y los endpoints HTTP. El bundle debe fijar una release concreta, URL de asset, SHA-256 de la release/attestation, licencia MIT y el hash local tras descomprimir. No se debe usar `winget`, `-hf` ni ningún descargador durante instalación o ejecución offline.

El identificador oficial actual es [Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B), licencia Apache-2.0. Es un modelo vision-language post-entrenado; no se publica bajo el nombre exacto `Qwen3.5-4B-Instruct`. La página oficial remite a cuantizaciones para llama.cpp; al momento de la consulta, una conversión disponible y licenciada Apache-2.0 es [unsloth/Qwen3.5-4B-GGUF](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF). Es una conversión de tercero, por lo que la revisión del repositorio, el nombre preciso del archivo GGUF y su SHA-256 deben fijarse antes de incorporarla. La alternativa de mayor procedencia es convertir localmente una revisión fijada del modelo oficial con una revisión fijada de llama.cpp, registrar ambos commits y el SHA-256 resultante, y conservar los avisos Apache.

**Corrección necesaria:** `installer/offline_assets.json` y `build_offline_bundle.py` todavía nombran `qwen3.5-4b-instruct-q4_k_m.gguf`, que no corresponde a una publicación oficial identificada en esta revisión. Antes de empaquetar, seleccionar un artefacto real (por ejemplo un GGUF con `repo_id`, `revision`, `filename`, `sha256`, licencia y aviso de conversión) y actualizar el nombre requerido y manifiesto en conjunto. El preflight actual falla cerrado por hashes y procedencia vacíos, que es el comportamiento correcto hasta entonces.

La integración existente en `prototype/egobits/ai/sidecar_client.py` ya reserva un puerto efímero TCP en `127.0.0.1`, genera una clave de proceso y valida SHA-256 antes de lanzar el proceso. Hay una pequeña ventana de carrera entre liberar la reserva y crear `llama-server`; para endurecerlo, iniciar el sidecar con puerto `0` si su versión expone el puerto final de manera parseable y verificar que el proceso queda ligado a loopback, o reintentar un número limitado de puertos ante error de bind. Mantener `--host 127.0.0.1`, `--no-webui`, API key por proceso y sin proxy. La gramática GBNF debe seguir siendo una ayuda de forma: el parser tipado local conserva la autoridad de validación.

### Activos fijables comprobados por API, sin descargarlos

La API oficial de Hugging Face devuelve la revisión `e87f176479d0855a907a41277aca2f8ee7a09523` para [unsloth/Qwen3.5-4B-GGUF](https://huggingface.co/api/models/unsloth/Qwen3.5-4B-GGUF). En el árbol de esa revisión, `Qwen3.5-4B-Q4_K_M.gguf` tiene 2,740,937,888 bytes (2.55 GiB) y el OID Git LFS `00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4`; para LFS este OID SHA-256 identifica el contenido completo. El artefacto queda direccionable sin rama mutable en [este resolve](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/e87f176479d0855a907a41277aca2f8ee7a09523/Qwen3.5-4B-Q4_K_M.gguf). Sigue siendo una conversión de tercero, con licencia declarada Apache-2.0, y debe verificarse de nuevo contra ese hash tras obtenerse por un canal controlado.

La API de GitHub identifica una release concreta de llama.cpp: [`b11146`](https://github.com/ggml-org/llama.cpp/releases/tag/b11146), commit `7fe450e19305b828c199d602c23a8337aaa1f03b`. Su asset CPU x64 de Windows es [llama-b11146-bin-win-cpu-x64.zip](https://github.com/ggml-org/llama.cpp/releases/download/b11146/llama-b11146-bin-win-cpu-x64.zip), 18,560,055 bytes, con digest publicado `sha256:14cf1303ca9ac3abd94816850532f9f9a69ac66fbaca3776fc6f9061c2fac1d1`. Ese hash corresponde al ZIP, no a `llama-server.exe`: sin descargar y calcular el SHA-256 del ejecutable extraído no existe un hash verificable que pueda escribirse en el manifiesto actual, que valida directamente el `.exe`.

## Tamaño del instalador: bloqueo de empaquetado único

Tauri 2 ofrece instaladores Windows mediante WiX/MSI o NSIS ([documentación oficial](https://v2.tauri.app/distribute/windows-installer/)). La configuración de resources los incorpora al bundle. El modelo Q4_K_M anterior supera por sí solo 2 GiB.

NSIS documenta un límite teórico de 2 GB para un instalador único ([documentación de NSIS](https://nsis.sourceforge.io/Failure_when_compiling_a_big_installer)). Para MSI, Windows Installer admite cabinets externos o embebidos y división de archivos entre cabinets ([Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/msi/cabinet-files)); WiX documenta un máximo de 2,048 MB por cabinet para división de archivos grandes ([FireGiant](https://docs.firegiant.com/wix3/xsd/wix/mediatemplate/)). Sin embargo, la incidencia abierta de Tauri [#7372](https://github.com/tauri-apps/tauri/issues/7372) registra fallo de sus bundlers MSI y NSIS para una aplicación mayor de 2 GB, bloqueado por dependencias upstream. No hay evidencia de que el pipeline Tauri 2 actual empaquete de forma fiable este archivo como un único instalador MSI o NSIS.

**Decisión:** no prometer MSI/NSIS monolítico con Q4_K_M. Se pueden entregar el instalador de aplicación y un paquete de modelo offline separado, ambos con manifiesto y hashes, para que el instalador local copie el GGUF ya presente sin red. Si el requisito exige una sola descarga/archivo, escoger una cuantización inferior a 2 GiB y validar que el bundle resultante se compila y se instala en Windows 10 y 11; esa decisión exige medir calidad y memoria, que todavía no se hizo.

## Ruta de cierre verificable

1. Elegir y revisar un asset exacto de llama.cpp y un GGUF exacto, luego completar `installer/offline_assets.json` con origen inmutable, licencia y SHA-256.
2. Ejecutar el preflight offline con los activos ya presentes, sin descargar nada, y archivar su salida en el reporte de build.
3. Probar sidecar en Windows x64 con el modelo elegido: health, puerto loopback, clave rechazada/aceptada, gramática y parada limpia.
4. Importar XML de prueba con tildes, `ñ`, caracteres no latinos y rutas Unicode desde Bridge en Rekordbox 6 y 7; registrar versión y resultado. La conformidad estructural no sustituye esas pruebas de producto.
5. Mantener la telemetría FLX4 como simulada/no disponible hasta contar con evidencia reproducible de pista audible.
6. Para Q4_K_M, diseñar el instalador como dos artefactos offline verificables; no activar target MSI/NSIS monolítico hasta resolver y probar el límite upstream de Tauri.

## Apéndice: contraste de escaneo del GGUF fijado

El árbol de la API de Hugging Face para la [revisión `e87f176479d0855a907a41277aca2f8ee7a09523`](https://huggingface.co/api/models/unsloth/Qwen3.5-4B-GGUF/tree/e87f176479d0855a907a41277aca2f8ee7a09523?recursive=true&expand=true) identifica `Qwen3.5-4B-Q4_K_M.gguf` con blob Git `4ca59aa028e499c9351f394e844f5e27056e5846` y OID LFS SHA-256 `00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4`. En la respuesta de ese mismo objeto, `securityFileStatus.protectAiScan.message` devuelve literalmente: `This file is vulnerable to threat(s) PAIT-GGUF-100.`

El informe de [Prisma AIRS para la misma revisión y blob](https://insights-db.paloaltonetworks.com/models/unsloth/Qwen3.5-4B-GGUF/e87f176479d0855a907a41277aca2f8ee7a09523/files?blob-id=4ca59aa028e499c9351f394e844f5e27056e5846&utm_source=huggingface) presenta para esa revisión `threat_status: SAFE`, `scan_status: SCANNED` y una lista `threats: []`. No se encontró una definición primaria pública de `PAIT-GGUF-100`, ni evidencia que la vincule específicamente a prompt injection de plantilla, a una vulnerabilidad del parser o a una mitigación disponible en llama.cpp `b11146`.

El SHA-256 permite comprobar integridad y la prueba local confirma que el runtime puede cargar y atender en el entorno evaluado; ninguna de esas dos evidencias determina la ausencia de una amenaza de seguridad. Conservar ambas referencias en la trazabilidad y reevaluar el aviso si Prisma AIRS o Hugging Face publica una descripción técnica.

## Implementación posterior a esta consulta

Se descargaron y verificaron los activos exactos anteriores; el manifiesto contiene hashes individuales del EXE/DLL y GGUF. El preflight pasó y la inferencia CPU completó tres consultas. El GGUF se entrega en ZIP64 junto al instalador, fuera del MSI/NSIS. Ver `REPORTE_VALIDACION_FASE2.md` para métricas y gates pendientes.
