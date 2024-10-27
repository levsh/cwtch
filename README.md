## cwtch [wip] - Python `dataclasses` with validation and views.

[Documentation](https://levsh.github.io/cwtch)

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

File <string>:12, in __init__(__cwtch_self__, i, s, **__extra_kwds)

ValidationError: type[ <class '__main__.D'> ] path[ 'i' ]
  type[ <class 'int'> ] input_type[ <class 'str'> ] input_value[ 'i' ]
    Error: invalid literal for int() with base 10: 'i'
