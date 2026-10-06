# Consolidación en lote · 0.3.8

## Uso

1. Mi colección → Verificar toda la colección.
2. Elegir **50%, 70%, 85%, 90%, 95% o 100% hacia arriba**. Revisar la regla muestra qué se conservará y qué queda protegido.
3. Cerrar Rekordbox y sus agentes. Configuración dispone del cierre normal con confirmación; no se fuerza la terminación.
4. **Eliminar duplicados desde este porcentaje…** prepara automáticamente un respaldo de la base y una propuesta cifrada. Windows solicita la confirmación final.
5. Desde Configuración → Respaldos y recuperación se pueden recuperar conjuntamente la colección y la música retirada.

## Qué modifica

La operación conserva un registro por grupo seguro, remapea las membresías de playlists y el historial al ID conservado, y retira los registros nativos redundantes. No cambia el orden ni elimina membresías. Los archivos duplicados independientes se mueven, bajo bloqueo exclusivo, a `.rekord-ai-recovery/<operación>/` en su mismo volumen. Las referencias al mismo archivo no retiran ese archivo.

Se genera y carga un XML consolidado nuevo dentro del directorio de operación. El XML fuente del DJ permanece intacto. Se conservan las preferencias de energía existentes. El respaldo de la base sigue cifrado; no se persiste su clave.

La recuperación conserva los archivos y por eso **no libera su espacio en disco**. No se incorpora borrado irreversible de la carpeta de recuperación.

## Porcentaje y protecciones

El puntaje indica evidencia de coincidencia, no probabilidad de identidad. Elegir 50% incluye candidatos en la revisión; no autoriza a borrar grabaciones distintas sólo porque se parecen sus metadatos. La ejecución exige SHA-256 completo idéntico, correspondencia exacta ID/ruta con la base actual y compatibilidad nativa.

Se protegen grupos con cues XML distintos, metadatos nativos diferentes, análisis ANLZ distintos, cues/tags/dependencias nativas sin consolidación certificada, vínculos de sincronización, referencias desconocidas, enlaces de archivos, rutas alteradas o archivos cambiados. **No se afirma que todos los grupos al 100% puedan eliminarse automáticamente.** La comparación normalizada de ANLZ, la fusión de cues nativos y la identidad acústica entre formatos diferentes quedan pendientes.

La publicación requiere estado cerrado comprobado, ausencia de WAL/SHM, espacio suficiente, respaldo SHA verificado, integridad SQLCipher, esquema compatible, propuesta vigente y aprobación HMAC emitida por el shell nativo. La interfaz no puede autorizar la operación por sí sola.

## Recuperación

La base y la música permanecen bloqueadas durante publicación y rollback. El diario persistente marca `publishing` antes del primer movimiento. Un fallo intenta restaurar ambos; si no puede, bloquea operaciones nuevas hasta recuperar. Tras reiniciar, la restauración localiza cada archivo en su origen o recuperación, verifica su SHA y no reemplaza rutas ocupadas.

Una base truncada sólo puede recuperarse sin leer su esquema actual si existe un recibo válido de publicación interrumpida y el esquema del respaldo coincide con el certificado de esa operación. Una restauración normal sigue rechazando cambios de esquema.

## Evidencia

- `prototype/tests/test_duplicate_publication.py`: 12 pruebas de correspondencia, conservación de orden/historial, protección ANLZ/metadatos/vínculos, Unicode con emoji, bloqueo exclusivo, rutas ocupadas, cambio de contenido, publicación SQLCipher, recuperación conjunta, fallo intermedio, reinicio y base truncada.
- `output/closure/release-038/final-source-suite.log`: 226 pruebas, 225 aprobadas y 1 omitida por MCP opcional. 29 archivos upstream y activos offline verificados.
- `output/closure/release-038/metadata-qa-b3fa2dde38674b3bb7966e22712c2a88/evidence.json`: backend congelado 0.3.8, interfaz de eliminación en lote, rechazo de eliminación sin aprobación, recomendaciones sin captura, XML real intacto.

Las pruebas de escritura usan una base cifrada y música de ensayo. No se modificó la base, música ni configuración personal del DJ, y no se cerró Rekordbox. La reapertura e inspección de una colección consolidada en un Rekordbox real no se certifican con estos ensayos.

La lectura acotada de la base real confirmó los IDs del primer grupo de la captura (`137667990`, `255440920`): tienen títulos nativos y rutas de análisis ANLZ diferentes. Ese grupo queda protegido, aunque comparte un archivo y tiene score 100%; no se borrará su único archivo de música. Evidencia sin escritura: `output/closure/release-038/screenshot-pair-readonly.json`.
