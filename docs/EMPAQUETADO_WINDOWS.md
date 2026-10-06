> Entrega de usuario vigente: **un �nico EXE Inno Setup**, sin PowerShell ni copia manual del modelo. Ver [instalaci�n](INSTALACION_USUARIO.md) y [build/evidencia actuales](CIERRE_INSTALADOR_UNICO.md). El procedimiento MSI/NSIS + ZIP siguiente es una variante t�cnica hist�rica.

# Compilación y entrega offline Windows

## Estado

Cierre actual: `MATRIZ_CIERRE.md`. Backend Windows real compilado, 89 tests; toolchain local preparado salvo MSVC/SDK (instalación elevada pendiente). NSIS se intentó y falló por `link.exe` ausente. Existe kit de ensayo del backend, no MSI/NSIS.

El backend Python, el protocolo MCP y la inferencia CPU se prueban por separado. Tauri requiere Rust MSVC, Windows SDK, herramientas C++ de Visual Studio, `tauri-cli` 2 y PyInstaller. No se declara un MSI/NSIS disponible hasta finalizar esa compilación y probar su instalación.

## Activos fijados

- `assets/bin/`: llama.cpp b11146 CPU x64 y sus DLL.
- `assets/models/Qwen3.5-4B-Q4_K_M.gguf`: Qwen3.5-4B, conversión Unsloth Q4_K_M.
- `installer/offline_assets.json`: revisiones, procedencias y SHA-256 de cada activo.
- `assets/licenses/`: textos de licencia y procedencia.

`python installer/build_offline_bundle.py` verifica upstream y activos sin descargar nada. Un archivo ausente, no listado o alterado bloquea el empaquetado. El runtime vuelve a verificar EXE, DLL y modelo antes de iniciar inferencia.

El GGUF ocupa **2.740.937.888 bytes**. Por los límites de NSIS/CAB se entrega separado del instalador dentro de un ZIP64. El instalador contiene la aplicación, backend, llama.cpp y WebView2 offline; nunca intenta descargar pesos durante la instalación. No incluir el GGUF en `tauri.conf.json/resources`.

## Compilar

Desde la raíz, en un entorno de build con dependencias declaradas ya disponibles:

```powershell
python -m venv build/venv
build/venv/Scripts/python.exe -m pip install --require-hashes -r installer/requirements-build.lock
python scripts/verify_kit.py
powershell -NoProfile -File installer/build_windows.ps1 -Format both
```

Para probar MCP se requiere además `python -m pip install -e "./prototype[mcp]"`. Las instalaciones de dependencias y la primera preparación del toolchain pueden necesitar internet. Eso es preparación de desarrollo; el producto final no requiere conexión. Para un build sin red también deben estar cacheados Cargo, PyInstaller, WiX/NSIS y WebView2.

El script congela Python, verifica su copia, ejecuta Tauri y sólo tras código 0 arma `dist/Rekord_AI_EgoBits_Windows_offline.zip`. `package_release.py` rechaza una entrega sin instaladores. No sobreescribe una entrega previa: conservá o mové el ZIP anterior para crear otra.

El entorno actual ya tiene venv/Rust/CLI locales. No reinstalarlos para continuar. `installer/toolchain.lock.json`, `tauri-cli.package-lock.json` y `desktop/src-tauri/Cargo.lock` fijan la preparación; el build usa `--locked`. Para recuperar activos ausentes desde sus URLs fijadas usar `build_windows.ps1 -DownloadAssets`. Las descargas verifican tamaño/hash antes de staging. `prepare_webview2.py` comprueba firma Microsoft, hash y URL Evergreen resuelta antes/después del build.

El único paso elevado pendiente está preparado en `installer/install_msvc_admin.ps1`. Los avisos de terceros y pendientes de redistribución están declarados en `assets/licenses/THIRD_PARTY_NOTICES.md` y la matriz; no se presenta la auditoría de licencias como cerrada.

## Instalar una entrega compilada sin conexión

1. Extraer todo el ZIP64 con soporte para archivos mayores de 2 GB.
2. Ejecutar el MSI o NSIS de `installers/`.
3. Ejecutar `powershell -NoProfile -File installer/install_model.ps1`. Verifica origen/copia y coloca el modelo en `%LOCALAPPDATA%/Rekord AI EgoBits/assets/models/`. No requiere Python ni internet. Conserva un modelo existente si su hash difiere.
4. Abrir la app y seleccionar el XML exportado por el DJ en Configuración.
5. Para activar inicio con Rekordbox: `powershell -NoProfile -File installer/register_autostart.ps1 -AppPath "RUTA_DEL_EXE_INSTALADO"`. Registra un watcher por usuario para el próximo inicio de sesión; detecta la transición a Rekordbox abierto. No requiere administrador. Para desactivar: el mismo script con `-Remove`. No se ha modificado el inicio de Windows del equipo de desarrollo.

El watcher no vuelve a abrir la app si el DJ elige Salir mientras Rekordbox sigue abierto; espera el próximo inicio de Rekordbox. La bandeja usa el monitor Python existente para el estado efectivo y preferencias persistidas para silencio/push.

## Paquete fuente

```powershell
python scripts/build_source_kit.py
python scripts/build_source_kit.py --include-assets
```

El primero es liviano; el segundo incluye pesos y runtime. Ambos contienen `SOURCE_SHA256.json` y checksum externo. Son kits fuente, no instaladores. Excluyen cachés, descargas intermedias, logs y builds.

## Gates de release pendientes

- Compilar Rust/Tauri con lockfile revisado y comprobar ambos instaladores.
- Probar instalación/desinstalación sin red en Windows 10/11 x64, inicio con Rekordbox, cierre y ausencia de sidecars huérfanos.
- Probar Toast real con un proveedor audible validado. Actualmente no existe proveedor habilitado: las notificaciones no inventan la pista en reproducción.
- Importar XML de prueba mediante Bridge en las versiones objetivo; verificar rutas Unicode, audio resoluble, cues y grids. El round-trip automatizado no sustituye esa prueba.
- Medir RAM/CPU e inferencia bajo carga de audio real antes de recomendar IA durante un set. No hay fallback 2B/GPU incorporado ni límite duro de RAM implementado.
