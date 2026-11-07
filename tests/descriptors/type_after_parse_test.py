# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""An ill-typed subexpression before a fault Core's parser stops on.

Issue btclib-org/bip32-descriptors#16. Core is the release
`integration-bitcoind.yml` pins. Its miniscript parser builds every
fragment whatever its type, and its descriptor reader refuses an
ill-typed one only once the parser has finished. So a fault that stops
the parser is what Core names, even after an ill-typed subexpression:
its fallback inside wsh() or a tr() leaf, or the key it refuses. Where
the type is the only fault there, parse names the innermost ill-typed
fragment. What Core names for each descriptor here is what
getdescriptorinfo answered on an offline node.
"""

import pytest
from btclib.b58 import wif_from_prv_key
from btclib.exceptions import BTClibValueError
from btclib.key import PrvKeyData

from bip32_descriptors.descriptors import parse
from bip32_descriptors.descriptors.miniscript import P2WSH, TAPSCRIPT
from bip32_descriptors.descriptors.miniscript import parse as parse_miniscript
from tests.descriptors import P2WSH_FAULT, TR_LEAF_FAULT
from tests.secret_free import assert_secret_free

K = PrvKeyData(1).pub.sec.hex()
K2 = PrvKeyData(2).pub.sec.hex()
K3 = PrvKeyData(3).pub.sec.hex()
X, X2, X3 = K[2:], K2[2:], K3[2:]
# a fixed random private key, so that no piece of it is a piece of a
# clean message, as `assert_secret_free` asks
_PRV_KEY = 0xC2E58B0C21FC8C9765C9E2B474B2A8A35F59B2588BBF2D258045FD36BB016246
# of the network parse reads by default
WIF = wif_from_prv_key(_PRV_KEY, "mainnet")
_KEY_FAULT = "^invalid key expression$"
_ILL_TYPED = "^ill-typed miniscript: and_v over Bdekmnosu, Bdekmnosu$"

# and_v() takes a V first: over two B it has no type
BAD = "and_v(pk(K),pk(K2))"

# an ill-typed subexpression at several depths, before LATER
SHAPES = [
    "and_v(BAD,LATER)",
    "and_v(and_v(BAD,pk(K)),LATER)",
    "or_d(and_v(and_v(BAD,pk(K)),pk(K2)),LATER)",
    "thresh(1,BAD,s:LATER)",
]

# a fault Core's parser stops on without naming a key
FALLBACKS = [
    "foo(1)",
    "sha256(zz)",
    "older(0)",
    "q:pk(K3)",
    "vv:pk(K3)",
    "thresh(2,pk(K3))",
    "thresh(0,pk(K3))",
    "MULTI(0,K3)",
]

# a key Core's parser refuses
KEY_FAULTS = ["pk(zz)", "MULTI(1,zz)"]

# where the later fault is the parse's own, not a fragment's
FALLBACK_EXPRESSIONS = [
    "thresh(2,BAD)",
    "and_v(v:pk(K3),thresh(2,BAD))",
    "and_v(BAD,pk(K3)",
    "and_v(BAD,pk(K3))x",
    "and_v(BAD,WRONG_MULTI(1,K3))",
    *(shape.replace("LATER", later) for shape in SHAPES for later in FALLBACKS),
]

KEY_FAULT_EXPRESSIONS = [
    shape.replace("LATER", later) for shape in SHAPES for later in KEY_FAULTS
]

# the type is the only fault
TYPE_ONLY = [
    "BAD",
    "and_v(BAD,pk(K3))",
    "or_d(and_v(BAD,pk(K3)),pk(K2))",
    "or_d(BAD,and_b(pk(K3),pk(K2)))",
    "thresh(1,pk(K3),s:BAD)",
]


def _written_for(expression: str, context: str) -> str:
    """Return the expression with the keys and the multisigs of the context."""
    text = expression.replace("BAD", BAD)
    if context == P2WSH:
        multi, wrong, keys = "multi", "multi_a", (K3, K2, K)
    else:
        multi, wrong, keys = "multi_a", "multi", (X3, X2, X)
    text = text.replace("WRONG_MULTI", wrong).replace("MULTI", multi)
    for name, key in zip(("K3", "K2", "K"), keys, strict=True):
        text = text.replace(name, key)
    return text


@pytest.mark.parametrize("expression", FALLBACK_EXPRESSIONS)
def test_core_s_fallback_is_named_after_an_ill_typed_subexpression(
    expression: str,
) -> None:
    """Core's parser stops before the type is asked, and names its fallback."""
    text = _written_for(expression, P2WSH)
    with pytest.raises(BTClibValueError, match=P2WSH_FAULT):
        parse(f"wsh({text})")
    text = _written_for(expression, TAPSCRIPT)
    with pytest.raises(BTClibValueError, match=TR_LEAF_FAULT):
        parse(f"tr({X},{text})")


