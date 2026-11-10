"""Select witnessed causes for the presenter story from actual contact records."""


def chapters(run):
    events = run["events"]
    if not events:
        return []
    sources = {e["tick"] * run["config"]["flies"] + e["fly"] + 1: e for e in events}

    def best(event):
        return max(
            (h for h in event["hits"] if h["outcome"] == -1),
            key=lambda h: h["score"],
            default=None,
        )

    def source(event):
        hit = best(event)
        return sources.get(hit["id"]) if hit else None

    def variant(event):
        return next(
            n["variant"]
            for n in run["nodes"][event["tick"] // run["config"]["epoch_steps"]]
            if n["id"] == event["object"]
        )

    def qualifies(event):
        observed = source(event)
        return (
            not event["neural"]["feeding"]
            and observed is not None
            and observed["object"] != event["object"]
            and (
                run["mode"] != "shared"
                or (
                    observed["fly"] != event["fly"] and event["shared_changed_decision"]
                )
            )
        )

    general = (
        next((e for e in events if qualifies(e)), None)
        if run["mode"] != "none"
        else None
    )
    harm = (
        source(general)
        if general
        else next((e for e in events if e["outcome"] == -1), None)
    )
    result = []
    if harm:
        result.append(
            {
                "event": harm,
                "title": "An injury becomes experience"
                if run["mode"] != "none"
                else "The first injury",
                "text": "A sweet scent hides a harmful meal.",
            }
        )
    if run["mode"] == "none":
        again = next(
            (
                e
                for e in events
                if harm
                and e["fly"] == harm["fly"]
                and e["tick"] > harm["tick"]
                and e["outcome"] == -1
            ),
            None,
        )
        if again:
            result.append(
                {
                    "event": again,
                    "title": "The same mistake",
                    "text": "The fly has no stored warning. It eats again.",
                }
            )
        return result
    if general:
        result.append(
            {
                "event": general,
                "witness_id": best(general)["id"],
                "title": "A different meal. A similar scent."
                if run["mode"] == "personal"
                else "Another fly retrieves the warning.",
                "text": "The observed injury supplies a warning for a different meal.",
            }
        )
    new_harm = next(
        (
            e
            for e in events
            if e["tick"] >= run["config"]["wave"]
            and e["outcome"] == -1
            and variant(e) == 5
        ),
        None,
    )
    if new_harm:
        simultaneous = [
            e["fly"] + 1
            for e in events
            if e["tick"] == new_harm["tick"] and e["outcome"] == -1 and variant(e) == 5
        ]
        text = "The colony must observe a new kind of danger."
        if len(simultaneous) > 1 and run["mode"] == "shared":
            text = f"Flies {', '.join(f'{f:02d}' for f in simultaneous)} encounter new poison before either observation is shared."
        result.append(
            {
                "event": new_harm,
                "title": "A new poison",
                "text": text,
                "simultaneous_flies": simultaneous,
            }
        )
        later = next(
            (
                e
                for e in events
                if e["tick"] > new_harm["tick"]
                and not e["neural"]["feeding"]
                and variant(e) == 5
                and source(e)
                and variant(source(e)) == 5
                and source(e)["tick"] >= new_harm["tick"]
                and (run["mode"] != "shared" or e["shared_changed_decision"])
            ),
            None,
        )
        if later:
            result.append(
                {
                    "event": later,
                    "witness_id": best(later)["id"],
                    "title": "The new warning works.",
                    "text": "The observed new poison now changes a later decision.",
                }
            )
    return result
