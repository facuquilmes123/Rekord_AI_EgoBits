# Instalar Rekord AI

> **0.3.4 verificada en esta PC (2026-10-01):** instalación completa,
> reinstalación, arranque nativo y análisis Defender aprobados con protección
> activa. No usar el Setup 0.3.3 anterior. La distribución pública sigue
> pendiente de firma y validación Windows limpio; ver `docs/DEFENDER_034.md`.

La entrega de usuario es **un único `Rekord_AI_Setup_0.3.4_x64.exe`**.
Incluye la aplicación, el modelo de IA, el motor local y el componente WebView2.
No requiere Python, Rust, Node, Ollama, cuenta, clave de API ni PowerShell.

1. Abrir el instalador con doble clic.
2. Elegir la carpeta y avanzar con **Siguiente**.
3. Elegir si se desea acceso directo e inicio automático con Rekordbox.
4. Pulsar **Instalar** y esperar la copia y verificación del modelo incluido.
5. Pulsar **Finalizar** y abrir Rekord AI desde el menú Inicio o el escritorio.

No se descarga el modelo durante la instalación ni en el primer arranque.
El modelo ocupa aproximadamente 2,74 GB; el asistente necesita espacio adicional
para la aplicación y temporales. El inicio automático opcional se activa en el
próximo inicio de sesión de Windows. La primera biblioteca mostrada es de demostración;
seleccionar un XML exportado por el DJ desde **Configuración > Explorar XML** para usar datos propios, sin escribir rutas. El botón de configuración llama la atención mientras falta una colección propia. Revisar `MEJORAS_030.md` para las funciones disponibles y pendientes.

Desinstalar desde **Configuración de Windows > Aplicaciones**. La biblioteca del DJ
y sus XML originales no forman parte del instalador. Los ajustes del usuario se
conservan fuera de la carpeta de aplicación; no se eliminan datos personales.

## Estado de validación

La matriz de cierre y el reporte `output/closure/single-installer.json` indican si
el EXE ya fue compilado y qué pruebas de instalación se ejecutaron. Un build correcto
no certifica por sí solo Windows 10/11 limpio ni las funciones de Rekordbox/FLX4.
La compilación local no tiene certificado comercial de firma de código; no se presenta
como una release pública firmada.

## Solo para desarrollo

`install_msvc_admin.ps1`, `build_backend.ps1` y `build_single_installer.ps1` son
herramientas de compilación de esta PC. **No son pasos de instalación del usuario.**
La entrega previa ZIP + `install_model.ps1` queda como mecanismo técnico de ensayo,
reemplazada para usuarios por el asistente único Inno Setup. El shell continúa siendo Tauri.


## Crear una playlist en tu colección real

En Preparar un set, seleccioná las canciones (máximo 100) y el nombre. Cerrá Rekordbox y salí de sus agentes desde la bandeja. En Configuración, usá Crear playlist en Rekordbox con respaldo. Aceptá el respaldo automático obligatorio, revisá la propuesta y confirmá Aplicar playlist. Esperá el aviso final antes de abrir Rekordbox.

En Respaldos y recuperación, Ver mis respaldos permite elegir y restaurar una colección previa. La restauración deshace cambios posteriores; antes se respalda el estado actual. Los backups conservan la base cifrada y masterPlaylists6.xml, no los archivos de música. Si se interrumpe una escritura, cerrá Rekordbox y restaurá el respaldo pendiente.


## Actualizar una versión anterior

El mismo Setup sirve para instalar por primera vez y actualizar. Antes de actualizar, esperá que terminen las operaciones y usá Salir en el icono de Rekord AI junto al reloj. Cerrar/minimizar la ventana mantiene el agente activo. Ejecutá el nuevo Setup y seguí el asistente; no necesitás desinstalar ni abrir PowerShell. Se conservarán carpeta previa, preferencias y respaldos. Un instalador anterior no puede reemplazar una versión más nueva.

Para cerrar Rekordbox antes de escribir, Configuración → Cerrar Rekordbox y sus agentes solicita cierre normal con confirmación. Si Rekordbox pide guardar o un agente no se cierra, seguí las instrucciones y reintentá. Nunca se habilita la escritura sólo por haber solicitado el cierre.
