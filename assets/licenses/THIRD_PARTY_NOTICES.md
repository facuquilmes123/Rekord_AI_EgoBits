# Componentes de terceros

Inventario: THIRD_PARTY_INVENTORY.json. Los archivos de dependencies/ conservan avisos de los paquetes resueltos o del commit VCS declarado por Cargo. El inventario incluye build y otras plataformas: no equivale al enlace final de Tauri, todavía no compilado.

- llama.cpp b11146: MIT; LLVM OpenMP: licencia y excepciones incluidas.
- Qwen3.5-4B / Unsloth Q4_K_M: Apache-2.0, licencia y model card incluidos.
- CPython 3.12.10: PSF y terceros, dependencies/CPython/LICENSE.txt.
- PyInstaller 6.22.3: GPL con excepción para distribución de ejecutables; texto original incluido.
- OpenSSL 3.0.16: Apache-2.0, texto incluido.
- Tauri/crates: licencias y avisos por componente en inventario.
- Microsoft WebView2: propietario, no se relicencia como MIT/Apache. Lock del artefacto completo en installer/webview2.lock.json. Distribución oficial: https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution
- Microsoft VCRUNTIME140.dll: procedente de CPython Windows; términos de redistribución Visual C++: https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files

Antes de publicación, cerrar avisos pendientes de la matriz y términos Microsoft aplicables. Este es un kit local de QA, no una release publicada. Los tonos WAV se generaron para ensayo; no son grabaciones de terceros.
