> **0.4.0, 2026-10-06:** Colección viva, MyTags, cues/frases, análisis acústico offline, Key Shift, DeviceSQL respaldado y simulación/receptor Pro DJ Link. [Uso, evidencia y límites](docs/COLECCION_INTELIGENTE_040.md). Actualización directa, sin nuevo Setup.

> **Desarrollo 0.3.12, 2026-10-06:** Consultas directas ampliadas, escaneo de duplicados por tamaño/prefijo/SHA completo, integridad de IA reutilizada con protección de archivos, recomendaciones compactas, eventos del shell y XML incremental hasta 256 MiB. [Evaluación, mediciones y límites](docs/RENDIMIENTO_0312.md). Actualización directa, sin nuevo Setup.

> **Entrega 0.3.9, 2026-10-02:** Setup `dist/Rekord_AI_Setup_0.3.9_x64.exe` generado; cierre desde el aviso de duplicados, versión nativa corregida, recuperación de transacciones con respaldo y restauración, consulta de análisis y configuración en pestañas. 247 pruebas (246 aprobadas, 1 omitida), builds y smoke reales aprobados, Defender sin amenazas en este host, instalación/actualización/anti-downgrade con payload completo aislado aprobados. No se modificó la instalación ni colección del DJ. Leer `docs/RELEASE_039.md` para evidencia y límites; notas inferiores históricas.

> **Asistente 0.3.11:** Resumen completo, inspección y auditoría de playlists/sets desde el chat; planificación desde toda la colección con búsqueda acotada informada. [Capacidades verificadas y ejemplos](docs/ASISTENTE_CAPACIDADES_0311.md).

# Rekord AI

Asistente DJ para Windows con chat local, planificación de sets, análisis de colección y recomendaciones por BPM, Camelot, género y energía con procedencia.

## Estado actual

**0.4.0**, con lectura nativa y Laboratorio DJ. El último Setup generado es **0.3.9**: [entrega y verificación](docs/RELEASE_039.md). **0.3.5 retirado por fallo de instalación**. El Setup Inno anterior incluye modelo y WebView2; la actualización directa de esta iteración no es un instalador distribuible. Master audible y flujos DJ reales siguen pendientes de certificación.

La creación nativa de playlists y la consolidación de duplicados seguros exigen Rekordbox/agentes cerrados, respaldo automático verificado, revisión y confirmación nativa Windows. La restauración verifica integridad y esquema y recupera la música retirada. El XML fuente no se sobrescribe. [Reglas y recuperación de duplicados](docs/DUPLICADOS_SEGUROS_038.md).

El popup por historial se activa con un botón y usa la última referencia registrada, con posible demora, aplicando los filtros guardados de la colección. BPM, género y tonalidad están activos por defecto en preferencias nuevas; las preferencias anteriores se conservan. El piloto WASAPI es optativo y acotado. Ninguno certifica el master audible; los Toasts confirmados requieren un proveedor fiable. La aceptación de un archivo por Windows no demuestra que Rekordbox lo cargó en un deck.

## Ejecutar y verificar el prototipo

Python 3.12+:

```powershell
cd prototype
python -m egobits --serve
```

Abrir `http://127.0.0.1:8765`. Seleccionar un XML en Configuración. Este modo no permite escritura nativa ni cierre de Rekordbox: esas operaciones requieren el shell Windows autenticado.

Desde la raíz:

```powershell
python scripts/verify_kit.py
python installer/release_contract.py
python installer/build_offline_bundle.py
python scripts/smoke_local_llm.py
```

Dependencias opcionales declaradas: `prototype[ai]` para verificación del sidecar, `prototype[native]` para SQLCipher, `prototype[audio]` para el piloto, `prototype[mcp]` para MCP stdio. El instalador incorpora dependencias y modelo local, sin APIs pagas ni descargas de pesos durante el uso.

MCP registra 15 herramientas; `collection.tools` describe 12 operaciones compartidas que se invocan mediante `collection.execute`. Configurar `EGB_LIBRARY_XML` y ejecutar `python -m egobits.mcp_server` desde `prototype`. La escritura nativa está reservada a revisión en Windows y no está expuesta al modelo ni por MCP.

## Documentación

- [Traspaso](HANDOVER_CODEX.md)
- [Cobertura actual e historial](docs/COBERTURA_PROMPT_ORIGINAL.md)
- [Chat y consultas](docs/ASISTENTE_CHAT_20261001.md)
- [Recomendaciones y popup](docs/RECOMENDACIONES_POPUP_20261002.md)
- [Escritura segura](docs/ESCRITURA_SEGURA_032.md)
- [Instalación](docs/INSTALACION_USUARIO.md)
- [Contrato de upgrades](docs/CIERRE_ACTUALIZACIONES_033.md)
- [Investigación y licencias](docs/INVESTIGACION_ACTUALIZACION.md)

Los informes históricos conservan sus resultados fechados. Windows 10/11 x64 son objetivos de distribución; falta certificar el instalador completo en equipos limpios y los flujos DJ con hardware real.
