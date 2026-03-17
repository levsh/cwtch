import typing

from collections import abc


def make_type_with_args(T, args):
    if T == typing.Callable or T == abc.Callable:
        return T[args[:-1], args[-1]]
    return T[*args]
