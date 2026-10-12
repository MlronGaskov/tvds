# HW2

```
python -m hw02_parsing.main hw02_parsing/input/valid.funny
```

Результат: AST в формате JSON.

Проверка синтаксических ошибок:

```
python -m hw02_parsing.main hw02_parsing/input/invalid.funny
```

Тесты:

```
python -m unittest discover -s hw02_parsing/tests -v
```
