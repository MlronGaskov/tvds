import unittest

from hw02_parsing.parser import parse_source
from hw03_types.semantic import analyze


class TypeTests(unittest.TestCase):
    def check(self, source):
        ast, errors = parse_source(source, with_positions=True)
        self.assertEqual([], errors)
        return analyze(ast)

    def ok(self, source):
        ast, errors = self.check(source)
        self.assertEqual([], errors)
        return ast

    def bad(self, source, *messages):
        _, errors = self.check(source)
        for message in messages:
            self.assertTrue(any(message in error for error in errors), errors)
        for error in errors:
            self.assertRegex(error, r"^\d+:\d+: ")
        return errors

    def test_integer_types(self):
        ast = self.ok("f(a:int) returns r:int { r = -(a + 2) * 3; }")
        value = ast["declarations"][0]["body"]["statements"][0]["value"]
        self.assertEqual("int", value["inferred_type"])
        self.assertEqual("int", value["left"]["inferred_type"])
        self.assertEqual((1, 39), (value["line"], value["column"]))

    def test_conditions_and_contracts(self):
        self.ok("f(x:int) requires x >= 0 returns r:int ensures r >= x { "
                "assume x >= 0; while (x > 0) invariant x >= 0 { r = x; } "
                "if (x == 0 or not (x > 0)) r = 1; else r = 2; assert r >= 0; }")

    def test_infer_local(self):
        ast = self.ok("f(a:int) returns r:int uses x { x = a + 1; r = x; }")
        func = ast["declarations"][0]
        self.assertEqual("int", func["uses"][0]["inferred_type"])
        self.assertEqual("int", func["body"]["statements"][1]["value"]["inferred_type"])

    def test_explicit_local(self):
        self.ok("f() returns r:int uses x:int { x = 3; r = x; }")

    def test_arrays(self):
        ast = self.ok("f(a:int[], i:int) returns r:int { a[i] = 7; r = a[i] + length(a); }")
        statements = ast["declarations"][0]["body"]["statements"]
        self.assertEqual("int[]", statements[0]["value"]["inferred_type"])
        self.assertEqual("int", statements[1]["value"]["inferred_type"])

    def test_function_call_and_forward_reference(self):
        self.ok("f(a:int) returns r:int { r = g(a); } "
                "g(a:int) returns r:int { r = a + 1; }")

    def test_multiple_returns(self):
        ast = self.ok("f(a:int) returns x:int, y:int { x = a; y = a + 1; } "
                      "g(a:int) returns x:int, y:int { x, y = f(a); }")
        call = ast["declarations"][1]["body"]["statements"][0]["value"]
        self.assertEqual(["int", "int"], call["inferred_type"])

    def test_formula_and_quantifier(self):
        self.ok("positive(x:int) => exists(i:int | i > x) "
                "f(x:int) requires positive(x) returns r:int { r = x; }")

    def test_duplicate_functions(self):
        self.bad("f() returns r:int { r = 1; } f() returns r:int { r = 2; }", "duplicate function 'f'")

    def test_duplicate_variables(self):
        self.bad("f(a:int) returns a:int uses x:int, x:int { a = 1; }",
                 "duplicate declaration 'a'", "duplicate declaration 'x'")

    def test_unknown_variable(self):
        errors = self.bad("f() returns r:int { r = missing + 2; }", "unknown variable 'missing'")
        self.assertIn("1:25:", errors[0])

    def test_unknown_function(self):
        self.bad("f() returns r:int { r = missing(2); }", "unknown function 'missing'")

    def test_wrong_argument_count(self):
        self.bad("f(x:int) returns r:int { r = x; } g() returns r:int { r = f(); }",
                 "expects 1 arguments, got 0")

    def test_wrong_argument_type(self):
        self.bad("f(x:int) returns r:int { r = x; } g(a:int[]) returns r:int { r = f(a); }",
                 "argument 1 of 'f': expected int, got int[]")

    def test_wrong_assigned_type(self):
        self.bad("f(a:int[]) returns r:int { r = a; }", "cannot assign int[]")

    def test_wrong_explicit_local_type(self):
        self.bad("f(a:int[]) returns r:int uses x:int { x = a; r = 1; }", "cannot assign int[]")

    def test_local_type_conflict(self):
        self.bad("f(a:int[]) returns r:int uses x { x = 2; x = a; r = 1; }", "cannot assign int[]")

    def test_local_used_before_assignment(self):
        self.bad("f() returns r:int uses x { r = x; x = 2; }", "used before type inference")

    def test_local_type_cannot_be_inferred(self):
        self.bad("f() returns r:int uses x { r = 1; }", "cannot infer type of local 'x'")

    def test_incompatible_binary_operands(self):
        self.bad("f(a:int[]) returns r:int { r = a + 1; }", "operator '+' cannot be applied")

    def test_condition_must_be_boolean(self):
        self.bad("f() returns r:int if (g()) r = 1; g() returns r:int { r = 2; }",
                 "expected bool, got int")

    def test_assert_must_be_boolean(self):
        self.bad("f() returns r:int { assert g(); r = 1; } "
                 "g() returns r:int { r = 2; }", "expected bool, got int")

    def test_invalid_array_base(self):
        self.bad("f(a:int) returns r:int { r = a[0]; }", "cannot index value of type int")

    def test_invalid_index_type(self):
        self.bad("f(a:int[]) returns r:int { r = a[positive(1)]; } "
                 "positive(x:int) => x > 0", "array index must be int")

    def test_invalid_array_element_type(self):
        self.bad("f(a:int[], b:int[]) returns r:int { a[0] = b; r = 1; }",
                 "array element must be int")

    def test_local_cannot_infer_tuple(self):
        self.bad("f(a:int) returns x:int, y:int { x = a; y = a; } "
                 "g(a:int) returns r:int uses z { z = f(a); r = 1; }",
                 "cannot infer type of 'z' from multiple return values")

    def test_multiple_return_count_mismatch(self):
        self.bad("f() returns r:int { r = 1; } "
                 "g() returns x:int, y:int { x, y = f(); }", "assignment expects 2 values, got 1")

    def test_multiple_return_type_mismatch(self):
        self.bad("f(a:int[]) returns x:int[], y:int { x = a; y = 1; } "
                 "g(a:int[]) returns x:int, y:int { x, y = f(a); }", "cannot assign int[]")

    def test_multiple_errors(self):
        errors = self.bad("f(a:int) returns r:int { r = unknown + 1; assert length(a) > 0; }",
                          "unknown variable", "argument 1 of 'length'")
        self.assertEqual(2, len(errors))

    def test_unknown_argument_does_not_cascade(self):
        errors = self.bad("f(a:int) returns r:int { r = length(missing); }", "unknown variable")
        self.assertEqual(1, len(errors))

    def test_parser_backward_compatibility(self):
        ast, errors = parse_source("f() returns r:int { r = 1; }")
        self.assertEqual([], errors)
        self.assertNotIn("line", ast["declarations"][0]["body"]["statements"][0]["value"])


if __name__ == "__main__":
    unittest.main()
