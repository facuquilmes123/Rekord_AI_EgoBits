# Consultas admitidas

Usá nombres/rutas de la colección cargada. `ROOT/X`, `ROOT/Y` e IDs 1/2 son ejemplos de la demostración, no nombres garantizados de tu biblioteca.

| Consulta | Resultado |
|---|---|
| `listar playlists` | Rutas y cantidad de pistas |
| `buscá temas de Artista` | Coincidencias con ID, título y artista |
| `buscar en coleccion una pista techhouse de 124 bpm con tonalidad 8a y buena energia` | Filtros combinados; alternativas identificadas si falta energía |
| `decime canciones similares en tonalidad y genero a @rodrigo-840` | Resuelve artista/título desde tu colección; Camelot compatible y mismo género |
| `buscame pistas de la misma tonalidad que @"Rodrigo - 840"` | Tonalidad exacta, nombre con espacios entre comillas |
| `recomendame canciones similares en bpm a @id:123` | BPM ±4; no impone género/tonalidad que no pediste |
| `similares en energia a @id:123` | Energía ±1/10, requiere valor con fuente registrada |
| `otras parecidas a esa pista` | Usa la referencia previamente invocada, si la revisión de la colección sigue vigente |
| `buscar techno; similares en genero a @id:123` | Hasta cinco búsquedas independientes separadas por punto y coma |
| `uní ROOT/X y ROOT/Y subiendo BPM con 4 temas` | Propuesta, nunca escritura automática |
| `uní ROOT/X y ROOT/Y en modo energía con 4 temas` | Requiere JSON de energía 0..10 con fuente por ID |
| `compará ROOT/X y ROOT/Y` | Pistas comunes y exclusivas |
| `auditá colección` | Metadatos faltantes y métricas |
| `qué duplicados tengo` | Posibles duplicados, no borra archivos |
| `describí pista 1` | Metadatos de ese ID |
| `transición entre 1 y 2` | Diferencias de BPM/energía y regla armónica |
| `recomendá desde pista 1` | Próximas candidatas con filtros guardados |
| `estado` | Estado real de proceso y colección |
| `qué está sonando en vivo` | Disponible sólo con fuente audible válida; hoy informa limitación |

Escribir `@` abre sugerencias de canciones de la colección; podés seleccionar
con mouse o flechas y Enter. Se inserta una referencia `@id:...` inequívoca.
Los nombres exactos se resuelven sólo si identifican una pista. Los nombres
parciales o ambiguos ofrecen candidatos y requieren elegir; nunca seleccionan
una versión arbitrariamente. Varias referencias @ exigen coincidencia con todas
y se excluyen de los resultados. Sin criterios explícitos se usa género y
compatibilidad Camelot; no implica similitud sonora ni lectura del master.

Cada respuesta ofrece preguntas o accesos sugeridos. El chat conserva en la
interfaz una referencia seleccionada y los últimos cuatro mensajes (hasta 500
caracteres por mensaje) para mantener contexto reciente. No es memoria permanente.
El historial se limpia al cargar otra colección; la referencia se invalida también
ante resultados ambiguos/múltiples. Una consulta desconocida pasa al modelo local si
está habilitado; errores/ambigüedades detectados por el parser no se relajan
mediante IA. La salida del modelo debe superar el esquema y validación determinista.

MCP también expone `library.diff` y `setlist.audit`; todavía no tienen flujo
conversacional. `library.similar` y `library.multisearch` son intents del chat,
no nuevas herramientas MCP. No se admiten comandos de shell ni envío externo de
datos por decisión del modelo. Creación nativa de playlists, cierre asistido y
restauración se revisan y confirman desde Configuración; el borrado recuperable
de música y base sigue pendiente. El asistente no promete permisos o funciones
que no estén implementados.

## Conversación abierta con el modelo local

También admite preguntas de organización, preparación, diagnóstico y uso de
Rekordbox: `¿Cómo organizo mi colección para preparar un set de una hora?`,
`¿Cómo preparo la preescucha en auriculares?` o `¿Qué debería revisar antes de tocar?`.
El servidor aporta estadísticas reales del XML, géneros/artistas frecuentes,
playlists y una muestra acotada de pistas relevantes. Los datos comprobados se
renderizan por código; el consejo general del modelo aparece identificado como
orientación y no equivale a documentación oficial verificada. Si la IA selecciona
una herramienta admitida, su petición pasa por el esquema y las mismas reglas
del motor determinista. No recibe acceso libre al sistema ni permiso para borrar.
Sin modelo disponible se informa la limitación; búsqueda y auditoría siguen funcionando.
