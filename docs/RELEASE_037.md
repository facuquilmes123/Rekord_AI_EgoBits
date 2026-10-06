# 0.3.7 · Recomendaciones sin capturar audio

Fuente y ejecutables compilados el 02/10/2026. El Setup 0.3.7 incorpora recomendaciones desde la última referencia registrada en el historial, no confirma la pista audible del master. Activación con un botón; BPM, género y tonalidad configurables, los tres activados por defecto en preferencias nuevas. Se conservan preferencias anteriores y se ofrece un preset explícito.

- 214 pruebas host aprobadas. Regresión aislada del instalador aprobada; no equivale a VM limpia.
- Backend EXE probado con copia del XML real y lectura del historial: tres sugerencias locales compatibles con Gata Only, 100 BPM, 12A, reggaeton. No se escribió la base real ni se capturó audio.
- Índice de rutas: consulta repetida reducida de 27,766 s a 0,578 s en este host.
- Build completo código 0; 44 módulos congelados comparados semánticamente con la fuente. Defender del host aprobó payload y Setup. Sin firma Authenticode.
- SHA Setup: `660273be4639d0d4d02eb4fc3356b944e8274b1995110a945bc6b3e4b9c10ee7`.

Evidencia: `output/closure/release-037/installer.json`, `metadata-qa-55d9dd77819a43a98b674280866353aa/evidence.json`, `final-pipeline.log`; `output/closure/live-metadata-performance.json` y `live-metadata-real-20261002.json`.

El borrado conjunto de duplicados se desarrolla después de este artefacto y requiere 0.3.8. La 0.3.7 no incorpora esa función. Master audible, arrastre a deck real y Windows limpio permanecen sin certificar.
