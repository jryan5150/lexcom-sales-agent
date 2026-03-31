# Jetson Orin Nano Super — Setup Guide

## Prerequisites

Your Jetson is running Ubuntu 22.04.5 LTS (confirmed from screenshot).
Device name: `bryan-desktop` — you'll probably want to rename this.

```bash
sudo hostnamectl set-hostname lexcom-edge
```

## 1. Ollama Setup

Ollama has native ARM64/Jetson support with CUDA acceleration.

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Verify it sees the GPU
ollama --version

# Pull the model — Mistral 7B quantized fits in 8GB
ollama pull mistral:7b-instruct-v0.3-q4_K_M

# Test it
ollama run mistral:7b-instruct-v0.3-q4_K_M "Hello, are you running on a Jetson?"

# Ollama runs as a systemd service on port 11434
systemctl status ollama
```

### Model Selection Notes

| Model | VRAM | Speed | Quality | Recommendation |
|-------|------|-------|---------|----------------|
| mistral:7b-instruct-v0.3-q4_K_M | ~4.5GB | Fast | Good | **Default — ticket classification, RAG** |
| llama3:8b-instruct-q4_K_M | ~5.2GB | Medium | Better | Better reasoning, slightly slower |
| phi3:mini-4k-instruct-q4_K_M | ~2.5GB | Very fast | Decent | If you need headroom for other GPU tasks |

The Orin Nano Super has 8GB shared between CPU and GPU. With Mistral 7B Q4,
you'll use ~4.5GB for the model leaving ~3.5GB for ChromaDB, FastAPI, and OS.

If you find memory tight, drop to phi3:mini. If you want better quality
and can afford the latency, try llama3:8b.

### Verify CUDA is working

```bash
# Should show your Tegra Orin GPU
nvidia-smi
# Or on Jetson:
sudo tegrastats
```

## 2. Python Environment

```bash
# Python 3.10 should already be installed on 22.04
python3 --version

# Create venv
cd /home/$USER/lexcom-edge
python3 -m venv .venv
source .venv/bin/activate

# Install deps
pip install --upgrade pip
pip install -r requirements.txt

# ChromaDB may need build tools on ARM
sudo apt install -y build-essential python3-dev
pip install chromadb
```

### ARM64 / Jetson gotchas

- `chromadb` compiles hnswlib from source on ARM — takes a few minutes, needs gcc
- `pypsrp` (for Hyper-V WinRM) installs cleanly on ARM
- `httpx` and `fastapi` are pure Python, no issues
- If `pydantic-settings` fails, try: `pip install pydantic-settings --no-build-isolation`

## 3. MCP SDK (for TD Synnex server)

```bash
pip install mcp
```

If `mcp` package isn't available yet via pip on ARM, install from source:
```bash
pip install git+https://github.com/modelcontextprotocol/python-sdk.git
```

## 4. Network Access

The Jetson needs outbound HTTPS access to:

| Service | Hostname | Port |
|---------|----------|------|
| ConnectWise | na.myconnectwise.net (or your instance) | 443 |
| Meraki | api.meraki.com | 443 |
| Hyper-V hosts | (internal IPs) | 5985 (WinRM HTTP) or 5986 (HTTPS) |
| TD Synnex | (StreamOne hostname) | 443 |
| Ollama | localhost | 11434 |

If the Jetson is on the Lexcom network, CW and Meraki are direct HTTPS.
Hyper-V WinRM needs internal network access to the Heaton hosts — 
confirm the Jetson can reach them. If it's on a separate VLAN, 
you may need a firewall rule or Tailscale mesh.

## 5. Tailscale (Optional but recommended)

If you want the Jetson accessible from your other dev machines:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

This lets you hit the FastAPI endpoint from your ThinkPad/T14 
without exposing it to the broader network.

## 6. Running the Heaton Agent

```bash
cd /home/$USER/lexcom-edge
source .venv/bin/activate

# Copy and fill in env vars
cp .env.example .env
nano .env  # Fill in your credentials

# First run: ingest historical data
python -c "
import asyncio
from heaton_agent.engine import HeatonEngine
from heaton_agent.adapters import ConnectWiseAdapter, MerakiAdapter
# ... initialize adapters with your config
# engine = HeatonEngine(adapters=[...])
# asyncio.run(engine.ingest_historical(days_back=180))
"

# Start the service
cd heaton_agent
uvicorn server:app --host 0.0.0.0 --port 8000

# Or run in background with systemd (see SYSTEMD.md)
```

## 7. Running the TD Synnex MCP Server

For Claude Code integration, add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "tdsynnex": {
      "command": "python",
      "args": ["-m", "tdsynnex.mcp.server"],
      "cwd": "/home/$USER/lexcom-edge",
      "env": {
        "TDSYNNEX_HOSTNAME": "...",
        "TDSYNNEX_ACCOUNT_ID": "...",
        "TDSYNNEX_REFRESH_TOKEN": "..."
      }
    }
  }
}
```

Or run standalone for testing:
```bash
cd /home/$USER/lexcom-edge
python -m tdsynnex.mcp.server
```

## 8. Systemd Service (Production)

Create `/etc/systemd/system/heaton-agent.service`:

```ini
[Unit]
Description=Heaton Environment Intelligence Agent
After=network.target ollama.service

[Service]
Type=simple
User=jace
WorkingDirectory=/home/jace/lexcom-edge/heaton_agent
Environment=PATH=/home/jace/lexcom-edge/.venv/bin:/usr/bin
EnvironmentFile=/home/jace/lexcom-edge/.env
ExecStart=/home/jace/lexcom-edge/.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable heaton-agent
sudo systemctl start heaton-agent
sudo journalctl -u heaton-agent -f  # Watch logs
```
