# cwtch [wip] - Python Data Classes with validation.

![tests](https://github.com/levsh/cwtch/workflows/tests/badge.svg)
![coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/levsh/f079c374abda6c5bd393c3ac723f1182/raw/coverage.json)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

```python
In [1]: from cwtch import dataclass, field

In [2]: @dataclass
   ...: class D:
   ...:     i: int
   ...:     s: str = field(validate=False)
   ...:

In [3]: D(i=1, s='s')
Out[3]: D(i=1, s='s')

In [4]: D(i='i', s='s')
---------------------------------------------------------------------------
ValueError                                Traceback (most recent call last)
...
ValidationError                           Traceback (most recent call last)
Cell In[4], line 1
----> 1 D(i='i', s='s')

File <string>:9, in __init__(__cwtch_self__, i, s, **__cwtch_kwds__)

ValidationError: validation error for <class '__main__.D'> path=['i']
  validation error for <class 'int'>
    - invalid literal for int() with base 10: 'i'

In [5]: D(i=1, s=0)
Out[5]: D(i=1, s=0)
```
