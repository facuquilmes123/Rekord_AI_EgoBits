> Documento de diseño previo. Para estado implementado y verificado al 2026-09-23, leer `COBERTURA_PROMPT_ORIGINAL.md`, `REPORTE_VALIDACION_FASE2.md` y `EMPAQUETADO_WINDOWS.md`. Las propuestas aquí no implican funciones disponibles.

# Instalación y funcionamiento 100 % local

**El ZIP de investigación no contiene instalador.** Construir un paquete x64 Windows reproducible con binarios y pesos predescargados, después de comprobar los términos de distribución de cada componente. Producto inicial recomendado: Tauri 2 + sidecar local basado en `llama.cpp` MIT + GGUF cuantizado de Qwen3.5 4B Apache 2.0, sujeto a validación de plantilla de chat, tool calling, velocidad y RAM del equipo. Ollama MIT es una alternativa opcional para usuarios que ya lo tengan y una ruta de experimentación; si se usa como runtime principal empacado, incluir su licencia, binarios y modelos, desactivar nube y verificar arranque local sin descarga. No requiere claves ni cobros de API.

El [modelo Qwen3.5:4b](https://ollama.com/library/qwen3.5%3A4b) figura con tamaño aproximado de 3,4 GB en distribución Ollama; [su licencia](https://ollama.com/library/qwen3.5%3A4b/blobs/7339fa418c9a) es Apache 2.0. Tamaño en instalador depende de GGUF, cuantización y compresión. Prever espacio adicional para memoria de inferencia, WebView2 y backups; no prometer uso aceptable en 4 GB de RAM sin benchmark. Variante 2B para equipos modestos y 9B en alta capacidad solo tras pruebas de exactitud y rendimiento. El modelo debe responder español y usar JSON/tool calling fiable con gramática y validador: la exactitud se mide en un banco de pedidos DJ, no por tamaño del modelo.

Tauri usa WebView2. Su [instalador offline](https://v2.tauri.app/distribute/windows-installer/) puede añadir aproximadamente 127 MB; versión fija añade aproximadamente 180 MB y acarrea actualizaciones de seguridad a cargo del producto. Elegir modo offlineInstaller y verificar compatibilidad/licencia del redistribuible WebView2. Tray y notificaciones requieren registro y pruebas de Windows; autoarranque **al detectar Rekordbox** mediante un pequeño watcher de eventos de proceso + fallback de sondeo moderado, single instance, sin privilegios administrativos permanentes. Alternativa de instalación: registrar app para iniciar con sesión Windows y permanecer dormida hasta que arranque Rekordbox. Empaquetar desinstalador y manejo de modelos/estado que no borre la colección.

## Matriz de compatibilidad que debe comprobarse

| Entorno | Objetivo / condición |
| --- | --- |
| Windows 11 x64 vigente | Objetivo principal; pruebas de instalador offline, UI, tray, LLM CPU y ruta GPU opcional |
| Windows 10 x64 22H2 | Objetivo explícito; WebView2 offline y runtime local comprobados |
| Windows 10 x64 anterior a 22H2 | No prometer compatibilidad hasta demostrarla; [Ollama para Windows](https://docs.ollama.com/windows) exige 22H2 según documentación consultada. `llama.cpp` propio podría ampliar soporte, sujeto a builds y pruebas |
| ARM64 Windows | Variante separada si se decide ofrecer; no suponer que binario x64/GPU funciona igual |
| Rekordbox 6 / 7 | XML primero; DB según adaptadores y versión del esquema, matriz específica de pruebas |
| FLX4 / controlador sin DJ Link | Lectura de master en vivo **por demostrar** con pruebas en el hardware real |

## Pipeline reproducible

1. Fijar revisiones de Tauri, `llama.cpp`, modelo cuantizado, WebView2 y librerías; descargar durante BUILD, verificar SHA-256/SHA-512, documentar URLs, autor, licencia y avisos de atribución. Nunca pedir descarga después de instalar el modo offline.
2. Integrar sidecar CPU compatible para baseline (p. ej. compilar arquitectura conservadora y seleccionar optimización AVX2 en tiempo de ejecución solo si está disponible); probar fallback GPU por familia y driver. Modelo comprimido/instalado una sola vez, fuera del directorio del usuario con permisos apropiados.
3. Bundle MSI/NSIS según pruebas y firma de código si hay distribución profesional. El usuario no necesita instalar Python, Rust, Node ni Ollama por separado.
4. Ejecutar instalación en una VM Windows limpia sin red, reconstruir XML fixture y usar chat de ejemplo; verificar que no hay tráfico, descargas, dependencia de API ni solicitudes de cuenta propias. La activación o servicios de **Rekordbox** no se controlan desde esta app y podrían tener requisitos independientes.
5. Ejecutar tests de Windows 10/11 en hardware de cabina, antivirus/SmartScreen, arranque/multiproceso, permisos de perfil, rutas Unicode, backups, desinstalación y compatibilidad de actualización de Rekordbox.

Fuentes: [Ollama Windows](https://docs.ollama.com/windows), [FAQ Ollama sobre nube](https://docs.ollama.com/faq), [Tauri installer](https://v2.tauri.app/distribute/windows-installer/), [rekordbox requisitos](https://rekordbox.com/en/download/).
