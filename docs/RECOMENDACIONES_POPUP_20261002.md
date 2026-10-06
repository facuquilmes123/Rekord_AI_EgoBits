# Recomendaciones y entrega al deck — 2026-10-02

## Implementación

### Referencia de reproducción

- Historial: lectura local de la base, espera entradas nuevas y resuelve por ruta una pista única del XML. Funciona independientemente de elegir ASIO o parlantes. El historial puede tener demora y no certifica el canal master. No se presenta como escucha real.
- Audio opcional: seguimiento continuo WASAPI de una selección de 2..20 pistas. Decodificación local con límites existentes, referencias acotadas a 256 MiB, ventanas de tres segundos y dos coincidencias consecutivas. Silencio, ambigüedad, antigüedad de cinco segundos, detención o cambio de colección deshabilitan el popup del piloto. Se detiene si Rekordbox no está fehacientemente abierto. No requiere ni modifica el driver del DJ.
- El popup de audio experimental requiere aceptación explícita; el puntaje espectral no se convierte en probabilidad de audibilidad. Pitch, time-stretch, EQ y mezclas siguen siendo limitaciones conocidas. No habilita Toast certificados.

### Sugerencias inteligentes

Sólo se toman candidatas de la colección cargada. Se mantienen los filtros configurables de margen BPM, Camelot, género, artista y energía. El género normaliza acentos, separadores y mayúsculas (Tech House/tech-house). Energía exige procedencia tanto en referencia como candidata.

La ordenación combina cercanía BPM (peso 40), armonía si está activada (35), coincidencia de género si la referencia lo tiene (15) y cercanía de energía si se configuró ese criterio (10). Los pesos activos se normalizan a 0..100. El género puede favorecer candidatas sin excluir otros géneros; la opción mismo género lo convierte en filtro obligatorio. Es un puntaje de compatibilidad por metadatos, no certeza de detección ni similitud sonora. Cada candidata incorpora diferencias y razones visibles en el popup.

### Popup y arrastre Windows

- Ventana independiente del tray, siempre visible sobre otras ventanas y sin solicitar foco al aparecer; posicionada en la esquina inferior derecha del área útil del monitor.
- Se activa desde Configuración o el menú del tray; respeta desactivación, Modo Silencio, intervalo y supresión de eventos repetidos. Se puede ocultar.
- El modo historial lleva una etiqueta explícita de master sin confirmar; sólo telemetría realmente confirmada conserva esa categoría y puede activar Toast.
- Cada tarjeta permite seleccionar y mantener el botón del mouse para arrastrar al deck. La transferencia usa el objeto de archivo del Shell de Windows, CF_HDROP/OLE y efecto COPY, sin mover ni borrar el original.
- El backend recibe ID + SHA de colección, nunca una ruta libre desde la interfaz/IA. Verifica la revisión del XML, pertenencia, archivo local, existencia y extensión de audio. Archivos ausentes, colección modificada y rutas remotas se rechazan.
- Soltar no equivale a iniciar reproducción ni prueba por sí solo que Rekordbox aceptó/cargó el deck. No se envían comandos para sustituir un deck que está sonando.

## Investigación de PulseDJ

La [web oficial](https://pulsedj.com/) indica lectura de biblioteca e historial. Su [explicación de funcionamiento](https://faq.pulsedj.com/what-is-automix) describe leer los archivos de historial de los programas DJ y copiar el nombre de la recomendación para buscarlo. Es evidencia de un flujo independiente de capturar ASIO, no evidencia de lectura certificada del master. No se asumió un protocolo privado ni una API pública inexistente.

Como referencia diferente, [Now Playing documenta on-air](https://nowplayingapp.com/help/guide/settings/on-air-detection/) mediante señales disponibles del mixer/controlador (faders, reproducción, EQ y banderas on-air). La cobertura depende del equipo. Incorporar esa ruta necesita detectar el equipo, mapear señales y validar audibilidad; no se implementó como si fuera universal.

El mecanismo de archivo nativo sigue [la documentación del Shell de Windows](https://learn.microsoft.com/en-us/windows/win32/shell/dataobject).

## Verificación

- `python scripts/verify_kit.py`: **190 pruebas aprobadas**, 29 archivos upstream verificados, código 0. `output/closure/verify-live-popup.log`.
- Rust: `cargo check --offline` y `cargo test --offline --locked` con código 0. Una prueba ejecutada en Windows obtiene CF_HDROP y confirma que contiene exactamente el archivo local con nombre `Canción ñ 日本語.wav`; no se simuló esa conversión. `output/closure/live-native-test.log`.
- JavaScript: sintaxis verificada para app, workspace y popup, código 0.
- Contrato de identidad/versión: 0.3.4 consistente. Dependencias Windows declaradas y fijadas a versiones ya presentes en Cargo.lock; compilación offline.
- Pruebas de comportamiento con fixtures: popup de historial etiquetado, candidatas locales, ausencia de archivos, silencio/configuración, referencias obsoletas, doble coincidencia y pérdida posterior, preferencia por compatibilidad conjunta, filtros y energía con fuente. No se alteraron datos reales ni se cerró Rekordbox.

## Pendiente de validación real y distribución

El nuevo popup y su interacción no se ensayaron aún sobre una sesión de Rekordbox: queda comprobar visualmente aparición sin robar foco, arrastre con mouse a cada deck y carga de la pista existente sin duplicar entradas. Tampoco se certificó el master ni una salida ASIO; el piloto sólo compara referencias seleccionadas.

Las recomendaciones por historial no son garantía de identificación instantánea de lo audible. Si se necesita on-air exacto, habrá que agregar y validar una fuente de señales del equipo o una ruta de master capturable. Estos cambios están en fuente posterior al Setup 0.3.4; **no se generó ni instaló un nuevo Setup en esta iteración**.
