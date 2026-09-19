"""Makes the swarm server's modules (../agent-workflow/server) importable from these scripts."""

import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2] / "agent-workflow" / "server"
sys.path.insert(0, str(SERVER))
