import unittest

from hw02_parsing.lexer import LexicalError, tokenize
from hw02_parsing.parser import parse_source


class ParsingTests(unittest.TestCase):
    def parse_ok(self, source):
        ast, errors = parse_source(source)
        self.assertEqual([], errors)
        return ast

    def parse_error(self, source):
        ast, errors = parse_source(source)
        self.assertTrue(errors)
        return ast, errors

    def test_token_positions(self):
        tokens = tokenize("// привет\r\n  x = 1;\r\n")
        self.assertEqual(("IDENT", "x", 2, 3),
                         (tokens[0].kind, tokens[0].lexeme, tokens[0].line, tokens[0].column))
        self.assertEqual(("ASSIGN", 2, 5), (tokens[1].kind, tokens[1].line, tokens[1].column))
        self.assertEqual(("EOF", 3, 1), (tokens[-1].kind, tokens[-1].line, tokens[-1].column))

    def test_simple_function_snapshot(self):
        ast = self.parse_ok("main() returns r:int { r = 1 + 2 * 3; }")
        self.assertEqual({
            "type": "Module", "declarations": [{
                "type": "Function", "name": "main", "params": [],
                "returns": [{"type": "VarDecl", "name": "r", "var_type": "int"}],
                "requires": None, "ensures": None, "uses": [],
                "body": {"type": "Block", "statements": [{
                    "type": "Assign", "target": {"type": "Var", "name": "r"},
                    "value": {"type": "Binary", "op": "+",
                              "left": {"type": "Int", "value": 1},
                              "right": {"type": "Binary", "op": "*",
                                        "left": {"type": "Int", "value": 2},
                                        "right": {"type": "Int", "value": 3}}}
                }]}
            }]
        }, ast)

    def test_contracts_and_local_variables(self):
        ast = self.parse_ok(
            "f(a:int[], n:int) requires n >= 0 returns r:int ensures r >= 0 uses i, j:int { i = length(a); r = i; }")
        function = ast["declarations"][0]
        self.assertEqual(["int[]", "int"], [param["var_type"] for param in function["params"]])
        self.assertEqual([None, "int"], [var["var_type"] for var in function["uses"]])
        self.assertEqual("Binary", function["requires"]["type"])
        self.assertEqual("Call", function["body"]["statements"][0]["value"]["type"])

    def test_optional_function_keyword(self):
        ast = self.parse_ok("function f(x:int) returns r:int { r = x; }")
        self.assertEqual("f", ast["declarations"][0]["name"])

    def test_if_else_and_while(self):
        ast = self.parse_ok(
            "f(x:int) returns r:int uses i:int { i = x; while (i > 0) invariant i >= 0 { i = i - 1; } if (i == 0) r = i; else r = 1; }")
        statements = ast["declarations"][0]["body"]["statements"]
        self.assertEqual(["Assign", "While", "If"], [s["type"] for s in statements])
        self.assertEqual("Binary", statements[1]["invariant"]["type"])
        self.assertEqual("Assign", statements[2]["otherwise"]["type"])

    def test_dangling_else_binds_nearest(self):
        ast = self.parse_ok("f() returns r:int if (true) if (false) r = 1; else r = 2;")
        outer = ast["declarations"][0]["body"]
        self.assertIsNone(outer["otherwise"])
        self.assertEqual("Assign", outer["then"]["otherwise"]["type"])

    def test_assert_assume_and_comments(self):
        ast = self.parse_ok("f(x:int) returns r:int { assume x > 0; // Привет 🙂\n assert x != 0; r = x; }")
        statements = ast["declarations"][0]["body"]["statements"]
        self.assertEqual(["Assume", "Assert", "Assign"], [s["type"] for s in statements])

    def test_array_update_desugaring(self):
        ast = self.parse_ok("f(a:int[], i:int) returns r:int[] { a[i] = 5; r = a; }")
        assignment = ast["declarations"][0]["body"]["statements"][0]
        self.assertEqual({"type": "Var", "name": "a"}, assignment["target"])
        self.assertEqual("ArraySet", assignment["value"]["type"])
        self.assertEqual("i", assignment["value"]["index"]["name"])

    def test_nested_array_update(self):
        ast = self.parse_ok("f(a:int[], i:int, j:int) returns r:int { a[i][j] = 5; r = 1; }")
        updated = ast["declarations"][0]["body"]["statements"][0]["value"]
        self.assertEqual("ArraySet", updated["type"])
        self.assertEqual("ArraySet", updated["value"]["type"])

    def test_array_access(self):
        ast = self.parse_ok("f(a:int[], i:int) returns r:int { r = a[i]; }")
        self.assertEqual("Index", ast["declarations"][0]["body"]["statements"][0]["value"]["type"])

    def test_multi_return_and_call(self):
        ast = self.parse_ok("f(a:int) returns x:int, y:int { x, y = pair(a); }")
        statement = ast["declarations"][0]["body"]["statements"][0]
        self.assertEqual("MultiAssign", statement["type"])
        self.assertEqual("pair", statement["value"]["name"])

    def test_formula_and_quantifier(self):
        ast = self.parse_ok(
            "positive(x:int) => exists(i:int | i > x)\nf(x:int) requires positive(x) returns r:int { r = x; }")
        self.assertEqual(["Formula", "Function"], [d["type"] for d in ast["declarations"]])
        self.assertEqual("Quantifier", ast["declarations"][0]["predicate"]["type"])

    def test_boolean_precedence_and_implication(self):
        ast = self.parse_ok("f(x:int, y:int) returns r:int if (not x > 0 and y < 2 or x == y -> true) r = 1;")
        condition = ast["declarations"][0]["body"]["condition"]
        self.assertEqual("->", condition["op"])
        self.assertEqual("or", condition["left"]["op"])
        self.assertEqual("and", condition["left"]["left"]["op"])
        self.assertEqual("not", condition["left"]["left"]["left"]["op"])

    def test_missing_closing_parenthesis(self):
        _, errors = self.parse_error("f() returns r:int { if (r > 0 { r = 1; } }")
        self.assertIn("expected ')', got '{'", errors[0])
        self.assertRegex(errors[0], r"\d+:\d+:")

    def test_extra_tokens(self):
        _, errors = self.parse_error("f() returns r:int { r = 1; } } ")
        self.assertIn("expected identifier, got '}'", errors[0])

    def test_invalid_operator(self):
        _, errors = self.parse_error("f() returns r:int { r : 1; r = 2; }")
        self.assertIn("expected '=', got ':'", errors[0])

    def test_missing_expression_and_recovery(self):
        ast, errors = self.parse_error("f() returns r:int { r = 1 + ; r = 2; assert r > 0; }")
        statements = ast["declarations"][0]["body"]["statements"]
        self.assertEqual(1, len(errors))
        self.assertEqual(["Assign", "Assert"], [s["type"] for s in statements])
        self.assertIn("2", str(statements[0]["value"]))

    def test_missing_semicolon(self):
        _, errors = self.parse_error("f() returns r:int { r = 1 }")
        self.assertIn("expected ';', got '}'", errors[0])

    def test_empty_source(self):
        _, errors = self.parse_error("")
        self.assertIn("got end of input", errors[0])

    def test_unclosed_block(self):
        _, errors = self.parse_error("f() returns r:int { r = 1;")
        self.assertIn("expected '}', got end of input", errors[0])

    def test_non_ascii_outside_comment(self):
        with self.assertRaises(LexicalError):
            parse_source("f() returns r:int { r = Ж; }")

    def test_bad_integer(self):
        with self.assertRaises(LexicalError):
            parse_source("f() returns r:int { r = 01; }")


if __name__ == "__main__":
    unittest.main()
