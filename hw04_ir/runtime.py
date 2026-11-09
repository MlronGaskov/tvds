from hw04_ir.optimize import evaluate


def run(functions, name, args, budget=None):
    budget = [100000] if budget is None else budget
    if name == "length":
        return (len(args[0]),)
    function = functions[name]
    params = function["params"]
    if len(args) != len(params):
        raise ValueError("wrong number of arguments")
    values = {param["name"]: value for param, value in zip(params, args)}
    code = function["instructions"]
    labels = {inst["name"]: index for index, inst in enumerate(code) if inst["op"] == "label"}
    pc = 0
    while pc < len(code):
        budget[0] -= 1
        if budget[0] < 0:
            raise RuntimeError("execution limit exceeded")
        inst = code[pc]
        op = inst["op"]
        if op == "const":
            values[inst["dst"]] = inst["value"]
        elif op == "copy":
            values[inst["dst"]] = values[inst["src"]]
        elif op == "un":
            values[inst["dst"]] = evaluate(inst["operator"], values[inst["arg"]])
        elif op == "bin":
            values[inst["dst"]] = evaluate(inst["operator"], values[inst["left"]], values[inst["right"]])
        elif op == "get":
            values[inst["dst"]] = values[inst["array"]][values[inst["index"]]]
        elif op == "set":
            array = list(values[inst["array"]])
            array[values[inst["index"]]] = values[inst["value"]]
            values[inst["dst"]] = array
        elif op == "call":
            outputs = run(functions, inst["name"], [values[arg] for arg in inst["args"]], budget)
            for dst, value in zip(inst["dsts"], outputs):
                values[dst] = value
        elif op == "branch":
            pc = labels[inst["true"] if values[inst["cond"]] else inst["false"]]
            continue
        elif op == "jump":
            pc = labels[inst["target"]]
            continue
        elif op == "assert":
            if not values[inst["cond"]]:
                raise AssertionError("assertion failed")
        elif op == "ret":
            return tuple(values[item] for item in inst["values"])
        pc += 1
    raise RuntimeError("missing return")
