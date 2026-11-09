# HW4

```
python -m hw04_ir.main hw04_ir/input/valid.funny
```

Результат: JSON с IR до/после оптимизаций, CFG, графом конфликтов, раскраской и метриками.

Отключение оптимизаций: `--no-opt` (все), `--no-const`, `--no-algebra`, `--no-dce` (по отдельности).

```
python -m hw04_ir.main hw04_ir/input/loop.funny
python -m hw04_ir.main hw04_ir/input/graph.funny
python -m hw04_ir.main hw04_ir/input/invalid.funny
python -m unittest discover -s hw04_ir/tests -v
```

IR: `const(dst,value)`, `copy(dst,src)`, `un(dst,operator,arg)`, `bin(dst,operator,left,right)`, `get(dst,array,index)`, `set(dst,array,index,value)`, `call(dsts,name,args)`, `branch(cond,true,false)`, `jump(target)`, `label(name)`, `assert(cond)`, `assume(cond)`, `ret(values)`. Временные - `%tN`, метки - `LN`. `set` возвращает новый массив. Именованные `returns` передаются через `ret` в конце функции.

Оптимизации: локальное распространение/свёртка констант, `x+0`, `x-0`, `x*0`, `x*1`, `x/1`, удаление мёртвых вычислений с учётом живости на CFG. Деление и операции с потенциальными эффектами не удаляются. Граф конфликтов строится по живости временных `%tN`, жадная раскраска нумерует цвета с нуля.
