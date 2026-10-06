# Matriz efectiva de estados

El estado proviene de `ProcessMonitor`: lista CSV completa y válida de procesos Windows. Fallo, plataforma no Windows o respuesta inválida => `unknown`. Las pruebas pueden forzar un estado; esa inyección no se publica por HTTP/MCP.

| Acción | Abierto | Cerrado | Desconocido | Condición adicional |
|---|---|---|---|---|
| Estado | Sí | Sí | Sí | Ninguna |
| Listar/buscar/auditar/comparar/describir | Sí | Sí | Sí | Snapshot XML legible |
| Planificar | Sí | Sí | Sí | Orígenes y metadatos válidos |
| Exportar XML nuevo | Sí | Sí | Sí | Revisión coincidente, origen sin cambios y destino inexistente |
| Recomendación manual | Sí | Sí | Sí | ID seleccionado y metadatos requeridos |
| Sugerencia live | Condicional | No | No | Fuente real, playing, antigüedad <5 s y ambas confianzas >85%, opt-in para aviso |
| Preferencias | Sí | Sí | Sí | Esquema válido |
| Crear playlist nativa / restaurar respaldo | No | Condicional | No | Agentes cerrados, base única 6/7, sin WAL, respaldo SHA-256, revisión fresca y bloqueo exclusivo Windows |
| Exportar USB | No | No | No | No implementado |

Cerrar Rekordbox no habilita por sí solo la escritura nativa. La UI y endpoints dedicados nativos implementan creación y restauración; el contrato MCP/chat no incorpora escritura automática. Ver `policy.py`, `test_core.py`, `test_live_suggestion.py`, `test_completion.py`, `test_desktop_auth.py` y `test_mcp_protocol.py`.

La exportación es un XML derivado que el DJ importa por Bridge. No sustituye al archivo fuente ni escribe `master.db`. El simulador nunca puede confirmar una sugerencia para Toast.
