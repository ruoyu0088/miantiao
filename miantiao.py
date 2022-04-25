from pprint import pformat, pprint
import sys
from functools import partial
from collections import ChainMap
import ast
import inspect
import textwrap
from io import StringIO
import html
import linecache


_filename_id = 1

class Wrap:
    def __init__(self, pipe, data, func, name, pass_data):
        self._pipe = pipe
        self._data = data
        self._func = func
        self._name = name
        self._pass_data = pass_data

    def __call__(self, *args, **kwargs):
        if self._pass_data:
            res = self._func(self._data, *args, **kwargs)
        else:
            res = self._func(*args, **kwargs)
        return self._pipe._set_result(self._name, res)

    def __getitem__(self, item):
        res = self._func[item]
        return self._pipe._set_result(self._name, res)

    def __getattr__(self, name):
        return Wrap(self._pipe, self._data, getattr(self._func, name), f'{self._name}.{name}', self._pass_data)


class Steps:
    def __init__(self, steps, tb=None):
        if steps is None:
            raise ValueError("Compile the pipe with step=True")

        self.steps = steps
        self.tb = tb

    def __getitem__(self, key):
        if isinstance(key, str):
            r = [item for item in self.steps if item[0] == key]
            if len(r) == 0:
                raise KeyError(f'step {key} not exists')
            elif len(r) == 1:
                return r[0][1]
            else:
                return Steps(r)
        elif isinstance(key, int):
            return self.steps[key][1]
        elif isinstance(key, tuple):
            name, index = key
            r = [item for item in self.steps if item[0] == name]
            return r[index][1]

    def _str_output(self, val):
        from altair import Chart
        if isinstance(val, Chart):
            return pformat(val.__dict__)
        else:
            return str(val)

    def __str__(self):
        buf = StringIO()
        for i, (name, step) in enumerate(self.steps):
            buf.write(f'{i:02d}: {name}\n')
            buf.write(len(name) * '-' + '\n')
            buf.write(self._str_output(step))
            buf.write('\n\n')
        return buf.getvalue()

    def __repr__(self):
        return self.__str__()

    def _repr_html_(self):
        from IPython import display
        from IPython.utils.capture import capture_output
        from pandas import DataFrame

        fmt_order = {
            'text/html':lambda x:x,
            'text/plain':lambda x:f"<pre>{html.escape(x)}</pre>"
        }

        with capture_output() as o:
            for i, (name, step) in enumerate(self.steps):
                display.display_html(f'<div style="margin-top:10px;"><b>{i:02d}: {name}</b></div>', raw=True)
                if isinstance(step, DataFrame):
                    display.display(step.head(10))
                else:
                    display.display(step)

        html_data = []

        for out in o.outputs:
            data = out.data
            for fmt, func in fmt_order.items():
                if fmt in data:
                    html_data.append(func(data[fmt]))
                    break

        return "".join(html_data)

class Pipe:
    def __init__(self, data, steps=False):
        self._steps = [] if steps else None
        self._last = data
        caller_frame = sys._getframe().f_back
        self._namespace = ChainMap(
            caller_frame.f_locals, 
            caller_frame.f_globals,
            caller_frame.f_builtins)

    def __getattr__(self, name):
        if name in self._namespace:
            return Wrap(self, self._last, self._namespace[name], name, pass_data=True)    

        func = getattr(self._last, name, None)
        if func is None:
            raise AttributeError(f"No global function or method:{name}")
        return Wrap(self, self._last, func, name, pass_data=False)

    def _set_result(self, name, res):
        if res is not None:
            self._last = res
            if self._steps is not None:
                self._steps.append((name, self._last))
        return self._last

            
def as_ast(code):
    return ast.parse(code).body[0]

def is_name(arg, name):
    return isinstance(arg, ast.Name) and arg.id == name

def get_name(func):
    if isinstance(func, ast.Name):
        return func.id
    elif isinstance(func, ast.Attribute):
        return f'{get_name(func.value)}.{func.attr}'

class SearchPlaceholder(ast.NodeVisitor):
    def __init__(self, placeholder):
        self.found = False
        self.placeholder = placeholder

    def is_placeholder(self, arg):
        return is_name(arg, self.placeholder)

    def has_placeholder(self, call):
        if any(self.is_placeholder(arg) for arg in call.args):
            return True
        if any(self.is_placeholder(arg.value) for arg in call.keywords):
            return True
        return False

    def visit_Call(self, node):
        if self.has_placeholder(node):
            self.found = True
        else:
            self.generic_visit(node)


