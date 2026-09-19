"""The event format the UI understands (protocol version 1).

Any data source — this simulation, a Gemini-backed pipeline, n8n, a partner's
service — can drive the UI by emitting these events in this order:

    meta → workflow → (step running/done, snapshot)* → end

The TypeScript mirror of these shapes is agent-workflow/ui/src/protocol.ts.
"""

PROTOCOL_VERSION = 1

STEP_KINDS = ("trigger", "code", "ai", "human")
STEP_STATUSES = ("running", "done", "flagged")


def meta(**info):
    """First event of a run. Put anything useful to display here (e.g. seed)."""
    return {"type": "meta", "protocol": PROTOCOL_VERSION, **info}


def workflow(steps, edges):
    """The graph the UI draws. steps: [{id, kind, title, role}], edges: [(source, target)]."""
    return {
        "type": "workflow",
        "steps": [dict(s) for s in steps],
        "edges": [{"source": a, "target": b} for a, b in edges],
    }


def running(*step_ids):
    """One or more steps started. Several at once means they run in parallel."""
    return [{"type": "step", "id": i, "status": "running"} for i in step_ids]


def step_done(step_id, summary, input, output, reasoning=None, flagged=False):
    """A step finished. `flagged` means a person needs to look at it."""
    return {
        "type": "step",
        "id": step_id,
        "status": "flagged" if flagged else "done",
        "summary": summary,
        "input": list(input),
        "output": list(output),
        "reasoning": reasoning,
    }


def snapshot(label, clock, units):
    """Bed counts. units: [{code, name, occupied, capacity, waiting}]."""
    return {"type": "snapshot", "label": label, "clock": clock, "units": units}


def error(message):
    return {"type": "error", "message": message}


def end():
    return {"type": "end"}


def pause(seconds):
    """Not sent to the UI. Tells the server to wait so a person can follow along."""
    return {"type": "pause", "seconds": seconds}
