# Instalación 0.3.3 bloqueada por Defender — 2026-10-01

## Causa comprobada

El error CreateProcess código 2 aparece porque falta `egobits-desktop.exe` en
`%LOCALAPPDATA%\Programs\Rekord IA`. El backend y otros archivos siguen presentes.
Defender registró detección y cuarentena del shell instalado a las 15:08–15:09
(UTC-03), con nombre `Trojan:Win32/Bearfoos.A!ml`, ThreatID 2147731250,
acción exitosa. También detectó el shell de compilación a las 15:14.
La ruta `Rekord IA` es una carpeta heredada conservada al actualizar; no es
la causa del archivo ausente.

No se ha demostrado que sea un falso positivo. No se restauró la cuarentena,
no se agregaron exclusiones y no se desactivó Defender. No se cerró Rekordbox
ni se modificó su colección. El Setup 0.3.3 se conserva como evidencia, pero
no debe distribuirse ni considerarse una instalación funcional.

## Correcciones locales

- El empaquetado exige análisis de shell, backend, ejecutables y DLL de
  `assets/bin`, y del instalador final, con MpCmdRun custom scan y
  `-DisableRemediation`. Un archivo ausente, análisis fallido o detección
  impide aprobar la entrega. El análisis no ejecuta el payload.
- Se fijan hashes de shell/backend en Inno y se verifican tras instalar y
  antes de ejecutar. Un componente ausente o alterado da un mensaje de
  Rekord AI con indicación de revisar Seguridad de Windows.
- La prueba de actualización aislada usa hashes de los fixtures respectivos.

Estos cambios mejoran detección y diagnóstico; **no resuelven por sí solos
la detección Bearfoos ni reparan la instalación existente**. Una aprobación
del antivirus local tampoco certifica inocuidad ni compatibilidad universal.

## Pendiente para una entrega funcional

Verificación de las correcciones: `output/closure/verify-defender-fix-final.log`
registra 129 pruebas, 128 aprobadas y 1 omitida (extra MCP), código 0, y 29
hashes upstream verificados. `output/closure/upgrade-lab-1790878606208169900/result.json`
registra instalación inicial, actualización, conservación de sentinelas,
rechazo de downgrade y de actualización con mutex, y limpieza del fixture,
todos aprobados. No se ejecutó otro binario real del shell ni otro Setup completo.
La inspección dirigida del shell local muestra conexión loopback, lanzamiento
del backend y terminación de su proceso propio; no demuestra inocuidad del
binario señalado por Defender ni permite atribuir la detección a una API concreta.

1. Revisar procedencia, toolchain y binario afectado; el código fuente por sí
   solo no prueba qué contiene el binario en cuarentena.
2. Solicitar revisión de la muestra como desarrollador a Microsoft. No se
   envió ningún archivo a servicios externos durante este diagnóstico.
3. Resolver el resultado de la revisión y volver a compilar con trazabilidad.
   No cambiar el binario únicamente para eludir la detección.
4. Validar antivirus, instalación completa, inicio real con tray y actualización
   preservando preferencias y backups; fixture Inno no sustituye esta prueba.
5. Firma Authenticode pendiente: contribuye a identidad/procedencia, no
   demuestra ausencia de malware ni elimina automáticamente detecciones.

Fuentes primarias:
- https://learn.microsoft.com/en-us/defender-xdr/developer-faq
- https://www.microsoft.com/en-us/wdsi/filesubmission
- https://learn.microsoft.com/en-us/defender-endpoint/command-line-arguments-microsoft-defender-antivirus
