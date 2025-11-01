## cwtch [wip] - Python `dataclasses` with validation and views.

[Documentation](https://levsh.github.io/cwtch)

![tests](https://github.com/levsh/cwtch/workflows/tests/badge.svg)
![coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/levsh/f079c374abda6c5bd393c3ac723f1182/raw/coverage.json)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

```python
In [1]: from cwtch import dataclass, field

In [2]: @dataclass
   ...: class M:
   ...:     i: int
   ...:     s: str = field(validate=False)
   ...: 

In [3]: M(i=1, s='s')
Out[3]: M(i=1, s='s')

In [4]: M(i='i', s='s')
---------------------------------------------------------------------------
ValidationError                           Traceback (most recent call last)
Cell In[4], line 1
----> 1 M(i='i', s='s')

File <string>:32, in __init__(__cwtch_self__, i, s, **__extra_kwds)

ValidationError: 
  Type: --> <class '__main__.M'>
  Path: ['i']
  ValidationError:
    Type: <class 'str'> --> <class 'int'>
    Input: 'i'
    ValueError: invalid literal for int() with base 10: 'i'
```