@pytest.mark.parametrize("expression", KEY_FAULT_EXPRESSIONS)
def test_a_key_core_refuses_is_named_after_an_ill_typed_subexpression(
    expression: str,
) -> None:
    """Core's parser stops on the key, before the type is asked."""
    for descriptor in (
        f"wsh({_written_for(expression, P2WSH)})",
        f"tr({X},{_written_for(expression, TAPSCRIPT)})",
    ):
        with pytest.raises(BTClibValueError, match=_KEY_FAULT):
            parse(descriptor)


@pytest.mark.parametrize("expression", TYPE_ONLY)
def test_the_innermost_ill_typed_fragment_is_named(expression: str) -> None:
    """Where the type is the only fault, the fragment that failed is named."""
    for descriptor in (
        f"wsh({_written_for(expression, P2WSH)})",
        f"tr({X},{_written_for(expression, TAPSCRIPT)})",
    ):
        with pytest.raises(BTClibValueError, match=_ILL_TYPED):
            parse(descriptor)


def test_the_type_comes_before_text_after_a_comma() -> None:
    """Core reads the miniscript up to the comma, and types it first."""
    with pytest.raises(BTClibValueError, match=_ILL_TYPED):
        parse(f"wsh({_written_for(BAD, P2WSH)},{K})")
    with pytest.raises(BTClibValueError, match=_ILL_TYPED):
        parse_miniscript(f"{_written_for(BAD, P2WSH)},{K}")


def test_the_type_comes_before_the_thresh_argument_bound() -> None:
    """Core reads every argument of a thresh(), and then types it."""
    arguments = ",".join([f"s:pk({X3})"] * 1000)
    text = f"thresh(1,{_written_for(BAD, TAPSCRIPT)},{arguments})"
    with pytest.raises(BTClibValueError, match=_ILL_TYPED):
        parse(f"tr({X},{text})")


def test_a_private_key_is_not_echoed() -> None:
    """Core's leaf message holds the leaf, and the leaf can hold a key."""
    text = f"and_v(and_v(pk({WIF}),pk({X2})),foo(1))"
    with pytest.raises(BTClibValueError, match=TR_LEAF_FAULT) as caught:
        parse(f"tr({X},{text})")
    assert_secret_free(caught.value, [WIF, f"{_PRV_KEY:064x}"])


@pytest.mark.parametrize(
    "expression,message",
    [
        ("and_v(BAD,foo(1))", "^unknown miniscript fragment$"),
        ("thresh(2,BAD)", r"^invalid thresh\(\) threshold: 2 of 1$"),
        ("and_v(BAD,pk(K3))x", "^trailing characters after the miniscript$"),
    ],
)
def test_the_standalone_parser_names_the_later_fault(
    expression: str, message: str
) -> None:
    """The language parser names the fault it found while reading."""
    with pytest.raises(BTClibValueError, match=message):
        parse_miniscript(_written_for(expression, P2WSH))
