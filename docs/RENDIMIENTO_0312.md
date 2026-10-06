# Rendimiento y evaluación de propuestas — 0.3.12

Fecha: 2026-10-06. Cambios desde 0.3.11. Actualización directa del host, sin generar Setup.

## Decisiones

| Propuesta | Resultado aplicado y criterio |
| --- | --- |
| Evitar hashes repetidos del modelo | Caché sólo durante el proceso, después de SHA-256 completo. En Windows mantiene handles que permiten lectura y bloquean escritura y sustitución. Comprueba identidad del archivo al reutilizar. No confía en tamaño/mtime ni en una caché persistente. Otros sistemas vuelven a calcular el hash. |
| GPU y respuestas de 2–4 segundos | Pendiente. Este host reporta Intel UHD Graphics; el runtime fijado es CPU. No se descargó otro runtime ni se habilitó offload. Hace falta seleccionar y verificar un backend compatible y medirlo con el modelo real y carga musical. Una cifra genérica no prueba este equipo. |
| Más variantes de metadatos y género | Consultas como «no tienen género», «género vacío», «sin definir» y «no tienen análisis» usan evidencia de la colección. «Qué temas de house tengo» usa búsqueda por género sin exigir BPM. El parser sigue teniendo vocabulario acotado; preguntas abiertas pasan al modelo. |
| Duplicados: tamaño → prefijo → SHA completo | Inventaría todas las referencias. Descarta tamaños únicos y prefijos distintos. Lee los primeros 64 KiB sólo de candidatos del mismo tamaño; calcula SHA completo cuando siguen coincidiendo. Un archivo de hasta 64 KiB ya se leyó completo. Una coincidencia parcial nunca confirma un duplicado ni autoriza eliminación. |
| Respuestas de recomendaciones más pequeñas | API/chat/historial envían recomendaciones, `excluded_count` y `excluded_reasons`; omiten la lista completa de excluidos. El motor conserva su diagnóstico completo para herramientas internas. Criterios y ranking no cambian. |
| Menos trabajo periódico | Detección de fondo con TTL de 60 s y ranking de historial con TTL de 5 s. Rescan explícito invalida la detección; escrituras y cierre mantienen detección y procesos frescos. Shell publica eventos de estado y entrega para la ventana principal; navegador conserva fallback y pausa cuando está oculto. |
| Arrastre en hilo STA separado | Se saca la consulta HTTP bloqueante del hilo de UI; OLE continúa en el hilo principal. Cambiar el hilo de `DoDragDrop` sin reproducir un fallo de OLE y verificar mouse/COM no tiene beneficio probado. Falta validar el gesto físico en Rekordbox. |
| XML más grande y lectura incremental | Límite de 256 MiB, rechazo previo por tamaño y límite durante lectura. Parseo en bloques y SHA incremental, sin copia adicional de todos los bytes. Se conserva el árbol para cues/beatgrids y exportaciones; no es memoria constante. DTD, entidades y codificación con NUL siguen rechazadas. |
| Quitar verificación Inno posterior al copiado | No se aplica: `Hash` de un archivo embebido comprueba el activo durante compilación; no sustituye el hash posterior al copiado. Se conserva esa defensa. No se compiló instalador. |
| Convertir referencias upstream en submodules | Pendiente sin migración. Las instantáneas fijadas y sus licencias sirven a investigación reproducible/offline. Cantidad de líneas, por sí sola, no justifica reemplazarlas ni introducir pasos de descarga nuevos. |

## Medidas en este host

Son mediciones puntuales, no promesas de latencia ni certificación bajo carga de audio.

| Ensayo | Resultado | Límite de interpretación |
| --- | --- | --- |
| Integridad de 23 activos de IA | Primera verificación 5,975 s; reutilización protegida 0,012 s | Sólo verificación SHA/handles. El primer arranque y cada nuevo proceso verifican completamente; no mide generación ni carga del modelo. |
| XML real de 22,88 MiB | 24.140 pistas cargadas en 1,139 s | Instantánea XML seleccionada; puede quedar desactualizada respecto de la base nativa. |
| Inventario real de archivos | 23.180 archivos locales disponibles; 959 referencias no disponibles; 22.413 tamaños únicos (96,69 %); 13,545 s | Sólo stat/inventario de lectura. No se ejecutó un escaneo completo ni se modificó música. Los tamaños únicos representan 98,06 % de los bytes inventariados, descartables sin leer contenido completo para buscar igualdad exacta. |
| JSON de recomendación real | 1.134.818 → 3.869 bytes (99,66 % menos) | Mismo resultado del motor, serializado antes/después; el ahorro no equivale a igual porcentaje de latencia. |
| XML sintético grande | 122,53 MiB, 60.000 pistas, 16 cues por pista; carga 7,250 s; RSS después de cargar 572,2 MiB | Supera el límite anterior de 100 MiB. Cues preservados. RSS puntual del proceso, no pico ni comparación de memoria antes/después. |
| Backend EXE con modelo real | Arranque 3,41 s; dos consultas directas juntas 0,016 s; primera conversación abierta 84,48 s | Perfil/XML fixture aislados, PATH sin Python/Node. Prueba funcional de carga bajo handles protegidos. Generación CPU sigue siendo lenta; no es comparación controlada con tiempos de versiones anteriores ni SLA. |

