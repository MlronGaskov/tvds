import csv
import json
import sys
from pathlib import Path

from src.automata import build_automata
from src.spec import REQUIRED_CASES, TOKEN_RULES

OUTPUT = Path("./output")


def export_json(dfa):
    accepting = {}
    for state, rule_index in enumerate(dfa.accepting):
        if rule_index is not None:
            accepting[str(state)] = dfa.rules[rule_index].name
    data = {
        "start_state": dfa.start,
        "trap_state": dfa.trap,
        "accepting": accepting,
        "transitions": dfa.transitions,
    }
    (OUTPUT / "dfa.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def export_csv(dfa):
    with (OUTPUT / "transitions.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["state", "token", *range(128)])
        for state, row in enumerate(dfa.transitions):
            rule_index = dfa.accepting[state]
            token = "" if rule_index is None else dfa.rules[rule_index].name
            writer.writerow([state, token, *row])


def run_cases(dfa):
    results = []
    for name, text, expected in REQUIRED_CASES:
        rule = dfa.recognize(text)
        actual = None if rule is None else rule.name
        results.append({"name": name, "input": text, "expected": expected, "actual": actual, "passed": actual == expected})
    (OUTPUT / "test_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def build():
    OUTPUT.mkdir(exist_ok=True)
    nfa, dfa, minimized = build_automata(TOKEN_RULES)
    export_json(minimized)
    export_csv(minimized)
    results = run_cases(minimized)
    passed = sum(result["passed"] for result in results)
    print(f"NFA: {nfa.state_count}")
    print(f"DFA: {dfa.state_count}")
    print(f"Min DFA: {minimized.state_count}")
    print(f"Trap: {minimized.trap}")
    print(f"Tests: {passed}/{len(results)}")


def tokenize(text):
    _, _, dfa = build_automata(TOKEN_RULES)
    try:
        tokens = dfa.tokenize(text)
    except ValueError:
        print("REJECT")
        return
    for rule, value in tokens:
        print(f"{rule.name}: {value!r}")


def tokenize_file(path):
    file = Path(path)
    if file.suffix.lower() != ".funny":
        raise SystemExit("Expected a .funny file")
    if not file.is_file():
        raise SystemExit(f"File not found: {file}")
    tokenize(file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    if len(sys.argv) == 1:
        build()
    elif len(sys.argv) == 2:
        argument = sys.argv[1]
        if Path(argument).suffix.lower() == ".funny":
            tokenize_file(argument)
        else:
            tokenize(argument)
    else:
        raise SystemExit(f"Usage: python {sys.argv[0]} [text|file.funny]")
