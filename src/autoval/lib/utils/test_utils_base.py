#!/usr/bin/env python3
from abc import ABCMeta, abstractmethod
from inspect import getmembers, signature
from typing import Any

import six


@six.add_metaclass(ABCMeta)
class TestUtilsBase:
    @classmethod
    def __init_subclass__(cls, **kwargs) -> None:
        super(TestUtilsBase, cls).__init_subclass__(**kwargs)
        verify_abs_method_signature(cls)

    @abstractmethod
    def test_setup(self) -> None:
        pass

    def test_cleanup(self) -> None:
        pass

    @abstractmethod
    def start_test(self) -> None:
        pass

    @abstractmethod
    def parse_results(self) -> Any:
        pass


def verify_abs_method_signature(cls) -> None:
    # Check the subclass of TestBase doesnt change signature of abstract methods
    sub_class_members = getmembers(cls)
    base_members = getmembers(TestUtilsBase)
    err = ""
    # remove all default methods
    base_abstract_methods = [mem for mem in base_members if not mem[0].startswith("_")]
    for b_mem in base_abstract_methods:
        for s_mem in sub_class_members:
            if b_mem[0] == s_mem[0]:
                if signature(b_mem[1]) == signature(s_mem[1]):
                    break
                else:
                    err += f"'{b_mem[0]}' "
    if err:
        raise Exception(
            f"{cls} methods - {err}have different signature then base class"
        )
