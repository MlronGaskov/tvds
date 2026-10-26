class SemanticAnalyzer:
    def __init__(self):
        self.errors = []
        self.functions = {}

    def error(self, node, message):
        self.errors.append(f"{node['line']}:{node['column']}: {message}")

    def declare(self, scope, declaration):
        name = declaration["name"]
        if name in scope:
            self.error(declaration, f"duplicate declaration '{name}'")
        else:
            scope[name] = declaration

    def analyze(self, ast):
        for declaration in ast["declarations"]:
            name = declaration["name"]
            if name in self.functions:
                self.error(declaration, f"duplicate function '{name}'")
                continue
            returns = (["bool"] if declaration["type"] == "Formula" else
                       [item["var_type"] for item in declaration["returns"]])
            self.functions[name] = ([item["var_type"] for item in declaration["params"]], returns)

        for declaration in ast["declarations"]:
            scope = {}
            for param in declaration["params"]:
                self.declare(scope, param)
            if declaration["type"] == "Formula":
                self.expect_bool(declaration["predicate"], scope)
                continue
            if declaration["requires"] is not None:
                self.expect_bool(declaration["requires"], scope)
            for result in declaration["returns"]:
                self.declare(scope, result)
            if declaration["ensures"] is not None:
                self.expect_bool(declaration["ensures"], scope)
            for local in declaration["uses"]:
                self.declare(scope, local)
            self.statement(declaration["body"], scope)
            for local in declaration["uses"]:
                if local["var_type"] is None and "inferred_type" not in local:
                    self.error(local, f"cannot infer type of local '{local['name']}'")
        return ast, self.errors

    def expect_bool(self, expression, scope):
        result = self.expression(expression, scope)
        if result not in ("bool", "error"):
            self.error(expression, f"expected bool, got {self.type_name(result)}")

    def type_name(self, value):
        if isinstance(value, tuple):
            return "(" + ", ".join(value) + ")"
        return value

    def expression(self, expr, scope):
        kind = expr["type"]
        if kind == "Int":
            result = "int"
        elif kind == "Bool":
            result = "bool"
        elif kind == "Var":
            name = expr["name"]
            if name not in scope:
                self.error(expr, f"unknown variable '{name}'")
                result = "error"
            else:
                decl = scope[name]
                result = decl["var_type"] or decl.get("inferred_type")
                if result is None:
                    self.error(expr, f"local '{name}' used before type inference")
                    result = "error"
        elif kind == "Call":
            name = expr["name"]
            args = [self.expression(arg, scope) for arg in expr["args"]]
            if name == "length":
                params, returns = ["int[]"], ["int"]
            elif name in self.functions:
                params, returns = self.functions[name]
            else:
                self.error(expr, f"unknown function '{name}'")
                params, returns = [], ["error"]
            if name == "length" or name in self.functions:
                if len(args) != len(params):
                    self.error(expr, f"function '{name}' expects {len(params)} arguments, got {len(args)}")
                for index, (actual, expected) in enumerate(zip(args, params), 1):
                    if actual not in (expected, "error"):
                        self.error(expr["args"][index - 1],
                                   f"argument {index} of '{name}': expected {expected}, got {self.type_name(actual)}")
            result = returns[0] if len(returns) == 1 else tuple(returns)
        elif kind in ("Index", "ArraySet"):
            array = self.expression(expr["array"], scope)
            index = self.expression(expr["index"], scope)
            if index not in ("int", "error"):
                self.error(expr["index"], f"array index must be int, got {self.type_name(index)}")
            if array not in ("int[]", "error"):
                self.error(expr["array"], f"cannot index value of type {self.type_name(array)}")
            if kind == "ArraySet":
                value = self.expression(expr["value"], scope)
                if value not in ("int", "error"):
                    self.error(expr["value"], f"array element must be int, got {self.type_name(value)}")
                result = "int[]" if array == "int[]" and index == "int" and value == "int" else "error"
            else:
                result = "int" if array == "int[]" and index == "int" else "error"
        elif kind == "Unary":
            actual = self.expression(expr["operand"], scope)
            expected, result = ("int", "int") if expr["op"] == "-" else ("bool", "bool")
            if actual not in (expected, "error"):
                self.error(expr, f"operator '{expr['op']}' expects {expected}, got {self.type_name(actual)}")
                result = "error"
            elif actual == "error":
                result = "error"
        elif kind == "Binary":
            left = self.expression(expr["left"], scope)
            right = self.expression(expr["right"], scope)
            op = expr["op"]
            if op in ("+", "-", "*", "/", "<", "<=", ">", ">="):
                valid = left == right == "int"
                result = "int" if op in ("+", "-", "*", "/") else "bool"
            elif op in ("and", "or", "->"):
                valid = left == right == "bool"
                result = "bool"
            else:
                valid = left == right and left in ("int", "bool", "int[]")
                result = "bool"
            if not valid and "error" not in (left, right):
                self.error(expr, f"operator '{op}' cannot be applied to {self.type_name(left)} and {self.type_name(right)}")
            if not valid:
                result = "error"
        elif kind == "Quantifier":
            nested = scope.copy()
            nested[expr["variable"]["name"]] = expr["variable"]
            self.expect_bool(expr["predicate"], nested)
            result = "bool"
        else:
            raise ValueError(f"unknown expression type: {kind}")
        expr["inferred_type"] = list(result) if isinstance(result, tuple) else result
        return result

    def assign(self, target, value_type, scope):
        name = target["name"]
        if name not in scope:
            self.error(target, f"unknown variable '{name}'")
            target["inferred_type"] = "error"
            return
        declaration = scope[name]
        declared = declaration["var_type"] or declaration.get("inferred_type")
        if declared is None and isinstance(value_type, tuple):
            self.error(target, f"cannot infer type of '{name}' from multiple return values")
        elif declared is None and value_type != "error":
            declaration["inferred_type"] = value_type
            declared = value_type
        target["inferred_type"] = declared or "error"
        if declared is not None and value_type not in (declared, "error"):
            self.error(target, f"cannot assign {self.type_name(value_type)} to '{name}' of type {declared}")

    def statement(self, stmt, scope):
        kind = stmt["type"]
        if kind == "Block":
            for item in stmt["statements"]:
                self.statement(item, scope)
        elif kind == "Assign":
            value_type = self.expression(stmt["value"], scope)
            self.assign(stmt["target"], value_type, scope)
        elif kind == "MultiAssign":
            value_type = self.expression(stmt["value"], scope)
            if value_type == "error":
                return
            types = value_type if isinstance(value_type, tuple) else (value_type,)
            if len(types) != len(stmt["targets"]):
                self.error(stmt, f"assignment expects {len(stmt['targets'])} values, got {len(types)}")
            for target, actual in zip(stmt["targets"], types):
                self.assign(target, actual, scope)
        elif kind == "If":
            self.expect_bool(stmt["condition"], scope)
            self.statement(stmt["then"], scope)
            if stmt["otherwise"] is not None:
                self.statement(stmt["otherwise"], scope)
        elif kind == "While":
            self.expect_bool(stmt["condition"], scope)
            if stmt["invariant"] is not None:
                self.expect_bool(stmt["invariant"], scope)
            self.statement(stmt["body"], scope)
        elif kind in ("Assert", "Assume"):
            self.expect_bool(stmt["predicate"], scope)
        else:
            raise ValueError(f"unknown statement type: {kind}")


def analyze(ast):
    return SemanticAnalyzer().analyze(ast)
