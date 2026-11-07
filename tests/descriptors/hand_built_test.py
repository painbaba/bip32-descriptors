# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""What `parse` never builds is refused when a descriptor is built by hand.

A field of the wrong type, in every `Descriptor` fragment and in a
`MultiA`, leaves as a `BTClibTypeError`. `TrDescriptor` and `MultiA` also
refuse a value `parse` refuses, as a `BTClibValueError`. Issues
btclib-org/bip32-descriptors#46 and btclib-org/bip32-descriptors#103.
"""

from __future__ import annotations

import pickle
from dataclasses import fields, replace
from typing import Any

import pytest
from btclib.exceptions import BTClibTypeError, BTClibValueError
from btclib.key import PrvKeyData

from bip32_descriptors.descriptors import miniscript, parse
from bip32_descriptors.descriptors.descriptors import (
    AddrDescriptor,
    ComboDescriptor,
    Descriptor,
    MiniscriptDescriptor,
    MultiA,
    MultiDescriptor,
    PkDescriptor,
    PkhDescriptor,
    RawDescriptor,
    RawLeaf,
    RawPkhDescriptor,
    RawTrDescriptor,
    ShDescriptor,
    TrDescriptor,
    WpkhDescriptor,
    WshDescriptor,
)
from tests.secret_free import assert_secret_free

_X = PrvKeyData(1).pub.sec.hex()[2:]
_X2 = PrvKeyData(2).pub.sec.hex()[2:]
(_KEY,) = parse(f"tr({_X})").key_expressions
(_KEY2,) = parse(f"tr({_X2})").key_expressions
_C = PrvKeyData(3).pub.sec.hex()
_RANDOM_HEX = "7e3d796f1b20eb42c57e4f6a0c6ecaf1879529ae1ad154cebf0ed79035de2901"


def _nested(levels: int, *, right: bool) -> object:
    """Return a tree of `levels` branches, nested on one side."""
    tree: object = RawLeaf(b"\x51")
    for _ in range(levels):
        tree = (RawLeaf(b"\x51"), tree) if right else (tree, RawLeaf(b"\x51"))
    return tree


def test_a_raw_descriptor_is_built_from_bytes() -> None:
    """The control: the bytes `parse` gives, written back as hex."""
    assert str(RawDescriptor(b"\x51")) == "raw(51)"


@pytest.mark.parametrize("script", ["51", 0x51, bytearray(b"\x51")])
def test_a_raw_descriptor_script_of_another_type_is_refused(script: Any) -> None:
    """Hex text is not the script: `parse` is what reads hex."""
    err_msg = f"^invalid script type: {type(script).__name__}$"
    with pytest.raises(BTClibTypeError, match=err_msg):
        RawDescriptor(script)


@pytest.mark.parametrize("internal_key", [_X, 5, None, MultiA(1, (_KEY,))])
def test_a_tr_internal_key_of_another_type_is_refused(internal_key: Any) -> None:
    """The internal key is a KEY expression, never its text."""
    err_msg = f"^invalid internal key type: {type(internal_key).__name__}$"
    with pytest.raises(BTClibTypeError, match=err_msg):
        TrDescriptor(internal_key)


@pytest.mark.parametrize(
    "tree",
    [5, f"pk({_X})", [_KEY, _KEY2], (_KEY, (_KEY2, "pk")), ((5, _KEY), _KEY2)],
    ids=["int", "text", "list", "right-leaf", "left-leaf"],
)
def test_a_tr_tree_node_of_another_type_is_refused(tree: Any) -> None:
    """Every node of the tree, at any depth, a branch being a tuple."""
    with pytest.raises(BTClibTypeError, match="^invalid script tree node type: "):
        TrDescriptor(_KEY, tree)


@pytest.mark.parametrize("branch", [(), (_KEY,), (_KEY, _KEY2, _KEY)])
def test_a_tr_branch_of_other_than_two_subtrees_is_refused(branch: Any) -> None:
    """A third subtree is not dropped, and a lone one is not a branch."""
    err_msg = f"^a script tree branch takes two subtrees, {len(branch)} given$"
    with pytest.raises(BTClibTypeError, match=err_msg):
        TrDescriptor(_KEY, (_KEY2, branch))


@pytest.mark.parametrize("right", [False, True])
def test_a_tr_tree_too_deep_is_refused_when_built(right: bool) -> None:
    """At 129 levels, and far past Python's recursion limit too.

    The deepest tree `parse` reads is built, and its text parses back.
    """
    deepest = TrDescriptor(_KEY, _nested(128, right=right))  # type: ignore[arg-type]
    assert parse(str(deepest)) == deepest
    for levels in (129, 5000):
        tree = _nested(levels, right=right)
        with pytest.raises(BTClibValueError, match="^script tree deeper than 128$"):
            TrDescriptor(_KEY, tree)  # type: ignore[arg-type]


def test_a_tr_miniscript_leaf_of_another_context_is_refused() -> None:
    """A leaf of the p2wsh context would commit to a 33-byte key.

    BIP342 reads that key as an unknown public key type, which any
    non-empty signature satisfies. Issue btclib-org/bip32-descriptors#111.
    """
    expression = f"and_v(v:pk({_C}),older(1))"
    leaf = miniscript.parse(expression, miniscript.TAPSCRIPT)
    assert parse(str(TrDescriptor(_KEY, leaf))) == TrDescriptor(_KEY, leaf)
    p2wsh = miniscript.parse(expression, miniscript.P2WSH)
    for tree in (p2wsh, (leaf, p2wsh), (p2wsh, _KEY2)):
        with pytest.raises(BTClibValueError, match="^not a tapscript node: and_v in "):
            TrDescriptor(_KEY, tree)


def _with_context(node: miniscript.Miniscript, context: object) -> None:
    """Give the node a context, as unpickling a stream holding it would.

    Unpickling skips `Miniscript`'s own checks, which refuse a node of an
    unknown context, or of a subexpression of another, when it is built.
    """
    object.__setattr__(node, "context", context)


def _unpickled(node: miniscript.Miniscript) -> miniscript.Miniscript:
    """Return a copy of the node, its subexpressions copied too."""
    return pickle.loads(pickle.dumps(node))  # noqa: S301


def test_a_tr_miniscript_leaf_holding_a_node_of_another_context_is_refused() -> None:
    """Each node writes its keys in its own context, whatever the root's."""
    expression = f"and_v(v:pk({_C}),older(1))"
    leaf = _unpickled(miniscript.parse(expression, miniscript.TAPSCRIPT))
    _with_context(leaf.subs[0], miniscript.P2WSH)
    with pytest.raises(BTClibValueError, match="^not a tapscript node: v: in P2WSH$"):
        TrDescriptor(_KEY, leaf)


