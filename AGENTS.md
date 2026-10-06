# Reglas del proyecto

- Cada Setup debe servir como instalación inicial y actualización sobre versiones anteriores, sin desinstalar primero ni borrar configuración, colección o respaldos.
- Conservar AppId `F57C7090-73DC-453B-96DF-8D9F3E215E10`, identifier `com.egobits.rekordai`, modo por usuario x64 y ubicaciones persistentes existentes. Cualquier migración futura exige backup, verificación y recuperación.
- `release.json` es el contrato de versión e identidad. Ejecutar `installer/release_contract.py` antes de compilar; versiones Python, HTTP/XML, Cargo/config/lock e instalador deben coincidir.
- Verificar código y suite antes de generar un Setup nuevo. Validar instalación inicial, actualización, conservación de datos y rechazo de downgrade en un entorno aislado; distinguir fixture de instalador completo y host de Windows limpio.
- No cerrar Rekordbox durante QA sin indicación explícita del DJ de que su sesión puede terminar. El botón de cierre requiere confirmación dentro de la app, identifica instalación/propietario y solicita cierre normal. No forzar terminación ni afirmar cerrado sólo por enviar WM_CLOSE.
- Preparar el contrato para futuras actualizaciones web; no habilitar comprobación online ahora. Antes de activar updater: HTTPS, manifest/artefacto firmados, verificación antes de ejecutar, anti-downgrade, pausa de operaciones, recuperación y consentimiento configurado. El uso musical e IA deben seguir funcionando offline.
