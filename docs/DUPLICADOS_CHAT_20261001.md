# Duplicados completos y búsquedas combinadas — 2026-10-01

## Estado de entrega

Cambios locales en código, posteriores al instalador 0.3.4. Ese instalador y la
aplicación ya instalada todavía no incluyen esta iteración. No se modificaron
la base real, el XML fuente ni archivos de música del DJ. No se añadieron dependencias.

## Verificación de duplicados

- Un clic en **Mi colección → Verificar toda la colección** procesa todas las
  referencias del XML cargado. Lee SHA-256 completo de cada audio disponible,
  incluso si no coincide su nombre. Una misma ruta inalterada se lee una vez.
- Trabajo en segundo plano, progreso de referencias/archivos/bytes, cancelación
  y recuperación del estado al recargar la interfaz mientras el backend siga vivo.
- Orden descendente por puntaje: 100 para contenido idéntico; 50 por título y
  artista; +20 por duración dentro de un segundo; +10 por BPM dentro de 0,1;
  +5 por tonalidad. Es un puntaje de evidencia, no probabilidad estadística.
- Hashes distintos pueden corresponder a la misma grabación con etiquetas o
  codificación diferentes. Esta iteración no reconoce igualdad de PCM entre formatos.
- Los errores de acceso, archivos ausentes, vacíos, no locales o no admitidos
  se informan por ID. No se presentan como verificados.
- Regla configurable **mayor o igual al porcentaje**: muestra referencias,
  archivos candidatos y pista conservada. Conserva la más utilizada en playlists
  del XML, con desempate por ID. La elección aún no tiene estadísticas nativas.
- Sólo grupos con hash idéntico y cues/beatgrids iguales entran en esa propuesta.
  Las referencias al mismo archivo lo conservan. Metadatos parecidos y cues
  diferentes quedan protegidos; la interfaz explica los motivos.
- Un XML cambiado, trabajo cancelado o archivo candidato modificado invalida
  la propuesta. La regla es sólo revisión, no autorización de escritura.

### Pendiente para eliminar de la base y Windows

El endpoint de eliminación continúa rechazando borrados. No se puede reutilizar
el respaldo actual de playlists como recuperación de música: sólo contiene
master.db y masterPlaylists6.xml. Falta implementar y probar en conjunto:

1. Correspondencia única con registros nativos actuales, incluyendo rutas
   compartidas y dependencias de cues, historial, tags, playlists y sincronización.
2. Preparación sobre copia cifrada, eliminación de dependencias y actualización
   de registros USN con invariantes de todas las filas que se conservan.
3. Respaldo verificado de cada audio retirado y retiro recuperable, con exclusión
   Windows para impedir cambios entre verificación y aplicación.
4. Un diario común para base/audio: fallos parciales, apagado y restauración sin
   sobrescribir archivos que aparezcan después. Restaurar música antes de publicar
   una base que vuelve a referenciarla.
5. Pruebas sobre copias, confirmación explícita del detalle y Rekordbox/agentes
   cerrados antes de habilitar la aplicación real.

Referencias investigadas: [API de pyrekordbox](https://pyrekordbox.readthedocs.io/en/stable/generated/pyrekordbox.db6.html)
y [remove de rekordbox-edit](https://rekordbox-edit.readthedocs.io/en/latest/commands/remove/).
La dependencia instalada pyrekordbox 0.4.4 no ofrece delete_content; su delete
genérico no sustituye la gestión completa de dependencias. El segundo proyecto
describe retiro irreversible de audio y sin undo: no se instaló ni ejecutó, y
no se incorporó su flujo como mecanismo de recuperación.

## Chat: búsqueda filtrada

La frase completa se estaba buscando como texto de título/artista/género, por
eso no encontraba canciones. Ahora genera una búsqueda tipada con filtros
separados, también admitidos y validados en la salida del modelo local:

`buscar en coleccion una pista techhouse de 124 bpm con tonalidad 8a y buena energia`

- Género Tech House, normalizando espacios/guiones y escritura `techhouse`.
- BPM 123,9–124,1: tolerancia explícita de 0,1 para metadatos decimales.
- Camelot 8A, con validación 1A–12B.
- Buena/alta energía = mínimo 7/10, informado en la respuesta.
- Energía sólo si existe valor con fuente registrada. Si no hay coincidencias
  completas, ofrece alternativas que cumplen los demás filtros y las identifica
  como **sin confirmar energía**. No inventa energía por BPM ni relaja filtros
  silenciosamente.
- También admite rangos BPM (`entre 123 y 126 bpm`), energía baja/media/alta o
  mínima numérica, y conserva las búsquedas por título/artista.
- Este caso se interpreta offline sin arrancar el modelo. El modelo conserva
  el contrato restringido; números no finitos, booleanos como números, rangos
  invertidos y tonalidades inválidas se rechazan.

## Evidencia

- `python scripts/verify_kit.py`: **150 pruebas aprobadas**, cero omisiones;
  29 archivos upstream verificados. Log: `output/closure/verify-duplicate-search-final.log`.
- 11 pruebas nuevas de duplicados y 9 de búsquedas filtradas.
- `node --check prototype/egobits/desktop/ui/app.js`: código 0.
- QA de navegador sobre seis archivos sintéticos: análisis 6/6; regla 100 con
  un archivo candidato y un grupo de cues protegido; regla 80 conserva protección
  de cues y agrega la de metadatos. Cero archivos eliminados.
- QA del chat con la frase original: alternativas visibles por género/BPM/key,
  con advertencia de energía faltante.
- Consulta de sólo lectura sobre el XML real de **23.482 pistas**: una cumple
  género/BPM/8A pero carece de energía registrada; cero coincidencias completas,
  una alternativa ofrecida. No se escaneó toda la música real ni se probó borrado.
- Se corrigió la prueba de autenticación para usar el XML de ejemplo y no
  depender del tamaño de la colección privada: el primer pase de 150 pruebas
  tuvo timeout al cargarla; el pase final completo terminó con código 0.
- Se corrigió CSS: botones con atributo hidden se ocultaban incorrectamente
  por reglas de display de la clase btn.

La comprobación audible del master real, recuperación nativa de música, firma
de distribución y validación en Windows limpio siguen pendientes.
