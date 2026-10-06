# Investigación: instalador único offline x64 de aproximadamente 3 GB

Fecha de consulta: 2026-09-24. Alcance: viabilidad y configuración de Inno Setup; no se construyó, instaló ni firmó ningún artefacto.

## Veredicto

**Es viable un único `Setup.exe` offline para Windows 10/11 x64 con Inno Setup 6.5.4** si el tamaño **comprimido final**, incluidos el GGUF, Tauri, sidecars y WebView2, queda por debajo de **4.200.000.000 bytes**. La cifra aproximada de 3 GB está dentro del límite, pero el criterio de aceptación debe ser el tamaño del EXE que emite ISCC, no la suma estimada de los archivos fuente.

Inno Setup 6.5.2 eliminó el límite anterior de casi 2 GB y elevó el máximo de un `Setup.exe` sin disk spanning a “nearly 4 GB”, cercano al máximo de Windows. La documentación actual precisa que `DiskSpanning=yes` es obligatorio desde 4.200.000.000 bytes comprimidos. Por tanto, un resultado cercano a 4 GB tiene poco margen y no debe prometerse como EXE único hasta medirlo en el build reproducible.

**Recomendación concreta:** usar **Inno Setup 6.5.4** si se quiere congelar la variante evaluada y el artefacto final queda cómodamente por debajo de 4.2 GB; usar `DiskSpanning=no` y conservar el GGUF dentro de `[Files]`. No se recomienda pasar a `DiskSpanning=yes` para este requisito, porque genera `Setup-*.bin` adicionales y deja de ser un único EXE. Si el build llega al límite, el alcance debe cambiar a varios archivos locales o reducir el payload, no intentar forzar el formato.

Inno Setup 7.1.0 es más nuevo y ofrece un compilador/instalador x64 y mejor compresión en equipos x64, pero no es necesario para resolver el límite de tamaño. Para no introducir ese cambio de generación sin necesidad, 6.5.4 es la opción reproducible mínima para este objetivo. La decisión puede revisarse si la memoria de compilación o el tiempo LZMA resultan insuficientes.

## Licencia y pago

La licencia oficial de `issrc` concede permiso para usar, modificar y redistribuir el software para **cualquier propósito, incluidas aplicaciones comerciales**. Sus condiciones son mantener avisos de copyright y URLs al redistribuir binarios, no atribuirse la autoría de Inno Setup y marcar versiones modificadas. No establece una compra o pago obligatorio.

Las notas de versión recientes muestran el mensaje “Using Inno Setup commercially? Please purchase a license.” y describen licencias comerciales con dos años de actualizaciones. Eso es una solicitud de apoyo/comercial, no una sustitución de la concesión explícita de la licencia. En consecuencia: **no hay una licencia de pago obligatoria para compilar o distribuir este producto con Inno Setup**, aunque comprarla es coherente con el pedido oficial para uso comercial. Esta conclusión debe conservar el `license.txt` de la versión efectivamente fijada junto con el build, por trazabilidad.

## Directivas relevantes

Propuesta de base para el futuro `.iss`; es una guía de investigación, no una modificación aplicada:

```iss
[Setup]
AppName=Rekord AI EgoBits
AppVersion=<version-fijada>
DefaultDirName={autopf}\Rekord AI EgoBits
OutputBaseFilename=Rekord_AI_EgoBits_Setup_<version>
Compression=lzma2/max
SolidCompression=yes
DiskSpanning=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
; GGUF, ejecutables Tauri/llama, DLL y WebView2 se incluyen como archivos locales.
; No usar external/download: el requisito es instalación sin red.
```

`ArchitecturesAllowed=x64compatible` admite Windows x64 y Windows 11 Arm64 capaz de emular x64. Si el producto debe funcionar **sólo** en CPU x64 real, usar `x64os`; para el binario x64 ordinario, la documentación recomienda `x64compatible`. `ArchitecturesInstallIn64BitMode=x64compatible` instala por defecto en la vista y rutas de 64 bits. Inno Setup 6 puede realizar este modo de instalación aunque su setup sea de 32 bits; Inno Setup 7 agrega un instalador x64 nativo, no imprescindible para el destino planteado.

`Compression=lzma2/max` es el valor predeterminado documentado. Un GGUF suele ser poco compresible, así que la reducción efectiva y el tamaño final se deben medir con el GGUF exacto. No elevar diccionarios o niveles a ciegas: LZMA/LZMA2 incrementan la RAM de compilación y extracción.

No configurar `UseSetupLdr=no`: la documentación lo reserva para depuración y dice explícitamente que no se use para evitar demoras de verificación de firma. `DiskSpanning=no` preserva el requisito de un solo EXE; `DiskSpanning=yes` solo sería alternativa si se acepta que `Setup.exe` vaya acompañado de archivos `.bin`.

