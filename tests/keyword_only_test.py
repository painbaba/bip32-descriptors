# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests that a keyword-only parameter stays keyword-only.

`*` in a signature is a calling-convention promise -- `check_validity`,
`legacy`, `rng` and the others that recur -- and a mutant of `*` to `/`
drops the keyword-only rule and adds a positional-only one in its place
while a call already written with the keyword goes on answering the same
(issue btclib-org/btclib#980). The reason a whole suite can miss it is
the same reason a single test can catch all of it: the property is
mechanical, one `inspect.signature(...).parameters[name].kind` per site,
so walking `__all__` once covers every site a hand-written test would
have to repeat once per callable.

`KEYWORD_ONLY` is that walk, run once against the current tree and
frozen here rather than recomputed by the test: recomputing it from the
same code the test is meant to guard would make the assertion read
whatever a mutation had just done to it and call that the answer, which
is the blindness this file exists to remove. What is derived at test
time is the *live* signature of each recorded site, checked against the
kind frozen above -- a `*` a mutant turned to `/` is read here as
`POSITIONAL_ONLY` where the table says `KEYWORD_ONLY`, and the two no
longer agree.

A function under a package's `__all__` is named directly; a class is
named once per public method of its own -- `__init__`, and every other
name in its own `__dict__` that does not start with an underscore, so an
alternate constructor (`parse`, `b58decode`, `from_dict`) and an
instance method (`serialize`, `b58encode`) are sites of their own and
not only `__init__`. `BIP32KeyData.parse`'s `check_validity` is exactly
the shape `BIP32KeyData.__init__`'s does not cover: a classmethod a walk
stopping at the constructor would miss. Inherited methods are not walked
a second time under a subclass that does not override them, deduplication
being by the id of the underlying function once resolved, so a name
re-exported under a second `__all__` -- `bip32_descriptors.bip32`
publishing what `bip32_descriptors.bip32.bip32` defines -- is one entry
and not two either.

Only a function defined in `bip32_descriptors` is walked, as its
`__module__` says: a name taken from another distribution has the
signature of whichever release is installed, and its `*` is in that
package's source, so no mutant of this tree reaches it either.
"""

from __future__ import annotations

import inspect
from importlib import import_module
from typing import Any

import pytest

from tests.all_test import library_modules

# Walked from `bip32_descriptors`, on the commit this file is part of: every
# public callable it defines that takes at least one keyword-only
# parameter, and the names of those parameters in declaration order. A
# site dropping out of this table -- a parameter renamed, one no longer
# keyword-only, a callable removed from `__all__` -- and a site missing
# from it -- a new keyword-only parameter nothing here has asked about
# yet -- are both a deliberate edit to make, which is what
# test_the_recorded_surface_is_the_whole_of_it asks for
KEYWORD_ONLY: dict[str, list[str]] = {
    "bip32_descriptors.bip32:BIP32KeyData.__init__": ["check_validity"],
    "bip32_descriptors.bip32:BIP32KeyData.b58decode": ["check_validity"],
    "bip32_descriptors.bip32:BIP32KeyData.b58encode": ["check_validity"],
    "bip32_descriptors.bip32:BIP32KeyData.parse": ["check_validity"],
    "bip32_descriptors.bip32:BIP32KeyData.serialize": ["check_validity"],
    "bip32_descriptors.bip32:BIP32KeyOrigin.__init__": ["check_validity"],
    "bip32_descriptors.bip32:BIP32KeyOrigin.from_description": ["check_validity"],
    "bip32_descriptors.bip32:BIP32KeyOrigin.from_dict": ["check_validity"],
    "bip32_descriptors.bip32:BIP32KeyOrigin.parse": ["check_validity"],
    "bip32_descriptors.bip32:BIP32KeyOrigin.serialize": ["check_validity"],
    "bip32_descriptors.bip32:BIP32KeyOrigin.to_dict": ["check_validity"],
    "bip32_descriptors.bip32:decode_from_bip32_derivs": ["check_validity"],
    "bip32_descriptors.bip32:hardenings_from_der_path": ["bip380_enforced"],
    "bip32_descriptors.bip32:indexes_from_der_path": ["bip380_enforced"],
    "bip32_descriptors.bip32:int_from_index_str": ["bip380_enforced"],
    "bip32_descriptors.descriptors:AddrDescriptor.__init__": ["network"],
    "bip32_descriptors.descriptors:ComboDescriptor.__init__": ["network"],
    "bip32_descriptors.descriptors:Descriptor.__init__": ["network"],
    "bip32_descriptors.descriptors:MiniscriptDescriptor.__init__": ["network"],
    "bip32_descriptors.descriptors:MultiDescriptor.__init__": ["network"],
    "bip32_descriptors.descriptors:PkDescriptor.__init__": ["network"],
    "bip32_descriptors.descriptors:PkhDescriptor.__init__": ["network"],
    "bip32_descriptors.descriptors:RawDescriptor.__init__": ["network"],
    "bip32_descriptors.descriptors:RawLeaf.__init__": ["bare"],
    "bip32_descriptors.descriptors:RawPkhDescriptor.__init__": ["network"],
    "bip32_descriptors.descriptors:RawTrDescriptor.__init__": ["network"],
    "bip32_descriptors.descriptors:ShDescriptor.__init__": ["network"],
    "bip32_descriptors.descriptors:TrDescriptor.__init__": ["network"],
    "bip32_descriptors.descriptors:UnusedDescriptor.__init__": ["network"],
    "bip32_descriptors.descriptors:WpkhDescriptor.__init__": ["network"],
    "bip32_descriptors.descriptors:WshDescriptor.__init__": ["network"],
}


def _resolve(label: str) -> Any:
    """Import `module:Class.method` or `module:function` back to the object.

    The colon is the split point rather than the last dot: a module name
    is dotted too (`btclib.ecc.dsa`), so the pair is stored apart instead
    of concatenated and re-split.
    """
    module_name, _, attr_path = label.partition(":")
    obj: Any = import_module(module_name)
    for part in attr_path.split("."):
        obj = getattr(obj, part)
    return obj


def _kwonly_names(signature: inspect.Signature) -> list[str]:
    """Return the keyword-only parameter names of one signature, in order."""
    return [
        parameter.name
        for parameter in signature.parameters.values()
        if parameter.kind == inspect.Parameter.KEYWORD_ONLY
    ]


def _defined_here(function: Any) -> bool:
    """Whether `bip32_descriptors` defines the function, not a dependency."""
    module_name = getattr(function, "__module__", None) or ""
    return module_name.partition(".")[0] == "bip32_descriptors"


def _class_sites(
    module: Any, name: str, cls: type, seen_ids: set[int]
) -> dict[str, list[str]]:
    """Every public method of one exported class that is keyword-only somewhere.

    `__init__` plus every name in the class's own `__dict__` that does
    not start with an underscore, so an alternate constructor (`parse`,
    `b58decode`, `from_dict`) and an instance method (`serialize`,
    `b58encode`) are sites of their own rather than invisible because
    they are not the constructor. A method inherited and not overridden
    is in a base class's own `__dict__` instead, so it is walked once,
    there.
    """
    found: dict[str, list[str]] = {}
    attr_names = sorted(
        attr for attr in vars(cls) if attr == "__init__" or not attr.startswith("_")
    )
    for attr_name in attr_names:
        bound = getattr(cls, attr_name)
        if not (inspect.isfunction(bound) or inspect.ismethod(bound)):
            continue  # a property or a plain class attribute
        target = bound.__func__ if inspect.ismethod(bound) else bound
        if id(target) in seen_ids or not _defined_here(target):
            continue
        seen_ids.add(id(target))
        if kwonly := _kwonly_names(inspect.signature(bound)):
            found[f"{module.__name__}:{name}.{attr_name}"] = kwonly
    return found


def _live_keyword_only() -> dict[str, list[str]]:
    """Recompute `KEYWORD_ONLY` from the tree currently under test.

    The same walk that produced the table above, run again: every
    module's `__all__`, a function named directly and a class expanded
    by `_class_sites`. Deduplicated by the id of the resolved function --
    `__func__` for a bound classmethod, the function itself otherwise --
    so an object reachable under two names is one entry. A function a
    dependency defines is left out, as the module docstring says.
    """
    seen_ids: set[int] = set()
    found: dict[str, list[str]] = {}
    for module in library_modules():
        for name in getattr(module, "__all__", ()):
            obj = getattr(module, name)
            if inspect.isclass(obj):
                found |= _class_sites(module, name, obj, seen_ids)
            elif inspect.isfunction(obj) or inspect.isbuiltin(obj):
                if id(obj) in seen_ids or not _defined_here(obj):
                    continue
                seen_ids.add(id(obj))
                if kwonly := _kwonly_names(inspect.signature(obj)):
                    found[f"{module.__name__}:{name}"] = kwonly
    return found


def test_the_recorded_surface_is_the_whole_of_it() -> None:
    """Nothing keyword-only is missing from the table, nothing extra is in it.

    The half `test_a_keyword_only_parameter_stays_keyword_only` cannot
    ask: that test parametrizes over `KEYWORD_ONLY` itself, so a
    keyword-only parameter added to the public surface without a line
    here would run no test at all rather than fail one. This recomputes
    the walk and asks the two agree -- a new site, a removed one, and a
    renamed parameter all show up as one dictionary differing from
    another rather than as a `KeyError` or a silent gap.
    """
    assert _live_keyword_only() == KEYWORD_ONLY


@pytest.mark.parametrize(
    "label, param_name",
    [
        pytest.param(label, param_name, id=f"{label}:{param_name}")
        for label, params in sorted(KEYWORD_ONLY.items())
        for param_name in params
    ],
)
def test_a_keyword_only_parameter_stays_keyword_only(
    label: str, param_name: str
) -> None:
    """One assertion per recorded site, so a mutant of one `*` fails by name.

    `ReplaceBinaryOperator_Mul_Div` turns the `*` in front of a
    keyword-only parameter into `/`, which makes every parameter in
    front of it positional-only and every one after it -- this one
    included -- plain `POSITIONAL_OR_KEYWORD` rather than
    `KEYWORD_ONLY`. Nothing about a call already written with the
    keyword changes, and nothing about the value returned does either,
    which is why no other test in the suite notices (issue
    btclib-org/btclib#980).
    """
    kind = inspect.signature(_resolve(label)).parameters[param_name].kind
    assert kind == inspect.Parameter.KEYWORD_ONLY, (
        f"{label}'s {param_name} is {kind}, not keyword-only"
    )
