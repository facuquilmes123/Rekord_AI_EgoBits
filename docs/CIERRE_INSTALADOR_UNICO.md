# Cierre: instalador único de Rekord IA — 2026-09-24

## Resultado

El toolchain MSVC/Windows SDK quedó instalado. Tauri compiló con código 0; se corrigieron dos errores Rust reales: variante inexistente PermissionState::Unknown y duración de un MutexGuard durante el cierre.

La entrega de usuario es un único **Rekord_IA_Setup_0.2.0_x64.exe** con asistente gráfico Inno Setup 6.5.4. Incluye shell Tauri, backend congelado, llama.cpp, sus DLL, GGUF y WebView2 completo. El modelo se copia y verifica desde el asistente. No se pide al usuario abrir PowerShell, instalar toolchains ni descargar pesos.

- Tamaño: **2.984.690.771 bytes**.
- SHA-256: **484bb3fef8f9797c6c09e6f39648ef6f91b7e3acc9ab23b8b81bc00076917453**.
- Archivo: `dist/Rekord_IA_Setup_0.2.0_x64.exe`.
- Hash externo: el mismo nombre con sufijo `.sha256`.
- Build Tauri: `output/closure/tauri-single-build.log`.
- Build Inno: `output/closure/inno-build.log` (código 0).
- Manifiesto de build: `output/closure/single-installer.json`.
- Suite: **89/89**, `output/closure/verify-kit-20260924.log`.

El instalador anterior al icono se conserva únicamente como evidencia en `dist/archive-pre-icon/`.
Los ZIP previos son kits técnicos históricos, no el flujo de instalación para usuarios.

## Nombre e iconos

Nombre visible: **Rekord IA** en ventana, UI, bandeja, instalador, accesos directos, MCP y metadatos XML exportados. Se conservan identificadores técnicos y el directorio histórico de preferencias para no perder configuración existente.

Icono principal: imagen original del usuario, conservada byte a byte. ICO multirresolución para Windows; PNG para ventana/UI. Bandeja: derivado simplificado con transparencia real y versiones 16, 24, 32, 48 y 64 px. Tauri integra la versión 64 px para escalado según DPI.

Activos, prompt y hashes: `assets/branding/README.md` y `assets/branding/manifest.json`.
Herramienta integrada image_gen para la adaptación; CLI oficial Tauri para conversión de formato/tamaños. No hay generación de imágenes ni API de pago en el producto.

## Verificación del instalador

**PASS en este host:** instalación y desinstalación terminaron con código 0. Coincidieron todos los hashes de activos instalados, shell y backend; la inferencia local real pasó. La desinstalación retiró el ejecutable y el registro de la aplicación de prueba.

El ensayo automatizado de instalación, hashes del modelo/runtime, inferencia real y desinstalación se registra en `output/closure/installer-host-test.json` y sus logs. El estado efectivo de ese reporte prevalece sobre una mera compilación. La prueba corre en una carpeta nueva del proyecto, sin cambiar la colección del DJ y con autostart/accesos directos desactivados.

No equivale a Windows limpio: el host tiene herramientas y WebView2 ya instalado y mantiene conexión. No se certifican todavía Windows 10 limpio, instalación del WebView2 faltante sin red, interfaz visual completa/tray/Toast, importación real Rekordbox ni fuente audible FLX4. Push sigue bloqueado sin proveedor válido. El EXE no está firmado con certificado comercial.

## Cómo continuar

Usuario: doble clic en el instalador, Siguiente, Instalar, Finalizar. Guía: `docs/INSTALACION_USUARIO.md`.

Desarrollo: `powershell -NoProfile -File installer/build_single_installer.ps1`.
La ruta antigua `build_windows.ps1` y los bundlers MSI/NSIS quedan como variantes técnicas; su límite de payload no se traslada al usuario mediante comandos manuales. Inno 6.5.4 admite este payload en un EXE único: ver `INSTALADOR_UNICO_INVESTIGACION.md`.

La investigación de licencias y la certificación en equipos reales conservan los pendientes registrados en la matriz anterior; no se declara release pública certificada.
