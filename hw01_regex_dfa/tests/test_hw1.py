import unittest

from src.automata import build_automata
from src.spec import REQUIRED_CASES, TOKEN_RULES


class HW1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nfa, cls.dfa, cls.min_dfa = build_automata(TOKEN_RULES)

    def test_required_cases(self):
        for name, text, expected in REQUIRED_CASES:
            with self.subTest(name=name):
                rule = self.min_dfa.recognize(text)
                actual = None if rule is None else rule.name
                self.assertEqual(expected, actual)

    def test_non_ascii_goes_to_trap(self):
        for state in range(self.min_dfa.state_count):
            self.assertEqual(self.min_dfa.trap, self.min_dfa.next_state(state, "Ж"))

    def test_trap_loops_to_itself(self):
        for code in range(128):
            self.assertEqual(self.min_dfa.trap, self.min_dfa.transitions[self.min_dfa.trap][code])

    def test_minimization(self):
        self.assertLessEqual(self.min_dfa.state_count, self.dfa.state_count)

    def test_tokenize_maximal_munch(self):
        tokens = self.min_dfa.tokenize("12345+67")
        actual = [(rule.name, value) for rule, value in tokens]
        self.assertEqual([("INT", "12345"), ("PLUS", "+"), ("INT", "67")], actual)

    def test_tokenize_longest_operator(self):
        tokens = self.min_dfa.tokenize("a==b")
        actual = [(rule.name, value) for rule, value in tokens]
        self.assertEqual([("IDENT", "a"), ("EQ", "=="), ("IDENT", "b")], actual)

    def test_tokenize_keyword_prefix(self):
        tokens = self.min_dfa.tokenize("ifValue if")
        actual = [(rule.name, value) for rule, value in tokens]
        self.assertEqual([("IDENT", "ifValue"), ("WS", " "), ("KW_IF", "if")], actual)

    def test_tokenize_non_ascii_rejected(self):
        with self.assertRaises(ValueError):
            self.min_dfa.tokenize("abcЖ")

    def test_bad_int_rejected(self):
        for text in ("00", "01", "007", "0123"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    self.min_dfa.tokenize(text)


if __name__ == "__main__":
    unittest.main()
