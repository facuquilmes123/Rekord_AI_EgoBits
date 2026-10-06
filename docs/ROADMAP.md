> Documento de diseño previo. Para estado implementado y verificado al 2026-09-23, leer `COBERTURA_PROMPT_ORIGINAL.md`, `REPORTE_VALIDACION_FASE2.md` y `EMPAQUETADO_WINDOWS.md`. Las propuestas aquí no implican funciones disponibles.

# Camino de implementación y criterios de salida

**Fase 0, lista en este kit.** Inventario y fuentes con revisiones, prototipo de lectura XML y plan BPM/energía, exportación segura, 24 pruebas. Limitaciones abiertas: prueba en Windows con Rekordbox, adapter MCP opcional no instalado en este entorno, importación Bridge sin prueba en la aplicación real, live telemetry no implementada.

**Fase 1, primer producto demostrable.** Núcleo de dominio con esquema de datos y tools tipadas; importación XML real, búsqueda, planificación, reporte de exclusiones, nuevo XML; Tauri chat local y formulario equivalente; modelo local incluido en build offline. Criterio: en Windows 10 22H2 y 11 sin red, el usuario introduce la orden X+Y/BPM, recibe preview y exporta un XML que importa en Rekordbox sin perder cues de pistas copiadas.

**Fase 2, asistente diario.** Tray, detección de proceso y estado, avisos configurables, análisis local opcional de energía, historiales confiables, diferencia de snapshots, MyTags en solo lectura, memoria local explicable. Criterio: al abrir Rekordbox desde cero la app muestra tray y no roba foco; CPU y memoria aceptables durante set; toda herramienta no disponible explica condición.

**Fase 3, señal de reproducción.** Investigación por versión/hardware de proveedores autorizables. Medir precisión/recall y latencia con FLX4 y otras configuraciones, master deck alternado, faders/crossfader, pistas simultáneas. Criterio: recomendaciones push habilitadas únicamente donde proveedor certifique pista audible con frescura y fiabilidad acordadas; desconexión/cambio de layout interrumpe notificaciones automáticamente. En ausencia de señal viable, ofrecer selección manual.

**Fase 4, escritura nativa optativa.** Matriz de versiones, backups verificables, preflight, reconciliación, restauración en copia, tests de fallos/power loss, beta aislada. Criterio: un fallo de backup, DB cambiada, Rekordbox abierto o estado desconocido deja la colección original intacta. No habilitar sobre biblioteca real hasta pruebas de importación y restauración observadas con la versión exacta.

**Fase 5, distribución.** Firma, instalador offline íntegro, NOTICE de terceros, actualizaciones con hash y opción offline, privacidad, consumo, tests de reinstalación/desinstalación, soporte de hardware declarado. El usuario puede desactivar modelo, sugerencias, autoarranque o borrado de datos locales por separado.

## Decisiones que deben resolverse al probar con el usuario

Versión de Windows (build), arquitectura y RAM/GPU; versión exacta de Rekordbox; controlador y si Pro DJ Link está presente; tamaño de colección; mecanismo de exportación XML; si los archivos son locales o streaming; utilidad real de una escala de energía personalizada; nivel de alertas tolerable en cabina. Ninguna de esas respuestas bloquea Fase 1 con fixtures ni la investigación ya entregada.
