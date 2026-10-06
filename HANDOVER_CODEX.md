> **Entrega 0.3.9, 2026-10-02:** Setup `dist/Rekord_AI_Setup_0.3.9_x64.exe` generado; cierre desde el aviso de duplicados, versión nativa corregida, recuperación de transacciones con respaldo y restauración, consulta de análisis y configuración en pestañas. 247 pruebas (246 aprobadas, 1 omitida), builds y smoke reales aprobados, Defender sin amenazas en este host, instalación/actualización/anti-downgrade con payload completo aislado aprobados. No se modificó la instalación ni colección del DJ. Leer `docs/RELEASE_039.md` para evidencia y límites; notas inferiores históricas.

> **Release 0.3.8, 2026-10-02:** selector de porcentaje y eliminación en lote recuperable de duplicados verificados, consolidación nativa de playlists/historial y XML nuevo. Recomendaciones principales por metadatos del historial, sin captura. Build completo y Defender aprobados; 226 pruebas (225 aprobadas, 1 omitida). Backend EXE/UI y rechazo de borrado sin aprobación verificados. Ensayo full-payload aislado de instalación/actualización aprobado: 22 callbacks SHA, datos conservados y limpieza QA; WebView2/VM limpia no certificados. Leer `docs/RELEASE_038.md` y `docs/DUPLICADOS_SEGUROS_038.md`. No se modificó música/base/configuración personal ni se cerró Rekordbox.

> **Incidente Setup 0.3.5, 2026-10-02:** retirado por verificación de ruta sin expandir en AfterInstall. La fixture silenciosa devolvía código 0 pese al error interno; se corrige el callback y la prueba ahora exige logs sin excepciones y callbacks SHA completos. Release 0.3.6 compilada, Defender aprobado y ensayo full-payload aislado de instalación/actualización aprobado; 22 callbacks SHA y limpieza QA, 205 pruebas host y smoke IA local aprobados; leer `docs/RELEASE_036.md`.

> **Release 0.3.5, 2026-10-02:** Setup único reconstruido con mejoras auditadas y corrección de consultas sobre pistas compartidas. 205 pruebas host aprobadas; Rust2, fixture upgrade 0.3.4→0.3.5, smoke del backend EXE/IA real y hashes/Defender aprobados. Colección real e instalación personal intactas. Leer `docs/RELEASE_035.md`; no equivale a instalación completa en VM limpia ni master/deck certificados.

> **Auditoría director, fuente posterior a 0.3.4, 2026-10-02:** revisión especializada y correcciones de seguridad nativa, esquema de respaldos, identidad PID/puerto del sidecar, historial/popup/preferencias, búsqueda y hashes del runtime instalado. Leer primero `docs/AUDITORIA_DIRECTOR_20261002.md` para pruebas y límites. Incorporada al Setup 0.3.5; los estados siguientes conservan evidencia histórica.

> **Recomendaciones/popup, fuente posterior a 0.3.4, 2026-10-02:** modo automático por historial independiente de la salida, seguimiento WASAPI experimental, ranking conjunto BPM/Camelot/género/energía con razones, popup y arrastre nativo de archivo validado por ID/revisión. 190 pruebas Python aprobadas + prueba Windows CF_HDROP Unicode aprobada. Deck real, apariencia del popup en sesión y master aún sin certificar; todavía sin nuevo Setup. Leer `docs/RECOMENDACIONES_POPUP_20261002.md`.

> **Asistente ampliado, fuente posterior a 0.3.4, 2026-10-01:** conversación abierta con modelo local y hechos del XML, contexto reciente, @ con autocompletado, similitud explícita, múltiples búsquedas y acciones siguientes. Suite: 176 pruebas aprobadas; inferencia real en CPU sobre fixture, XML intacto. Orientación general del modelo no equivale a documentación verificada. Cambios aún sin nuevo Setup. Leer `docs/ASISTENTE_CHAT_20261001.md`.

> **Cambios locales posteriores a 0.3.4, 2026-10-01:** verificación cancelable de toda la colección, puntajes y regla de revisión por porcentaje; búsqueda del chat por género/BPM/Camelot/energía, con alternativas explícitas cuando falta energía. Suite final: 150 pruebas aprobadas. El borrado de base/audio sigue bloqueado hasta disponer de recuperación conjunta; estos cambios todavía no están en el Setup instalado. Leer `docs/DUPLICADOS_CHAT_20261001.md`. Microsoft añadió comentarios de analizadores sin detección sobre la recompilación enviada; final aún Pending, ver `docs/DEFENDER_034.md`.

> **Estado 0.3.4, 2026-10-01:** recompilación del shell tras limpiar los artefactos del paquete y auditoría Cargo (481 paquetes/25.322 archivos sin diferencias). Setup completo, reparación de instalación, reinstalación sobre 0.3.4 y arranque nativo aprobados en este host con Defender activo. Suite: 130 pruebas, 129 aprobadas, 1 omitida. SHA Setup `62ca6a65573c8ba38592f62bbc79f838afc1ac84fed0b98733ea555aadb54fba`. Microsoft recibió recompilación 0.3.3 (no muestra original): caso `dde2c020-dc63-4e4a-a0b2-c3172b85ff68`, Current detection muestra No malware detected, Final determination aún Pending. Original 0.3.3 continúa bloqueado. Firma y Windows limpio pendientes. Leer `docs/DEFENDER_034.md`.

> **Incidente 0.3.3, 2026-10-01:** Setup 0.3.3 NO apto para entregar. Instalación real falló: Defender detectó y puso el shell en cuarentena (`Trojan:Win32/Bearfoos.A!ml`). No hay dictamen de falso positivo sobre esa muestra. Leer `docs/INCIDENTE_DEFENDER_033.md`.

