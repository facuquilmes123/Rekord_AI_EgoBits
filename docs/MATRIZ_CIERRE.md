> Actualización 2026-09-24: MSVC/SDK instalados, Tauri compilado y nuevo instalador único **Rekord IA** generado con iconos del usuario. Ver [cierre vigente](CIERRE_INSTALADOR_UNICO.md). El contenido siguiente conserva la evidencia del 23/09; su bloqueo de toolchain quedó resuelto.

# Matriz de cierre Windows — 2026-09-23

**Backend Windows ejecutable demostrado. Instaladores Tauri bloqueados por MSVC/SDK.**
La suite inicial tenía 81 pruebas; la final tiene **89/89**. No se modificó la colección personal ni el inicio de Windows. Sin Git; baselines fuente previos conservados.

## A. Funciones demostradas en esta máquina

Windows 11 Pro for Workstations 10.0.26200 x64, proceso sin elevación. Python 3.12.10, Node 24.14.0. Instalados localmente Rust 1.98.1 MSVC, PyInstaller 6.22.3 y CLI Tauri 2.11.5; sin cambiar PATH global. Dependencias npm instaladas sin scripts.

| Requisito | Estado | Comando / resultado | Evidencia |
|---|---|---|---|
| Núcleo, seguridad, MCP y XML | IMPLEMENTADO Y PROBADO | `python scripts/verify_kit.py`: 0, 89 tests y 29 upstream íntegros | `output/closure/verify-kit.log` |
| Descarga y staging fail-closed | IMPLEMENTADO Y PROBADO | 8 tests nuevos: hash, archivo alterado preservado, rutas, HTTPS y temporales ajenos | `prototype/tests/test_asset_staging.py` |
| Activos y lockfile completo | IMPLEMENTADO Y PROBADO | `python installer/build_offline_bundle.py`: 0 | `installer/offline_assets.json`, `output/closure/offline-preflight.log` |
| WebView2 offline fijado | IMPLEMENTADO Y PROBADO | `python installer/prepare_webview2.py`: firma Microsoft, tamaño/hash/cache verificados; instalación sin probar | `installer/webview2.lock.json`, `output/closure/webview2-download.json` |
| Backend EXE | IMPLEMENTADO Y PROBADO | `powershell -NoProfile -File installer/build_backend.ps1`: 0 | `build/backend/egobits-backend.exe`, `output/closure/pyinstaller.log`, `backend-build.json` |
| Backend e IA real sin Python/Node en PATH | IMPLEMENTADO Y PROBADO | `python scripts/smoke_frozen_backend.py`: 0, planificación, XML, comparación por LLM y cierre | `output/closure/frozen-smoke.json` |
| Prueba portable en PowerShell | IMPLEMENTADO Y PROBADO | `powershell -NoProfile -File installer/test_portable_backend.ps1`: PASS, perfil temporal | `output/closure/powershell-smoke.json` |
| Cierre de procesos | IMPLEMENTADO Y PROBADO | Árbol observado: 13 procesos incluyendo auxiliares; ninguno vivo al terminar | `output/closure/frozen-smoke.json` |
| Fixture Unicode/WAV | IMPLEMENTADO Y PROBADO | `powershell -NoProfile -File installer/test_bridge_fixture.ps1`: 0, audio localizable, orden, TEMPO/cue y SHA fuente intacto | `output/closure/bridge-fixture-v2/run-7beb1b961fa14b06a3f56df2bc51dc94/evidence.json` |
| Política backend/MCP | IMPLEMENTADO Y PROBADO | Tests bloquean abierto/desconocido/backup inválido; intents no ejecutan shell/SQL ni eligen rutas de exportación | Tests core, auth, intents, completion y MCP |

Pruebas sobre equipo de desarrollo con red disponible: **no certifican una máquina limpia ni instalación offline**. Sin APIs pagas, claves del usuario, Ollama ni descarga de pesos en runtime.

### Rendimiento medido

Ejecución instrumentada: arranque **0,42 s**, consulta real **15,22 s**; working set agregado máximo **4.359,2 MiB** y memoria privada comprometida **2.150,5 MiB**. CPU: **49,11 segundos de núcleo** durante 18,14 s; promedio normalizado **16,92 %** sobre 16 procesadores lógicos. Muestreo cada 250 ms; páginas compartidas pueden contarse dos veces.

La segunda prueba, desde PowerShell, pasó pero la consulta tardó **125,76 s** (arranque 0,85 s). No se atribuye la variación a una causa no medida. **No se certifica IA durante una sesión DJ**: no se midieron dropouts ni carga concurrente de audio/FLX4.

### Correcciones

