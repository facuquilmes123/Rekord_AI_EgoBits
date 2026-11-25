# Security Policy

## Supported Versions

| Version | Supported |
| --- | --- |
| `0.4.x` (`main`) | Yes |
| `< 0.4.0` | Security fixes backported to `0.4.x` |

## Security Architecture & Guarantees

Rekord AI is engineered with a **fail-closed, 100% offline-first** architecture:

- **Zero External Telemetry or Cloud APIs**: No track metadata, library paths, or user prompts leave your machine.
- **Strict Trust Boundary for Local LLMs**: The local `llama.cpp` sidecar is constrained to `127.0.0.1` with an ephemeral per-session Bearer token, process-ownership verification (`psutil`), and strict JSON schema validation. The LLM cannot execute shell commands, arbitrary SQL, or unapproved native writes.
- **Cryptographic Asset Verification**: Every downloaded runtime binary and GGUF model weight is verified against pinned SHA-256 hashes and HTTPS-only sources before activation (`VerifiedAssets` holds Windows read-only share locks during inference).
- **Non-Destructive Library Access**: Reading `master.db` uses SQLCipher `mode=ro` + `query_only`. Any native playlist creation, USB DeviceSQL write, or duplicate consolidation requires Rekordbox closed, a verified backup, preview, and HMAC-signed Windows confirmation.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.
Instead, report vulnerabilities privately via GitHub Security Advisories on this repository once public, or contact the maintainer directly.

Please include:
- Affected component (`prototype/`, `desktop/src-tauri/`, `installer/`, or `scripts/`)
- Steps to reproduce
- Impact assessment and suggested remediation (if available)
