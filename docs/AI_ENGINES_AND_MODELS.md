# Local AI Engines & Model Tiers Guide

Because GitHub repositories have a 100 MB file-size limit, heavy GGUF model weights (500 MB – 5.3 GiB) and `llama.cpp` runtime binaries are **not** stored directly in Git. Instead, Rekord AI lets you choose the exact model and engine that fits your laptop or studio workstation.

> **Important:** You do **not** need an AI model to use Rekord AI! Deterministic set planning (BPM & Energy curves), Camelot harmonic matching, live SQLCipher `master.db` browsing, LUFS acoustic energy analysis, SHA-256 duplicate cleanup, Pro DJ Link monitoring, and all 13 MCP tools work **100% locally with 0 MB of AI weights**.

---

## Option 1: Automatic One-Command Installer (Recommended)

Run the interactive setup script from the repository root. It detects your system RAM, recommends the optimal tier, downloads over HTTPS only, verifies the exact **SHA-256** hash, and configures `assets/models/active_ai.json` automatically:

```powershell
python scripts/setup_ai.py
```

Or pass flags directly in PowerShell / terminal:

```powershell
# List all models, engines, and direct download URLs
python scripts/setup_ai.py --list

# Examples:
python scripts/setup_ai.py --profile lite --engine cpu          # 4–6 GB RAM laptops (~508 MB)
python scripts/setup_ai.py --profile compact --engine cpu       # 6–8 GB RAM laptops (~1.19 GiB)
python scripts/setup_ai.py --profile balanced --engine cpu      # 8–16 GB RAM (Default, ~2.55 GiB)
python scripts/setup_ai.py --profile pro --engine vulkan        # 16+ GB RAM + AMD/Intel/NVIDIA GPU (~5.29 GiB)
python scripts/setup_ai.py --profile balanced --engine cuda     # NVIDIA RTX/GTX CUDA 12.4
python scripts/setup_ai.py --profile none                       # Deterministic mode only (0 MB)
```

On Windows PowerShell, you can also run:

```powershell
.\scripts\setup_ai.ps1 -Profile balanced -Engine cpu
```

---

## Option 2: Direct Manual Download Links & SHA-256 Checksums

If you prefer to download files manually (for an air-gapped booth PC or USB transfer), download **one inference engine** + **one GGUF model** below and verify their SHA-256 checksums.

### Step A — Choose Your GGUF Model (Apache-2.0 License)

Place the downloaded `.gguf` file inside `assets/models/`:

| Profile | Model | Size | Min RAM | Best For | Direct Download (HuggingFace) | SHA-256 |
| --- | --- | --- | --- | --- | --- | --- |
| `lite` | **Qwen3.5 0.8B Q4_K_M** | 508 MiB | 4 GB | Older booth laptops, quick intent parsing | [Download GGUF](https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF/resolve/main/Qwen3.5-0.8B-Q4_K_M.gguf) | `bd258782e35f7f458f8aced1adc053e6e92e89bc735ba3be89d38a06121dc517` |
| `compact` | **Qwen3.5 2B Q4_K_M** | 1.19 GiB | 6 GB | Ultrabooks & mid-range DJ laptops | [Download GGUF](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-Q4_K_M.gguf) | `aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223` |
| `balanced` | **Qwen3.5 4B Q4_K_M** *(Default)* | 2.55 GiB | 8 GB | Best balance of accuracy, Spanish/English & speed | [Download GGUF](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/e87f176479d0855a907a41277aca2f8ee7a09523/Qwen3.5-4B-Q4_K_M.gguf) | `00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4` |
| `pro` | **Qwen3.5 9B Q4_K_M** | 5.29 GiB | 16 GB | Studio workstations & GPU rigs | [Download GGUF](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf) | `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8` |

### Step B — Choose Your `llama.cpp` Runtime Engine (`b11146`, MIT License)

Extract the `.exe` and `.dll` files into `assets/bin/`:

| Engine | Hardware Target | Download Size | Direct Download (GitHub Releases) | SHA-256 |
| --- | --- | --- | --- | --- |
| `cpu` *(Default)* | Any Windows x64 CPU (AVX2 / SSE4.2) | 17.7 MiB | [llama-b11146-bin-win-cpu-x64.zip](https://github.com/ggml-org/llama.cpp/releases/download/b11146/llama-b11146-bin-win-cpu-x64.zip) | `14cf1303ca9ac3abd94816850532f9f9a69ac66fbaca3776fc6f9061c2fac1d1` |
| `vulkan` | AMD, Intel Arc & NVIDIA GPUs (Vulkan) | 30.6 MiB | [llama-b11146-bin-win-vulkan-x64.zip](https://github.com/ggml-org/llama.cpp/releases/download/b11146/llama-b11146-bin-win-vulkan-x64.zip) | `55a378aa095b466979d85075234f66d7655c7a7483222af0c006c0e55b4d7bd6` |
| `cuda` | NVIDIA RTX/GTX GPUs (CUDA 12.4) | 242.1 MiB + 373.3 MiB runtime | [llama-b11146-bin-win-cuda-12.4-x64.zip](https://github.com/ggml-org/llama.cpp/releases/download/b11146/llama-b11146-bin-win-cuda-12.4-x64.zip) + [cudart-llama-bin-win-cuda-12.4-x64.zip](https://github.com/ggml-org/llama.cpp/releases/download/b11146/cudart-llama-bin-win-cuda-12.4-x64.zip) | `3c806a6ceccc3dae1c743ceb1a1fb2cce5b76f40bfbd4c6b7b8afb6ef45a5807` / `8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6` |

### Step C — Offline Staging From Local Cache

If you placed the downloaded `.zip` and `.gguf` files into `build/asset-cache/`, simply run `python scripts/setup_ai.py --profile <your_tier> --engine <your_engine>`. It detects the cached files, validates their SHA-256 hashes without re-downloading, and writes `assets/models/active_ai.json`.
