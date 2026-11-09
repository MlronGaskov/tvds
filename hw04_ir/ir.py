class IRBuilder:
    def __init__(self):
        self.code = []
        self.temps = 0
        self.labels = 0

    def emit(self, op, **fields):
        self.code.append({"op": op, **fields})

    def temp(self):
        self.temps += 1
        return f"%t{self.temps}"

    def label(self):
        self.labels += 1
        return f"L{self.labels}"

    def expression(self, expr):
        kind = expr["type"]
        if kind in ("Int", "Bool"):
            dst = self.temp()
            self.emit("const", dst=dst, value=expr["value"], type=expr["inferred_type"])
            return dst
        if kind == "Var":
            return expr["name"]
        if kind == "Call":
            args = [self.expression(arg) for arg in expr["args"]]
            types = expr["inferred_type"]
            types = types if isinstance(types, list) else [types]
            dsts = [self.temp() for _ in types]
            self.emit("call", dsts=dsts, name=expr["name"], args=args, types=types)
            return dsts[0] if len(dsts) == 1 else tuple(dsts)
        if kind in ("Index", "ArraySet"):
            array = self.expression(expr["array"])
            index = self.expression(expr["index"])
            dst = self.temp()
            if kind == "Index":
                self.emit("get", dst=dst, array=array, index=index, type="int")
            else:
                value = self.expression(expr["value"])
                self.emit("set", dst=dst, array=array, index=index, value=value, type="int[]")
            return dst
        if kind == "Unary":
            arg = self.expression(expr["operand"])
            dst = self.temp()
            self.emit("un", dst=dst, operator=expr["op"], arg=arg, type=expr["inferred_type"])
            return dst
        if kind == "Binary":
            left = self.expression(expr["left"])
            op = expr["op"]
            if op in ("and", "or", "->"):
                dst = self.temp()
                rhs, end = self.label(), self.label()
                if op == "->":
                    initial = self.temp()
                    self.emit("un", dst=initial, operator="not", arg=left, type="bool")
                    self.emit("copy", dst=dst, src=initial, type="bool")
                else:
                    self.emit("copy", dst=dst, src=left, type="bool")
                self.emit("branch", cond=left,
                          true=rhs if op != "or" else end,
                          false=end if op != "or" else rhs)
                self.emit("label", name=rhs)
                right = self.expression(expr["right"])
                self.emit("copy", dst=dst, src=right, type="bool")
                self.emit("label", name=end)
                return dst
            right = self.expression(expr["right"])
            dst = self.temp()
            self.emit("bin", dst=dst, operator=op, left=left, right=right,
                      type=expr["inferred_type"])
            return dst
        raise ValueError(f"unsupported IR expression: {kind}")

    def statement(self, stmt):
        kind = stmt["type"]
        if kind == "Block":
            for item in stmt["statements"]:
                self.statement(item)
        elif kind == "Assign":
            value = self.expression(stmt["value"])
            self.emit("copy", dst=stmt["target"]["name"], src=value,
                      type=stmt["target"]["inferred_type"])
        elif kind == "MultiAssign":
            values = self.expression(stmt["value"])
            values = values if isinstance(values, tuple) else (values,)
            for target, value in zip(stmt["targets"], values):
                self.emit("copy", dst=target["name"], src=value,
                          type=target["inferred_type"])
        elif kind == "If":
            condition = self.expression(stmt["condition"])
            yes, no, end = self.label(), self.label(), self.label()
            self.emit("branch", cond=condition, true=yes, false=no)
            self.emit("label", name=yes)
            self.statement(stmt["then"])
            self.emit("jump", target=end)
            self.emit("label", name=no)
            if stmt["otherwise"] is not None:
                self.statement(stmt["otherwise"])
            self.emit("label", name=end)
        elif kind == "While":
            head, body, end = self.label(), self.label(), self.label()
            self.emit("label", name=head)
            if stmt["invariant"] is not None:
                self.emit("assert", cond=self.expression(stmt["invariant"]))
            condition = self.expression(stmt["condition"])
            self.emit("branch", cond=condition, true=body, false=end)
            self.emit("label", name=body)
            self.statement(stmt["body"])
            self.emit("jump", target=head)
            self.emit("label", name=end)
        elif kind in ("Assert", "Assume"):
            self.emit(kind.lower(), cond=self.expression(stmt["predicate"]))
        else:
            raise ValueError(f"unsupported IR statement: {kind}")


def generate(ast):
    functions = {}
    for declaration in ast["declarations"]:
        builder = IRBuilder()
        if declaration["type"] == "Formula":
            result = builder.expression(declaration["predicate"])
            returns = [{"name": "result", "type": "bool"}]
            builder.emit("ret", values=[result])
        else:
            if declaration["requires"] is not None:
                builder.emit("assume", cond=builder.expression(declaration["requires"]))
            builder.statement(declaration["body"])
            if declaration["ensures"] is not None:
                builder.emit("assert", cond=builder.expression(declaration["ensures"]))
            returns = [{"name": item["name"], "type": item["var_type"]}
                       for item in declaration["returns"]]
            builder.emit("ret", values=[item["name"] for item in returns])
        functions[declaration["name"]] = {
            "params": [{"name": item["name"], "type": item["var_type"]}
                       for item in declaration["params"]],
            "returns": returns,
            "instructions": builder.code
        }
    return functions