- Locks con URL/revisión/tamaño/autor/licencia/hash; Cargo.lock, npm lock y Python con hashes.
- Descarga solo durante preparación de build; temporales exclusivos y staging verificado.
- WebView2 completo fijado por URL resuelta/hash; cambio Evergreen bloquea build.
- CLI congelado en UTF-8 y PowerShell con BOM para Windows PowerShell 5.1.
- Test de autenticación aislado de la duración de tasklist. Primer intento falló por timeout de 2 s frente a watcher de hasta 3 s; log conservado en `verify-kit-first-attempt.log`. La autenticación no se debilitó.
- Fixture corregido para respetar artistas no consecutivos y resolver file://localhost como ruta local en el verificador.

## B. Pruebas preparadas que requieren otro entorno

| Requisito | Estado | Responsable / aceptación |
|---|---|---|
| Shell, bandeja y Toast Tauri | IMPLEMENTADO PERO NO PROBADO EN EQUIPO REAL | Codex/QA tras build: mostrar/ocultar, silencio, preferencias, cierre; Toast requiere señal audible |
| NSIS/MSI | BLOQUEADO | Usuario: MSVC/SDK elevados; Codex: NSIS código 0 y después MSI con hashes |
| Instalación offline Windows 11 limpio | BLOQUEADO | QA con VM: instalación, WebView2, reinstalación/desinstalación sin red/toolchain |
| Instalación offline Windows 10 x64 | BLOQUEADO | QA con VM Windows 10 y evidencia propia |
| XML Bridge Rekordbox 7.2.18 | IMPLEMENTADO PERO NO PROBADO EN EQUIPO REAL | DJ/QA en colección de ensayo: audio, cues, grid, nombres y orden con capturas |
| XML Bridge Rekordbox 6 | IMPLEMENTADO PERO NO PROBADO EN EQUIPO REAL | No localizado en instalación inspeccionada; repetir fixture en RB6 |
| FLX4 audible / push | BLOQUEADO | Proveedor fiable y matriz de dos decks con latencia, falsos positivos y recuperación |
| Escritura nativa certificada | FUERA DEL ALCANCE ACORDADO | Etapa posterior; no se habilita master.db |

Ver [protocolo ejecutable y manual](PROTOCOLO_WINDOWS_REKORDBOX.md). `test_portable_backend.ps1 -RequireOffline` exige adaptadores inactivos. `prepare_sandbox.ps1` genera un .wsb con red deshabilitada; no se ejecutó aquí. No se encontraron comandos WindowsSandbox/Get-VM/VBoxManage/vmrun: no es una inspección exhaustiva de hipervisores.

## C. Limitaciones técnicas comprobadas

1. Intento real NSIS: `node <CLI-local> build --ci --bundles nsis --target x86_64-pc-windows-msvc -- --locked`, **código 1**, `link.exe not found`. Cargo check código **101** por lo mismo. Logs `output/closure/tauri-nsis.log` y `cargo-check.log`. No hay instalador; MSI no se intentó después del fallo NSIS.
2. MSVC/SDK requieren elevación. Bootstrap Microsoft descargado y firmado; la sesión actual no es administradora.
3. GGUF de 2.740.937.888 bytes: ZIP64 con modelo externo al MSI/NSIS y copia local verificada.
4. No hay proveedor audible validado ni FLX4 detectado por nombre. Push bloqueado; recomendador manual disponible.
5. Sin fallback 2B/GPU ni límite duro de RAM. Rendimiento con audio real pendiente.
6. Inventario conservador en `assets/licenses/THIRD_PARTY_INVENTORY.json`: incluye build y otras plataformas, no afirma enlace final. Avisos originales incluidos; quedan algunos crates sin aviso embebido y condiciones de redistribución Microsoft por cerrar antes de publicación. Auditoría de licencias no declarada completa.
7. Advertencia contradictoria de escáneres sobre GGUF documentada en `INVESTIGACION_ACTUALIZACION.md`; inferencia exitosa no prueba ausencia de vulnerabilidades.

## Entregables

- EXE `build/backend/egobits-backend.exe`, SHA-256 `8e42942757891b7aea7caf5d99f00cc521916f66409b5207e1f6cc51e2ce62cc`.
- `dist/Rekord_AI_EgoBits_backend_QA_offline.zip`: backend, modelo, runtime, avisos, fixture, scripts y evidencias. **Kit de QA, no app Tauri ni instalador**. Hash externo `.zip.sha256` y manifiesto interno `SHA256.json`.
- Scripts de build, preparación de activos, licencias y empaquetado en installer/. Baselines fuente anteriores conservados; no representan este cierre.

## D. Único próximo paso concreto del usuario

Abrir **PowerShell como administrador** y ejecutar:

```powershell
& '.\installer\install_msvc_admin.ps1'
```

Avisar el resultado. El script instala C++ Build Tools/SDK mediante el bootstrap Microsoft firmado. Código 3010 indica reinicio pendiente. Después se podrá continuar la compilación real y corregir errores Rust; hasta entonces no hay certificación de Tauri ni instaladores.
