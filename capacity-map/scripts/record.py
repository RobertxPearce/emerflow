"""Records the offline fixtures the UI uses when the swarm server isn't running.

    npm run record      (from capacity-map/; needs ../agent-workflow set up with `npm run setup`)

Writes ui/src/fixtures/region.json (GET /region) and ui/src/fixtures/simulation.json
(GET /simulate for the scenario below), both at 21:47, the demo's crisis time.
"""

import json
from datetime import datetime
from pathlib import Path

import _swarm  # noqa: F401  (adds the swarm server to the import path)
import region

AT = datetime(2026, 9, 19, 21, 47)
# Recorded what-if: a crowd crush after a game at the stadium downtown.
SCENARIO = {"lat": 39.2780, "lon": -76.6227, "casualties": 60}

FIXTURES = Path(__file__).resolve().parents[1] / "ui" / "src" / "fixtures"


def write(name, data):
    path = FIXTURES / name
    path.write_text(json.dumps(data, indent=1) + "\n")
    print(f"wrote {path.relative_to(FIXTURES.parents[2])}")


if __name__ == "__main__":
    FIXTURES.mkdir(parents=True, exist_ok=True)
    write("region.json", region.snapshot(now=AT))
    write("simulation.json", region.simulate(**SCENARIO, now=AT))
