from hw02_parsing.lexer import tokenize
from hw01_regex_dfa.src.spec import TOKEN_RULES


class ParseError(Exception):
    pass


def node(kind, **fields):
    return {"type": kind, **fields}


PRECEDENCE = {
    "IMPLIES": 10,
    "KW_OR": 20,
    "KW_AND": 30,
    "EQ": 40, "NE": 40, "LT": 40, "LE": 40, "GT": 40, "GE": 40,
    "PLUS": 50, "MINUS": 50,
    "STAR": 60, "SLASH": 60,
}

ARITHMETIC = {"PLUS", "MINUS", "STAR", "SLASH"}
COMPARISON = {"EQ", "NE", "LT", "LE", "GT", "GE"}

TOKEN_LABELS = {
    rule.name: repr(rule.regex.replace("\\", ""))
    for rule in TOKEN_RULES
    if rule.name not in {"WS", "COMMENT", "BAD_INT", "INT", "IDENT"}
}
TOKEN_LABELS.update({"IDENT": "identifier", "INT": "integer", "EOF": "end of input"})


class Parser:
    def __init__(self, tokens, with_positions=False):
        self.with_positions = with_positions
        self.tokens = tokens
        self.pos = 0
        self.errors = []

    def located(self, kind, token, **fields):
        result = node(kind, **fields)
        if self.with_positions:
            result.update(line=token.line, column=token.column)
        return result

    def peek(self):
        return self.tokens[self.pos]

    def at(self, kind):
        return self.peek().kind == kind

    def take(self):
        token = self.peek()
        if not self.at("EOF"):
            self.pos += 1
        return token

    def match(self, kind):
        if self.at(kind):
            self.take()
            return True
        return False

    def error(self, expected):
        token = self.peek()
        expected = TOKEN_LABELS.get(expected, expected)
        actual = "end of input" if token.kind == "EOF" else repr(token.lexeme)
        raise ParseError(f"{token.line}:{token.column}: expected {expected}, got {actual}")

    def expect(self, kind):
        if not self.at(kind):
            self.error(kind)
        return self.take()

    def parse(self):
        declarations = []
        if self.at("EOF"):
            self.errors.append("1:1: expected declaration, got end of input")
        while not self.at("EOF"):
            previous = self.pos
            try:
                declarations.append(self.declaration())
            except ParseError as error:
                self.errors.append(str(error))
                self.recover_declaration(previous)
            if self.pos == previous:
                self.take()
        return node("Module", declarations=declarations), self.errors

    def recover_declaration(self, start):
        depth = 0
        for token in self.tokens[start:self.pos]:
            if token.kind == "LBRACE":
                depth += 1
            elif token.kind == "RBRACE":
                depth -= 1
        while not self.at("EOF"):
            if depth == 0 and self.pos > start:
                if self.at("KW_FUNCTION") or (self.at("IDENT") and self.tokens[self.pos + 1].kind == "LPAREN"):
                    return
            token = self.take()
            if token.kind == "LBRACE":
                depth += 1
            elif token.kind == "RBRACE":
                if depth == 0:
                    return
                depth -= 1
                if depth == 0:
                    return

    def typed_var(self, optional_type=False):
        token = self.expect("IDENT")
        name = token.lexeme
        type_name = None
        if self.match("COLON"):
            self.expect("KW_INT")
            type_name = "int"
            if self.match("LBRACKET"):
                self.expect("RBRACKET")
                type_name = "int[]"
        elif not optional_type:
            self.error("COLON")
        return self.located("VarDecl", token, name=name, var_type=type_name)
    def typed_vars(self, required=False, optional_type=False):
        vars_ = []
        if required or self.at("IDENT"):
            vars_.append(self.typed_var(optional_type))
            while self.match("COMMA"):
                vars_.append(self.typed_var(optional_type))
        return vars_

    def declaration(self):
        start = self.peek()
        explicit_function = self.match("KW_FUNCTION")
        name = self.expect("IDENT").lexeme
        self.expect("LPAREN")
        params = self.typed_vars()
        self.expect("RPAREN")
        if self.match("FAT_ARROW"):
            if explicit_function:
                self.error("KW_RETURNS")
            predicate = self.boolean("predicate")
            return self.located("Formula", start, name=name, params=params, predicate=predicate)
        requires = None
        if self.match("KW_REQUIRES"):
            requires = self.boolean("predicate")
        self.expect("KW_RETURNS")
        returns = self.typed_vars(required=True)
        ensures = None
        if self.match("KW_ENSURES"):
            ensures = self.boolean("predicate")
        uses = []
        if self.match("KW_USES"):
            uses = self.typed_vars(required=True, optional_type=True)
        body = self.statement()
        return self.located("Function", start, name=name, params=params, returns=returns,
                    requires=requires, ensures=ensures, uses=uses, body=body)

    def statement(self):
        start = self.peek()
        if self.match("LBRACE"):
            statements = []
            while not self.at("RBRACE") and not self.at("EOF"):
                previous = self.pos
                try:
                    statements.append(self.statement())
                except ParseError as error:
                    self.errors.append(str(error))
                    self.recover_statement(previous)
                if self.pos == previous and not self.at("EOF") and not self.at("RBRACE"):
                    self.take()
            self.expect("RBRACE")
            return self.located("Block", start, statements=statements)
        if self.match("KW_IF"):
            self.expect("LPAREN")
            condition = self.boolean("condition")
            self.expect("RPAREN")
            then = self.statement()
            otherwise = self.statement() if self.match("KW_ELSE") else None
            return self.located("If", start, condition=condition, then=then, otherwise=otherwise)
        if self.match("KW_WHILE"):
            self.expect("LPAREN")
            condition = self.boolean("condition")
            self.expect("RPAREN")
            invariant = self.boolean("predicate") if self.match("KW_INVARIANT") else None
            return self.located("While", start, condition=condition, invariant=invariant, body=self.statement())
        if self.match("KW_ASSERT"):
            predicate = self.boolean("predicate")
            self.expect("SEMICOLON")
            return self.located("Assert", start, predicate=predicate)

        if self.match("KW_ASSUME"):
            predicate = self.boolean("predicate")
            self.expect("SEMICOLON")
            return self.located("Assume", start, predicate=predicate)

        if self.at("IDENT"):
            return self.assignment()
        self.error("statement")
        return None

    def recover_statement(self, start):
        depth = 0
        for token in self.tokens[start:self.pos]:
            if token.kind == "LBRACE":
                depth += 1
            elif token.kind == "RBRACE":
                depth -= 1
        while not self.at("EOF"):
            kind = self.peek().kind
            if kind == "LBRACE":
                depth += 1
                self.take()
            elif kind == "RBRACE":
                if depth == 0:
                    return
                depth -= 1
                self.take()
                if depth == 0:
                    return
            elif kind == "SEMICOLON" and depth == 0:
                self.take()
                return
            else:
                self.take()

    def assignment(self):
        first = self.expect("IDENT")
        name = first.lexeme
        root = self.located("Var", first, name=name)
        target = root
        indexes = []
        prefixes = []
        while self.match("LBRACKET"):
            prefixes.append(target)
            index = self.expression()
            self.expect("RBRACKET")
            indexes.append(index)
            target = self.located("Index", first, array=target, index=index)
        targets = [target]
        while self.match("COMMA"):
            token = self.expect("IDENT")
            targets.append(self.located("Var", token, name=token.lexeme))
        self.expect("ASSIGN")
        value = self.expression()
        self.expect("SEMICOLON")

        if len(targets) > 1:
            if indexes or value["type"] != "Call":
                raise ParseError(f"{first.line}:{first.column}: multiple assignment requires a function call")
            return self.located("MultiAssign", first, targets=targets, value=value)
        if indexes:
            for array, index in reversed(list(zip(prefixes, indexes))):
                value = self.located("ArraySet", first, array=array, index=index, value=value)
            return self.located("Assign", first, target=root, value=value)
        return self.located("Assign", first, target=target, value=value)
    def boolean(self, mode):
        value = self.expression(mode=mode)
        if value["type"] not in ("Bool", "Binary", "Unary", "Quantifier", "Call"):
            self.error("predicate" if mode == "predicate" else "condition")
        if value["type"] == "Binary" and value["op"] in ("+", "-", "*", "/"):
            self.error("comparison")
        return value

    def expression(self, min_bp=0, mode="arithmetic"):
        token = self.peek()
        allowed = {"INT", "IDENT", "KW_LENGTH", "MINUS", "LPAREN"}
        if mode != "arithmetic":
            allowed.update(("KW_NOT", "KW_TRUE", "KW_FALSE"))
        if mode == "predicate":
            allowed.update(("KW_FORALL", "KW_EXISTS"))
        if token.kind not in allowed:
            self.error("expression")
        self.take()
        if token.kind == "INT":
            left = self.located("Int", token, value=int(token.lexeme))
        elif token.kind in ("IDENT", "KW_LENGTH"):
            left = self.located("Var", token, name=token.lexeme)
            while True:
                if left["type"] == "Var" and self.match("LPAREN"):
                    args = []
                    if not self.at("RPAREN"):
                        args.append(self.expression())
                        while self.match("COMMA"):
                            args.append(self.expression())
                    self.expect("RPAREN")
                    left = self.located("Call", token, name=left["name"], args=args)
                elif self.match("LBRACKET"):
                    index = self.expression()
                    self.expect("RBRACKET")
                    left = self.located("Index", token, array=left, index=index)
                else:
                    break
        elif token.kind == "MINUS":
            left = self.located("Unary", token, op="-", operand=self.expression(70, mode))
        elif token.kind == "KW_NOT" and mode != "arithmetic":
            left = self.located("Unary", token, op="not", operand=self.expression(35, mode))
        elif token.kind in ("KW_TRUE", "KW_FALSE") and mode != "arithmetic":
            left = self.located("Bool", token, value=token.kind == "KW_TRUE")
        elif token.kind in ("KW_FORALL", "KW_EXISTS") and mode == "predicate":
            self.expect("LPAREN")
            variable = self.typed_var()
            self.expect("PIPE")
            predicate = self.boolean("predicate")
            self.expect("RPAREN")
            left = self.located("Quantifier", token, op=token.lexeme, variable=variable, predicate=predicate)
        elif token.kind == "LPAREN":
            left = self.expression(mode=mode)
            self.expect("RPAREN")
        while True:
            op_token = self.peek()
            op = op_token.kind
            if op not in PRECEDENCE:
                break
            if mode == "arithmetic" and op not in ARITHMETIC:
                break
            if mode == "predicate" and op == "IMPLIES":
                break
            bp = PRECEDENCE[op]
            if bp < min_bp:
                break
            self.take()
            right_bp = bp if op == "IMPLIES" else bp + 1
            right = self.expression(right_bp, mode)
            left = self.located("Binary", op_token, op=op_token.lexeme, left=left, right=right)
        return left

def parse_source(text, with_positions=False):
    return Parser(tokenize(text), with_positions).parse()
