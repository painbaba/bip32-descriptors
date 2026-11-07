# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""``unused(KEY)``: a key and no script, as Bitcoin Core reads it.

Issue btclib-org/bip32-descriptors#134. Core is the release
`integration-bitcoind.yml` pins. `CORE_UNUSED` and `CORE_UNPARSABLE` are
the cases of its `unused_descriptor_test`, which `tests/_data/README.md`
pins. The other answers named Core's here are what getdescriptorinfo,
deriveaddresses and listdescriptors answered on an offline regtest node,
and `tests/integration/unused_test.py` asks the node again.
"""

from __future__ import annotations

import pytest
from btclib.exceptions import BTClibValueError

from bip32_descriptors.descriptors import (
    UnusedDescriptor,
    add_checksum,
    at_index,
    multipath_descriptors,
    normalized,
    parse,
    private_string,
    wallet_policy,
)
from tests.secret_free import assert_secret_free

# the cases of Core's `CheckUnused`: the private spelling and the public one
CORE_UNUSED = [
    (
        "unused(xprvA1RpRA33e1JQ7ifknakTFpgNXPmW2YvmhqLQYMmrj4xJXXWYpDPS3xz7iAxn8L39njGVyuoseXzU6rcxFLJ8HFsTjSyQbLYnMpCqE2VbFWc)",
        "unused(xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL)",
    ),
    (
        "unused(L4rK1yDtCWekvXuE6oXD9jCYfFNV2cWRpVuPLBcCU2z8TrisoyY1)",
        "unused(03a34b99f22c790c4e36b2b3c2c35a36db06226e41c692fc82b8b56ac1c540c5bd)",
    ),
    (
        "unused(xprvA1RpRA33e1JQ7ifknakTFpgNXPmW2YvmhqLQYMmrj4xJXXWYpDPS3xz7iAxn8L39njGVyuoseXzU6rcxFLJ8HFsTjSyQbLYnMpCqE2VbFWc/0h/0h/1)",
        "unused(xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL/0h/0h/1)",
    ),
]

# the cases of Core's `CheckUnparsable` and `CheckSingleUnparsable`: the
# private spelling, the public one, and the message `parse` refuses the
# public one with. Core's message is "unused(): only one key expected" for
# the first, "Can only have unused at top level" for the second and
# "Pubkey '<key>' is invalid" for the last. Core reads the error of the
# public string alone, so the private one is only held to be refused
CORE_UNPARSABLE = [
    (
        "unused(L4rK1yDtCWekvXuE6oXD9jCYfFNV2cWRpVuPLBcCU2z8TrisoyY1,5KYZdUEo39z3FPrtuX2QbbwGnNP5zTd7yyr2SC1j299sBCnWjss)",
        "unused(03a34b99f22c790c4e36b2b3c2c35a36db06226e41c692fc82b8b56ac1c540c5bd,04a34b99f22c790c4e36b2b3c2c35a36db06226e41c692fc82b8b56ac1c540c5bd5b8dec5235a0fa8722476c7709c02559e3aa73aa03918ba2d492eea75abea235)",
        r"^unused\(\) takes one argument, 2 given$",
    ),
    (
        "wsh(unused(L4rK1yDtCWekvXuE6oXD9jCYfFNV2cWRpVuPLBcCU2z8TrisoyY1))",
        "wsh(unused(03a34b99f22c790c4e36b2b3c2c35a36db06226e41c692fc82b8b56ac1c540c5bd))",
        r"^unused\(\) is not allowed inside wsh\(\)$",
    ),
    (
        "unused(xprvA1RpRA33e1JQ7ifknakTFpgNXPmW2YvmhqLQYMmrj4xJXXWYpDPS3xz7iAxn8L39njGVyuoseXzU6rcxFLJ8HFsTjSyQbLYnMpCqE2VbFWc/*)",
        "unused(xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL/*)",
        r"^unused\(\): key cannot be ranged$",
    ),
    ("unused()", "unused()", "^No key provided$"),
    (
        "unused(a34b99f22c790c4e36b2b3c2c35a36db06226e41c692fc82b8b56ac1c540c5bd)",
        "unused(a34b99f22c790c4e36b2b3c2c35a36db06226e41c692fc82b8b56ac1c540c5bd)",
        "^x-only public keys are allowed in a taproot key expression only$",
    ),
]

# the private keys of Core's cases above
CORE_SECRETS = [
    "L4rK1yDtCWekvXuE6oXD9jCYfFNV2cWRpVuPLBcCU2z8TrisoyY1",
    "5KYZdUEo39z3FPrtuX2QbbwGnNP5zTd7yyr2SC1j299sBCnWjss",
    "xprvA1RpRA33e1JQ7ifknakTFpgNXPmW2YvmhqLQYMmrj4xJXXWYpDPS3xz7iAxn8L39njGVyuoseXzU6rcxFLJ8HFsTjSyQbLYnMpCqE2VbFWc",
]

# keys of the test networks, which Core's regtest node reads: the private
# key 1 as a WIF and its compressed and uncompressed public keys, and an
# extended key with its xpub
K = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
U = (
    "0479be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
    "483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8"
)
WIF = "cMahea7zqjxrtgAbB7LSGbcQUr1uX1ojuat9jZodMN87JcbXMTcA"
XPRV = "tprv8ZgxMBicQKsPe3g3HwF9xxTLiyc5tNyEtjhBBAk29YA3MTQUqULrmg7aj9qTKNfieuu2HryQ6tGVHse9x7ANFGs3f4HgypMc5nSSoxwf7TK"
XPUB = "tpubD6NzVbkrYhZ4XWhqBaukNN7TJ1823iA9U3HxTgnKZoxSBwfFTsASxAjSuHvUjejQM6r1RSQwQCdnKYQ2KB458gkCqiY5DceFARXm7zfWpKS"

# a key Core reads and cannot derive: a hardened step from an xpub
HARDENED_PUBLIC = f"unused({XPUB}/0h)"

# a descriptor and the descriptor getdescriptorinfo answers for it
CORE_ACCEPTED = [
    (f"unused({K})", f"unused({K})#qxhn8d3e"),
    (f"unused({U})", f"unused({U})#vzyrwgxz"),
    (f"unused({WIF})", f"unused({K})#qxhn8d3e"),
    (f"unused({XPRV})", f"unused({XPUB})#gs7x5hcj"),
    (f"unused({XPRV}/0h/1)", f"unused({XPUB}/0h/1)#0myj8xkw"),
    (HARDENED_PUBLIC, f"unused({XPUB}/0h)#rumn5ptr"),
    (f"unused([deadbeef/1h]{XPUB}/0)", f"unused([deadbeef/1h]{XPUB}/0)#9gjh9wv0"),
]

# a descriptor Core refuses, and the message `parse` refuses it with; the
# comment gives Core's where it differs
CORE_REFUSED = [
    # Core: Can only have unused at top level
    (f"sh(unused({K}))", r"^unused\(\) is not allowed inside sh\(\)$"),
    (f"wsh(unused({K}))", r"^unused\(\) is not allowed inside wsh\(\)$"),
    (f"tr({K[2:]},unused({K}))", r"^unused\(\) is not allowed inside tr\(\)$"),
    (f"sh(unused({WIF}))", r"^unused\(\) is not allowed inside sh\(\)$"),
    (f"wsh(unused({XPRV}))", r"^unused\(\) is not allowed inside wsh\(\)$"),
    (f"tr({K[2:]},unused({WIF}))", r"^unused\(\) is not allowed inside tr\(\)$"),
    (f"unused({XPUB}/*)", r"^unused\(\): key cannot be ranged$"),
    (f"unused({XPUB}/*h)", r"^unused\(\): key cannot be ranged$"),
    (f"unused({XPRV}/*)", r"^unused\(\): key cannot be ranged$"),
    (f"unused({XPRV}/0h/*h)", r"^unused\(\): key cannot be ranged$"),
    # Core: unused(): only one key expected
    (f"unused({WIF},{XPRV})", r"^unused\(\) takes one argument, 2 given$"),
    (f"unused(musig({K},{U}))", r"^musig\(\) is only allowed in tr\(\) and rawtr\(\)$"),
]


@pytest.mark.parametrize("prv, pub", CORE_UNUSED)
def test_core_unused_cases_parse_to_the_public_spelling(prv: str, pub: str) -> None:
    """Both spellings parse to one key, and write the public one back."""
    for descriptor in (prv, pub):
        prv_keys: dict[str, str] = {}
        parsed = parse(descriptor, prv_keys=prv_keys)
        assert isinstance(parsed, UnusedDescriptor)
        assert str(parsed) == pub
        assert len(parsed.key_expressions) == 1
        # `parse` files an xprv, and no WIF
        assert bool(prv_keys) == (descriptor == prv and "xprv" in prv)


@pytest.mark.parametrize("prv, pub, message", CORE_UNPARSABLE)
def test_core_unparsable_cases_are_refused(prv: str, pub: str, message: str) -> None:
    """The public spelling with the message above, the private one at all."""
    with pytest.raises(BTClibValueError, match=message):
        parse(pub)
    with pytest.raises(BTClibValueError) as e:
        parse(prv)
    assert_secret_free(e.value, CORE_SECRETS)


@pytest.mark.parametrize("descriptor, core", CORE_ACCEPTED)
def test_the_descriptor_is_what_core_answers(descriptor: str, core: str) -> None:
    """`str` with the checksum is getdescriptorinfo's descriptor."""
    assert add_checksum(str(parse(descriptor, "regtest"))) == core


