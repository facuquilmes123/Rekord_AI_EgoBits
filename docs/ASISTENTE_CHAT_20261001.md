# Asistente de Rekord AI — 2026-10-01

## Cambios implementados en el código fuente

- Conversación abierta offline: organización de la colección, preparación de sets, diagnóstico y preguntas generales sobre Rekordbox, además de las herramientas deterministas existentes.
- Contexto real y acotado del XML: totales, faltantes de metadatos, energía con fuente, géneros/artistas frecuentes, playlists más grandes y hasta cuatro pistas relevantes. El bloque de datos comprobados lo genera el servidor, no el modelo.
- El modelo puede proponer una herramienta existente mediante JSON validado. No se habilitan comandos arbitrarios ni se ejecutan escrituras a partir de prosa generada.
- Invocación con @ por nombre, artista/título o ID; autocompletado accesible. Las coincidencias parciales o ambiguas requieren seleccionar la pista exacta.
- Hasta cinco búsquedas independientes por consulta, criterios de similitud explícitos y referencias múltiples.
- Contexto reciente: cuatro mensajes, 500 caracteres por mensaje, sólo en memoria de la interfaz. Se limpia al cargar otra colección. Referencias de pista vinculadas a la revisión SHA del XML.
- Cada respuesta ofrece preguntas o acciones siguientes. Las acciones nativas mantienen revisión, cierre verificado y backup.
- Se corrigió la interceptación de preguntas generales sobre preescucha como si fueran consultas sobre la capacidad de escuchar del agente.
- Guardas contra referencias a pistas desconocidas, acciones inexistentes, contradicciones específicas observadas en inferencia y exposición de nombres internos de herramientas.

## Evidencia

- `python scripts/verify_kit.py`: **176 pruebas aprobadas**, código 0; 29 archivos upstream verificados. Log: `output/closure/verify-open-assistant-final.log`.
- `node --check prototype/egobits/desktop/ui/app.js`: código 0.
- Interfaz verificada con una colección sintética: autocompletado @, selección inequívoca, resultados, botones de seguimiento y referencia a “esa pista”.
- Inferencia real con llama.cpp y Qwen3.5 4B en CPU, sobre fixture de seis pistas: pregunta abierta sobre organizar un set de una hora; respuesta en español con orientación, datos reales y tres consultas siguientes; `applied=false`, SHA XML sin cambios. Tiempo total en frío: **81,05 segundos**, incluyendo verificación/carga del runtime. Reporte: `output/closure/assistant-local-inference.json`.
- La primera prueba real reveló contradicciones sobre tonalidades y requisitos de confirmación; una prueba posterior expuso parámetros internos inventados. Se ajustaron instrucciones y validación; la prueba final no reprodujo estos problemas. No se considera esto una garantía universal de exactitud.
- Resolución de una referencia parcial sobre la colección real sólo en lectura: pidió seleccionar la coincidencia; no se modificó el XML ni la base.

## Límites vigentes

El conocimiento general del modelo es orientación offline, no documentación oficial actualizada ni una verificación de todas sus afirmaciones. Las guardas acotadas no prueban cada frase. El contexto enviado no contiene toda la biblioteca ni audio; sólo estadísticas y muestras seleccionadas. No se atribuye acceso al master certificado, similitud sonora o escucha real que aún no se hayan validado.

La conversación abierta requiere activar y disponer del modelo local; si falla, se informa el error y las herramientas deterministas continúan disponibles. Una respuesta en frío puede tardar más de un minuto en CPU.

El borrado recuperable conjunto de base y música continúa pendiente. No se borraron archivos reales ni se alteró la sesión DJ. Los cambios son posteriores a 0.3.4: **todavía no están en el instalador o la aplicación instalada**. La identidad y versión del instalador vigente se conservan hasta preparar una nueva compilación.
