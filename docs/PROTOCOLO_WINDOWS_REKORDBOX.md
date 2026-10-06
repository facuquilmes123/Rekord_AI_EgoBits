# Pruebas externas reproducibles

Estado: **preparadas, no ejecutadas en Windows limpio ni dentro de Rekordbox**.
No confundir el kit ejecutable del backend con un instalador Tauri.

## 1. Backend en Windows 10/11 x64 sin herramientas

Usar una VM descartable con usuario local estándar. Anotar edición/build de Windows,
RAM, CPU, versión de PowerShell y fecha. Extraer completo el kit QA ZIP64; verificar
el SHA-256 externo antes de abrirlo. No requiere Python, Node, Rust, Ollama ni cuenta.

Deshabilitar la NIC desde la configuración de la VM. El script comprueba que no haya
adaptadores activos; no cambia la red del equipo. Ejecutar desde el kit extraído:

```powershell
powershell -NoProfile -File .\installer\test_portable_backend.ps1 -Backend .\egobits-backend.exe -ResourceRoot . -RequireOffline
powershell -NoProfile -File .\installer\test_bridge_fixture.ps1 -Backend .\egobits-backend.exe -Fixture .\fixture
```

Guardar `evidence.json` en la ruta que imprime cada prueba. La primera prueba usa
perfil temporal, PATH limitado a System32, token efímero, inferencia real, comparación
tipada, exportación y cierre. **No instala ni valida bandeja o WebView2.**
El muestreo de CPU/RAM del equipo de desarrollo está en `output/closure/frozen-smoke.json`;
repetir mediciones en la VM con Administrador de tareas y anotar procesos backend/llama.

Alternativa para un equipo con Windows Sandbox habilitado:

```powershell
powershell -NoProfile -File .\installer\prepare_sandbox.ps1 -Kit .
```

Abrir el `.wsb` creado. La red se deshabilita en la configuración del sandbox;
`sandbox-evidence/` recoge el resultado. Esta configuración no se ejecutó en el host
actual: WindowsSandbox/Get-VM/VBoxManage/vmrun no aparecieron entre los comandos disponibles.
Sandbox hereda la versión del host; **no sustituye la VM Windows 10**.

## 2. Instaladores NSIS/MSI (gate pendiente)

No hay instaladores generados. Tras instalar MSVC/SDK y obtener build código 0:

1. Conservar snapshot limpio de cada VM y ejecutar los controles del punto 1 con NIC deshabilitada.
2. Extraer `Rekord_AI_EgoBits_Windows_offline.zip`; registrar SHA-256 del ZIP y del instalador.
3. Ejecutar primero el NSIS. Repetir con MSI en un snapshot independiente.
   Para MSI se puede capturar log con `msiexec /i "RUTA.msi" /L*V "install.log"`.
   Seguir el diálogo normal; no ejecutar instaladores silenciosos sobre el equipo personal.
4. Registrar instalación de WebView2 cuando no existía. Verificar que no hubo descarga:
   NIC deshabilitada durante toda la prueba y ninguna conexión requerida para finalizar.
5. Ejecutar `installer/install_model.ps1` desde la entrega. Verificar hash de la copia local.
6. Abrir app; probar chat con «¿Hay canciones en común entre ROOT/X y ROOT/Y?» y
   confirmar estado IA lista, comparación real y exportación. El parser solo no prueba inferencia.
7. Cerrar ventana: debe seguir en bandeja. Probar Mostrar/Ocultar, Silencio, desactivar push,
   persistencia al reabrir y Salir. Tras Salir no deben quedar backend/llama de esta app.
8. Probar inicio con Rekordbox mediante `register_autostart.ps1` únicamente en la VM.
   Salir de EgoBits con Rekordbox abierto no debe relanzarlo hasta el próximo inicio de Rekordbox.
9. Reinstalar. Confirmar ajustes/modelo conservados sin duplicar procesos.
10. Desinstalar desde Aplicaciones de Windows; verificar archivos, acceso directo, procesos
    y registro de autostart. Registrar lo que persiste en LOCALAPPDATA (modelo/ajustes) y
    retirar autostart con `register_autostart.ps1 -Remove` si se habilitó.

Adjuntar acta con PASS/FAIL/NO PROBADO por paso, captura de versión, logs y hashes.
No marcar Windows 10/11 aprobado por una ejecución en una sola versión.

## 3. XML Bridge con audio propio de ensayo

El fixture contiene tres tonos WAV generados por el proyecto, metadatos Unicode,
rutas con espacios, BPM 120/122/124, tonalidad Am, TEMPO 0 y hot cue A en 1,5 s.
El volumen de los tonos es bajo; comenzar con salida moderada. No contiene música personal.
`test_bridge_fixture.ps1` crea un directorio `run-UUID`, ajusta las rutas al lugar de
extracción, genera `export.xml` con el EXE y registra hashes antes/después del XML fuente.
No toca `master.db`. Cada ejecución preserva las anteriores.

Rekordbox detectado en este equipo: **7.2.18.0**. Rekordbox 6 no fue encontrado en
la carpeta de instalación inspeccionada; no se afirma compatibilidad validada con 6.

En una cuenta Windows/colección de ensayo aislada:

1. Anotar versión exacta de Rekordbox y guardar captura. Conservar la carpeta del fixture.
2. En preferencias, habilitar la vista `rekordbox xml` y elegir el `export.xml` generado
   como biblioteca XML importada. La documentación oficial del Bridge lo denomina
   **Preferences > Bridge > Imported Library**; la ubicación visual puede cambiar por versión.
3. Abrir la playlist `EgoBits Bridge QA` de esa biblioteca. Verificar 3 entradas y orden
   `Peña & Percusión`, `Noche 東京`, `Último <ritmo>`; títulos y artistas sin caracteres corruptos.
4. Importar únicamente esa playlist a la **colección de ensayo**. Si la sesión muestra
   la colección personal, detener aquí: este protocolo no autoriza modificarla.
5. Cargar y escuchar cada WAV, comprobar duración de 8 s, archivo localizable,
   BPM indicado, grid en 0 y hot cue A `Entrada ñ 東京` en 1,5 s. No autorizar
   sobrescritura de análisis de pistas personales ni manipular decks en un set.
6. Guardar capturas de playlist/track/grid/cue. Recalcular hash de `source.xml` y
   compararlo con `evidence.json`. Completar un acta separada para RB7 y RB6.

La validación XML automatizada es estructural. La conservación efectiva del grid/cue
en Rekordbox solo queda aprobada tras estos pasos. Fuentes:
[Bridge oficial](https://rekordbox.com/en/support/developer/) y
[especificación XML](https://cdn.rekordbox.com/files/20200410160904/xml_format_list.pdf).

## 4. FLX4 y señal audible

Actualmente no hay proveedor real habilitado. Push queda **BLOQUEADO**; el recomendador
manual está disponible. No se detectó un dispositivo presente con nombre FLX4 en la inspección.
Historial, pista seleccionada, MIDI y proceso abierto no demuestran audio audible.

Antes de habilitar un proveedor: registrar identidad, reproducción, marca temporal y
correspondencia con salida master. Probar dos decks, volumen cero, crossfader a ambos
extremos, cambio de master, pausa, pista resaltada sin reproducir, pérdida de señal y
recuperación. Medir falsos positivos y latencia; confianza >85 % y frescura <5 s son
gates del contrato, no mediciones alcanzadas. No se inyectan DLL ni se controlan decks.
