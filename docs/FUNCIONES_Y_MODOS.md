> Documento de diseño previo. Para estado implementado y verificado al 2026-09-23, leer `COBERTURA_PROMPT_ORIGINAL.md`, `REPORTE_VALIDACION_FASE2.md` y `EMPAQUETADO_WINDOWS.md`. Las propuestas aquí no implican funciones disponibles.

# Diccionario de consultas y reglas de disponibilidad

Estados: **cualquiera** = abierta/cerrada si existe snapshot XML legible; **abierto** = Rekordbox iniciado y, cuando se requiere, señal en vivo vigente; **cerrado** = cierre inequívoco de todos los procesos que acceden a la DB; **manual** = importación desde la UI de Rekordbox hecha por el DJ. El bloqueo se hace tanto en la UI como en backend, con razón visible. Cada tool con datos faltantes devuelve preguntas específicas, alternativas declaradas y vista previa.

| Pedido en lenguaje natural | Tool propuesta | Estado | Resultado y condición |
| --- | --- | --- | --- |
| «¿Qué playlists tengo?», «buscá los tracks de X» | `playlist.list`, `library.search` | Cualquiera | XML/snapshot con hora/revisión; mostrar antigüedad |
| «Compará X e Y», «encontrá temas duplicados» | `playlist.compare`, `library.duplicates` | Cualquiera | Diferencias por ID/ruta normalizada, sin borrar |
| «Uní X e Y y subí de 124 a 130 BPM» | `playlist.plan` | Cualquiera | Vista previa, deduplicación, restricciones y motivos |
| «Armá una curva de energía creciente» | `playlist.plan` | Cualquiera | Energía manual/analizada verificada; sin dato: consultar modo proxy explícito |
| «Agrupá mis mejores temas de tech house de 60 minutos» | `playlist.plan` | Cualquiera | Duración aproximada, tags/rating existentes, nunca inventar |
| «Creá la playlist llamada Warm Up» | `playlist.export_xml` | Cualquiera | XML nuevo para Bridge; luego importar manualmente |
| «Aplicá directamente esa playlist a mi colección» | `playlist.apply_native` | Cerrado | **Fase posterior**, backup validado y adaptador certificado; si no existe, ofrecer XML |
| «¿Qué sigue ahora?» | `recommend.manual` | Cualquiera | El DJ indica track actual, recomendaciones explicadas |
| «Avisame la próxima canción compatible» | `recommend.live` | Abierto | Solo si hay `NowPlaying` confiable, fresco y opt-in; si no, bloqueado |
| «Activá/pausá avisos de BPM, energía y género» | `notification.configure` | Cualquiera | Intervalo, umbral, géneros permitidos, volumen de alertas |
| «Mostrame key, BPM y género de esta pista» | `track.describe` | Cualquiera | Procedencia por campo; advertir valores ausentes |
| «Qué tracks carecen de tono/BPM/ruta» | `library.audit` | Cualquiera | Diagnóstico y lista de acciones no destructivas |
| «Qué cambió desde mi última exportación» | `library.diff` | Cualquiera | Revisión comparada, sin inferir track audible |
| «Evitá repetir lo que ya sonó esta noche» | `history.exclude_recent` | Cualquiera | Historial disponible con origen y frescura |
| «Qué transición harías de A a B» | `transition.explain` | Cualquiera | BPM/key/género/energía + incertidumbre |
| «Armá plan B si el ambiente baja» | `setlist.branch` | Cualquiera | Variantes de set con ramas, sin accionar deck |
| «Marcá los cortes de energía de mi set» | `setlist.audit` | Cualquiera | Alertas de salto, cansancio de artista y repetición |
| «Estimá energía de mis MP3 locales» | `audio.analyze_local` | Cualquiera, fuera de sesión | Análisis local opt-in, progreso, CPU limitada, fuente del score |
| «Explícame por qué elegiste estas tres» | `recommend.explain` | Cualquiera | Factores y comparación con candidatas descartadas |
| «Exportá el informe del set» | `setlist.export_report` | Cualquiera | Archivo JSON/CSV/HTML local con revisiones |
| «Sincronizá mi música con USB» | `device.export` | No habilitado en v1 | No modificar medios montados/en uso; desarrollo aparte |

Para consultas como «hacé lo que quieras», el chat debe convertir la idea en propuesta acotada que el usuario aprueba. Historial, cues, loops, MyTags y ratings nativos solo aparecen como herramientas cuando el adaptador instalado certifique formato y backup en la versión detectada. La configuración debe mostrar «Disponible», «Necesita Rekordbox cerrado», «Necesita Rekordbox abierto», «Faltan datos/sensor» o «En desarrollo».

## Ejemplo de interacción esperada

Usuario: «Recorré las playlists Warm y Peak y creá otra que empiece en 122 BPM, crezca hasta 129 y tenga tech house, sin repetir artista seguido».

Respuesta del agente: «Encontré 142 pistas en 2 playlists y 11 sin BPM. Propongo 16 temas de 122 a 129 BPM. Tres cambios de tonalidad requieren escucha previa. Te muestro el orden, alternativas y duración estimada. Puedo exportar ahora un XML nuevo para importar con Bridge; para aplicar directamente sobre la DB necesito que Rekordbox esté cerrado y que la versión de la base sea compatible».

En set en vivo: «Pista actual confirmada por [proveedor], observada hace 2 s. Siguiente sugerencia: [pista], +1 BPM, tonalidad vecina, género compatible. Alternativas: ...». Si la detección es insuficiente: «No sé con seguridad qué está sonando; elegí el tema actual para recomendar manualmente».
