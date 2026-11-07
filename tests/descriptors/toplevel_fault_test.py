# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Expressions no descriptor function takes, at the top level and in sh().

Issues btclib-org/bip32-descriptors#14, btclib-org/bip32-descriptors#118
and btclib-org/bip32-descriptors#128. Core is the release
`integration-bitcoind.yml` pins. Its ``ParseScript`` reads such an
expression as a tapscript miniscript in every position. Its miniscript
parser builds a miniscript whatever its type, so a type fault comes after
the position. Its ``Func`` takes a name only where the text ends in ")",
so a whole descriptor followed by a "}" is such an expression too. What
Core names for each descriptor here is what getdescriptorinfo answered on
an offline node.
"""

import pytest
from btclib.b58 import wif_from_prv_key
from btclib.exceptions import BTClibValueError
from btclib.key import PrvKeyData

from bip32_descriptors.bip32 import rootxprv_from_seed
from bip32_descriptors.descriptors import multipath_descriptors, parse
from tests.descriptors import MINISCRIPT_OUTSIDE, P2SH_FAULT, TOP_FAULT
from tests.secret_free import assert_secret_free

K = PrvKeyData(1).pub.sec.hex()
K2 = PrvKeyData(2).pub.sec.hex()
X, X2 = K[2:], K2[2:]
# of the network parse reads by default, from fixed random values
WIF = wif_from_prv_key(
    0x1F2E3D4C5B6A79881F2E3D4C5B6A79881F2E3D4C5B6A79881F2E3D4C5B6A7988, "mainnet"
)
XPRV = rootxprv_from_seed("1f2e3d4c" * 8)

# miniscripts Core's tapscript parser reads, of any type, sane or not
MINISCRIPTS = [
    f"and_v(v:pk({K}),pk({K2}))",
    f"and_v(v:pk({X}),pk({X2}))",
    f"or_b(pk({K}),a:pk({K2}))",
    f"and_v(v:pk({K}),older(1))",
    f"and_v(v:pk({K}),multi_a(1,{X2}))",
    f"and_v(v:pk({K}),pk({K}))",
    f"thresh(1,pk({K}))",
    "older(1)",
    "0",
    "1",
    f"and_v(pk({K}),pk({K2}))",
    f"and_v(v:pk({K}),and_v(pk({K2}),pk({K})))",
    f"or_b(pk({K}),pk({K2}))",
    f"thresh(1,pk({K}),pk({K2}))",
    f"v:pk({K})",
    f"pk_h({K})",
    f"a:pk({K})",
]

# expressions Core's tapscript parser fails on without naming a key
NO_FUNCTIONS = [
    "foo(1)",
    "foo",
    "foo(",
    "",
    "pk",
    "(pk)",
    f"nope({K})",
    f"q:pk({K})",
    f"thresh(2,pk({K}))",
    f"and_v(v:pk({K}),foo(1))",
    f"and_v(and_v(pk({K}),pk({K2})),foo(1))",
    f"thresh(2,and_v(pk({K}),pk({K2})))",
    f"and_v(and_v(pk({K}),pk({K2})),multi(1,{K}))",
    f"and_v(v:pk({K}),multi(1,{K2}))",
    f"and_v(v:pk({K}),pk({K2}))x",
    f"and_v(pk({K}),pk({K2}))x",
    f"v:pk({K})x",
    f"and_v(v:pk({K}),pk(zz)x)",
    "0x",
    f"multi(1,[dead]]{K})junk",
    f"multi_a(1,{X})x",
    f"musig({K},{K2})x",
    f"pk({K})x",
    f"pkh({K})(",
    f"wpkh({K}){{",
    f"multi(1,{K})x",
    f"sortedmulti(1,{K},{K2})x",
    f"wsh(pk({K}))x",
    "raw(51)x",
]


@pytest.mark.parametrize("expression", MINISCRIPTS)
def test_a_miniscript_outside_wsh_and_tr_is_refused(expression: str) -> None:
    """Core reads the miniscript, then refuses it for where it is."""
    for descriptor in (expression, f"sh({expression})"):
        with pytest.raises(BTClibValueError, match=MINISCRIPT_OUTSIDE):
            parse(descriptor)


@pytest.mark.parametrize("expression", NO_FUNCTIONS)
def test_an_expression_no_function_takes_is_the_fallback(expression: str) -> None:
    """Core names its fallback for the position where its parser fails."""
    with pytest.raises(BTClibValueError, match=TOP_FAULT):
        parse(expression)
    with pytest.raises(BTClibValueError, match=P2SH_FAULT):
        parse(f"sh({expression})")


@pytest.mark.parametrize(
    "descriptor",
    [
        f"wsh(and_v(v:pk({K}),pk({K2}))}})",
        f"tr({X},{{and_v(v:pk({X}),pk({X2}))}},pk({X2})}})",
        f"pk({K}}}))",
        f"sh(pk({K})}})",
        f"wsh(pk({K})}})",
        "sh(foo(1)})",
        f"tr({X})x",
        f"sh(pk({K}))x",
        f"combo({K})(",
        f"rawtr({X}){{",
    ],
)
def test_text_after_a_whole_descriptor_is_the_top_level_fallback(
    descriptor: str,
) -> None:
    """Core's top-level expression does not end in ")": no function takes it."""
    with pytest.raises(BTClibValueError, match=TOP_FAULT):
        parse(descriptor)


