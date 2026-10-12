import json
import sys
from pathlib import Path

from hw02_parsing.lexer import LexicalError
from hw02_parsing.parser import parse_source


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m hw02_parsing.main file.funny")
    path = Path(sys.argv[1])
    if path.suffix.lower() != ".funny" or not path.is_file():
        raise SystemExit("Expected an existing .funny file")
    try:
        ast, errors = parse_source(path.read_text(encoding="utf-8"))
    except LexicalError as error:
        ast, errors = None, [str(error)]
    print(json.dumps({"ast": ast, "errors": errors}, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
