# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""What a `Miniscript` built by hand is refused for, and what it names.

A context the library does not define, a fragment it does not know, and
a subexpression whose context is not the node's. The first two are any
value a caller passes, so the refusal names none of it. Issues
btclib-org/bip32-descriptors#120 and btclib-org/bip32-descriptors#130.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from btclib.exceptions import BTClibTypeError, BTClibValueError
from btclib.key import PrvKeyData

from bip32_descriptors.descriptors import parse
from bip32_descriptors.descriptors.descriptors import (
    MiniscriptDescriptor,
    WshDescriptor,
)
from bip32_descriptors.descriptors.miniscript import P2WSH, TAPSCRIPT, Miniscript
from bip32_descriptors.descriptors.miniscript import parse as parse_miniscript
from tests.secret_free import assert_secret_free

_C = PrvKeyData(3).pub.sec.hex()
_WIF = "L4rK1yDtCWekvXuE6oXD9jCYfFNV2cWRpVuPLBcCU2z8TrisoyY1"
_RANDOM_HEX = "7e3d796f1b20eb42c57e4f6a0c6ecaf1879529ae1ad154cebf0ed79035de2901"


@pytest.mark.parametrize("context", [P2WSH, TAPSCRIPT])
def test_a_node_built_by_hand_in_one_context_is_built(context: str) -> None:
    """The control: the node `parse` reads, built field by field."""
    older = Miniscript("older", context, threshold=1)
    verify = Miniscript("v:", context, (Miniscript("1", context),))
    node = Miniscript("and_v", context, (verify, older))
    assert node == parse_miniscript("and_v(v:1,older(1))", context)


@pytest.mark.parametrize("unknown", [_WIF, _RANDOM_HEX])
def test_an_unknown_fragment_is_refused_without_its_text(unknown: str) -> None:
    """Text in the wrong field, a WIF among them, is not echoed."""
    node = parse_miniscript("1", TAPSCRIPT)
    with pytest.raises(BTClibValueError, match="^unknown miniscript fragment$") as e:
        replace(node, fragment=unknown)
    assert_secret_free(e.value, [unknown])


@pytest.mark.parametrize("context", [_WIF, _RANDOM_HEX])
def test_an_unknown_context_is_refused_without_its_text(context: str) -> None:
    """Unrefused, every rule would read it as the p2wsh context."""
    node = parse_miniscript("1", TAPSCRIPT)
    err_msg = r"^unknown spend context; it must be one of \['P2WSH', 'tapscript'\]$"
    with pytest.raises(BTClibValueError, match=err_msg) as e:
        replace(node, context=context)
    assert_secret_free(e.value, [context])


# a fixed random value in each shape other than text, and the spelling of
# it a refusal could print
@pytest.mark.parametrize(
    "context,spelling",
    [
        (770907403214864877517, "770907403214864877517"),
        (bytes.fromhex(_RANDOM_HEX), bytes.fromhex(_RANDOM_HEX)),
    ],
)
def test_a_context_of_another_type_is_refused(
    context: Any, spelling: str | bytes
) -> None:
    """A context is text, and the refusal names its type alone."""
    node = parse_miniscript("1", TAPSCRIPT)
    err_msg = f"^invalid context type: {type(context).__name__}$"
    with pytest.raises(BTClibTypeError, match=err_msg) as e:
        replace(node, context=context)
    assert_secret_free(e.value, [spelling])


def test_a_p2wsh_node_of_a_tapscript_subexpression_is_refused() -> None:
    """Its key would be written x-only into a p2wsh script.

    Built, ``wsh()`` of it would write a script whose text `parse` reads
    with the 33-byte key, so the descriptor would not round-trip.
    """
    tapscript = parse_miniscript(f"and_v(v:pk({_C}),older(1))", TAPSCRIPT)
    older = Miniscript("older", P2WSH, threshold=1)
    err_msg = "^a subexpression of and_v is not in P2WSH$"
    with pytest.raises(BTClibValueError, match=err_msg) as e:
        Miniscript("and_v", P2WSH, (tapscript.subs[0], older))
    assert_secret_free(e.value, [_C, _C[2:]])
    p2wsh = parse_miniscript(f"and_v(v:pk({_C}),older(1))", P2WSH)
    descriptor = WshDescriptor(MiniscriptDescriptor(p2wsh))
    assert parse(str(descriptor)) == descriptor


def test_a_subexpression_of_another_context_is_refused_in_any_position() -> None:
    """A ``thresh()`` is checked past its first subexpression."""
    one = Miniscript("1", TAPSCRIPT)
    Miniscript("thresh", TAPSCRIPT, (one, one, one), threshold=1)
    err_msg = "^a subexpression of thresh is not in tapscript$"
    with pytest.raises(BTClibValueError, match=err_msg) as e:
        Miniscript("thresh", TAPSCRIPT, (one, one, Miniscript("1")), threshold=1)
    assert_secret_free(e.value, [P2WSH])
