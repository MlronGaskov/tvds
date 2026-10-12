from dataclasses import dataclass
from functools import lru_cache

from hw01_regex_dfa.src.automata import build_automata
from hw01_regex_dfa.src.spec import TOKEN_RULES


@dataclass(frozen=True)
class Token:
    kind: str
    lexeme: str
    line: int
    column: int


class LexicalError(Exception):
    pass


@lru_cache(maxsize=1)
def get_dfa():
    return build_automata(TOKEN_RULES)[2]


def advance_position(text, line, column):
    previous_cr = False
    for char in text:
        if char == "\r":
            line += 1
            column = 1
            previous_cr = True
        elif char == "\n":
            if not previous_cr:
                line += 1
            column = 1
            previous_cr = False
        else:
            column += 1
            previous_cr = False
    return line, column


def tokenize(text):
    dfa = get_dfa()
    tokens = []
    pos = 0
    line = column = 1

    while pos < len(text):
        state = dfa.start
        end = pos
        last_accept = None

        while end < len(text):
            char = text[end]
            current_rule = dfa.accepting[state]
            if ord(char) >= 128 and current_rule is not None and dfa.rules[current_rule].name == "COMMENT":
                char = " "
            state = dfa.next_state(state, char)
            if state == dfa.trap:
                break
            end += 1
            rule = dfa.accepting[state]
            if rule is not None:
                last_accept = (end, rule)

        if last_accept is None:
            raise LexicalError(f"{line}:{column}: unexpected character {text[pos]!r}")

        end, rule = last_accept
        lexeme = text[pos:end]
        kind = dfa.rules[rule].name
        if kind == "BAD_INT":
            raise LexicalError(f"{line}:{column}: invalid integer {lexeme!r}")
        if kind not in ("WS", "COMMENT"):
            tokens.append(Token(kind, lexeme, line, column))
        line, column = advance_position(lexeme, line, column)
        pos = end

    tokens.append(Token("EOF", "", line, column))
    return tokens
