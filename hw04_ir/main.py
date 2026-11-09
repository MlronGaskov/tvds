import argparse
import json
from pathlib import Path

from hw02_parsing.lexer import LexicalError
from hw02_parsing.parser import parse_source
from hw03_types.semantic import analyze
from hw04_ir.flow import cfg, color, interference, metrics
from hw04_ir.ir import generate
from hw04_ir.optimize import optimize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)
    parser.add_argument("--no-opt", action="store_true")
    parser.add_argument("--no-const", action="store_true")
    parser.add_argument("--no-algebra", action="store_true")
    parser.add_argument("--no-dce", action="store_true")
    args = parser.parse_args()
    if args.file.suffix.lower() != ".funny" or not args.file.is_file():
        parser.error("expected an existing .funny file")
    try:
        ast, errors = parse_source(args.file.read_text(encoding="utf-8"), with_positions=True)
        if not errors:
            ast, errors = analyze(ast)
        if errors:
            print("\n".join(errors))
            raise SystemExit(1)
        functions = generate(ast)
        result = {}
        for name, function in functions.items():
            before = function["instructions"]
            after = optimize(before,
                             propagate=not (args.no_opt or args.no_const),
                             algebra=not (args.no_opt or args.no_algebra),
                             dce=not (args.no_opt or args.no_dce))
            blocks = cfg(after)
            graph = interference(blocks)
            colors = color(graph)
            result[name] = {
                "params": function["params"], "returns": function["returns"],
                "before": before, "after": after, "cfg": blocks,
                "interference": graph, "colors": colors,
                "metrics": {"before": metrics(before), "after": metrics(after),
                            "colors": len(set(colors.values()))}
            }
        print(json.dumps({"functions": result, "errors": []}, ensure_ascii=False, indent=2))
    except (LexicalError, ValueError) as error:
        print(json.dumps({"errors": [str(error)]}, ensure_ascii=False, indent=2))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
