# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Bitcoin Core answers ``unused()`` as `tests/descriptors/unused_test.py` says.

Skipped unless `BTCLIB_INTEGRATION=1` and a `bitcoind` is available; the
conftest beside this says which switch was off.
"""

from __future__ import annotations

import pytest
from bitcoin_core_rpc import BitcoinCoreRpcClient, FetchError

from bip32_descriptors.descriptors import add_checksum
from tests import vector_id
from tests.descriptors.unused_test import (
    CORE_ACCEPTED,
    CORE_REFUSED,
    HARDENED_PUBLIC,
    XPUB,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "descriptor, core",
    [
        pytest.param(descriptor, core, id=vector_id(index, descriptor))
        for index, (descriptor, core) in enumerate(CORE_ACCEPTED)
    ],
)
def test_core_answers_the_descriptor(
    node: BitcoinCoreRpcClient, descriptor: str, core: str
) -> None:
    """getdescriptorinfo's descriptor, and no address to derive from it."""
    assert node.call("getdescriptorinfo", [descriptor])["descriptor"] == core
    message = (
        "Cannot derive script without private keys"
        if descriptor == HARDENED_PUBLIC
        else "Unexpected empty result"
    )
    with pytest.raises(FetchError, match=message):
        node.call("deriveaddresses", [add_checksum(descriptor)])


@pytest.mark.parametrize(
    "descriptor",
    [
        pytest.param(descriptor, id=vector_id(index, descriptor))
        for index, (descriptor, _) in enumerate(CORE_REFUSED)
    ],
)
def test_core_refuses_the_descriptor(
    node: BitcoinCoreRpcClient, descriptor: str
) -> None:
    """Each descriptor `parse` refuses, Core refuses."""
    with pytest.raises(FetchError, match="rpc error code -5"):
        node.call("getdescriptorinfo", [descriptor])


def test_core_expands_the_multipath_key(node: BitcoinCoreRpcClient) -> None:
    """The two descriptors `multipath_descriptors` answers."""
    info = node.call("getdescriptorinfo", [f"unused({XPUB}/<0;1>)"])
    assert info["multipath_expansion"] == [
        f"unused({XPUB}/0)#ehkv04xm",
        f"unused({XPUB}/1)#rk389kxy",
    ]
