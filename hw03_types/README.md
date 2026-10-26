# HW3

```
python -m hw03_types.main hw03_types/input/valid.funny
```

Результат: аннотированный AST в формате JSON (`inferred_type` у выражений).

Проверка семантических ошибок:

```
python -m hw03_types.main hw03_types/input/invalid.funny
```

Тесты:

```
python -m unittest discover -s hw03_types/tests -v
```

Типы: `int`, `int[]`, `bool` (логические выражения), сигнатуры функций. 
Тип локальной переменной без аннотации выводится из первого корректного присваивания.
