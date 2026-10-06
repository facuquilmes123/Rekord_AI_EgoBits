# Interfaz de escritorio y detección — 2026-10-01

## Implementación

- Interfaz clara con navegación lateral, chat inicial, composición multilínea, atajos Enter/Shift+Enter, foco visible y modo de movimiento reducido.
- Logo conservado. Shell Tauri, cierre a bandeja y menú nativo no cambiados.
- Detección de ejecutables mediante registro Windows (usuario/equipo, vistas 32/64 bits) y directorios conocidos sin lista fija de versiones.
- Localización de configuración Pioneer/Pioneer DJ/AlphaTheta, masterDbDirectory y db-path de Rekordbox Agent. La base sólo se localiza: no se abre ni modifica.
- Exportaciones declaradas por CollectionAutoExportXmlFile aparecen como candidatas; elección explícita evita cargar una colección equivocada. Sin exportación, se solicita el XML con instrucciones concretas. Preferencias existentes se conservan.
- No se recorren indiscriminadamente discos ni archivos personales. Una instalación portable fuera del registro/directorios conocidos puede no encontrarse. Detectar una versión futura no certifica su formato.

## Evidencia

- En esta PC: Rekordbox 7.2.19 y master.db localizados mediante API y visibles en Configuración.
- Navegador real: pantalla inicial inspeccionada; configuración/detección visible; consulta de auditoría responde 6 pistas y 91,7% en demo; planificador devuelve 4 pistas de 124 a 128 BPM. No se exportó ni modificó la biblioteca personal.
- Suite: 92 pruebas ejecutadas sin fallos, 1 omitida por extra MCP no instalado en este entorno (91 aprobadas). Log: output/closure/verify-ui-20261001.log.
- node --check app.js: código 0.
- Tres pruebas de descubrimiento: entorno vacío, versión futura/directorio de base trasladado, configuración dañada.
- El instalador previo del 24/09 se conserva en dist/archive-20260924.

## Límites

Pendiente: validación visual de bandeja/Toast en Windows nativo, equipos limpios Windows 10/11 y lectura certificada de las diferentes bases nativas. La nueva UI sigue usando el adaptador XML existente. No se promete compatibilidad universal con toda versión de Rekordbox ni carga automática desde una base cifrada.

La exportación XML está documentada por el fabricante: https://rekordbox.com/en/support/faq/rekordbox7/ (File > Export Collection in xml format). La ruta de importación XML es una fuente externa y no debe confundirse con una exportación actual de la colección del usuario.

## Instalador actualizado

Build Tauri release e Inno finalizaron con código 0.

Archivo: `dist/Rekord_IA_Setup_0.2.0_x64.exe`

SHA-256: `1606d53a397ea9a21dc0c376f2d436d1f20602f39899daeac338353835e05623`

Tamaño: 2984700495 bytes.

La instalación/desinstalación del 24/09 corresponde al artefacto archivado, no a este nuevo hash. El nuevo instalador no se reinstaló en este turno. Sin firma digital.
