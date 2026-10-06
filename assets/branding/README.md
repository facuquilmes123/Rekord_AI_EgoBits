# Identidad de Rekord IA

- `rekord-ia-original.png`: copia exacta de la imagen proporcionada por el usuario.
- `rekord-ia-tray-source.png`: derivado simplificado para bandeja, generado mediante la herramienta integrada `image_gen` el 2026-09-24.
- `manifest.json`: hashes, formato y dimensiones de los activos integrados.
- Aplicación/instalador: `desktop/src-tauri/icons/rekord-ia.ico` y `rekord-ia.png`.
- Bandeja: `desktop/src-tauri/icons/rekord-ia-tray.png`, RGBA 64 px, escalado por Windows según DPI.
- UI: `prototype/egobits/desktop/ui/rekord-ia.png` y `favicon.png`.

Conversión de formato y tamaños: CLI oficial Tauri 2.11.5 `tauri icon`.
No se redibujó el icono principal. Ambos originales PNG tienen transparencia real.
Las variantes 16/24/32/48/64 de bandeja se conservan en `build/branding/tray-icons/`.

## Prompt usado (herramienta integrada, sin API externa configurada)

Use case: precise-object-edit. Input image is the user's approved Rekord IA app logo, edit target. Create ONE faithful simplified small Windows system tray icon derivative, square canvas 1024x1024 with genuine transparent background (alpha, no black rectangular background). Preserve the recognizable six interwoven rounded petals in bright cyan/electric blue surrounding a central black vinyl disc with cyan center and black hole. Preserve the same orientation, silhouette and relative composition. Simplify drastically for 16px and 32px legibility: bold continuous blue/cyan bands, clean dark charcoal petal interiors, central vinyl disc indicated by ONE subtle ring only, remove fine grooves, microscopic highlights, textures and shadow noise. Flat clean high contrast pictogram, clear silhouette on light and dark taskbars, icon occupies 90% of canvas with even padding. No text, no letters, no new symbols, no badge, no frame, no mockup, no screenshot, no multiple icons. This is a derivative for the tray only; do not redesign the brand.

El generador devolvió 1254×1254; las dimensiones de consumo se generaron con Tauri.
