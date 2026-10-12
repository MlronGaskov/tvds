# HW1

```
python -m hw01_regex_dfa.main
```

Распознавание последовательности токенов:

```
python -m hw01_regex_dfa.main "1+1x"
```

Результат:

```
INT: '1'
PLUS: '+'
INT: '1'
IDENT: 'x'
```

Тесты:

```
python -m unittest discover -s hw01_regex_dfa/tests -v
```

Распознавание файла Funny:

```
python -m hw01_regex_dfa.main hw01_regex_dfa/input/input.funny
```