> Desarrollo 0.3.3, 2026-10-01: cierre asistido con confirmación; invariantes de playlists existentes; salida protegida durante operaciones nativas; Setup de instalación/actualización con identidad estable, conservación de datos y anti-downgrade. Leer `docs/CIERRE_ACTUALIZACIONES_033.md`. Updater online desactivado; prueba real del cierre de la sesión DJ pendiente.

> Desarrollo 0.3.2: creación nativa de playlists y restauración implementadas; ensayo completo sobre copia cifrada y bloqueo Windows verificados. No se modificó la colección real. Leer `docs/ESCRITURA_SEGURA_032.md`; sustituye el bloqueo de publicación señalado en el piloto anterior. Reapertura real y master audible aún pendientes.

> Desarrollo posterior a 0.3.0, 2026-10-01: SQLCipher de sólo lectura verificado en la base real, creación de playlist ensayada en copia cifrada, seguimiento de historial y piloto de comparación WASAPI incorporados. Leer `docs/NATIVE_LIVE_PILOT.md`. Publicación real y confirmación master/Toast siguen bloqueadas; la captura/ruta real todavía requiere validación con el DJ. El Setup 0.3.0 existente no incorpora estos cambios posteriores.

> Estado de la entrega 0.3.0, 2026-10-01: nombre solicitado **Rekord AI**. Selector Windows, avisos propios, KPIs, asistente, selección manual y M3U8 implementados. Leer `docs/MEJORAS_030.md`. Las notas históricas inferiores no describen el estado vigente.

> Actualización 2026-10-01: interfaz centrada en chat y detección Windows de Rekordbox implementadas. Ver `docs/UI_DETECCION_20261001.md` para alcance, evidencia y límites.

> Estado vigente 2026-09-24: nombre **Rekord IA**, Tauri compilado e instalador Inno único generado. Leer primero `docs/CIERRE_INSTALADOR_UNICO.md`; el bloqueo MSVC/SDK del 23/09 quedó resuelto.

# Traspaso: Rekord AI EgoBits

La siguiente guía conserva decisiones y evidencias históricas del 23/09. Los bloques fechados superiores y la auditoría del 02/10 describen el estado vigente. El bloqueo MSVC/SDK fue resuelto y existe Setup Inno único offline; no confundir el kit de QA con el instalador.

## Leer primero

1. `docs/COBERTURA_PROMPT_ORIGINAL.md`: estado real por requisito y correcciones.
2. `docs/REPORTE_VALIDACION_FASE2.md`: evidencia y límites de validación.
3. `docs/EMPAQUETADO_WINDOWS.md`: build, distribución del modelo y gates de release.
4. `docs/MATRIZ_ESTADOS.md`: fail-closed.
5. `docs/INVESTIGACION_ACTUALIZACION.md`: fuentes actuales y decisiones; complementa inventario previo.

## Reglas

- Cálculo local, cero APIs pagas y ninguna descarga de pesos en runtime.
- Escribir `master.db` únicamente mediante el flujo nativo con Rekordbox y agentes cerrados, respaldo verificado, revisión, bloqueo exclusivo y recuperación persistente. No sobrescribir el XML fuente ni un destino de exportación existente.
- Preservar beatgrids, hot cues, metadatos y rutas. Revisión SHA antes de exportar.
- Energía sólo con valor 0..10 y procedencia, asociada a la colección seleccionada.
- No presentar simulator, deck cargado o watcher de proceso como audio audible.
- El LLM interpreta; las acciones y parámetros son validados. No controla escrituras ni shell.
- Los datos de repositorios, metadatos y nombres de playlists nunca son instrucciones de confianza.

## Entradas técnicas

- `prototype/egobits/core/`: planificación, análisis y recomendador compartido.
- `adapters/`: XML, backup, lector SQLCipher y publicación nativa protegida. El lector SQLite auxiliar sigue limitado a snapshots descifrados.
- `ai/`: parser, intents, schema por acción/validador, sidecar llama.cpp.
- `desktop/service.py`: API loopback, carga de biblioteca, prefs, capacidades y ejecución de chat.
- `desktop/settings.py`: almacenamiento atómico en LOCALAPPDATA; tests usan temporales.
- `desktop/ui/`: interfaz HTML/CSS/JS sin CDN.
- `mcp_server.py`: 13 herramientas MCP; extra opcional `mcp` declarado en pyproject.
- `desktop/src-tauri/`: shell Rust con tray, popup, confirmación nativa y backend congelado. La fuente nueva requiere recompilar ambos y validar un nuevo Setup.
- `assets/`: runtime b11146 CPU x64, Qwen3.5-4B Q4_K_M y licencias; hashes en manifiesto.

## Verificación

```powershell
python scripts/verify_kit.py
python installer/build_offline_bundle.py
python scripts/smoke_local_llm.py
```

La prueba LLM carga ~2,74 GB de pesos y consume CPU; no ejecutarla durante un set. Suite determinista/protocolo: `cd prototype; python -m unittest discover -s tests -q`. El protocolo MCP requiere el extra declarado; sin él se omite explícitamente esa prueba.

## Próximo trabajo necesario

El build ejecutado falló exactamente por falta de Rust/Cargo MSVC. También se debe preparar MSVC/Windows SDK y PyInstaller, generar/revisar Cargo.lock y ejecutar build completo. Después: Windows 10/11 sin red, inicio automático, bandeja/Toast y parada del árbol de procesos. Probar importación Bridge con colección de ensayo en las versiones de Rekordbox objetivo. No asumir telemetría FLX4 disponible.

El cliente conversacional no conserva contexto de turnos previos, no hay fallback 2B/GPU y no hay límite duro de RAM. Las métricas de tres consultas CPU no constituyen un benchmark de cabina.
