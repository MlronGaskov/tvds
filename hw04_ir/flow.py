def used(inst):
    op = inst["op"]
    fields = {
        "copy": ["src"], "un": ["arg"], "bin": ["left", "right"],
        "get": ["array", "index"], "set": ["array", "index", "value"],
        "branch": ["cond"], "assert": ["cond"], "assume": ["cond"]
    }
    if op in ("call", "ret"):
        return set(inst["args"] if op == "call" else inst["values"])
    return {inst[key] for key in fields.get(op, [])}


def defined(inst):
    if inst["op"] == "call":
        return set(inst["dsts"])
    return {inst["dst"]} if "dst" in inst else set()


def cfg(code):
    if not code:
        return []
    leaders = {0}
    for index, inst in enumerate(code):
        if inst["op"] == "label":
            leaders.add(index)
        if inst["op"] in ("jump", "branch", "ret") and index + 1 < len(code):
            leaders.add(index + 1)
    starts = sorted(leaders)
    blocks = [{"id": f"B{i}", "instructions": code[start:end], "succ": [], "pred": []}
              for i, (start, end) in enumerate(zip(starts, starts[1:] + [len(code)]))]
    labels = {block["instructions"][0]["name"]: block["id"]
              for block in blocks if block["instructions"][0]["op"] == "label"}
    for index, block in enumerate(blocks):
        last = block["instructions"][-1]
        if last["op"] == "jump":
            block["succ"] = [labels[last["target"]]]
        elif last["op"] == "branch":
            block["succ"] = list(dict.fromkeys([labels[last["true"]], labels[last["false"]]]))
        elif last["op"] != "ret" and index + 1 < len(blocks):
            block["succ"] = [blocks[index + 1]["id"]]
    lookup = {block["id"]: block for block in blocks}
    for block in blocks:
        for successor in block["succ"]:
            lookup[successor]["pred"].append(block["id"])
    return blocks


def liveness(blocks):
    use, defs, inside, outside = {}, {}, {}, {}
    for block in blocks:
        ident = block["id"]
        use[ident], defs[ident] = set(), set()
        for inst in block["instructions"]:
            use[ident].update(used(inst) - defs[ident])
            defs[ident].update(defined(inst))
        inside[ident], outside[ident] = set(), set()
    changed = True
    while changed:
        changed = False
        for block in reversed(blocks):
            ident = block["id"]
            new_out = set().union(*(inside[s] for s in block["succ"]))
            new_in = use[ident] | (new_out - defs[ident])
            if new_in != inside[ident] or new_out != outside[ident]:
                inside[ident], outside[ident] = new_in, new_out
                changed = True
    return inside, outside


def interference(blocks):
    _, outside = liveness(blocks)
    temps = {item for block in blocks for inst in block["instructions"]
             for item in used(inst) | defined(inst) if item.startswith("%t")}
    graph = {item: set() for item in temps}
    for block in blocks:
        live = outside[block["id"]].copy()
        for inst in reversed(block["instructions"]):
            defs = defined(inst)
            for dst in defs:
                if dst not in graph:
                    continue
                for other in live | (defs - {dst}):
                    if other in graph and other != dst:
                        graph[dst].add(other)
                        graph[other].add(dst)
            live.difference_update(defs)
            live.update(used(inst))
    return {item: sorted(neighbors) for item, neighbors in sorted(graph.items())}


def color(graph):
    colors = {}
    for name in sorted(graph, key=lambda node: (-len(graph[node]), node)):
        occupied = {colors[neighbor] for neighbor in graph[name] if neighbor in colors}
        colors[name] = next(number for number in range(len(graph) + 1) if number not in occupied)
    return colors


def metrics(code):
    temps = {item for inst in code for item in used(inst) | defined(inst) if item.startswith("%t")}
    return {"instructions": len(code), "temporaries": len(temps)}