@pytest.mark.parametrize("descriptor, message", CORE_REFUSED)
def test_what_core_refuses_is_refused(descriptor: str, message: str) -> None:
    """Refused where Core refuses it, with no private key in the refusal."""
    with pytest.raises(BTClibValueError, match=message) as e:
        parse(descriptor, "regtest")
    assert_secret_free(e.value, [WIF, XPRV])


def test_multipath_descriptors_answers_core_multipath_expansion() -> None:
    """getdescriptorinfo's `multipath_expansion`, checksums included."""
    assert multipath_descriptors(f"unused({XPUB}/<0;1>)", "regtest") == [
        f"unused({XPUB}/0)#ehkv04xm",
        f"unused({XPUB}/1)#rk389kxy",
    ]
    with pytest.raises(BTClibValueError, match=r"^unused\(\): key cannot be ranged$"):
        multipath_descriptors(f"unused({XPUB}/<0;1>/*)", "regtest")


def test_normalized_and_private_string_are_what_listdescriptors_writes() -> None:
    """listdescriptors, and listdescriptors with its private flag."""
    prv_keys: dict[str, str] = {}
    descriptor = parse(f"unused({XPRV}/0h/1)", "regtest", prv_keys)
    assert add_checksum(str(normalized(descriptor, prv_keys))) == (
        "unused([f2bbcaff/0h]tpubDA3cBfTCfhWK45otn6ez68ypCicaFFe2Pd5tD4HFVXBfw"
        "XjR1pZyFu1g2H5uMGMHhyCgecF157p8JJECEcapYYW8PFwdmkBFt9nuxUgpkfc/1)#zrz73suz"
    )
    assert add_checksum(private_string(descriptor, prv_keys)) == (
        f"unused({XPRV}/0h/1)#rcj0e95f"
    )


