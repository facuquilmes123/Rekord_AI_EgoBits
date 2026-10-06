# ADR 001: inferencia local con llama.cpp

Estado: implementado y con smoke CPU local; distribución Tauri pendiente de compilación.

- Runtime: llama.cpp b11146 Windows CPU x64, commit y hashes en `installer/offline_assets.json`.
- Modelo oficial: Qwen/Qwen3.5-4B. Activo GGUF: conversión Unsloth Q4_K_M fijada por revisión, Apache-2.0, 2.740.937.888 bytes. No existe un requisito de nombre `4B-Instruct` para este activo.
- llama.cpp es MIT; se preservan licencias de dependencias incluidas y procedencia de la conversión.
- Inicio con EXE/modelo/DLL verificados, puerto efímero 127.0.0.1, clave por sesión en entorno del proceso, sin proxy ni redirects. Se exige endpoint autenticado. `--offline`, `--no-agent`, UI deshabilitada, CPU 4 hilos, contexto 2048, un slot.
- API `/v1/chat/completions`, template del modelo y thinking deshabilitado. JSON Schema restringe sintaxis y claves; llama.cpp lo convierte a gramática. La validación Python restringe acciones y parámetros. Una gramática NO garantiza semántica correcta ni elimina prompt injection.
- El modelo sólo interpreta consultas; planificación y recomendaciones son deterministas. No se le exponen shell, borrado, escritura nativa ni exportación automática.
- El parser resuelve primero consultas reconocidas y valida ambigüedades. Ante fallo de IA queda una respuesta explícita y el formulario sigue disponible.
- Pesos separados del MSI/NSIS dentro de ZIP64 offline; el copiado local comprueba SHA-256.

## Límites vigentes

No hay fallback 2B descargado, selección de GPU, límite duro de RAM ni certificación bajo carga de audio. CPU es la configuración comprobada en este equipo. No se publican cifras de RAM sin medir. No hay memoria conversacional entre turnos. Bibliotecas muy grandes pueden exceder el contexto de nombres; el formulario y parser permanecen disponibles.

La inspección de HF arrojó un aviso de seguridad contradictorio con el informe Prisma del mismo blob. Se conserva evidencia y límite de interpretación en `INVESTIGACION_ACTUALIZACION.md`; no se le atribuye una vulnerabilidad concreta no demostrada.

Fuentes: [servidor llama.cpp fijado](https://github.com/ggml-org/llama.cpp/blob/b11146/tools/server/README.md), [Qwen oficial](https://huggingface.co/Qwen/Qwen3.5-4B), [conversión GGUF](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF).
