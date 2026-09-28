from dataclasses import dataclass

ASCII = frozenset(range(128))


@dataclass(frozen=True)
class CharSet:
    chars: frozenset[int]


@dataclass(frozen=True)
class Concat:
    parts: tuple


@dataclass(frozen=True)
class Alternate:
    parts: tuple


@dataclass(frozen=True)
class Star:
    inner: object


@dataclass(frozen=True)
class Plus:
    inner: object


class RegexParser:
    def __init__(self, pattern: str):
        self.pattern = pattern
        self.pos = 0

    def parse(self):
        node = self.parse_alternate()
        if self.pos != len(self.pattern):
            raise ValueError(f"unexpected {self.pattern[self.pos]!r}")
        return node

    def parse_alternate(self):
        parts = [self.parse_concat()]
        while self.peek() == "|":
            self.pos += 1
            parts.append(self.parse_concat())
        return parts[0] if len(parts) == 1 else Alternate(tuple(parts))

    def parse_concat(self):
        parts = []
        while self.pos < len(self.pattern) and self.peek() not in ")|":
            parts.append(self.parse_repeat())
        if not parts:
            raise ValueError("empty regex part")
        return parts[0] if len(parts) == 1 else Concat(tuple(parts))

    def parse_repeat(self):
        node = self.parse_atom()
        while self.peek() in ("*", "+"):
            op = self.peek()
            self.pos += 1
            node = Star(node) if op == "*" else Plus(node)
        return node

    def parse_atom(self):
        ch = self.peek()
        if ch == "(":
            self.pos += 1
            node = self.parse_alternate()
            if self.peek() != ")":
                raise ValueError("missing )")
            self.pos += 1
            return node
        if ch == "[":
            return CharSet(self.parse_class())
        if ch == "\\":
            return CharSet(frozenset((self.parse_escape(),)))
        if ch is None or ch in ")|*+":
            raise ValueError(f"unexpected regex symbol {ch!r}")
        self.pos += 1
        self.check_ascii(ch)
        return CharSet(frozenset((ord(ch),)))

    def parse_class(self):
        self.pos += 1
        negated = self.peek() == "^"
        if negated:
            self.pos += 1
        chars = set()
        first = True
        while True:
            if self.pos >= len(self.pattern):
                raise ValueError("unterminated character class")
            if self.peek() == "]" and not first:
                self.pos += 1
                break
            start = self.parse_class_char()
            first = False
            if self.peek() == "-" and self.pos + 1 < len(self.pattern) and self.pattern[self.pos + 1] != "]":
                self.pos += 1
                end = self.parse_class_char()
                chars.update(range(start, end + 1))
            else:
                chars.add(start)
        return ASCII.difference(chars) if negated else frozenset(chars)

    def parse_class_char(self):
        if self.peek() == "\\":
            return self.parse_escape()
        ch = self.peek()
        if ch is None:
            raise ValueError("unterminated character class")
        self.pos += 1
        self.check_ascii(ch)
        return ord(ch)

    def parse_escape(self):
        self.pos += 1
        if self.pos >= len(self.pattern):
            raise ValueError("trailing backslash")
        ch = self.pattern[self.pos]
        self.pos += 1
        escaped = {"n": "\n", "r": "\r", "t": "\t"}
        ch = escaped.get(ch, ch)
        self.check_ascii(ch)
        return ord(ch)

    def peek(self):
        return self.pattern[self.pos] if self.pos < len(self.pattern) else None

    @staticmethod
    def check_ascii(ch: str):
        if ord(ch) >= 128:
            raise ValueError("regex alphabet is ASCII")


def parse_regex(pattern: str):
    return RegexParser(pattern).parse()