class PipeTransform(ast.NodeTransformer):
    def __init__(self, placeholder='P'):
        self._placeholder = placeholder
        self.pipe = "_pipe"
        self.nested_func_level = 0

    @property
    def P(self):
        return self._placeholder

    def is_placeholder(self, arg):
        return is_name(arg, self._placeholder)

    def has_placeholder(self, call):
        search = SearchPlaceholder(self.P)
        search.visit(call)
        return search.found

    def visit_FunctionDef(self, node):
        #print('FunctionDef', node.name, self.nested_func_level)
        if self.nested_func_level > 0:
            from_name = node.name
            to_name = node.returns.id
            node = self.generic_visit(node)
            body = node.body
            if from_name != '_':
                body.insert(0, as_ast(f'_pipe._last = P = {from_name}'))
            body.append(as_ast(f'{to_name} = P'))
            return body
        else:
            self.nested_func_level += 1
            self.generic_visit(node)
            self.nested_func_level -= 1
        return node

    def visit_Assign(self, node):
        if self.is_placeholder(node.targets[0]):
            return as_ast(f'_pipe._last = {ast.unparse(node)}')
        return node

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call):
            if self.has_placeholder(node.value):
                return as_ast(f'{self.P} = {self.pipe}._set_result("{get_name(node.value.func)}", {ast.unparse(node)})')
            if isinstance(node.value.func, ast.Name):
                return as_ast(f'{self.P} = {self.pipe}.{ast.unparse(node)}')
            elif isinstance(node.value.func, ast.Attribute):
                if self.is_placeholder(node.value.func.value):
                    return as_ast(f'{self.P} = {self.pipe}._set_result("{node.value.func.attr}", {ast.unparse(node)})')
                else:
                    return as_ast(f'{self.P} = {self.pipe}.{ast.unparse(node)}')
                    
        elif isinstance(node.value, ast.Subscript):
            if self.is_placeholder(node.value.value):
                return as_ast(f'{self.P} = {self.pipe}._set_result("[]", {ast.unparse(node)})')
            else:
                return as_ast(f'{self.P} = {self.pipe}.{ast.unparse(node)}')
        else:
            return node

def _make_pipe(func, steps=False, show_code=False):
    global _filename_id
    code = textwrap.dedent(inspect.getsource(func))
    arg0 = inspect.getargs(func.__code__).args[0]
    pt = PipeTransform()
    ast_tree = ast.parse(code)
    ast_tree = pt.visit(ast_tree)
    func_def = ast_tree.body[0]
    func_def.decorator_list = []
    func_body = func_def.body
    func_body.insert(0, 
        as_ast(f"{pt.P}, {pt.pipe} = {arg0}, Pipe({arg0}, steps={steps})")
    )
    if not steps:
        func_body.append(as_ast(f'return {pt.P}'))
    else:
        func_body.append(as_ast(f'return Steps({pt.pipe}._steps)'))

    try_expr = ast.Try(
        body=func_body, 
        handlers=[ast.ExceptHandler(body=[
            as_ast('import traceback'),
            as_ast('traceback.print_exc()'),
            as_ast(f'return Steps({pt.pipe}._steps)')
            ])],
        orelse=[],
        finalbody=[])

    ast_tree.body[0].body = [try_expr]

    funcname = ast_tree.body[0].name = f'_pipe_{func.__name__}'
    src_code = ast.unparse(ast_tree).strip()
    run_code = f'''
def __create_func(Pipe, Steps):
{textwrap.indent(src_code, '    ')}
    return {funcname}
    '''
    if show_code:
        print(src_code)
    filename = f'<dynamic_{_filename_id}>'
    code = compile(run_code, filename=filename, mode='exec')
    
    lines = [line + '\n' for line in run_code.splitlines()]
    linecache.cache[filename] = (len(run_code), None, lines, filename)

    _filename_id += 1
    namespace = func.__globals__
    args = [Pipe, Steps]
    exec(code, namespace)
    func = namespace['__create_func'](*args)
    del namespace['__create_func']
    return func


def pipe(func=None, steps=False, show_code=False):
    if func is not None:
        return _make_pipe(func, steps=False, show_code=False)
    else:
        def decorator(func):
            return _make_pipe(func, steps=steps, show_code=show_code)
        return decorator

def call_pipe(func=None, steps=False, show_code=False):
    def get_args(func):
        frame = sys._getframe().f_back.f_back
        namespace = ChainMap(frame.f_locals, frame.f_globals)
        arg_names = inspect.getargs(func.__code__).args
        args = []
        for arg in arg_names:
            if arg not in namespace:
                raise NameError(f'Cannot find {arg}')
            else:
                args.append(namespace[arg])
        return args

    if func is not None:
        args = get_args(func)
        pipe_func = _make_pipe(func, steps=False, show_code=False)
        return pipe_func(*args)
    else:
        def decorator(func):
            args = get_args(func)
            pipe_func = _make_pipe(func, steps=steps, show_code=show_code)
            return pipe_func(*args)
        return decorator