# a fixed random value in each shape an unpickled node's context can
# take, and the spelling of it a refusal could print
_UNKNOWN_CONTEXTS = [
    (770907403214864877517, "770907403214864877517"),
    (bytes.fromhex(_RANDOM_HEX), bytes.fromhex(_RANDOM_HEX)),
    (_RANDOM_HEX, _RANDOM_HEX),
]


@pytest.mark.parametrize("context,spelling", _UNKNOWN_CONTEXTS)
def test_a_tr_leaf_of_an_unknown_context_is_refused(
    context: Any, spelling: str | bytes
) -> None:
    """A context the library does not define is not echoed, being any value."""
    leaf = _unpickled(miniscript.parse("1", miniscript.TAPSCRIPT))
    _with_context(leaf, context)
    err_msg = "^not a tapscript node: 1 in another context$"
    with pytest.raises(BTClibValueError, match=err_msg) as e:
        TrDescriptor(_KEY, leaf)
    assert_secret_free(e.value, [spelling])


@pytest.mark.parametrize("sort", [False, True])
def test_a_multi_a_built_by_hand_parses_back(sort: bool) -> None:
    """The control: a leaf built by hand is the leaf `parse` reads."""
    descriptor = TrDescriptor(_KEY, MultiA(2, (_KEY, _KEY2), sort=sort))
    assert parse(str(descriptor)) == descriptor


@pytest.mark.parametrize("threshold", ["1", 1.0, True, None])
def test_a_multi_a_threshold_of_another_type_is_refused(threshold: Any) -> None:
    """A bool is no number of signatures, though Python makes it an int."""
    err_msg = f"^invalid threshold type: {type(threshold).__name__}$"
    with pytest.raises(BTClibTypeError, match=err_msg):
        MultiA(threshold, (_KEY,))


@pytest.mark.parametrize(
    "keys,what",
    [([_KEY], "keys"), (_KEY, "keys"), ((_KEY, _X2), "key"), ((None,), "key")],
)
def test_multi_a_keys_of_another_type_are_refused(keys: Any, what: str) -> None:
    """A tuple of KEY expressions, as `parse` builds it."""
    with pytest.raises(BTClibTypeError, match=f"^invalid {what} type: "):
        MultiA(1, keys)


@pytest.mark.parametrize("sort", [1, "sortedmulti_a", None])
def test_a_multi_a_sort_of_another_type_is_refused(sort: Any) -> None:
    """The flag says which of two scripts is built, so it is a bool."""
    err_msg = f"^invalid sort type: {type(sort).__name__}$"
    with pytest.raises(BTClibTypeError, match=err_msg):
        MultiA(1, (_KEY,), sort=sort)


@pytest.mark.parametrize("sort", [False, True])
@pytest.mark.parametrize(
    "threshold,keys",
    [(0, (_KEY,)), (-1, (_KEY,)), (3, (_KEY, _KEY2)), (1, ())],
    ids=["zero", "negative", "above-key-count", "no-key"],
)
def test_a_multi_a_threshold_out_of_range_is_refused(
    threshold: int, keys: tuple[Any, ...], sort: bool
) -> None:
    """From 1 to the number of keys, named as `parse` names the function."""
    name = "sortedmulti_a" if sort else "multi_a"
    err_msg = f"^invalid k in k-of-n {name}: {threshold}$"
    with pytest.raises(BTClibValueError, match=err_msg):
        MultiA(threshold, keys, sort=sort)