Las mediciones locales completas quedan en `output/closure/` (ignorado por Git). Se publican sólo agregados, nunca rutas/nombres musicales, configuración ni credenciales.

## Pruebas y revisión

- Regresiones reproducidas antes de corregir: negaciones/metadatos, género sin BPM, lectura innecesaria de tamaños únicos y lectura XML completa antes de verificar el límite.
- Suite con Python del host: 274 pruebas, 11 omitidas por dependencias opcionales, código 0.
- Suite con el entorno de build y dependencias nativas/audio fijadas: 274 pruebas, 1 omitida (SDK MCP), código 0. Incluye copias SQLCipher aisladas; no escribe la base musical real.
- Rust: 2 pruebas aprobadas (vector HMAC RFC 4231 y payload de arrastre Unicode), código 0.
- JavaScript: `node --check` aprobado para `app.js` y `workspace.js`.
- Backend PyInstaller y shell Tauri compilados con salida completa y código 0. Smoke del EXE: 15 comprobaciones aprobadas, conversación real, estado `ready`, salida 0 y sin procesos huérfanos. La primera ejecución del script detectó una expectativa equivocada del contrato de test (`params` en vez del campo plano `genre`); se corrigió el script y se repitió satisfactoriamente, sin cambiar el backend.
- Pruebas del escáner verifican SHA completo frente a un oráculo, prefijos iguales con colas distintas, referencias repetidas, cancelación, cambios de archivos, XML obsoleto y protección de cues.
- Prueba Windows de activos: reutilización, lectura permitida, escritura y sustitución bloqueadas; tras cerrar la protección una modificación se detecta al volver a verificar.
- Historial: caché aislada de mutaciones del popup, invalidación por referencia/revisión/opciones y expiración. No se confirma master audible mediante historial.
- Revisión manual del agente principal: los hashes parciales sólo descartan candidatos; ninguna caché participa en autorización de escritura; el modelo/MCP no recibe nuevas facultades de mutación. No constituye revisión humana independiente.

## Reproducir validaciones

Desde la raíz, con dependencias ya fijadas:

```powershell
python installer/release_contract.py
$env:PYTHONPATH='prototype'
python -m unittest discover -s prototype/tests -q
node --check prototype/egobits/desktop/ui/app.js
node --check prototype/egobits/desktop/ui/workspace.js
& installer/build_backend.ps1 -Python (Join-Path (Get-Location) 'build/venv/Scripts/python.exe')
# Shell: usar toolchain existente y cargo build/test --release --locked --target x86_64-pc-windows-msvc.
& build/venv/Scripts/python.exe scripts/smoke_frozen_backend.py
```

El smoke usa XML y perfil temporales, arranca el EXE real, ejecuta conversación con el modelo local y comprueba salida limpia. La actualización instalada y sus hashes se registran en `DEVELOPMENT.md`. No sustituye pruebas de instalación nueva/Setup, Windows limpio ni hardware DJ.

## Fuentes contrastadas

- [Inno Setup, sección Files y Hash](https://jrsoftware.org/ishelp/topic_filessection.htm): distinción entre validación del archivo embebido durante compilación y activos externos durante instalación.
- [Microsoft, DoDragDrop](https://learn.microsoft.com/en-us/windows/win32/api/ole2/nf-ole2-dodragdrop) y [drag and drop OLE](https://learn.microsoft.com/en-us/windows/win32/com/drag-and-drop): ciclo modal y protocolo OLE. La consulta HTTP síncrona sí se retiró del hilo de UI.
- [llama.cpp b11146, backends de build](https://github.com/ggml-org/llama.cpp/blob/b11146/docs/build.md): un backend de GPU requiere runtime/compilación compatibles; el binario CPU fijado no adquiere soporte GPU sólo por cambiar `--n-gpu-layers`.
