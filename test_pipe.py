from miantiao import pipe, call_pipe, Steps
import unittest
import io
import contextlib
import itertools as it

def concat(a, b):
    return a + b

def func_call_global(d):
    concat([1, 2, 3])
    concat([-1, -2, -3], P)
    concat(P[:2])

def func_local_import(n):
    # local import must be before all calls
    from operator import add, sub, mul 
    add(5)
    mul(3)
    sub(10)

def func_string_method(s):
    strip()
    capitalize()
    filter(lambda c:c not in "aeiou")
    str.join('')

def func_map_filter(s):
    split()
    filter(lambda x:x.startswith('p'))
    map(str.capitalize)
    list()

def func_acc(n):
    range()
    it.accumulate()
    enumerate()
    zip(*P)
    list()

def func_forking(s):
    def _() -> base:
        strip()
        capitalize()

    def base() -> no_a:
        filter(lambda c:c != 'a')
        str.join('')

    def base() -> no_o:
        filter(lambda c:c != 'o')
        str.join('')

    def base() -> no_i:
        filter(lambda c:c != 'i')
        str.join('')

    P = (no_a, no_o, no_i)
    str.join(',')


class TestPipe(unittest.TestCase):
    def test_func_call_global(self):
        self.assertEqual(pipe(func_call_global)(['a', 'b']), [-1, -2, -3, 'a', 'b', 1, 2, 3, -1, -2])
        
    def test_func_local_import(self):
        self.assertEqual(pipe(func_local_import)(6), 23)
    def test_func_string_method(self):
        self.assertEqual(pipe(func_string_method)(' location  '), "Lctn")

    def test_func_acc(self):
        self.assertEqual(pipe(func_acc)(5), [(0, 1, 2, 3, 4), (0, 1, 3, 6, 10)])

    def test_func_map_filter(self):
        self.assertEqual(pipe(func_map_filter)('python ruby javascript php'), ["Python", "Php"])

    def test_func_forking(self):
        self.assertEqual(pipe(func_forking)(' location  '), "Loction,Lcatin,Locaton")

    def test_steps(self):
        func = pipe(steps=True)(func_string_method)
        res = func(' location  ')
        self.assertIsInstance(res, Steps)
        self.assertEqual(res[0], 'location')
        self.assertEqual(res[1], 'Location')
        self.assertEqual(res[-1], 'Lctn')

    def test_call_pipe1(self):
        n = 5
        res = call_pipe(func_acc)
        self.assertEqual(res, [(0, 1, 2, 3, 4), (0, 1, 3, 6, 10)])

    def test_call_pipe2(self):
        n = 5
        @call_pipe
        def res(n):
            range()
            it.accumulate()
            enumerate()
            zip(*P)
            list()
        self.assertEqual(res, [(0, 1, 2, 3, 4), (0, 1, 3, 6, 10)])

    def test_show_code(self):
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            pipe(show_code=True)(func_call_global)
        self.assertEqual(f.getvalue().strip(), '''def _pipe_func_call_global(d):
    try:
        (P, _pipe) = (d, Pipe(d, steps=False))
        P = _pipe.concat([1, 2, 3])
        P = _pipe._set_result('concat', concat([-1, -2, -3], P))
        P = _pipe.concat(P[:2])
        return P
    except:
        import traceback
        traceback.print_exc()
        return Steps(_pipe._steps)''')
        

if __name__ == '__main__':
    unittest.main()