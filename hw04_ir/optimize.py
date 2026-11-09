from copy import deepcopy

from hw04_ir.flow import cfg, defined, liveness, used


def evaluate(op, *values):
    if op == "-" and len(values) == 1:
        return -values[0]
    if op == "not":
        return not values[0]
    if op == "+":
        return values[0] + values[1]
    if op == "-":
        return values[0] - values[1]
    if op == "*":
        return values[0] * values[1]
    if op == "/":
        if values[1] == 0:
            raise ZeroDivisionError
        return (abs(values[0]) // abs(values[1])) * (-1 if (values[0] < 0) != (values[1] < 0) else 1)
    return {"==": lambda a, b: a == b, "!=": lambda a, b: a != b,
            "<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
            ">": lambda a, b: a > b, ">=": lambda a, b: a >= b}[op](*values)


def simplify(code, propagate, algebra):
    result = []
    fields = {
        "copy": ("src",), "un": ("arg",), "bin": ("left", "right"),
        "get": ("array", "index"), "set": ("array", "index", "value"),
        "branch": ("cond",), "assert": ("cond",), "assume": ("cond",)
    }
    for block in cfg(code):
        known = {}
        aliases = {}
        for original in block["instructions"]:
            inst = original.copy()
            op = inst["op"]
            for field in fields.get(op, ()):
                inst[field] = aliases.get(inst[field], inst[field])
            if op in ("call", "ret"):
                field = "args" if op == "call" else "values"
                inst[field] = [aliases.get(value, value) for value in inst[field]]
            if op in ("copy", "un", "bin"):
                args = ([inst["src"]] if op == "copy" else
                        [inst["arg"]] if op == "un" else
                        [inst["left"], inst["right"]])
                values = [known.get(arg) for arg in args]
                replacement = None
                if propagate and all(value is not None for value in values):
                    try:
                        value = values[0] if op == "copy" else evaluate(inst["operator"], *values)
                        replacement = {"op": "const", "dst": inst["dst"], "value": value, "type": inst["type"]}
                    except ZeroDivisionError:
                        pass
                if replacement is None and op == "bin" and algebra:
                    left, right = inst["left"], inst["right"]
                    a, b = known.get(left), known.get(right)
                    operator = inst["operator"]
                    src = None
                    if operator == "+":
                        src = right if a == 0 else left if b == 0 else None
                    elif operator == "-" and b == 0:
                        src = left
                    elif operator == "*":
                        if a == 0 or b == 0:
                            replacement = {"op": "const", "dst": inst["dst"], "value": 0, "type": inst["type"]}
                        else:
                            src = right if a == 1 else left if b == 1 else None
                    elif operator == "/" and b == 1:
                        src = left
                    if src is not None:
                        replacement = {"op": "copy", "dst": inst["dst"], "src": src, "type": inst["type"]}
                inst = replacement or inst
            for dst in defined(inst):
                known.pop(dst, None)
                aliases.pop(dst, None)
                aliases = {name: src for name, src in aliases.items() if src != dst}
            if inst["op"] == "const":
                known[inst["dst"]] = inst["value"]
            elif inst["op"] == "copy":
                if propagate and inst["src"] in known:
                    known[inst["dst"]] = known[inst["src"]]
                if inst["src"] != inst["dst"]:
                    aliases[inst["dst"]] = inst["src"]
            result.append(inst)
    return result


def eliminate(code):
    result = code
    while True:
        blocks = cfg(result)
        _, outside = liveness(blocks)
        filtered = []
        for block in blocks:
            live = outside[block["id"]].copy()
            kept = []
            for inst in reversed(block["instructions"]):
                defs = defined(inst)
                pure = inst["op"] in ("const", "copy", "un", "bin")
                pure = pure and not (inst["op"] == "bin" and inst["operator"] == "/")
                if pure and defs.isdisjoint(live):
                    continue
                kept.append(inst)
                live.difference_update(defs)
                live.update(used(inst))
            filtered.extend(reversed(kept))
        if filtered == result:
            return result
        result = filtered


def optimize(code, propagate=True, algebra=True, dce=True):
    code = deepcopy(code)
    if propagate or algebra:
        code = simplify(code, propagate, algebra)
    if dce:
        code = eliminate(code)
    return code
