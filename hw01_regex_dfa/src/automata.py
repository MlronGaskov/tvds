from collections import defaultdict, deque
from dataclasses import dataclass

from .regex_parser import Alternate, CharSet, Concat, Plus, Star, parse_regex
from .spec import TokenRule

ASCII_SIZE = 128
EPSILON = None


@dataclass(frozen=True)
class Fragment:
    start: int
    accept: int


@dataclass
class NFA:
    start: int
    transitions: list
    accepting: dict

    @property
    def state_count(self):
        return len(self.transitions)


@dataclass
class DFA:
    transitions: list[list[int]]
    accepting: list[int | None]
    start: int
    trap: int
    rules: tuple[TokenRule, ...]

    @property
    def state_count(self):
        return len(self.transitions)

    def next_state(self, state: int, ch: str):
        code = ord(ch)
        return self.transitions[state][code] if code < ASCII_SIZE else self.trap

    def recognize(self, text: str):
        state = self.start
        for ch in text:
            state = self.next_state(state, ch)
        rule = self.accepting[state]
        if rule is None or self.rules[rule].name == "BAD_INT":
            return None
        return self.rules[rule]

    def tokenize(self, text: str):
        tokens = []
        pos = 0

        while pos < len(text):
            state = self.start
            end = pos
            last_accept = None

            while end < len(text):
                state = self.next_state(state, text[end])
                if state == self.trap:
                    break
                end += 1
                rule = self.accepting[state]
                if rule is not None:
                    last_accept = (end, rule)

            if last_accept is None:
                raise ValueError(f"unexpected character {text[pos]!r}")

            end, rule = last_accept
            if self.rules[rule].name == "BAD_INT":
                raise ValueError(f"invalid integer {text[pos:end]!r}")
            tokens.append((self.rules[rule], text[pos:end]))
            pos = end

        return tokens


class Thompson:
    def __init__(self):
        self.transitions = []

    def new_state(self):
        state = len(self.transitions)
        self.transitions.append(defaultdict(set))
        return state

    def add(self, source, symbol, target):
        self.transitions[source][symbol].add(target)

    def build(self, node):
        if isinstance(node, CharSet):
            start, accept = self.new_state(), self.new_state()
            for ch in node.chars:
                self.add(start, ch, accept)
            return Fragment(start, accept)
        if isinstance(node, Concat):
            parts = [self.build(part) for part in node.parts]
            for left, right in zip(parts, parts[1:]):
                self.add(left.accept, EPSILON, right.start)
            return Fragment(parts[0].start, parts[-1].accept)
        if isinstance(node, Alternate):
            start, accept = self.new_state(), self.new_state()
            for part in node.parts:
                fragment = self.build(part)
                self.add(start, EPSILON, fragment.start)
                self.add(fragment.accept, EPSILON, accept)
            return Fragment(start, accept)
        if isinstance(node, Star):
            start, accept = self.new_state(), self.new_state()
            inner = self.build(node.inner)
            self.add(start, EPSILON, accept)
            self.add(start, EPSILON, inner.start)
            self.add(inner.accept, EPSILON, inner.start)
            self.add(inner.accept, EPSILON, accept)
            return Fragment(start, accept)
        if isinstance(node, Plus):
            start, accept = self.new_state(), self.new_state()
            inner = self.build(node.inner)
            self.add(start, EPSILON, inner.start)
            self.add(inner.accept, EPSILON, inner.start)
            self.add(inner.accept, EPSILON, accept)
            return Fragment(start, accept)
        raise TypeError(type(node))


def build_nfa(rules):
    rules = tuple(rules)
    builder = Thompson()
    start = builder.new_state()
    accepting = {}
    for index, rule in enumerate(rules):
        fragment = builder.build(parse_regex(rule.regex))
        builder.add(start, EPSILON, fragment.start)
        accepting[fragment.accept] = index
    return NFA(start, builder.transitions, accepting)


def closure(nfa, states):
    result = set(states)
    stack = list(result)
    while stack:
        state = stack.pop()
        for target in nfa.transitions[state].get(EPSILON, ()):
            if target not in result:
                result.add(target)
                stack.append(target)
    return frozenset(result)


def move(nfa, states, symbol):
    result = set()
    for state in states:
        result.update(nfa.transitions[state].get(symbol, ()))
    return result


def subset_construction(nfa, rules):
    start_subset = closure(nfa, (nfa.start,))
    ids = {start_subset: 0}
    queue = deque((start_subset,))
    transitions = []
    accepting = []

    while queue:
        subset = queue.popleft()
        state = ids[subset]
        transitions.append([0] * ASCII_SIZE)
        candidates = [nfa.accepting[s] for s in subset if s in nfa.accepting]
        accepting.append(min(candidates) if candidates else None)
        for symbol in range(ASCII_SIZE):
            target = closure(nfa, move(nfa, subset, symbol))
            if target not in ids:
                ids[target] = len(ids)
                queue.append(target)
            transitions[state][symbol] = ids[target]

    trap = ids[frozenset()]
    transitions[trap] = [trap] * ASCII_SIZE
    return DFA(transitions, accepting, 0, trap, tuple(rules))


def hopcroft(dfa):
    groups = defaultdict(set)
    for state, rule in enumerate(dfa.accepting):
        groups[rule].add(state)
    partitions = {frozenset(group) for group in groups.values()}
    work = set(partitions)
    predecessors = [[set() for _ in range(dfa.state_count)] for _ in range(ASCII_SIZE)]

    for source, row in enumerate(dfa.transitions):
        for symbol, target in enumerate(row):
            predecessors[symbol][target].add(source)

    while work:
        splitter = work.pop()
        for symbol in range(ASCII_SIZE):
            before = set()
            for target in splitter:
                before.update(predecessors[symbol][target])
            for block in list(partitions):
                left = block & before
                right = block - before
                if not left or not right:
                    continue
                left, right = frozenset(left), frozenset(right)
                partitions.remove(block)
                partitions.update((left, right))
                if block in work:
                    work.remove(block)
                    work.update((left, right))
                else:
                    work.add(left if len(left) <= len(right) else right)

    blocks = list(partitions)
    old_to_block = {}
    for block_id, block in enumerate(blocks):
        for state in block:
            old_to_block[state] = block_id

    block_transitions = []
    block_accepting = []
    for block in blocks:
        state = next(iter(block))
        block_transitions.append([old_to_block[target] for target in dfa.transitions[state]])
        block_accepting.append(dfa.accepting[state])

    start_block = old_to_block[dfa.start]
    trap_block = old_to_block[dfa.trap]
    remap = {start_block: 0}
    queue = deque((start_block,))
    order = []

    while queue:
        block = queue.popleft()
        order.append(block)
        for target in block_transitions[block]:
            if target not in remap:
                remap[target] = len(remap)
                queue.append(target)

    transitions = [[remap[target] for target in block_transitions[block]] for block in order]
    accepting = [block_accepting[block] for block in order]
    return DFA(transitions, accepting, 0, remap[trap_block], dfa.rules)


def build_automata(rules):
    rules = tuple(rules)
    nfa = build_nfa(rules)
    dfa = subset_construction(nfa, rules)
    return nfa, dfa, hopcroft(dfa)
