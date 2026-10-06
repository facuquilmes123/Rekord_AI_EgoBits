# Defender y entrega local 0.3.4 — 2026-10-01

## Actualización del caso Microsoft

Nueva lectura del portal tras pulsar Refresh: estado **In progress** y
**Final determination: Pending**. El analista informa que sus analizadores
no detectan malware ni indicadores de telemetría para la muestra enviada,
y plantea cerrar el envío sin más acciones. Esto corresponde a la recompilación
limpia 0.3.3; no certifica el ejecutable original en cuarentena ni el Setup.
El portal mantiene No malware detected en Cloud/Client, inteligencia 1.459.505.0.

Si persiste la detección original, Microsoft pide un diagnóstico Defender CAB.
No se generó ni envió: la autorización del DJ abarca únicamente el ejecutable,
no logs del equipo. El alcance y contenido de cualquier diagnóstico requieren
revisión y autorización específica antes de compartirlo.

## Resultado

`dist/Rekord_AI_Setup_0.3.4_x64.exe` se compiló, analizó e instaló correctamente
en este host. La aplicación instalada abrió su ventana nativa y cargó la
colección configurada. Defender Antivirus y protección en tiempo real quedaron
activos (modo Normal, inteligencia 1.459.501.0). Los scans posteriores de los
ejecutables instalados no encontraron amenazas; no se registraron detecciones
nuevas durante instalación/arranque. No se desactivaron protecciones, agregaron
exclusiones ni restauraron archivos en cuarentena.

SHA-256 Setup: `62ca6a65573c8ba38592f62bbc79f838afc1ac84fed0b98733ea555aadb54fba`.
Shell: `14e506f9e629a4bda5d375886648b2db549944910ced2eaab7cdecfa472fb008`.
Backend: `234c33f19711ba075fb78f424fab89baced7e9cab5d1b8f07e40183031602ed3`.

## Trabajo realizado

- Se limpiaron los artefactos del paquete Rust de la aplicación antes de
  recompilar el mismo código 0.3.3 para diagnóstico. Se reutilizó el cache de
  compilación de dependencias: no fue un build completo en VM limpia.
- Auditoría de 481 archivos de paquetes Cargo y sus 25.322 archivos extraídos
  contra hashes de Cargo.lock: sin diferencias. Esto comprueba integridad
  respecto del lock, no certifica inocuidad de dependencias, toolchain o binario.
- La recompilación 0.3.3 pasó Defender; su hash difiere del original. No se
  identificó una línea de código como causa cierta de la alerta original.
- Se incorporaron gates antivirus al empaquetado, hashes shell/backend al
  instalador, verificación tras copiar y antes de arrancar, y diagnóstico claro
  para componentes ausentes/bloqueados. Los gates también detectan cambios
  de archivo durante un scan y fallan si el análisis no termina correctamente.
- Se generó 0.3.4 para incorporar esos cambios de instalador y coherencia de
  versión. La lógica musical y las reglas de escritura segura se conservaron.
- El script de build exige suite previa y Cargo locked/offline. No se
  ofuscaron binarios ni se modificó el código para eludir detecciones.

## Evidencia

- `output/closure/rust-supply-chain-audit.json`: auditoría de integridad.
- `output/closure/defender-clean-baseline-build.log`: build 0.3.3, código 0.
- `output/closure/defender-clean-baseline-scan.log`: sin amenazas en baseline.
- `output/closure/verify-034-final.log`: 130 pruebas, 129 aprobadas y una omitida
  por extra MCP. Primera corrida tuvo timeout en HTTP de un test de autenticación;
  repetición y corrida final completas aprobadas. No se ocultó el fallo inicial.
- `output/closure/build-034-defender.log`: backend/Rust aprobados; primer ISCC
  falló con EndUpdateResource 110. Se conservó salida fallida como evidencia
  (`failed-034-resource-update.bin`), no como instalador utilizable.
- `output/closure/package-034-retry.log`: mismo empaquetado reintentado,
  compilación y análisis final aprobados, código 0.
- `output/closure/defender-payload.log`, `defender-installer.log` y
  `defender-installed-034.log`: análisis locales sin amenazas.
- `output/closure/full-install-1790882173837767300/result.json`: reparación
  completa y reinstalación 0.3.4 sobre 0.3.4, ambas código 0, registro de versión
  y hashes correctos. Se preservó el único archivo persistente existente
  (preferencias); no había backups nativos reales en estas carpetas para
  probar su conservación. Los sentinelas de backup se probaron en fixture Inno.
- `output/closure/rekord-ai-034-installed.png`: ventana del EXE instalado.

No se cerró Rekordbox ni se escribió en su colección durante las pruebas.
El ensayo real actual no demuestra un upgrade desde una instalación 0.3.3 sana
(Defender había eliminado su registro); esa ruta está cubierta sólo por fixture.
Windows limpio, WebView2 ausente e Internet desconectado quedan sin certificar.

## Revisión de Microsoft

Con autorización del usuario se envió sólo la recompilación 0.3.3 del shell;
el original sigue en cuarentena. El usuario inició sesión y completó CAPTCHA.
El informe aclara que no es byte idéntico al original e incluye ambos hashes.
No se envió colección, música ni configuración.

Caso: https://www.microsoft.com/en-us/wdsi/submission/dde2c020-dc63-4e4a-a0b2-c3172b85ff68

Última lectura: Submission Submitted, Final determination Pending;
Current detection: No malware detected (Cloud y Client), definición 1.459.505.0.
Eso no constituye un dictamen de falso positivo sobre la muestra original ni
una aprobación específica del Setup 0.3.4. Comprobante: `microsoft-submission.png`.

## Distribución pública

La instalación local está reparada y la app se dejó abierta. La firma
Authenticode sigue ausente; no hay certificado de firma disponible en los
almacenes revisados CurrentUser/My y LocalMachine/My. No se compró un certificado.
Antes de distribuir: firma con identidad confiable de editor, validación en
Windows 10/11 limpio y evaluación del resultado de Microsoft. La firma ayuda
a identificar al editor; no garantiza ausencia de malware ni cero advertencias.

Guía oficial de desarrolladores:
https://learn.microsoft.com/en-us/defender-xdr/developer-faq