_K = PrvKeyData(1).pub.sec.hex()
_K2 = PrvKeyData(2).pub.sec.hex()
_MINISCRIPT = parse(f"wsh(and_v(v:pk({_K}),older(1)))")
assert isinstance(_MINISCRIPT, WshDescriptor)
# one descriptor of each fragment, as `parse` builds it
_PARSED: dict[type[Descriptor], Descriptor] = {
    type(descriptor): descriptor
    for descriptor in (
        parse(f"pk({_K})"),
        parse(f"pkh({_K})"),
        parse(f"wpkh({_K})"),
        parse(f"sh(wpkh({_K}))"),
        parse(f"wsh(pk({_K}))"),
        _MINISCRIPT.inner,
        parse(f"multi(1,{_K},{_K2})"),
        parse(f"combo({_K})"),
        parse("addr(bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4)"),
        parse("raw(51)"),
        parse(f"rawpkh({'00' * 20})"),
        parse(f"tr({_X})"),
        parse(f"rawtr({_X})"),
    )
}
_KEY_FIELD_CLASSES = (
    PkDescriptor,
    PkhDescriptor,
    WpkhDescriptor,
    ComboDescriptor,
    RawTrDescriptor,
)
# (fragment, field, a value of the wrong type, the name the refusal gives)
_WRONG: list[tuple[type[Descriptor], str, Any, str]] = [
    *(
        (cls, "network", value, "network")
        for cls in _PARSED
        for value in (5, None, b"mainnet")
    ),
    *(
        (cls, "key", value, "key")
        for cls in _KEY_FIELD_CLASSES
        for value in (_K, 5, None, _MINISCRIPT.inner)
    ),
    *(
        (cls, "inner", value, "inner descriptor")
        for cls in (ShDescriptor, WshDescriptor)
        for value in (f"pk({_K})", 5, _KEY)
    ),
    (MiniscriptDescriptor, "node", "and_v(v:pk(K),older(1))", "miniscript"),
    (MiniscriptDescriptor, "node", _MINISCRIPT, "miniscript"),
    (MultiDescriptor, "threshold", "1", "threshold"),
    (MultiDescriptor, "threshold", 1.0, "threshold"),
    (MultiDescriptor, "threshold", True, "threshold"),
    (MultiDescriptor, "keys", [_KEY, _KEY2], "keys"),
    (MultiDescriptor, "keys", _KEY, "keys"),
    (MultiDescriptor, "keys", (_KEY, _K2), "key"),
    (MultiDescriptor, "sort", 1, "sort"),
    (MultiDescriptor, "sort", "sortedmulti", "sort"),
    (AddrDescriptor, "addr", b"bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", "address"),
    (AddrDescriptor, "addr", 5, "address"),
    (RawDescriptor, "script", "51", "script"),
    (RawPkhDescriptor, "key_hash", "00" * 20, "key hash"),
    (TrDescriptor, "internal_key", _X, "internal key"),
    (TrDescriptor, "tree", 5, "script tree node"),
]


def _fragments(cls: type) -> list[type]:
    """Return every subclass of `cls`, at any depth."""
    found: list[type] = []
    subs: list[type] = cls.__subclasses__()
    for sub in subs:
        found += [sub, *_fragments(sub)]
    return found


def test_every_field_of_every_fragment_has_a_wrong_type_tried() -> None:
    """The census: a fragment or a field added later is tried here too."""
    assert set(_PARSED) == set(_fragments(Descriptor))
    tried = {(cls, name) for cls, name, _, _ in _WRONG}
    every = {(cls, f.name) for cls in _PARSED for f in fields(cls)}
    assert tried == every


@pytest.mark.parametrize("cls", list(_PARSED), ids=lambda cls: cls.__name__)
def test_a_fragment_rebuilt_from_its_own_fields_is_the_same(
    cls: type[Descriptor],
) -> None:
    """The control: each field `parse` builds is one the fragment takes."""
    descriptor = _PARSED[cls]
    assert type(descriptor) is cls
    assert replace(descriptor) == descriptor


@pytest.mark.parametrize(
    "cls,name,value,what",
    _WRONG,
    ids=[f"{c.__name__}-{n}-{type(v).__name__}" for c, n, v, _ in _WRONG],
)
def test_a_fragment_field_of_another_type_is_refused(
    cls: type[Descriptor], name: str, value: Any, what: str
) -> None:
    """A `BTClibTypeError` when it is built, naming the field."""
    err_msg = f"^invalid {what} type: "
    with pytest.raises(BTClibTypeError, match=err_msg):
        replace(_PARSED[cls], **{name: value})
