# HW1

Запуск:

```
python main.py
```

Распознавание последовательности токенов:

```
python main.py "1+1x"
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
python -m unittest discover -s tests -v
```

Распознавание файла Funny:

```
python main.py ./input/input.funny
```
