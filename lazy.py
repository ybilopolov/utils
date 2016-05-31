import collections
import operator
from functools import partial
from itertools import chain


# -- core: ---------------------------------------------------------------------

def eval(item):
    reeval = lambda x: partial(eval, x)
    if isinstance(item, Lazy):
        for result in item:
            yield result
    elif isinstance(item, (list, tuple)):
        for elements in iproduct(*map(reeval, item)):
            yield type(item)(elements)
    elif isinstance(item, dict):
        for values in iproduct(*map(reeval, item.values())):
            yield type(item)(zip(item, values))
    elif isinstance(item, Shadow):
        yield item.real
    else:
        yield item


class Lazy(object):

    __slots__ = ['f', 'args', 'kwargs', 'cache']

    def __init__(self, f, *args, **kw):
        self.f = f
        self.args = args
        self.kwargs = kw
        self.cache = Empty

    def __iter__(self):
        if self.cache is not Empty:
            if isinstance(self.cache, CircularReference):
                raise self.cache
            yield self.cache
        else:
            self.cache = CircularReference('at: {}'.format(self))
            for f, args, kwargs in eval((self.f, self.args, self.kwargs)):
                for maybe_lazy in f(*args, **kwargs):
                    for x in eval(maybe_lazy):
                        self.cache = x
                        yield x
            self.cache = Empty

    def __call__(self, *args, **kwargs):
        return Lazy(yield_apply, self, *args, **kwargs)

    def __getattr__(self, item):
        return lazy(getattr)(self, item)

    # todo: add full comparison methods support for py3 compatibility
    # def __cmp__(self, other):
    #     return lazy(cmp)(self, other)

    def __not__(self):
        return lazy(operator.not_)(self)

    def __add__(self, item):
        return lazy(operator.add)(self, item)

    def __and__(self, other):
        return lazy(operator.and_)(self, other)

    def __div__(self, other):
        return lazy(operator.truediv)(self, other)

    def __mul__(self, other):
        return lazy(operator.mul)(self, other)

    def __len__(self):
        return lazy(len)(self)

    def __neg__(self):
        return lazy(operator.neg)(self)

    def __or__(self, other):
        return lazy(operator.or_)(self, other)

    def __pos__(self):
        return lazy(operator.pos)(self)

    def __pow__(self, other):
        return lazy(operator.pow)(self, other)

    def __sub__(self, other):
        return lazy(operator.sub)(self, other)

    def __xor__(self, other):
        return lazy(operator.xor)(self, other)

    def __contains__(self, other):
        return lazy(operator.contains)(other, self)

    def __getitem__(self, other):
        return lazy(operator.getitem)(self, other)

    def __repr__(self):
        return 'lazy: {}({})'.format(
            self.f, repr_args(*self.args, **self.kwargs))


class Shadow(object):
    __slots__ = ['real']

    def __init__(self, real):
        self.real = real


class CircularReference(ReferenceError): pass


Empty = object()


def singleton(x):
    yield x


def iproduct(*iter_getters):
    def _iproduct(iter_getters, stack=()):
        if not iter_getters:
            yield stack
        else:
            for item in iter_getters[0]():
                for x in _iproduct(iter_getters[1:], stack + (item,)):
                    yield x
    return _iproduct(iter_getters)


def yield_apply(f, *args, **kwargs):
    yield f(*args, **kwargs)


def repr_args(*args, **kwargs):
    return ', '.join(list(map(repr, args)) +
                     ['='.join((str(k), repr(v))) for k, v in kwargs.items()])


# -- aliases: ------------------------------------------------------------------

lazy_provider = lambda f: partial(Lazy, f)
lazy = lazy_provider(singleton)
foreach = lazy_provider(chain)


# -- nice dict references: -----------------------------------------------------

def is_namedtuple(obj):
    return isinstance(obj, tuple) and hasattr(obj, '_fields')


def get_child(d, k):
    if isinstance(d, collections.Mapping):
        return d[k]
    elif isinstance(d, collections.Sequence) and not is_namedtuple(d):
        return d[int(k)]
    else:
        return getattr(d, k)


@lazy_provider
def get_path(coll, path):
    if not path:
        yield coll
    else:
        try:
            child = get_child(coll, path[0])
            if isinstance(child, Lazy):
                for ch in child:
                    yield get_path(Shadow(ch), path[1:])
            else:
                yield get_path(Shadow(child), path[1:])
        except (IndexError, KeyError, AttributeError) as e:
            raise e.__class__('path not fund: {}'.format(path))


class argcol(object):

    def __init__(self, f, *args):
        self.f = f
        self.__args = args

    def __call__(self, *args):
        return argcol(self.f, *self.__args + args)

    def __getattr__(self, name):
        return self(name)

    def __getitem__(self, item):
        return self(item)

    def __invert__(self):
        return self.f(self.__args)

    def __repr__(self):
        return '{}:{}({})'.format(self.__class__.__name__, self.f, self.__args)


def lazy_dict(*keys):
        d = dict.fromkeys(keys)
        return [d] + list(map(argcol(partial(get_path, Shadow(d))), keys))


# -- tests: --------------------------------------------------------------------

if __name__ == '__main__':
    import random
    from pprint import pprint

    print( foreach([1]) )
    print( list(foreach([1, 2, 3])) )

    print( lazy(lambda x: lambda y: x + y)(1)(foreach([1, 2, 3])) )
    print( list(lazy(lambda x: lambda y: x + y)(1)(foreach([1, 2, 3]))) )


    @lazy
    def add_letters(side, middle):
        return middle.join([side] * 2)


    @lazy
    class Word(object):

        def __init__(self, w):
            print('me da', w)
            self.w = w

        def x2(self, m):
            return self.w + '-' + self.w + m

    lstr = lazy(str)
    lrandom = lazy(random)

    root, params, staff = lazy_dict('params', 'staff')

    root.update(
        params=dict(
            list=lazy(lambda x: x)([1, 2, 3]),
            side=foreach(['w', 'l']),
            middle=foreach(['a', 'o']),
            word=add_letters(~params.side, ~params.middle),
            true_word=lstr(~params.side + ~params.middle + ~params.side),
            wordobj=Word(~params.true_word),
            some_math=~params.list[0] + (~params.list)[lrandom.randrange(3)]),
        staff=dict(
            result=lazy('Hello, {}').format((~params.wordobj).x2('!'))))

    pprint(root)

    for each in ~staff.result:
        print(each)

    for each in ~params:
        print(each)

    print(list(eval(~params.true_word)))

    print(list(lstr(foreach([' a ', ' b ', ' c '])).strip().upper()))

    print(list(foreach(lazy(random.sample)(range(10), 5))))
