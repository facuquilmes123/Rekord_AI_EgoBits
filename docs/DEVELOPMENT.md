# Desarrollo y registro de cambios

## Fuente de verdad

- `release.json` fija versión, identidad, mutex y rutas persistentes. Ejecutar `python installer/release_contract.py` antes de compilar.
- `AGENTS.md` establece las reglas de preservación, QA y actualización. Leerlo antes de cambiar la app.
- `prototype/egobits/desktop/service.py` sirve la API local y enruta el chat. `opportunities.py` responde consultas de metadatos desde la colección completa; `assistant_context.py` acota los datos enviados al modelo.
- `prototype/egobits/desktop/ui/` contiene la interfaz. `desktop/src-tauri/` contiene el shell Windows y la firma de aprobaciones nativas.
- `docs/RELEASE_039.md` conserva la evidencia del último Setup completo; este cambio 0.3.10 es una actualización directa del host, sin nuevo Setup.

## Para cada cambio

1. Crear una rama desde `main` y describir el problema, el alcance y la prueba que lo reproduce en un issue o PR.
2. Cambiar el mínimo de archivos necesarios. No incluir XML de colección, bases, música, modelos, binarios compilados, configuraciones locales, tokens ni logs.
3. Ejecutar desde la raíz con Python y dependencias fijadas: `python installer/release_contract.py` y `$env:PYTHONPATH='prototype'; python -m unittest discover -s prototype/tests -q`.
4. Registrar en el PR el resultado de pruebas, la versión, los límites de validación y cualquier cambio de seguridad o datos. Revisar el diff y pedir revisión antes de fusionar.
5. Para un nuevo Setup, seguir `docs/CIERRE_ACTUALIZACIONES_033.md` y validar instalación inicial, actualización, datos conservados y rechazo de downgrade en entorno aislado. No asumir que una actualización directa del host certifica ese Setup.

## Colección y respuestas

El chat necesita un XML real exportado por Rekordbox. Si está la biblioteca de demostración o falta el XML, solicita cargarlo en Configuración. Los conteos de metadatos cubren el XML cargado completo; sólo los ejemplos de pistas son una muestra. El XML puede quedar desactualizado frente a Rekordbox y no representa el master audible. Las listas de pistas sin género, BPM o tonalidad son de lectura, y la corrección se realiza en Rekordbox seguida de una nueva exportación.

## Actualización directa de este host

Compilar backend y shell con la versión de `release.json`, comprobar hashes y hacer copia de los dos ejecutables instalados. Cerrar sólo Rekord AI cuando no haya operaciones nativas activas; no cerrar Rekordbox. Copiar únicamente los ejecutables y recursos nuevos necesarios, verificar hashes y arrancar la app. Confirmar `/api/status`, la colección cargada y una consulta real. Conservar `settings.json`, la colección, modelos y respaldos. Si falla, restaurar los ejecutables anteriores desde la copia verificada. El registro de Windows del Setup previo no sustituye la verificación de los binarios instalados.

## Verificación de 0.3.10 en este host (2026-10-06)

- `python installer/release_contract.py`: contrato 0.3.10 verificado.
- `PYTHONPATH=prototype python -m unittest discover -s prototype/tests -q`: 251 pruebas, 11 omitidas, código 0.
- PyInstaller backend y `cargo build --release --locked --target x86_64-pc-windows-msvc`: completados con código 0. No se generó Setup.
- Smoke de backend congelado con XML fixture aislado: arranque, comparación, conversación real local, cierre limpio y sin huérfanos aprobados. La primera conversación abierta tardó 88,8 s; el modelo local sigue siendo el límite de esa ruta.
- Actualización directa: respaldo SHA-256 verificado de ambos ejecutables previos; cierre limpio del backend y del shell de Rekord AI; copia y hashes nuevos verificados; `settings.json` conservado byte por byte. Rekordbox no se cerró.
- Instalación reiniciada: `/api/status` informó 0.3.10, colección real de 23.482 pistas y sin operación nativa activa. `/api/chat` respondió una consulta de faltantes en 0,081 s, con 14.215 pistas en la unión de género/BPM/tonalidad y enlaces a los tres listados.
- Estos ensayos no certifican instalación nueva, actualización por Setup, Windows limpio, audio master ni hardware DJ. El registro de desinstalación del Setup previo puede conservar su versión anterior hasta publicar un nuevo instalador.
