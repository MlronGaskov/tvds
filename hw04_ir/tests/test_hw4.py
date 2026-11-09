import json
import unittest

from hw02_parsing.parser import parse_source
from hw03_types.semantic import analyze
from hw04_ir.flow import cfg, color, interference, metrics
from hw04_ir.ir import generate
from hw04_ir.optimize import optimize
from hw04_ir.runtime import run


class IRTests(unittest.TestCase):
    def compile(self, source):
        ast, errors = parse_source(source, with_positions=True)
        self.assertEqual([], errors)
        ast, errors = analyze(ast)
        self.assertEqual([], errors)
        functions = generate(ast)
        optimized = {name: {**function, "instructions": optimize(function["instructions"])}
                     for name, function in functions.items()}
        return functions, optimized

    def equivalent(self, source, cases, name="f"):
        before, after = self.compile(source)
        for args in cases:
            self.assertEqual(run(before, name, args), run(after, name, args))
        return before, after

    def test_arithmetic_and_simplification(self):
        source = "f(a:int) returns r:int uses x { x = 2 * 3 + 0; r = x + a; }"
        before, after = self.equivalent(source, [[-10], [0], [1], [7]])
        self.assertLess(metrics(after["f"]["instructions"])["instructions"],
                        metrics(before["f"]["instructions"])["instructions"])

    def test_integer_division(self):
        source = "f(a:int) returns r:int { r = (0 - a) / 2; }"
        self.equivalent(source, [[-5], [-2], [1], [7], [0]])

    def test_if_else(self):
        source = "f(a:int) returns r:int { if (a > 0) r = a; else r = 0 - a; }"
        before, after = self.equivalent(source, [[-10], [0], [1], [5]])
        blocks = cfg(after["f"]["instructions"])
        self.assertTrue(any(len(block["succ"]) == 2 for block in blocks))
        self.assertTrue(any(len(block["pred"]) == 2 for block in blocks))

    def test_while(self):
        source = ("f(n:int) returns r:int uses i { r = 0; i = 0; "
                  "while (i < n) invariant i >= 0 { r = r + i; i = i + 1; } }")
        before, after = self.equivalent(source, [[0], [1], [2], [5], [10]])
        self.assertEqual((10,), run(after, "f", [5]))
        blocks = cfg(after["f"]["instructions"])
        self.assertTrue(any(block["id"] in other["succ"] and other["id"] != block["id"]
                            for block in blocks for other in blocks))

    def test_forward_call(self):
        source = ("f(x:int) returns r:int { r = g(x) + 1; } "
                  "g(x:int) returns r:int { r = x * 2; }")
        self.equivalent(source, [[-3], [0], [4]])

    def test_multiple_returns(self):
        source = ("pair(x:int) returns a:int, b:int { a = x; b = x + 1; } "
                  "f(x:int) returns r:int uses a, b { a, b = pair(x); r = a + b; }")
        before, after = self.equivalent(source, [[0], [1], [6]])
        self.assertEqual((13,), run(after, "f", [6]))

    def test_array_get_and_update(self):
        source = "f(a:int[], i:int) returns r:int { a[i] = 7; r = a[i] + length(a); }"
        args = [[1, 2, 3], 1]
        before, after = self.equivalent(source, [args])
        self.assertEqual((10,), run(after, "f", args))
        self.assertEqual([1, 2, 3], args[0])

    def test_formula(self):
        source = "positive(x:int) => x > 0 f(x:int) returns r:int { if (positive(x)) r = 1; else r = 0; }"
        before, after = self.equivalent(source, [[-1], [0], [7]], name="f")
        self.assertEqual((True,), run(after, "positive", [1]))
        self.assertEqual((False,), run(before, "positive", [0]))

    def test_short_circuit(self):
        source = ("f(x:int) returns r:int { "
                  "if (x == 0 or 10 / x > 1) r = 1; else r = 2; }")
        before, after = self.equivalent(source, [[0], [1], [2], [10], [-1]])
        self.assertEqual((1,), run(after, "f", [0]))

    def test_implication(self):
        source = "f(x:int) returns r:int { if (x > 0 -> x >= 1) r = 1; else r = 2; }"
        self.equivalent(source, [[-1], [0], [1], [3]])

    def test_assert_and_assume(self):
        source = ("f(x:int) requires x >= 0 returns r:int ensures r >= x "
                  "{ assume x >= 0; r = x + 1; assert r > 0; }")
        self.equivalent(source, [[0], [1], [5]])

    def test_dead_code(self):
        source = "f(x:int) returns r:int uses y:int { y = 4 + 5; y = 7; r = x; }"
        before, after = self.equivalent(source, [[1], [3]])
        self.assertLess(len(after["f"]["instructions"]), len(before["f"]["instructions"]))

    def test_division_by_zero_is_not_removed(self):
        source = "f(x:int) returns r:int uses y:int { y = 10 / x; r = 2; }"
        before, after = self.compile(source)
        self.assertTrue(any(i["op"] == "bin" and i["operator"] == "/"
                            for i in after["f"]["instructions"]))
        for version in (before, after):
            with self.assertRaises(ZeroDivisionError):
                run(version, "f", [0])

    def test_interference_and_coloring(self):
        source = "f(a:int, b:int) returns r:int { r = (a + 1) * (b + 2); }"
        before, after = self.equivalent(source, [[2, 3], [0, 1]])
        graph = interference(cfg(after["f"]["instructions"]))
        colors = color(graph)
        for name, neighbors in graph.items():
            for neighbor in neighbors:
                self.assertNotEqual(colors[name], colors[neighbor])
        self.assertGreaterEqual(len(set(colors.values())), 2)

    def test_disable_optimizations(self):
        source = "f() returns r:int { r = 2 * 3 + 0; }"
        before, _ = self.compile(source)
        code = before["f"]["instructions"]
        self.assertEqual(code, optimize(code, False, False, False))
        self.assertNotEqual(code, optimize(code))

    def test_json_output(self):
        before, after = self.compile("f(x:int) returns r:int { r = x + 1; }")
        code = after["f"]["instructions"]
        json.dumps({"before": before["f"], "after": code, "cfg": cfg(code),
                    "interference": interference(cfg(code))})


if __name__ == "__main__":
    unittest.main()