@pytest.mark.parametrize(
    "descriptor,message",
    [
        (f"and_v(v:pk(zz),pk({K}))", "^invalid key expression$"),
        (f"sh(and_v(v:pk(zz),pk({K})))", "^invalid key expression$"),
        (f"and_v(and_v(pk({K}),pk({K2})),pk(zz))", "^invalid key expression$"),
        (f"sh(and_v(and_v(pk({K}),pk({K2})),pk(zz)))", "^invalid key expression$"),
        ("v:pk(zz)", "^invalid key expression$"),
        (
            f"multi_a(1,[dead]]{X})x",
            r"^more than one '\]' in a single key expression$",
        ),
        (
            f"sh(multi_a(1,[dead]]{X})x)",
            r"^more than one '\]' in a single key expression$",
        ),
    ],
)
def test_a_key_core_refuses_is_the_fault(descriptor: str, message: str) -> None:
    """Core names a key its miniscript parser refuses before its fallback."""
    with pytest.raises(BTClibValueError, match=message):
        parse(descriptor)


@pytest.mark.parametrize(
    "expression", [f"and_v(v:pk({K}),pk({K2}))", f"and_v(pk({K}),pk({K2}))"]
)
def test_a_comma_inside_sh_ends_the_miniscript_core_refuses(expression: str) -> None:
    """Core reads the miniscript before the comma, and refuses it there."""
    with pytest.raises(BTClibValueError, match=MINISCRIPT_OUTSIDE):
        parse(f"sh({expression},{K})")


def test_multipath_descriptors_names_the_same_fault() -> None:
    """The multipath reader reads the expression as parse does."""
    with pytest.raises(BTClibValueError, match=MINISCRIPT_OUTSIDE):
        multipath_descriptors(f"and_v(v:pk({XPRV}/<0;1>/*),pk({K2}))")
    with pytest.raises(BTClibValueError, match=TOP_FAULT):
        multipath_descriptors(f"wsh(and_v(v:pk({XPRV}/<0;1>/*),pk({K2}))}})")


@pytest.mark.parametrize(
    "descriptor,message",
    [
        (WIF, TOP_FAULT),
        (XPRV, TOP_FAULT),
        (f"{WIF}(0)", TOP_FAULT),
        (f"foo({WIF},{XPRV})", TOP_FAULT),
        (f"wpkh({WIF}", TOP_FAULT),
        (f"pk({WIF})x", TOP_FAULT),
        (f"and_v(v:pk({WIF}),foo({XPRV}))", TOP_FAULT),
        (f"wsh(and_v(v:pk({WIF}),pk({XPRV}/0))}})", TOP_FAULT),
        (f"tr({XPRV},{{and_v(v:pk({WIF}),pk({X2}))}},pk({X2})}})", TOP_FAULT),
        (f"sh({WIF})", P2SH_FAULT),
        (f"sh(foo({WIF},{XPRV}))", P2SH_FAULT),
        (f"sh(pk({WIF})x)", P2SH_FAULT),
        (f"and_v(v:pk({XPRV}/0),pk({WIF}))", MINISCRIPT_OUTSIDE),
        (f"sh(and_v(v:pk({XPRV}/0),pk({WIF})))", MINISCRIPT_OUTSIDE),
        (f"and_v(pk({WIF}),pk({XPRV}/0))", MINISCRIPT_OUTSIDE),
        (f"sh(and_v(pk({XPRV}/0),pk({WIF})))", MINISCRIPT_OUTSIDE),
        (f"v:pk({XPRV}/0)", MINISCRIPT_OUTSIDE),
        (f"sh(pk_h({WIF}))", MINISCRIPT_OUTSIDE),
    ],
)
def test_the_refusal_leaves_the_expression_out(descriptor: str, message: str) -> None:
    """Core quotes the top-level expression, and it can hold a private key."""
    with pytest.raises(BTClibValueError, match=message) as e:
        parse(descriptor)
    assert_secret_free(e.value, [WIF, XPRV])
