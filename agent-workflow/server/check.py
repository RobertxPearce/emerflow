"""Self-check: runs many random crises and verifies every run follows the protocol.

    .venv/bin/python check.py            # 100 seeds
    .venv/bin/python check.py 500        # more seeds

Exits non-zero on the first broken run, printing the seed so it can be replayed.
"""

import json
import sys
from collections import Counter

import workflow
from protocol import PROTOCOL_VERSION, STEP_KINDS

UNIT_KEYS = {"code", "name", "occupied", "capacity", "waiting"}


def check_run(seed: int, casualties: int) -> dict:
    events = [e for e in workflow.run(seed, casualties) if e["type"] != "pause"]
    json.dumps(events)  # must be JSON-serializable

    assert events[0]["type"] == "meta" and events[0]["protocol"] == PROTOCOL_VERSION, "first event must be meta"
    assert events[1]["type"] == "workflow", "second event must be workflow"
    assert events[-1]["type"] == "end", "last event must be end"

    graph = events[1]
    ids = [s["id"] for s in graph["steps"]]
    assert len(ids) == len(set(ids)), "step ids must be unique"
    assert all(s["kind"] in STEP_KINDS for s in graph["steps"]), "unknown step kind"
    assert all(e["source"] in ids and e["target"] in ids for e in graph["edges"]), "edge points to unknown step"

    state = {i: "idle" for i in ids}
    for e in events[2:-1]:
        if e["type"] == "step":
            assert e["id"] in state, f"unknown step {e['id']}"
            if e["status"] == "running":
                assert state[e["id"]] == "idle", f"{e['id']} started twice"
            else:
                assert state[e["id"]] == "running", f"{e['id']} finished before it started"
                assert isinstance(e["summary"], str) and e["summary"], f"{e['id']} has no summary"
                assert isinstance(e["input"], list) and isinstance(e["output"], list)
            state[e["id"]] = e["status"]
        elif e["type"] == "snapshot":
            assert all(set(u) == UNIT_KEYS for u in e["units"]), "bad snapshot unit"
        else:
            raise AssertionError(f"unexpected event type {e['type']}")

    assert all(s in ("done", "flagged") for s in state.values()), f"steps never finished: {state}"
    return state


def main():
    seeds = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    flagged = Counter()
    for seed in range(1, seeds + 1):
        for casualties in (15, 25, 60):
            try:
                state = check_run(seed, casualties)
            except AssertionError as err:
                print(f"FAIL seed={seed} casualties={casualties}: {err}")
                sys.exit(1)
            flagged.update(k for k, v in state.items() if v == "flagged")
    print(f"OK: {seeds * 3} runs follow protocol v{PROTOCOL_VERSION}. Flagged step counts: {dict(flagged)}")


if __name__ == "__main__":
    main()
