"""Records one run to ui/src/fixtures/sample-run.json.

The UI uses this file to draw the default graph and to replay a run with no
server. Re-run after changing steps, edges or event contents:

    .venv/bin/python record_fixture.py [seed] [casualties]
"""

import json
import sys
from pathlib import Path

import workflow

OUT = Path(__file__).resolve().parent.parent / "ui" / "src" / "fixtures" / "sample-run.json"


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    casualties = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    at, events = 0.0, []
    for event in workflow.run(seed, casualties):
        if event["type"] == "pause":
            at += event["seconds"]
        else:
            events.append({"at": round(at, 2), "event": event})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"seed": seed, "casualties": casualties, "events": events}, indent=1, ensure_ascii=False) + "\n")
    print(f"Wrote {len(events)} events ({at:.1f}s) to {OUT}")


if __name__ == "__main__":
    main()
