## Miantiao

`miantiao`帮助你编写很长的面条(意面)程序。该模块提供了两个装饰器：`pipe`和`call_pipe`。详细用法请查看
`test_miantiao.ipynb`。

`miantiao` helps you write very long noodle (spaghetti) programs. This module provides two decorators: `pipe` and `call_pipe`. For detailed usage, please see
`test_miantiao.ipynb`.

```python
import requests
from bs4 import BeautifulSoup
import re
from collections import Counter
import pandas as pd

@pipe
def word_count(url):
    requests.get()
    P = P.text
    BeautifulSoup('html.parser')
    P = P.html.text
    re.findall(r'[A-Za-z]+', P)
    map(str.lower, P)
    Counter()
    most_common(50)
    pd.DataFrame(columns=['word', 'count'])
    plot.bar(x='word', y='count', figsize=(16, 5), grid=True)

r = word_count('https://en.wikipedia.org/wiki/Python_(programming_language)');
```

![](example_output.png)