## Integridad y firma: build e instalación

1. **Entradas del build.** Mantener en el manifiesto de activos las rutas, versión, tamaño, licencia y SHA-256 del GGUF, sidecar `llama.cpp`, Tauri y WebView2. Antes de ISCC, recalcular SHA-256 y bloquear si no coincide. Para una entrada `[Files]` local, el parámetro `Hash` permite a ISCC comprobar SHA-256 durante la compilación; sirve como defensa adicional frente a una entrada distinta a la fijada.
2. **Artefacto emitido.** Tras un ISCC exitoso, registrar tamaño y `Get-FileHash -Algorithm SHA256` del `Setup.exe`, y publicar el hash por un canal autenticado junto al archivo. Verificar de nuevo ese hash antes de ejecutar en la VM/equipo de prueba.
3. **Firma de código.** Si se dispone de certificado Authenticode, definir `SignTool` con `signtool.exe sign` usando SHA-256 (`/fd sha256`) y sellado RFC 3161 SHA-256 (`/td sha256 /tr ...`); activar `SignedUninstaller=yes` (es el valor predeterminado cuando hay `SignTool`). La firma evita el aviso de editor desconocido cuando es válida. Requiere un certificado de firma de código de una CA, que normalmente tiene coste: no confundir esta necesidad de confianza pública con la licencia de Inno Setup.
4. **Comprobación posterior.** Validar `Get-AuthenticodeSignature` del `Setup.exe` y del `unins*.exe` instalado, además de sus SHA-256. La integridad no demuestra la instalación: ejecutar instalación offline en Windows 10/11 x64 limpio, iniciar la app y desinstalar; registrar versión, hash, estado de firma y exit codes.

Las firmas `.issig` de `ISSigTool` son ECDSA P-256 y se pueden crear sin certificado de CA, pero no eliminan el aviso “Unknown publisher” de Windows. Son útiles para verificar archivos externos o la cadena de build, no sustituyen Authenticode del EXE público.

## Límites y gates antes de declarar listo

- El GGUF conocido mide 2.740.937.888 bytes; todavía faltan Tauri, backend, `llama.cpp`, WebView2 y la sobrecarga del instalador. El tamaño sin comprimir no determina el límite, pero obliga a medir el EXE exacto.
- Si el resultado es mayor o igual que 4.200.000.000 bytes, el formato de un solo EXE queda bloqueado por documentación oficial. No es suficiente que Windows 10/11 soporte archivos grandes.
- Un EXE grande y firmado puede demorar al inicio porque Windows verifica la firma sobre mucho contenido. La propia guía de Inno recomienda disk spanning con `DiskSliceSize=max` para mitigar ese caso, pero ello contradice el requerimiento de archivo único; medir el arranque y decidir con esa evidencia.
- Esta investigación no valida el runtime de Tauri/WebView2, el contenido redistribuible del runtime, SmartScreen, antivirus, instalación real ni compatibilidad de Windows 10 22H2. Esos son gates posteriores de producto.

## Fuentes primarias

- [Inno Setup 6.5 revision history: 6.5.2 elimina el límite de 2 GB y 6.5.4](https://jrsoftware.org/files/is6.5-whatsnew.htm)
- [[Setup]: DiskSpanning: umbral exacto de 4.200.000.000 bytes y archivos `.bin`](https://jrsoftware.org/ishelp/topic_setup_diskspanning.htm)
- [[Setup]: UseSetupLdr](https://jrsoftware.org/ishelp/topic_setup_usesetupldr.htm)
- [[Setup]: Compression y memoria LZMA/LZMA2](https://jrsoftware.org/ishelp/topic_setup_compression.htm)
- [[Setup]: ArchitecturesAllowed](https://jrsoftware.org/ishelp/topic_setup_architecturesallowed.htm) y [[Setup]: ArchitecturesInstallIn64BitMode](https://jrsoftware.org/ishelp/topic_setup_architecturesinstallin64bitmode.htm)
- [[Files]: `Hash` SHA-256](https://jrsoftware.org/ishelp/topic_filessection.htm)
- [[Setup]: SignTool](https://jrsoftware.org/ishelp/topic_setup_signtool.htm) y [[Setup]: SignedUninstaller](https://jrsoftware.org/ishelp/topic_setup_signeduninstaller.htm)
- [ISSigTool y firma `.issig`](https://jrsoftware.org/ishelp/topic_issig.htm)
- [Verificación oficial de descargas de Inno Setup: Authenticode, attestation y SHA-256](https://jrsoftware.org/isdl-verify.php)
- [Licencia oficial de `jrsoftware/issrc`](https://github.com/jrsoftware/issrc/blob/main/license.txt)
- [Inno Setup 7 revision history, para contexto de versión nueva](https://jrsoftware.org/files/is7-whatsnew.htm)