def test_no_script_and_no_address() -> None:
    """Core's deriveaddresses answers "Unexpected empty result"."""
    prv_keys: dict[str, str] = {}
    descriptor = parse(f"unused({XPRV}/0h/1)", "regtest", prv_keys)
    assert not descriptor.is_ranged
    assert descriptor.script_pub_keys(0, prv_keys) == []
    assert descriptor.addresses(0, prv_keys) == []
    assert descriptor.index_of(b"\x51", 5, prv_keys) is None
    assert at_index(descriptor) == descriptor
    for method in (descriptor.script_pub_key, descriptor.address):
        with pytest.raises(BTClibValueError, match="^0 scripts: "):
            method(0, prv_keys)


def test_a_key_that_cannot_derive_is_refused() -> None:
    """Core's deriveaddresses: "Cannot derive script without private keys"."""
    descriptor = parse(HARDENED_PUBLIC, "regtest")
    for method in (descriptor.script_pub_keys, descriptor.addresses):
        with pytest.raises(BTClibValueError, match="hardened derivation"):
            method()


def test_the_provider_holds_the_key_and_its_origin() -> None:
    """Core's `Expand` adds the key, and makes no script."""
    prv_keys: dict[str, str] = {}
    descriptor = parse(f"unused({XPRV}/0h/1)", "regtest", prv_keys)
    provider = descriptor.provider(0, prv_keys)
    sec = descriptor.key_expressions[0].sec(0, "regtest", prv_keys)
    origin = provider.keys[sec]
    assert origin is not None
    assert origin.description == "f2bbcaff/0h/1"
    assert len(provider.keys) == 1
    assert provider.scripts == ()
    assert provider.trees == {}


def test_there_is_nothing_to_satisfy_or_update() -> None:
    """No script, so no spend and no psbt field."""
    descriptor = parse(f"unused({K})")
    with pytest.raises(BTClibValueError, match="cannot be satisfied: it has no script"):
        descriptor.satisfy({})
    with pytest.raises(BTClibValueError, match="cannot update a psbt: it has no script"):
        descriptor.expansion()


def test_it_is_no_wallet_policy() -> None:
    """BIP388 lists no ``unused()``, whose key takes no wildcard anyway."""
    with pytest.raises(BTClibValueError, match="not a BIP388 SCRIPT expression"):
        wallet_policy(parse(f"unused({XPUB}/0)", "regtest"))
