# Reporte de verificación

Fecha: 2026-09-23. Implementación local ampliada; release Windows pendiente.

## Evidencia

| Verificación | Resultado |
|---|---|
| Suite original al inicio del empaquetado | 50/50 (baseline histórico del reporte anterior) |
| Suite completa actual | **81/81**, código 0, incluye protocolo MCP real |
| Procedencia upstream | 29 archivos con hashes correctos |
| Activos offline | 22 archivos EXE/DLL + un GGUF, SHA-256 coincidentes |
| MCP stdio | initialize, listado de 13 tools, plan correcto y error por playlist inexistente |
| Inferencia real CPU | 3/3 consultas: comparación, plan de 4 pistas, rechazo de orden maliciosa |
| JavaScript | `node --check` código 0 |
| PowerShell | Parser de los scripts de instalación/build sin errores |
| Navegador real | Demo identificada; chat crea propuesta de 4 pistas; botón abre tabla; recomendador manual devuelve IDs 2 y 3; acciones nativas/live deshabilitadas con motivo |
| Build MSI/NSIS | **Bloqueado**, código 1: `Falta Rust/Cargo MSVC.`; preflight de activos pasó antes del fallo |

La prueba del navegador registró un 404 de favicon, corregido con icono vacío local. No detectó errores de ejecución del flujo probado. Captura local: `output/playwright/planner.png`.

## IA real

Modelo y runtime exactos declarados en `installer/offline_assets.json`. Arranque autenticado: 5.11 s. Consultas: 20.05 s, 16.75 s, 22.92 s. Evidencia JSON: `docs/LLM_SMOKE.json`. Se cerró el sidecar al finalizar.

Una primera prueba ampliada falló porque el modelo generó parámetros ajenos a la acción. El validador los rechazó. Se cambió a JSON Schema por acción; la repetición pasó las tres consultas. Esto es un smoke acotado, no garantía de comprensión general ni benchmark bajo carga de audio. La respuesta de ayuda puede contener explicaciones imprecisas del modelo; no se ejecutan acciones a partir de ellas.

## Seguridad y regresiones cubiertas

- Colección real sin heredar energías demo; ruta inexistente no cae a demo.
- Carga inválida conserva biblioteca/preferencias; ajustes inválidos no reemplazan archivo.
- Petición desconocida/ambigua no crea playlist ni elige orígenes; validación fallida no pasa al modelo para relajarse.
- Parámetros IA fuera de catálogo y escrituras rechazados.
- BPM/energía ausentes no se inventan; filtros compartidos manual/live.
- Exportación antigua/origen alterado bloqueados, XML fuente preservado, DTD y UTF-16 rechazados.
- Unicode/tildes/rutas URI, TEMPO y POSITION_MARK preservados en pruebas round-trip.
- Autenticación HTTP, Origin, forma de JSON y parámetros validados.
- Proveedor de telemetría ausente/simulado/fallido no confirma avisos; watcher inválido => unknown.
- Lector de snapshot SQLite corregido y probado con esquema real mínimo; SQLCipher explícitamente no soportado.

## Pendientes que impiden llamar al producto terminado

1. Toolchain Rust/MSVC/PyInstaller, compilación Tauri y lockfile revisado. No se generó ni ejecutó un instalador.
2. Instalación/desinstalación offline en Windows 10/11, watcher registrado, bandeja, Toast y cierre del árbol de procesos.
3. Importación efectiva Bridge en Rekordbox 6/7 con audio y metadatos de ensayo. Compatibilidad estructural no equivale a “100% compatible” en producto.
4. Proveedor real de pista audible, especialmente FLX4; actualmente no se habilita push live en producción.
5. Benchmark RAM/CPU con audio real, corpus de consultas y fallback 2B/GPU si las mediciones lo justifican.

Se preservaron XML fuente y base real de Rekordbox. Los tests usan fixtures y temporales. No se activó inicio automático del equipo ni se importó contenido en la colección del DJ.
