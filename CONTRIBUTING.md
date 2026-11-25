# Contributing to Rekord AI

Thank you for helping build the open-source offline AI companion for Rekordbox DJs!

## Development Workflow

1. **Fork & Branch**: Create a feature branch from `main` (e.g., `feat/my-feature` or `fix/issue-123`).
2. **Keep Sensitive Data Out**: Never commit real `master.db` files, personal XML exports, audio files, `.gguf` weights, binaries, `.env` files, or personal machine paths.
3. **Verify Release Contract & Tests**:
   ```powershell
   python installer/release_contract.py
   python scripts/verify_kit.py
   ```
   Or run the Python test suite directly:
   ```powershell
   $env:PYTHONPATH = "prototype"
   python -m unittest discover -s prototype/tests -v
   ```
4. **Pull Request**: Explain the motivation, test evidence, and any hardware/Rekordbox limitations clearly.

## Project Rules

- Preserve offline-first operation and deterministic fallbacks when no LLM is loaded.
- Maintain strict validation between LLM intent/answer proposals and executable actions.
- Any feature touching native Rekordbox databases or USB exports must enforce backups, read/write separation, and user confirmation.
