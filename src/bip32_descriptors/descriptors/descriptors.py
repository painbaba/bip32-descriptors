# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Output descriptors: the checksum, the parser, the scripts, the spend.

A descriptor says which scripts a wallet owns, in one line of text. This
module reads that line and answers with both halves of what a wallet
does with it: `parse` returns a `Descriptor`, whose `script_pub_keys`
gives what the descriptor pays to at an index -- the receiving side --
and whose `satisfy` gives the script_sig and the witness that spend one
of those scripts, the signatures being handed in. The fragment classes
below are one per grammar function, which is what lets satisfaction be a
method of each rather than a dispatch table.

`satisfy` assembles and does not verify. A signature is checked against
the hash it committed to, that hash is a property of the spending
transaction, and a descriptor has no transaction -- which is also why
the signatures are a parameter rather than something this module makes.
btclib-wallet's `psbt.finalize` does have one and does check, and builds
the same bytes from a psbt carrying the same signatures.

`expansion` is the third answer, and the one for a spend the signers do
not make all at once: the scripts and the key origins BIP174's Updater
writes into a psbt, for signers to fill in at their own pace and
btclib-wallet's `psbt.finalize` to assemble. btclib-wallet's
`psbt.update_psbt_input` and `psbt.update_psbt_output` are that Updater.
This package imports nothing of btclib-wallet: a psbt is a transaction
being built, and a descriptor is what a wallet knows about the outputs
it holds.

BIP380: https://github.com/bitcoin/bips/blob/master/bip-0380.mediawiki

The grammar read is BIP380 to BIP390:

- ``pk``, ``pkh``, ``wpkh``, ``combo`` (BIP381, BIP382, BIP384)
- ``sh``, ``wsh``, including ``sh(wpkh())`` and ``sh(wsh())``
- ``multi``, ``sortedmulti`` (BIP383)
- ``addr``, ``raw`` (BIP385)
- ``tr``, with a key path and a script tree whose leaves are ``pk()``,
  ``multi_a()`` and ``sortedmulti_a()`` (BIP386, BIP387)
- ``rawtr`` (BIP394), whose key is the output key itself
- ``rawnode``, ``rawleaf`` and ``rawpkh``, which no BIP specifies, and
  ``raw`` inside ``sh()``, ``wsh()`` and a ``tr()`` tree: they let a
  descriptor say what it knows of an output it knows in part. Bitcoin
  Core's bitcoin/bitcoin#30243 specifies the first two, and the draft BIP
  of bitcoin/bips#1721 specifies ``rawnode`` too. BIP385 says
  ``raw(HEX)`` can only be a top level descriptor and lists
  ``sh(raw(deadbeef))`` and ``wsh(raw(deadbeef))`` as invalid; the draft
  BIP of bitcoin/bips#1721 allows the nested ``raw``, and this module
  follows the draft
- key expressions: hex public keys (compressed, uncompressed and, inside
  ``tr()`` and ``rawtr()``, x-only), WIF private keys, xpub/xprv with a
  derivation path, key origin, ``/*`` and ``/*h`` wildcards, both ``h``
  and ``'`` hardened markers
- ``musig``, the BIP390 key expression: the BIP327 aggregate of its
  participants, inside a ``tr()`` or a ``rawtr()`` and nowhere else, with
  BIP328 derivation of the aggregate key where it has a path of its own
- the ``<a;b>`` multipath form of BIP389, through `multipath_descriptors`
- a BIP379 miniscript, in both of the positions that BIP allows: inside
  ``wsh()``, where it is a `MiniscriptDescriptor`, and as a leaf of a
  ``tr()`` script tree, where it is a leaf beside the ``pk()`` and the
  ``multi_a()`` ones. Which expression is read as which is the order
  Bitcoin Core reads them in: the functions above are tried first, so the
  ``pk()``, ``pkh()`` and ``multi()`` that belong to both grammars are the
  descriptor functions they were before miniscript, and what is left is a
  miniscript -- of the P2WSH dialect inside ``wsh()`` and of the tapscript
  one inside ``tr()``, which is where ``multi_a()`` replaces ``multi()``

`satisfy` takes a `SpendContext` beside the signatures for the one
fragment that reads more than they carry: a miniscript satisfaction
chooses among branches, and the choice reads hash preimages and the lock
times the transaction being built will carry. Every other fragment ignores
it, having neither a branch to choose nor a preimage to look up.

`parse` refuses every ``<a;b>`` step, even one Bitcoin Core accepts, and
what reaches a `Descriptor` is one path per key. `multipath_descriptors`
expands the steps and hands each result to `parse`, so that one reader
names the faults; its docstring says which.

A parsed descriptor holds no key that signs. `parse` neuters an xprv to
the xpub the `KeyExpression` then carries, and hands the private spelling
back through the `prv_keys` mapping a caller passes in -- Bitcoin Core's
`Parse(desc, out, error)`, whose descriptor keeps no reference to the
`FlatSigningProvider` it filled. Expanding a descriptor takes the mapping
back for the one thing an xpub cannot do, a hardened step, which is why
`script_pub_keys`, `satisfy`, `expansion` and the rest all end in an
optional `prv_keys`. A WIF is not in that mapping: it was already reduced
to its public key on the way in, this module deriving nothing from it and
signing nothing with it.

Nor does a parsed descriptor hold a hash preimage. A hash fragment's
``preimage(HEX)`` is read to the digest the node keeps, and the preimage
goes back through the `preimages` mapping a caller passes in, keyed by
that digest. The `miniscript` module docstring says what that syntax is.

The network is a parameter of `parse` and not part of a descriptor: a
descriptor names keys and scripts, and the same one means something on
any chain, which is why Bitcoin Core takes the chain from its own context
too. ``addr()`` is the exception, an address carrying the network in its
own prefix.

`str(descriptor)` is the way back: the descriptor as text, without its
checksum. `add_checksum(str(descriptor))` is the checksummed form: Core's
`ToString`, `ToStringHelper` writing none, and HWI's and Electrum's
`to_string`. What it writes is public by construction, there being no
private material left in a parsed descriptor to write. `private_string`
is Core's `ToPrivateString`: it takes the two mappings back and writes
the xprv and ``preimage(HEX)`` spellings, as its docstring says.

`infer_descriptor` goes back from a script instead: Bitcoin Core's
`InferDescriptor`, reading the script and what a `Provider` knows of its
keys and scripts. `Descriptor.provider` is what a descriptor expanded at
an index knows. `scantxoutset` infers with the providers of every index
of its range, merged in order.

`normalized` is the other direction Bitcoin Core has, its
`ToNormalizedString`: the same descriptor with the xpub at each last
hardened step and the hardened prefix moved into the key origin, so that
a holder of no private key can compute every script it describes. That is
what `getdescriptorinfo` answers with, and what an export to a watch-only
wallet wants.

What this module exports is the checksum functions, `parse` and
`multipath_descriptors`, and the fragment classes a parsed descriptor is
made of -- `DescriptorTree` and the `MultiA`, `RawLeaf` and `RawNode` a
tree may hold among them, all being names a caller reads off
`TrDescriptor.tree`.
`KeyExpression` and `PrvKeys` are `key_expression`'s, and `Preimages` and
the `Miniscript` a `MiniscriptDescriptor` holds are `miniscript`'s; the
package `__init__` re-exports them, being what a caller reads off
`Descriptor.key_expressions` and annotates a mapping with.
`INPUT_CHARSET`, `CHECKSUM_CHARSET` and `GENERATOR` stay out: they are the
three tables BIP380's checksum is computed from, which is what `checksum`,
`add_checksum` and `strip_checksum` answer.
"""

from __future__ import annotations

import operator
import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, fields, replace
from typing import Any, cast

from btclib.alias import Octets, ScriptList
from btclib.exceptions import BTClibTypeError, BTClibValueError
from btclib.hashes import hash160, ripemd160
from btclib.key import PubKeyData
from btclib.network import (
    normalized_network_name,
    validated_network_name,
)
from btclib.script.limits import (
    MAX_PUBKEYS_PER_MULTISIG,
    MAX_SCRIPT_ELEMENT_SIZE,
    MAX_SCRIPT_SIZE,
)
from btclib.script.script import op_code_spans, op_int, serialize
from btclib.script.script_pub_key import ScriptPubKey, script_from_script_pub_key
from btclib.script.taproot import (
    MAX_TREE_DEPTH,
    leaf_hash,
    output_pubkey_from_merkle_root_var,
)
from btclib.script.witness import Witness
from btclib.utils import assert_type, bytes_from_octets, is_integer
from ecc.ecc.ssa import point_from_bip340pub_key_var
from ecc.exceptions import EccValueError
from ecc.hashes import tagged_hash
from typing_extensions import override

from bip32_descriptors.bip32.bip32 import (
    _derive,
    _xpub_from_xprv,
    fingerprint,
    key_data_from_bip32_key,
)
from bip32_descriptors.bip32.der_path import (
    _HARDENING,
    HARDENED_OFFSET,
    _int_from_digits,
)
from bip32_descriptors.bip32.key_origin import BIP32KeyOrigin
from bip32_descriptors.descriptors import miniscript
from bip32_descriptors.descriptors.key_expression import (
    _PRINTED_PRV_KEYS,
    KeyExpression,
    PrvKeys,
    _assert_index_range,
    _assert_multipath_keys,
    _assert_musig_allowed,
    _assert_network,
    _assert_prv_keys,
    _derived_once,
    _expression,
    _offered_signature,
    _one_hardening,
    _parse_key,
    _read_multipath_keys,
    _read_split,
    _split_arguments,
    _split_function,
    _split_unpaired_arguments,
    _steps_compared,
    _steps_set_aside,
)
from bip32_descriptors.descriptors.miniscript import (
    _HEX,
    _PRINTED_PREIMAGES,
    Miniscript,
    Preimages,
    SpendContext,
    _assert_sane,
    _has_raw_key_hash,
    _read_unclosed_multisig_keys,
    _script_number,
    _tree_eval,
)
from bip32_descriptors.descriptors.miniscript import (
    from_script as _miniscript_from_script,
)
from bip32_descriptors.descriptors.miniscript import parse as _parse_miniscript

__all__ = [
    "AddrDescriptor",
    "ComboDescriptor",
    "Descriptor",
    "DescriptorLeaf",
    "DescriptorTree",
    "Expansion",
    "MiniscriptDescriptor",
    "MultiA",
    "MultiDescriptor",
    "PkDescriptor",
    "PkhDescriptor",
    "Provider",
    "RawDescriptor",
    "RawLeaf",
    "RawNode",
    "RawPkhDescriptor",
    "RawTrDescriptor",
    "ShDescriptor",
    "TrDescriptor",
    "WpkhDescriptor",
    "WshDescriptor",
    "add_checksum",
    "at_index",
    "checksum",
    "derived_origin",
    "from_address",
    "infer_descriptor",
    "multipath_descriptors",
    "normalized",
    "parse",
    "private_string",
    "strip_checksum",
    "wallet_policy",
    "wallet_policy_address",
    "wallet_policy_descriptor",
]

INPUT_CHARSET = "0123456789()[],'/*abcdefgh@:$%{}IJKLMNOPQRSTUVWXYZ&+-.;<=>?!^_|~ijklmnopqrstuvwxyzABCDEFGH`#\"\\ "
CHECKSUM_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
GENERATOR = [0xF5DEE51989, 0xA9FDCA3312, 0x1BAB10E32D, 0x3706B1677A, 0x644D626FFD]

# a digit for every character, built once: `char not in INPUT_CHARSET`
# and `INPUT_CHARSET.find(char)` were each a scan of all 92 characters,
# one to validate and one to find the index. -1 rather than None keeps
# the lookup a plain int and doubles as the validity check, since a
# digit is never negative
_INPUT_INDEX = {c: i for i, c in enumerate(INPUT_CHARSET)}


def _pub_key_data(sec: bytes, network: str) -> PubKeyData:
    """Return the parsed public key an address or a script is built from.

    check_validity=False: `key_expression` proves every KEY expression's
    key a point of the curve when it parses one, which is more than
    `assert_valid` reads off it (issue btclib-org/btclib#1188).
    """
    return PubKeyData(sec, network, check_validity=False)


def __descsum_polymod(symbols: list[int]) -> int:
    """Compute the descriptor checksum polymod."""
    chk = 1
    for value in symbols:
        top = chk >> 35
        chk = (chk & 0x7FFFFFFFF) << 5 ^ value
        for i in range(5):
            chk ^= GENERATOR[i] if ((top >> i) & 1) else 0
    return chk


def __descsum_expand(descriptor_string: str) -> list[int]:
    """Perform the character to symbol expansion."""
    groups: list[int] = []
    symbols: list[int] = []
    for char in descriptor_string:
        index = _INPUT_INDEX.get(char, -1)
        if index == -1:
            raise BTClibValueError(f"invalid descriptor character: {char!r}")
        symbols.append(index & 31)
        groups.append(index >> 5)
        if len(groups) == 3:
            symbols.append(groups[0] * 9 + groups[1] * 3 + groups[2])
            groups = []
    if len(groups) == 1:
        symbols.append(groups[0])
    elif len(groups) == 2:
        symbols.append(groups[0] * 3 + groups[1])
    return symbols


def checksum(descriptor: str) -> str:
    """Compute the descriptor checksum."""
    symbols = [*__descsum_expand(descriptor), 0, 0, 0, 0, 0, 0, 0, 0]
    polymod = __descsum_polymod(symbols) ^ 1
    return "".join(CHECKSUM_CHARSET[(polymod >> (5 * (7 - i))) & 31] for i in range(8))


def strip_checksum(descriptor: str) -> str:
    """Return the descriptor without its checksum, verifying a present one.

    A descriptor without one comes back unchanged: the checksum is
    optional in the language, and only some of Bitcoin Core's RPCs
    require it. What is never accepted is a checksum that does not match,
    which is what the eight characters are there for.
    """
    body, separator, given_checksum = descriptor.partition("#")
    if "#" in given_checksum:
        position = len(body) + 1 + given_checksum.index("#")
        raise BTClibValueError(
            f"more than one '#' in the descriptor at position {position}"
        )
    # computed before the comparison, and whether or not there is one to
    # compare against: it is also what refuses a character outside
    # INPUT_CHARSET, which is an error in a descriptor with no checksum
    expected = checksum(body)
    if separator and given_checksum != expected:
        # neither checksum is echoed. What follows the '#' is the rest of
        # the descriptor where the '#' is a stray one, and the right
        # checksum confirms a guess at a key mistyped in the descriptor
        raise BTClibValueError("invalid descriptor checksum")
    return body


def add_checksum(descriptor: str) -> str:
    """Return the descriptor with its checksum, verifying a present one."""
    body = strip_checksum(descriptor)
    return f"{body}#{checksum(body)}"


def from_address(address: str) -> str:
    """Return the addr() descriptor of the address, checksummed."""
    return add_checksum(f"addr({address})")


# the tapscript leaf version, which is the only one a BIP386 tree has
_TAPSCRIPT_LEAF_VERSION = 0xC0

# where a SCRIPT expression sits. BIP381 to BIP386 give each function a
# position rule -- sh() is top level only, wpkh() is top level or inside
# sh(), and so on -- so the context is an argument of the parser, and
# these strings are what its error messages say
_TOP = "top level"
_P2SH = "sh()"
_P2WSH = "wsh()"
_P2TR = "tr()"

# where a miniscript may be written, and which of BIP379's two contexts
# that position is: inside wsh() and inside a tr() leaf, and nowhere else,
# which is the BIP's own "only valid in wsh() and tr() contexts". The two
# dialects differ in more than their keys, so the position is what picks
# between them rather than something a caller passes
_MINISCRIPT_CONTEXTS = {_P2WSH: miniscript.P2WSH, _P2TR: miniscript.TAPSCRIPT}

# BIP387's own bound on the keys of a multi_a(): the satisfaction puts one
# stack element per key, and a script whose spend would push more than the
# 1000 elements BIP342 allows is one nobody can spend
_MAX_MULTI_A_KEYS = 999

# the keys a multi() or sortedmulti() may hold as a bare output script:
# Bitcoin Core's IsStandard refuses a bare multisig of more, and its
# descriptor parser refuses a top-level multi() of more
_MAX_BARE_MULTISIG_KEYS = 3

# the two functions BIP387 allows inside tr() and nowhere else. Not in
# _PARSERS with the SCRIPT expressions: what they parse to is a leaf of a
# script tree and not a descriptor, so `_parse_leaf` reads them and this
# is what refuses them anywhere a SCRIPT expression is expected
_TREE_FUNCTIONS = ("multi_a", "sortedmulti_a")

# the two functions that name a tree node whose script, or whose subtree,
# is not a descriptor's to say. No BIP specifies them: Bitcoin Core's
# bitcoin/bitcoin#30243 does, and the draft BIP of bitcoin/bips#1721
# specifies rawnode() too. They belong inside tr() only for the reason the
# two above do
_RAW_TREE_FUNCTIONS = ("rawnode", "rawleaf")

# the bytes of a tree node's hash and of the hash160 a p2pkh script holds
_NODE_HASH_SIZE = 32
_KEY_HASH_SIZE = 20
# rawleaf() takes a script and a leaf version of one byte
_RAWLEAF_ARGUMENTS = 2
_LEAF_VERSION_DIGITS = 2

_THRESHOLD = re.compile(r"[0-9]+")
# a multipath step. A text that `parse` has read, each step on its first
# path, holds no "<" or ">" but in one, as a whole element of a key's path
_MULTIPATH_STEP = re.compile(r"<[^<>]*>")
# a key with such a step, from the "(" or "," before it to the next one
# that ends it. A musig() path follows a ")" and is no key's
_KEY_WITH_STEP = re.compile(r"(?<=[(,])[^(),{}]*<[^<>]*>[^(),{}]*")


def _multipath_steps(text: str) -> list[tuple[int, int, list[str]]]:
    """Return the ``<a;b>`` steps of `text`: start, end and items of each.

    `text` is one `parse` has read whole, so every step it holds is a legal
    one of a key.
    """
    return [
        (match.start(), match.end(), match[0][1:-1].split(";"))
        for match in _MULTIPATH_STEP.finditer(text)
    ]


@dataclass(frozen=True)
class MultiA:
    """``multi_a(k,KEY,...)`` or ``sortedmulti_a(k,KEY,...)``: a leaf, BIP387.

    A leaf of a ``tr()`` script tree, beside the bare `KeyExpression` that
    is a ``pk()`` leaf, and not a `Descriptor`: BIP387 allows these two
    functions inside ``tr()`` and nowhere else, so no output pays to one
    of them -- what an output pays to is the ``tr()`` that commits to it
    as one of its tapscripts.
    """

    threshold: int
    keys: tuple[KeyExpression, ...]
    # the ordering that is the whole difference between the two functions,
    # as BIP67 is for sortedmulti(): the keys of a sortedmulti_a() are
    # sorted in the script, so the participants need not agree on an order
    # to agree on an address
    sort: bool = False

    def __post_init__(self) -> None:
        """Refuse a field of the wrong type, and a k or an n `parse` refuses.

        A threshold of none or of more keys than there are, or more keys
        than BIP387 allows, describes a script nobody can spend.
        """
        if not is_integer(self.threshold):
            err_msg = f"invalid threshold type: {type(self.threshold).__name__}"
            raise BTClibTypeError(err_msg)
        assert_type(self.keys, tuple, "keys")
        for key in self.keys:
            assert_type(key, KeyExpression, "key")
        assert_type(self.sort, bool, "sort")
        name = "sortedmulti_a" if self.sort else "multi_a"
        if not 1 <= self.threshold <= len(self.keys):
            raise BTClibValueError(f"invalid k in k-of-n {name}: {self.threshold}")
        if len(self.keys) > _MAX_MULTI_A_KEYS:
            raise BTClibValueError(f"invalid n in k-of-n {name}: {len(self.keys)}")

    @override
    def __str__(self) -> str:
        """Return the ``multi_a()`` or ``sortedmulti_a()`` leaf as text."""
        name = "sortedmulti_a" if self.sort else "multi_a"
        return _expression(name, str(self.threshold), *map(str, self.keys))

    def _pub_keys(
        self, index: int, network: str, prv_keys: PrvKeys | None
    ) -> list[bytes]:
        """Return the SEC keys in the order the script holds them.

        Sorted on the x-only bytes and not on these: what a tapscript
        carries is 32 bytes per key, and the 33-byte form adds to them a
        prefix saying the parity of y -- so sorting the SEC bytes would
        order the keys by that parity first, and a ``sortedmulti_a()``
        naming a key by its WIF would get another script than the same
        key written x-only.
        """
        pub_keys = [key.sec(index, network, prv_keys) for key in self.keys]
        key_x = operator.itemgetter(slice(1, None))
        return sorted(pub_keys, key=key_x) if self.sort else pub_keys

    def _script(self, index: int, network: str, prv_keys: PrvKeys | None) -> ScriptList:
        """Return the tapscript of BIP387: a CHECKSIG, then CHECKSIGADDs.

        The threshold is pushed as OP_1 to OP_16 where an op code means
        it and as the number itself above that, which is what BIP387 says
        and the one place the two spellings differ.
        """
        pub_keys = self._pub_keys(index, network, prv_keys)
        script: ScriptList = [pub_keys[0][1:], "OP_CHECKSIG"]
        for pub_key in pub_keys[1:]:
            script += [pub_key[1:], "OP_CHECKSIGADD"]
        threshold = op_int(self.threshold) if self.threshold <= 16 else self.threshold
        return [*script, threshold, "OP_NUMEQUAL"]

    def _stack(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        network: str,
        prv_keys: PrvKeys | None,
    ) -> list[bytes] | None:
        """Return one element per key, or None where the keys have not signed.

        `threshold` of the elements are signatures and the rest the empty
        push. A signature beyond the threshold is not spare, which is the
        first difference from `multi()`: OP_CHECKSIGADD counts every
        signature that verifies and OP_NUMEQUAL compares the count with
        the threshold, where OP_CHECKMULTISIG stops at the signatures it
        was built to pop.

        The elements go in the reverse of the key order, which is the
        second: the signature of the first key is popped first, so it is
        the last element of the witness and the top of the stack. Bitcoin
        Core's satisfier says the same in a comment of its own.

        None rather than an error where fewer keys than the threshold have
        signed: a leaf is one spending path of a tree, and which of them
        the signatures at hand open is the question `TrDescriptor` walks
        the leaves to answer.
        """
        offered = [
            _offered_signature(signatures, sec, x_only=True)
            for sec in self._pub_keys(index, network, prv_keys)
        ]
        if sum(signature is not None for signature in offered) < self.threshold:
            return None
        stack: list[bytes] = []
        signed = 0
        for signature in offered:
            if signature is None or signed == self.threshold:
                stack.append(b"")
            else:
                stack.append(signature)
                signed += 1
        stack.reverse()
        return stack


@dataclass(frozen=True)
class RawLeaf:
    """``rawleaf(HEX,VER)`` or ``raw(HEX)``: a tree leaf written as its bytes.

    A leaf of a ``tr()`` script tree that says which script and which leaf
    version the output key commits to, and nothing about the keys in it. No
    BIP specifies ``rawleaf()``: Bitcoin Core's bitcoin/bitcoin#30243 does, and
    the draft BIP of bitcoin/bips#1721 specifies ``raw()`` there, a leaf
    of version c0. `bare` says the leaf was written the second way, which
    is a different text and a different checksum for the same output.

    The version is printed as two hex digits, whereas PR 30243 prints it
    with ``%x``, and its own parser refuses the one digit that prints for a
    version below 0x10.
    """

    script: bytes
    version: int = _TAPSCRIPT_LEAF_VERSION
    bare: bool = field(default=False, kw_only=True)

    def __post_init__(self) -> None:
        """Refuse a version `parse` refuses, and a ``raw()`` leaf not of c0.

        A version is one byte, and an even one: the low bit of a control
        block's first byte is the parity of the output key.
        """
        assert_type(self.script, bytes, "leaf script")
        if not is_integer(self.version):
            err_msg = f"invalid leaf version type: {type(self.version).__name__}"
            raise BTClibTypeError(err_msg)
        assert_type(self.bare, bool, "bare")
        if not 0 <= self.version <= 0xFF or self.version & 1:
            raise BTClibValueError("Leaf Version is invalid")
        if self.bare and self.version != _TAPSCRIPT_LEAF_VERSION:
            raise BTClibValueError("a raw() leaf has the leaf version c0")

    @override
    def __str__(self) -> str:
        """Return the leaf as ``raw(HEX)``, or as ``rawleaf(HEX,VER)``."""
        if self.bare:
            return _expression("raw", self.script.hex())
        return _expression("rawleaf", self.script.hex(), f"{self.version:02x}")


@dataclass(frozen=True)
class RawNode:
    """``rawnode(HEX)``: a node of a ``tr()`` tree known by its hash alone.

    A branch, or the whole tree, whose subtree the descriptor does not
    hold: the output key commits to it, and no script of it can be spent
    from here. No BIP specifies it: Bitcoin Core's bitcoin/bitcoin#30243
    does, and so does the draft BIP of bitcoin/bips#1721.
    A hash that is a leaf's own is still a node here, the descriptor
    having no script to show for it.
    """

    digest: bytes

    def __post_init__(self) -> None:
        """Refuse a hash that is not bytes; `_tree_walk` refuses its size."""
        assert_type(self.digest, bytes, "node hash")

    @override
    def __str__(self) -> str:
        """Return the node as ``rawnode(HEX)``."""
        return _expression("rawnode", self.digest.hex())


def _tree_expression(tree: DescriptorTree) -> str:
    """Return a BIP386 TREE as text: a leaf, or two subtrees in braces."""
    if isinstance(tree, tuple):
        return f"{{{_tree_expression(tree[0])},{_tree_expression(tree[1])}}}"
    if isinstance(tree, (MultiA, Miniscript, RawLeaf, RawNode)):
        return str(tree)
    return _expression("pk", str(tree))


# A tr() script tree. A leaf is the KEY expression a `pk()` leaf is, the
# `MultiA` of BIP387's two functions, a miniscript or a `RawLeaf`; a node
# known by its hash is a `RawNode`; a branch is a tuple, which is what
# tells a branch from a leaf. The leaves hold KEY expressions and not
# scripts because a ranged descriptor has no script until an index is
# given
DescriptorLeaf = KeyExpression | MultiA | Miniscript | RawLeaf
#: A `DescriptorLeaf`, a `RawNode`, or a branch, a tuple of two subtrees.
DescriptorTree = DescriptorLeaf | RawNode | tuple["DescriptorTree", "DescriptorTree"]
# what a tree holds where it is not a branch
_TREE_NODE_TYPES = (KeyExpression, MultiA, Miniscript, RawLeaf, RawNode)


def _leaf_keys(leaf: DescriptorLeaf) -> tuple[KeyExpression, ...]:
    """Return the KEY expressions of one leaf, in the order it names them."""
    if isinstance(leaf, MultiA):
        return leaf.keys
    if isinstance(leaf, Miniscript):
        return leaf.key_expressions
    if isinstance(leaf, RawLeaf):
        return ()
    return (leaf,)


def _tree_leaves(tree: DescriptorTree) -> tuple[DescriptorLeaf, ...]:
    """Return the leaves left to right, which is the order they are numbered.

    `_tree_walk` visits the left subtree before the right one, so the n-th
    leaf here is the n-th leaf there. A `RawNode` is no leaf and is not
    numbered.
    """
    if isinstance(tree, tuple):
        return _tree_leaves(tree[0]) + _tree_leaves(tree[1])
    if isinstance(tree, RawNode):
        return ()
    return (tree,)


def _has_raw_node(tree: DescriptorTree) -> bool:
    """Return True where a subtree of the tree is known by its hash alone."""
    if isinstance(tree, tuple):
        return _has_raw_node(tree[0]) or _has_raw_node(tree[1])
    return isinstance(tree, RawNode)


def _tree_keys(tree: DescriptorTree) -> tuple[KeyExpression, ...]:
    keys: tuple[KeyExpression, ...] = ()
    for leaf in _tree_leaves(tree):
        keys += _leaf_keys(leaf)
    return keys


def _leaf_script(
    leaf: DescriptorLeaf, index: int, network: str, prv_keys: PrvKeys | None
) -> bytes:
    """Return the tapscript of one leaf."""
    if isinstance(leaf, MultiA):
        return serialize(leaf._script(index, network, prv_keys))
    if isinstance(leaf, Miniscript):
        return leaf.script(index, network, prv_keys)
    if isinstance(leaf, RawLeaf):
        return leaf.script
    return serialize([leaf.sec(index, network, prv_keys)[1:], "OP_CHECKSIG"])


def _leaf_version(leaf: DescriptorLeaf) -> int:
    """Return the leaf version of one leaf, c0 unless a `RawLeaf` says."""
    return leaf.version if isinstance(leaf, RawLeaf) else _TAPSCRIPT_LEAF_VERSION


def _assert_tree(tree: DescriptorTree) -> None:
    """Refuse a node of the wrong type, and a tree deeper than MAX_TREE_DEPTH.

    A leaf below that depth has no control block to be spent with, and
    `parse` stops there too. The bound also keeps the recursive walks of a
    tree inside Python's recursion limit, so this one keeps a stack of its
    own.

    A miniscript leaf is refused where any of its nodes is not of the
    tapscript context. Each node writes its keys in its own context, and
    BIP342 reads a 33-byte key as an unknown public key type, which any
    non-empty signature satisfies.
    """
    stack: list[tuple[object, int]] = [(tree, 0)]
    while stack:
        node, depth = stack.pop()
        if isinstance(node, Miniscript):
            if node.context != miniscript.TAPSCRIPT:
                # a hand-built context is any value, so only the library's
                # own is named, a refusal echoing no value it was given
                known = node.context == miniscript.P2WSH
                context = miniscript.P2WSH if known else "another context"
                err_msg = f"not a tapscript node: {node.fragment} in {context}"
                raise BTClibValueError(err_msg)
            stack += [(sub, depth) for sub in node.subs]
            continue
        if not isinstance(node, tuple):
            assert_type(node, _TREE_NODE_TYPES, "script tree node")
            continue
        if len(node) != 2:
            err_msg = f"a script tree branch takes two subtrees, {len(node)} given"
            raise BTClibTypeError(err_msg)
        if depth == MAX_TREE_DEPTH:
            raise BTClibValueError(f"script tree deeper than {MAX_TREE_DEPTH}")
        stack += [(node[1], depth + 1), (node[0], depth + 1)]


@dataclass(frozen=True)
class _TreeLeaf:
    """One leaf of a tree walk, with what a control block proves it by."""

    depth: int
    version: int
    script: bytes
    # the hashes of the siblings from the leaf up to the root
    path: bytes


def _tree_walk(
    tree: DescriptorTree,
    depth: int,
    index: int,
    network: str,
    prv_keys: PrvKeys | None,
) -> tuple[list[_TreeLeaf], bytes]:
    """Return the leaves of a tree left to right, and its merkle root.

    BIP341's `taproot_tree_helper`, which `btclib.script.taproot.tree_helper`
    is, taking a `RawNode` as a hash with no leaf below it. The leaves are
    in the order `_tree_leaves` numbers them, and the depth is the number
    of branches above each.

    A branch puts its leaves one level below itself, and a leaf's depth is
    the length of the merkle path proving it.
    """
    if isinstance(tree, tuple):
        left, left_hash = _tree_walk(tree[0], depth + 1, index, network, prv_keys)
        right, right_hash = _tree_walk(tree[1], depth + 1, index, network, prv_keys)
        leaves = [replace(leaf, path=leaf.path + right_hash) for leaf in left]
        leaves += [replace(leaf, path=leaf.path + left_hash) for leaf in right]
        low, high = sorted((left_hash, right_hash))
        return leaves, tagged_hash(b"TapBranch", low + high)
    if isinstance(tree, RawNode):
        if len(tree.digest) != _NODE_HASH_SIZE:
            raise BTClibValueError("256 bits digest expected")
        return [], tree.digest
    script = _leaf_script(tree, index, network, prv_keys)
    version = _leaf_version(tree)
    return [_TreeLeaf(depth, version, script, b"")], leaf_hash(version, script)


def _leaf_stack(
    leaf: DescriptorLeaf,
    signatures: Mapping[bytes, bytes],
    index: int,
    network: str,
    prv_keys: PrvKeys | None,
    spend: SpendContext | None,
) -> list[bytes] | None:
    """Return what satisfies one leaf, None where the signatures do not.

    None rather than a refusal, for a miniscript leaf as for the others:
    which leaf the signatures at hand open is the question the caller is
    walking the tree to answer, so a leaf they do not open is an answer
    and not an error -- including one whose branches want a preimage or a
    lock time this spend does not have.
    """
    if isinstance(leaf, MultiA):
        return leaf._stack(signatures, index, network, prv_keys)
    if isinstance(leaf, Miniscript):
        offered = cast("Mapping[Octets, Octets]", signatures)
        try:
            return leaf.satisfy(offered, spend, index, network, prv_keys)
        except BTClibValueError:
            return None
    if isinstance(leaf, RawLeaf):
        # bytes name no key, so no signature opens the leaf
        return None
    signature = _offered_signature(
        signatures, leaf.sec(index, network, prv_keys), x_only=True
    )
    return None if signature is None else [signature]


def _required_signature(signatures: Mapping[bytes, bytes], sec: bytes) -> bytes:
    """Return the signature made with a public key, refusing where none is.

    The key is named in the error: it is public by construction, and
    which of a descriptor's keys has not signed is the whole content of
    the refusal.
    """
    signature = _offered_signature(signatures, sec, x_only=False)
    if signature is None:
        raise BTClibValueError(f"no signature for public key {sec.hex()}")
    return signature


def _derived_origin(key: KeyExpression, index: int) -> BIP32KeyOrigin:
    """`derived_origin`, with nothing checked."""
    der_path = [*key.der_path]
    if key.wildcard is not None:
        der_path.append(key.wildcard + index)
    if key.origin is not None:
        return BIP32KeyOrigin(
            key.origin.master_fingerprint, [*key.origin.der_path, *der_path]
        )
    if key.pub_key is not None:
        return BIP32KeyOrigin(hash160(key.pub_key)[:4], der_path)
    return BIP32KeyOrigin(fingerprint(key.xkey), der_path)


def derived_origin(key: KeyExpression, index: int = 0) -> BIP32KeyOrigin:
    """Return the origin of the key at `index`.

    `KeyExpression.origin` is the path down to the extended key the
    descriptor holds, and what BIP174 carries is the path down to the
    key itself: the derivation the descriptor then does, the wildcard
    step at `index` included, appended to it. A signer given the shorter
    path would derive the wrong key from it.

    A key without an origin is its own master, as in Bitcoin Core's
    `ConstPubkeyProvider` and `BIP32PubkeyProvider`: a fixed key under
    the first four bytes of its hash160 with an empty path, an extended key
    under its own fingerprint with the derivation.

    An index outside 0 to 2**31 - 1 is refused, whether the key is ranged
    or not, as `KeyExpression.sec` refuses it. So is a ``musig()`` key:
    BIP373 gives an aggregate the fingerprint of BIP328's synthetic xpub,
    and computing the aggregate takes the network and the ``prv_keys``
    that `KeyExpression.aggregate` takes, which this function does not.
    """
    assert_type(key, KeyExpression, "key")
    _assert_index_range(index)
    if key.is_aggregate:
        raise BTClibValueError("no origin of its own for an aggregate key")
    return _derived_origin(key, index)


def _aggregate_origin(
    key: KeyExpression, index: int, network: str, prv_keys: PrvKeys | None
) -> BIP32KeyOrigin:
    """Return where an aggregate key, derived or not, came from.

    BIP373's answer to "how does this key relate to the aggregate the
    participants make": the derivation path, under the fingerprint of
    BIP328's synthetic xpub, which is hash160 of the aggregate key -- and
    which is what lets a signer recognize the field as BIP328 derivation
    without a `PSBT_GLOBAL_XPUB` naming that synthetic key.
    btclib-wallet's `psbt.musig2` reads it back exactly that way.

    The path is empty where the expression derives nothing, the key in the
    script being the aggregate itself: Bitcoin Core's `MuSigPubkeyProvider`
    gives that key the same fingerprint.
    """
    der_path = [*key.der_path]
    if key.wildcard is not None:
        der_path.append(key.wildcard + index)
    aggregate = key.aggregate(index, network, prv_keys)
    return BIP32KeyOrigin(hash160(aggregate)[:4], der_path)


def _taproot_derivations(
    keys: Sequence[KeyExpression],
    leaf_hashes: Mapping[bytes, list[bytes]],
    index: int,
    network: str,
    prv_keys: PrvKeys | None,
) -> dict[bytes, tuple[list[bytes], BIP32KeyOrigin]]:
    """Return BIP371's derivation field for a set of taproot key expressions.

    Keyed by the 32 bytes a tapscript holds, and carrying the tapleaf hash
    of every leaf the key appears in, which the caller has worked out: none
    for a key that is only the internal one, and one per leaf otherwise.

    A ``musig()`` puts two kinds of entry here, both of which BIP373 asks
    the Updater for: the key in the script, under the origin
    `_aggregate_origin` computes, and each participant -- the second being
    how a signer finds out that one of the keys it holds is in this group
    at all. A participant's entry carries the leaves where its key is a
    plain key and the leaves of every group it is in.

    Bitcoin Core gives a participant the hash of every leaf of the tree
    instead, because `SignMuSig2` in its `src/script/sign.cpp`
    (bitcoin/bitcoin@f0de87f040) fills in the participants of every
    aggregate for each leaf key it cannot sign for. Here an entry names
    only the leaves its key can sign.

    Where one key is spelled more than once, an explicit origin beats one
    `_derived_origin` makes up, and then a plain key's origin beats a
    participant's. Where those ranks tie, the first spelling's origin is
    the entry's, inside one fragment too, as in `Descriptor._hd_key_paths`.
    Bitcoin Core keeps the entry `Descriptor.provider` keeps, which inside
    one fragment is the later of two explicit origins.

    Core's later one wins as a side effect of the ``insert_or_assign`` that
    bitcoin/bitcoin@b42f7fade0 put in `OriginPubkeyProvider::GetPubKey`.
    That commit fixes the origin a participant got from two different
    explicit origins, but neither it nor its pull request says which should
    win, and no test of Core's spells one key with two different explicit
    origins.
    """
    origins: dict[bytes, tuple[tuple[bool, bool], BIP32KeyOrigin]] = {}
    hashes: dict[bytes, list[bytes]] = {}

    def add(
        x_only: bytes, rank: tuple[bool, bool], origin: BIP32KeyOrigin, group: bytes
    ) -> None:
        if x_only not in origins or rank > origins[x_only][0]:
            origins[x_only] = (rank, origin)
        entry = hashes.setdefault(x_only, list(leaf_hashes.get(x_only, [])))
        for hash_ in leaf_hashes.get(group, []):
            if hash_ not in entry:
                entry.append(hash_)

    for key in keys:
        x_only = key.sec(index, network, prv_keys)[1:]
        origin = (
            _aggregate_origin(key, index, network, prv_keys)
            if key.is_aggregate
            else _derived_origin(key, index)
        )
        add(x_only, (key.origin is not None, True), origin, b"")
        for participant in key.participants:
            add(
                participant.sec(index, network, prv_keys)[1:],
                (participant.origin is not None, False),
                _derived_origin(participant, index),
                x_only,
            )
    return {x_only: (hashes[x_only], origin) for x_only, (_, origin) in origins.items()}


def _musig2_participants(
    keys: Sequence[KeyExpression],
    index: int,
    network: str,
    prv_keys: PrvKeys | None,
) -> dict[bytes, list[bytes]]:
    """Return BIP373's participant field: each aggregate key's own list.

    Keyed by the 33-byte aggregate key rather than by what the script
    holds, which BIP373 requires and which is the whole use of the field:
    the participants are what a signer checks its own keys against, and a
    child of the aggregate is a key the same list answers for.
    """
    return {
        key.aggregate(index, network, prv_keys): key.participant_keys(
            index, network, prv_keys
        )
        for key in keys
        if key.is_aggregate
    }


@dataclass(frozen=True)
class Provider:
    """The keys and scripts a caller knows, for `infer_descriptor` to read.

    Bitcoin Core's `SigningProvider` without the private keys, at
    bitcoin/bitcoin@f0de87f040 (the v32.1 tag). `Descriptor.provider` is
    what a descriptor expanded at an index tells one, and `merged` joins
    several.

    `keys` maps a SEC public key to the origin it derives from, None where
    it has none. `scripts` holds the scripts a ``sh()`` or a ``wsh()``
    embeds, found by their hash160. `trees` maps the x-only output key of
    a ``tr()`` to its x-only internal key, its merkle root (empty where it
    has no tree) and each leaf script with its leaf version, keyed by the
    control block that proves it.
    """

    keys: Mapping[bytes, BIP32KeyOrigin | None] = field(default_factory=dict)
    scripts: tuple[bytes, ...] = ()
    trees: Mapping[bytes, tuple[bytes, bytes, Mapping[bytes, tuple[bytes, int]]]] = (
        field(default_factory=dict)
    )

    def merged(self, other: Provider) -> Provider:
        """Return both providers as one, this one's entry winning a clash.

        Core's `FlatSigningProvider::Merge`, which keeps what it already
        holds. A key this one knows with no origin takes the other's.
        """
        assert_type(other, Provider, "other")
        keys = {**self.keys, **other.keys} | {
            key: origin for key, origin in self.keys.items() if origin is not None
        }
        return Provider(
            keys=keys,
            scripts=tuple(dict.fromkeys(self.scripts + other.scripts)),
            trees={**other.trees, **self.trees},
        )


@dataclass(frozen=True)
class Expansion:
    """What a descriptor expanded at an index tells a psbt's Updater.

    `Descriptor.expansion` builds it, and BIP174's Updater writes it into a
    psbt: each field is named after the field of an input or an output map
    it fills, and holds what that field takes. `Provider` is the expansion
    `infer_descriptor` reads instead.

    `hd_key_paths` maps the SEC public key of each key to the origin it
    derives from. It is empty for a ``tr()`` and a ``rawtr()``, whose keys
    BIP371 files by their x-only form in `taproot_hd_key_paths`, each with
    the tapleaf hash of every leaf it is in. `redeem_script` is the script
    a ``sh()`` embeds and `witness_script` the one a ``wsh()`` embeds,
    empty where nothing does.

    `taproot_internal_key`, `taproot_merkle_root`, `taproot_leaf_scripts`
    and `taproot_tree` are a ``tr()``'s: its x-only internal key, the root
    its output key commits to, every leaf script with its leaf version
    keyed by the control block that proves it, and every leaf with its
    depth, as BIP371's PSBT_OUT_TAP_TREE lists them. A ``tr(KEY)`` has an
    empty root and an empty tree, so the two are None for every other
    descriptor, a ``rawtr()`` included, whose internal key is empty.
    `musig2_participant_pub_keys` maps each ``musig()`` aggregate key to
    its participants, BIP373's field.

    The tree is None for a ``tr()`` with a ``rawnode()`` too, whose whole
    tree is not known. That expansion describes an input and not an output:
    its internal key does not tweak to the output key without the tree, so
    an output's Updater has to refuse it rather than write the key alone.
    """

    hd_key_paths: Mapping[bytes, BIP32KeyOrigin] = field(default_factory=dict)
    redeem_script: bytes = b""
    witness_script: bytes = b""
    taproot_internal_key: bytes = b""
    taproot_merkle_root: bytes | None = None
    taproot_leaf_scripts: Mapping[bytes, tuple[bytes, int]] = field(
        default_factory=dict
    )
    taproot_tree: list[tuple[int, int, bytes]] | None = None
    taproot_hd_key_paths: Mapping[bytes, tuple[list[bytes], BIP32KeyOrigin]] = field(
        default_factory=dict
    )
    musig2_participant_pub_keys: Mapping[bytes, list[bytes]] = field(
        default_factory=dict
    )


@dataclass(frozen=True, kw_only=True)
class Descriptor(ABC):
    """A parsed output descriptor: the scripts it describes, on demand.

    Keyword-only so that the fragments below can add positional fields of
    their own: a dataclass field with a default followed by one without
    is a TypeError, and `network` has a default.
    """

    network: str = "mainnet"

    def __post_init__(self) -> None:
        # every fragment's generated `__init__` calls this, none of them
        # defining its own `__init__`. A name that is not a string is
        # refused, as a field of the wrong type is in every fragment. A
        # string no network answers to is not: the parse path already
        # refuses it (`validated_network_name`, above), so what is left to
        # the direct constructor is the same tolerance rule issue
        # btclib-org/btclib#216 kept for everything else. The name is
        # normalized here because without that, two spellings of one
        # network build descriptors that are neither equal nor hashed
        # alike, `network` comparing and hashing as the plain field it is
        assert_type(self.network, str, "network")
        object.__setattr__(self, "network", normalized_network_name(self.network))

    @property
    @abstractmethod
    def key_expressions(self) -> tuple[KeyExpression, ...]:
        """Return every KEY expression the descriptor holds."""

    @abstractmethod
    @override
    def __str__(self) -> str:
        """Return the descriptor as text, without its checksum.

        Public by construction, `parse` having kept no private material
        to write: the same guarantee Bitcoin Core's `ToString` gives by
        holding only a neutered key, where its `ToPrivateString` has to
        be handed the keys back. `private_string` is that one, and is the
        one place this writes a private spelling.

        Without the checksum because a fragment inside another one is
        written by this very method, and a checksum there would be part
        of the outer descriptor's text. `add_checksum(str(descriptor))`
        is the checksummed form: Core's `ToString`, `ToStringHelper`
        writing none, and HWI's and Electrum's `to_string`.

        Two things are normalized rather than echoed, both because the
        parse keeps the meaning and not the characters: a WIF and an
        uppercase hex key come back as lowercase hex, and an xprv as its
        xpub. The hardening symbol is not one of them -- `KeyExpression`
        remembers which of `h` and `'` was read, the two spellings being
        two checksums.
        """

    @abstractmethod
    def _scripts(self, index: int, prv_keys: PrvKeys | None) -> list[bytes]:
        """Return the scriptPubKey bytes at `index`, in Bitcoin Core's order."""

    @property
    def is_ranged(self) -> bool:
        """Return True if the descriptor describes a range of scripts."""
        return any(key.is_ranged for key in self.key_expressions)

    def _assert_index(self, index: int) -> None:
        """Refuse a non-integer or out-of-range index, or one with no script.

        `satisfy` asks the two questions `script_pub_keys` asks, and has
        to ask them first: a descriptor with no wildcard would otherwise
        be satisfied at an index where it has no script.
        """
        _assert_index_range(index)
        if index and not self.is_ranged:
            err_msg = f"not a ranged descriptor: no script at index {index}"
            raise BTClibValueError(err_msg)

    def script_pub_keys(
        self, index: int = 0, prv_keys: PrvKeys | None = None
    ) -> list[ScriptPubKey]:
        """Return the scripts the descriptor describes at `index`.

        A list because ``combo()`` is a set of scripts and not one
        script; every other fragment answers with exactly one.
        """
        _assert_prv_keys(prv_keys)
        self._assert_index(index)
        with _derived_once(prv_keys):
            return [
                ScriptPubKey(script, self.network)
                for script in self._scripts(index, prv_keys)
            ]

    def script_pub_key(
        self, index: int = 0, prv_keys: PrvKeys | None = None
    ) -> ScriptPubKey:
        """Return the one script the descriptor describes at `index`."""
        script_pub_keys = self.script_pub_keys(index, prv_keys)
        if len(script_pub_keys) != 1:
            err_msg = f"{len(script_pub_keys)} scripts: use script_pub_keys instead"
            raise BTClibValueError(err_msg)
        return script_pub_keys[0]

    def redeem_script(self, index: int = 0, prv_keys: PrvKeys | None = None) -> bytes:
        """Return the script that ``sh()`` or ``wsh()`` embeds this one as."""
        return self.script_pub_key(index, prv_keys).script

    def address(self, index: int = 0, prv_keys: PrvKeys | None = None) -> str:
        """Return the address of the script at `index`, if it has one."""
        return self.script_pub_key(index, prv_keys).address

    def addresses(self, index: int = 0, prv_keys: PrvKeys | None = None) -> list[str]:
        """Return the address of each script at `index`, empty where none."""
        return [
            script_pub_key.address
            for script_pub_key in self.script_pub_keys(index, prv_keys)
        ]

    def provider(self, index: int = 0, prv_keys: PrvKeys | None = None) -> Provider:
        """Return what the descriptor expanded at `index` tells a `Provider`.

        Bitcoin Core's `Expand`: each key with its origin, the script each
        ``sh()`` and ``wsh()`` embeds, the p2wpkh script of a ``combo()``
        of a compressed key, and the spend data of a ``tr()``.

        A key without an origin is its own master, as in Core: a fixed key
        under the first four bytes of its hash160, an extended key under
        its own fingerprint with the path it derives. Where one fragment
        spells a key twice, an origin the descriptor writes replaces the
        entry already there, and a made-up one does not; where two
        fragments spell it, the first one's entry stays. Core does both.
        """
        _assert_prv_keys(prv_keys)
        self._assert_index(index)
        keys: dict[bytes, BIP32KeyOrigin | None] = {}
        scripts: dict[bytes, None] = {}
        trees: dict[bytes, tuple[bytes, bytes, Mapping[bytes, tuple[bytes, int]]]] = {}
        with _derived_once(prv_keys):
            _expand(self, index, prv_keys, keys, scripts, trees)
        return Provider(keys, tuple(scripts), trees)

    def expand(
        self, index: int = 0, prv_keys: PrvKeys | None = None
    ) -> tuple[list[ScriptPubKey], Provider]:
        """Return the scripts and the provider at `index`, from one derivation.

        Each key is derived once. Bitcoin Core's `Descriptor::Expand`.
        Calling `script_pub_keys` and then `provider` gives the same answers
        and derives each key twice.
        """
        _assert_prv_keys(prv_keys)
        with _derived_once(prv_keys):
            return (
                self.script_pub_keys(index, prv_keys),
                self.provider(index, prv_keys),
            )

    def _stack(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> list[bytes]:
        """Return the elements that satisfy this fragment's own script.

        What ``sh()`` writes into its script_sig and what ``wsh()`` puts
        in its witness under the script: the same elements, only written
        somewhere else, which is why this is one method and not two.
        Answered by the fragments that are a script another one embeds
        -- ``pk``, ``pkh``, ``wpkh``, ``multi`` -- and refused by the
        rest. The grammar refuses those in an embedding position too, so
        what this answers is a descriptor built by hand.
        """
        err_msg = f"{type(self).__name__} is not a script another one embeds"
        raise BTClibValueError(err_msg)

    def satisfy(
        self,
        signatures: Mapping[Octets, Octets],
        index: int = 0,
        prv_keys: PrvKeys | None = None,
        spend: SpendContext | None = None,
    ) -> tuple[bytes, Witness]:
        """Return the script_sig and witness that spend the script at `index`.

        `signatures` maps a public key to the signature made with it,
        which is the shape btclib-wallet's `psbt.PsbtIn.partial_sigs` has.
        Keyed by key and not a sequence because the order the signatures
        go on the stack is the descriptor's own knowledge -- the key order
        of a ``multi()``, the sorted order of a ``sortedmulti()`` -- and a
        caller that had to know it would be building the script itself.

        Both halves come back and one of the two is always empty: a
        legacy script has no witness, and a native segwit one has the
        empty script_sig BIP141 requires.

        A signature short of what the script pops is an error and not a
        shorter answer. A 2-of-3 holding one signature is a psbt waiting
        for the second, btclib-wallet's `psbt.PsbtIn.partial_sigs` is where
        that state belongs, and bytes that do not spend would be a second
        and weaker spelling of it.

        `spend` is what a miniscript satisfaction reads beside the
        signatures -- hash preimages, and the lock times the transaction
        being built will carry -- and is ignored by every other fragment,
        none of which has a branch to choose or a preimage to look up. A
        `wsh()` holding a miniscript is the one shape that needs it, and
        it says so: without one it refuses the fragments that would have
        read it.
        """
        _assert_prv_keys(prv_keys)
        self._assert_index(index)
        return self._satisfy(
            {
                bytes_from_octets(key): bytes_from_octets(signature)
                for key, signature in signatures.items()
            },
            index,
            prv_keys,
            spend,
        )

    def _satisfy(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> tuple[bytes, Witness]:
        """Return the satisfaction, the mapping being already in bytes.

        The legacy answer -- the stack pushed into the script_sig, and
        no witness -- which is what ``pk()``, ``pkh()`` and ``multi()``
        are spent with; the fragments spent otherwise override it.
        Separate from `satisfy` so that a wrapper can satisfy its
        argument without normalizing the same mapping a second time.
        """
        return serialize(
            cast(ScriptList, self._stack(signatures, index, prv_keys, spend))
        ), Witness()

    def index_of(
        self,
        script_pub_key: Octets | ScriptPubKey,
        last_index: int = 999,
        prv_keys: PrvKeys | None = None,
    ) -> int | None:
        """Return the index whose script is this one, None where none is.

        What makes an output *this wallet's*, and the only thing that
        does: the script is derived and compared whole. A key origin whose
        fingerprint matches is not an answer -- four bytes of a hash160
        collide, and a psbt is written by whoever sends it, so an output
        marked as change on a fingerprint is an output a wallet may hand
        to somebody else believing it keeps it.

        The output is named however the caller holds it: the
        `ScriptPubKey` that `script_pub_key` returns, that script as
        bytes or as a hex-string, or the address it renders as -- "which
        index is this address" being the question a human has, and
        `ScriptPubKey.from_address` being what answers it. What is
        compared is the script in every case: an address is read for the
        script it encodes, and the network its prefix carries is not part
        of the answer, the same key paying to the same script on every
        chain.

        Anything else is a `BTClibTypeError`, and a string that names no
        output -- neither hex nor an address, the `""` that a script with
        no address renders as among them -- a `BTClibValueError`, because
        None is not "you passed the wrong thing" here: it is *this output
        is not this wallet's*, which is the answer a caller acts on to
        say that an address is somebody else's or that an output is not
        its own change (issue btclib-org/btclib#540).

        `last_index` bounds the search, both ends included, and is the
        caller's: how far ahead of its own gap limit a wallet is willing
        to look is a policy this module has no view on. A descriptor that
        is not ranged has one script and answers 0 or None.

        `last_index` is an integer, ranged descriptor or not, and a bool
        is refused: `True` would bound a ranged search at 1. A negative
        one is refused too, as it bounds no search: answering None for it
        would say the output is not this wallet's.
        """
        _assert_prv_keys(prv_keys)
        script = script_from_script_pub_key(script_pub_key)
        if not is_integer(last_index):
            raise BTClibTypeError(
                f"invalid last_index type: {type(last_index).__name__}"
            )
        if last_index < 0:
            raise BTClibValueError(f"negative last_index: {last_index}")
        last = last_index if self.is_ranged else 0
        return next(
            (
                index
                for index in range(last + 1)
                if any(
                    candidate.script == script
                    for candidate in self.script_pub_keys(index, prv_keys)
                )
            ),
            None,
        )

    def expansion(self, index: int = 0, prv_keys: PrvKeys | None = None) -> Expansion:
        """Return what the descriptor expanded at `index` tells a psbt.

        What BIP174's Updater writes into a psbt for this descriptor's
        script: the redeem script of a ``sh()``, the witness script of a
        ``wsh()``, the internal key, merkle root, leaf scripts and tree of
        a ``tr()``, and the origin of every key -- which is what a hardware
        signer needs, and what `KeyExpression.origin` is kept for.
        `Expansion` says which field holds what.

        What it does not hold is what a descriptor does not know: the
        utxo, the sighash type, the signatures. ``combo()``, ``addr()``,
        ``raw()`` and ``rawpkh()`` refuse, each saying why.
        """
        _assert_prv_keys(prv_keys)
        self._assert_index(index)
        with _derived_once(prv_keys):
            return self._expansion(index, prv_keys)

    def _expansion(self, index: int, prv_keys: PrvKeys | None) -> Expansion:
        """Return the key origins, which is what every fragment knows.

        And the whole of what ``pk()``, ``pkh()``, ``wpkh()`` and
        ``multi()`` know: their script is the script_pub_key, which the
        psbt has from the utxo rather than from here. The fragments that
        embed one of those add their scripts to this.
        """
        return Expansion(hd_key_paths=self._hd_key_paths(index, prv_keys))

    def _hd_key_paths(
        self, index: int, prv_keys: PrvKeys | None
    ) -> dict[bytes, BIP32KeyOrigin]:
        """Return the origin of each key, keyed by public key.

        A key without an origin gets the one `_derived_origin` makes up
        for it, as in Bitcoin Core. Where one key is spelled more than
        once, an explicit origin beats a made-up one, and otherwise the
        first spelling's origin is the entry's. `_taproot_derivations`
        says why the first of two explicit origins is kept.
        """
        hd_key_paths: dict[bytes, BIP32KeyOrigin] = {}
        explicit: set[bytes] = set()
        for key in self.key_expressions:
            sec = key.sec(index, self.network, prv_keys)
            if sec in hd_key_paths and (sec in explicit or key.origin is None):
                continue
            hd_key_paths[sec] = _derived_origin(key, index)
            if key.origin is not None:
                explicit.add(sec)
        return hd_key_paths


@dataclass(frozen=True)
class PkDescriptor(Descriptor):
    """``pk(KEY)``: a P2PK output, BIP381."""

    key: KeyExpression

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        assert_type(self.key, KeyExpression, "key")

    @override
    def __str__(self) -> str:
        return _expression("pk", str(self.key))

    @property
    @override
    def key_expressions(self) -> tuple[KeyExpression, ...]:
        """Return the one KEY expression, as the base class's tuple."""
        return (self.key,)

    @override
    def _scripts(self, index: int, prv_keys: PrvKeys | None) -> list[bytes]:
        pub_key = _pub_key_data(
            self.key.sec(index, self.network, prv_keys), self.network
        )
        return [ScriptPubKey.p2pk(pub_key).script]

    @override
    def _stack(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> list[bytes]:
        # the key is in the script already, so the signature is the whole
        # of what spending a p2pk output takes
        return [
            _required_signature(signatures, self.key.sec(index, self.network, prv_keys))
        ]


@dataclass(frozen=True)
class PkhDescriptor(Descriptor):
    """``pkh(KEY)``: a p2pkh output, BIP381."""

    key: KeyExpression

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        assert_type(self.key, KeyExpression, "key")

    @override
    def __str__(self) -> str:
        return _expression("pkh", str(self.key))

    @property
    @override
    def key_expressions(self) -> tuple[KeyExpression, ...]:
        """Return the one KEY expression, as the base class's tuple."""
        return (self.key,)

    @override
    def _scripts(self, index: int, prv_keys: PrvKeys | None) -> list[bytes]:
        pub_key = _pub_key_data(
            self.key.sec(index, self.network, prv_keys), self.network
        )
        return [ScriptPubKey.p2pkh(pub_key).script]

    @override
    def _stack(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> list[bytes]:
        # what the output commits to is the hash of the key, so the key
        # goes on the stack for the script to hash for itself
        sec = self.key.sec(index, self.network, prv_keys)
        return [_required_signature(signatures, sec), sec]


@dataclass(frozen=True)
class WpkhDescriptor(Descriptor):
    """``wpkh(KEY)``: a p2wpkh output, BIP382."""

    key: KeyExpression

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        assert_type(self.key, KeyExpression, "key")

    @override
    def __str__(self) -> str:
        return _expression("wpkh", str(self.key))

    @property
    @override
    def key_expressions(self) -> tuple[KeyExpression, ...]:
        """Return the one KEY expression, as the base class's tuple."""
        return (self.key,)

    @override
    def _scripts(self, index: int, prv_keys: PrvKeys | None) -> list[bytes]:
        pub_key = _pub_key_data(
            self.key.sec(index, self.network, prv_keys), self.network
        )
        return [ScriptPubKey.p2wpkh(pub_key).script]

    @override
    def _stack(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> list[bytes]:
        # the witness of a p2wpkh spend is what the script_sig of a p2pkh
        # one is, BIP143 having moved it and changed nothing else
        sec = self.key.sec(index, self.network, prv_keys)
        return [_required_signature(signatures, sec), sec]

    @override
    def _satisfy(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> tuple[bytes, Witness]:
        # the empty script_sig of BIP141, which is not the same as an
        # empty push: btclib's own engine refuses a native segwit input
        # whose script_sig is there at all (issue btclib-org/btclib#249). A
        # sh(wpkh()) gets its one push from the sh() above
        return b"", Witness(self._stack(signatures, index, prv_keys, spend))


@dataclass(frozen=True)
class ShDescriptor(Descriptor):
    """``sh(SCRIPT)``: the argument, p2sh-embedded, BIP381."""

    inner: Descriptor

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        assert_type(self.inner, Descriptor, "inner descriptor")

    @override
    def __str__(self) -> str:
        return _expression("sh", str(self.inner))

    @property
    @override
    def key_expressions(self) -> tuple[KeyExpression, ...]:
        """Return the wrapped SCRIPT's KEY expressions."""
        return self.inner.key_expressions

    @override
    def _scripts(self, index: int, prv_keys: PrvKeys | None) -> list[bytes]:
        return [ScriptPubKey.p2sh(self.inner.redeem_script(index, prv_keys)).script]

    @override
    def _satisfy(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> tuple[bytes, Witness]:
        """Return the argument's satisfaction, the redeem script pushed last.

        One rule for the three shapes ``sh()`` wraps, because the two
        wrapped segwit ones satisfy into the witness and leave the
        script_sig empty: what is appended is the same push either way,
        and what it is appended to is nothing where the spend is a
        witness. Appending is concatenation because a script_sig is
        pushes and nothing else, so serializing them together and
        serializing them apart give the same bytes.
        """
        redeem_script = _embedded(self, index, prv_keys)
        script_sig, witness = self.inner._satisfy(signatures, index, prv_keys, spend)
        return script_sig + serialize(cast(ScriptList, [redeem_script])), witness

    @override
    def _expansion(self, index: int, prv_keys: PrvKeys | None) -> Expansion:
        """Add the redeem script to what the argument expands to.

        Delegated rather than dispatched on: the argument of a
        ``sh(wsh())`` is what knows there is a witness script below the
        redeem script, and it is the same method that adds it for a
        native ``wsh()``. A ``raw()`` or a ``rawpkh()`` argument is no
        such fragment: it holds no key origin, and its bytes are the
        redeem script.
        """
        return replace(
            _inner_expansion(self.inner, index, prv_keys),
            redeem_script=_embedded(self, index, prv_keys),
        )


@dataclass(frozen=True)
class WshDescriptor(Descriptor):
    """``wsh(SCRIPT)``: the argument, P2WSH-embedded, BIP382."""

    inner: Descriptor

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        assert_type(self.inner, Descriptor, "inner descriptor")

    @override
    def __str__(self) -> str:
        return _expression("wsh", str(self.inner))

    @property
    @override
    def key_expressions(self) -> tuple[KeyExpression, ...]:
        """Return the wrapped SCRIPT's KEY expressions."""
        return self.inner.key_expressions

    @override
    def _scripts(self, index: int, prv_keys: PrvKeys | None) -> list[bytes]:
        return [ScriptPubKey.p2wsh(self.inner.redeem_script(index, prv_keys)).script]

    @override
    def _satisfy(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> tuple[bytes, Witness]:
        """Return the witness of a p2wsh spend: the stack, then the script.

        The argument's stack and not its satisfaction, which would be
        those same elements serialized as a script_sig: a witness is a
        stack already, so BIP141 puts them in it one by one and the
        witness script last.
        """
        witness_script = _embedded(self, index, prv_keys)
        stack = self.inner._stack(signatures, index, prv_keys, spend)
        return b"", Witness([*stack, witness_script])

    @override
    def _expansion(self, index: int, prv_keys: PrvKeys | None) -> Expansion:
        """Add the witness script; the redeem script is ``sh()``'s to add.

        Which is the whole difference between a native ``wsh()`` and a
        wrapped one, in the psbt as in the spend: the same witness script,
        and a redeem script only where something wraps it. A ``raw()``
        or a ``rawpkh()`` argument holds no key origin, and its bytes
        are the witness script.
        """
        return replace(
            _inner_expansion(self.inner, index, prv_keys),
            witness_script=_embedded(self, index, prv_keys),
        )


@dataclass(frozen=True)
class MiniscriptDescriptor(Descriptor):
    """A BIP379 miniscript where a SCRIPT expression may be one.

    Which is inside ``wsh()``: a miniscript inside ``tr()`` is a leaf of
    the script tree and not a SCRIPT expression, so `DescriptorTree` holds
    that one directly, the way it holds a ``multi_a()``. What this holds is
    the `Miniscript`, whose own interface -- the type properties, the
    resource bounds, the script both ways, the satisfaction -- is
    `bip32_descriptors.descriptors.miniscript`'s.

    A fragment like the others in what it answers: the script at an index,
    the KEY expressions it names, and the psbt fields those keys fill.
    Unlike the others it does not satisfy: a miniscript satisfaction needs
    more than a mapping of public keys to signatures, so `satisfy` refuses
    and says so.
    """

    node: Miniscript

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        assert_type(self.node, Miniscript, "miniscript")

    @override
    def __str__(self) -> str:
        return str(self.node)

    @property
    @override
    def key_expressions(self) -> tuple[KeyExpression, ...]:
        """Return the KEY expressions of the fragments, left to right."""
        return self.node.key_expressions

    @override
    def _scripts(self, index: int, prv_keys: PrvKeys | None) -> list[bytes]:
        return [self.node.script(index, self.network, prv_keys)]

    @override
    def _stack(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> list[bytes]:
        """Return the witness elements that satisfy the miniscript.

        The one fragment that reads the spend context, and the reason
        `satisfy` takes one: a miniscript satisfaction chooses among
        branches, and the choice reads the hash preimages a ``sha256()``
        wants and the lock times an ``older()`` or an ``after()`` is
        checked against. Non-malleable or refused, which is
        `Miniscript.satisfy`'s rule and BIP379's.
        """
        # cast because `Mapping` is invariant in its key: these bytes are
        # every bit an `Octets`, and a mapping of them is still not a
        # mapping of "bytes or hex" as far as the type checker is concerned
        offered = cast("Mapping[Octets, Octets]", signatures)
        return self.node.satisfy(offered, spend, index, self.network, prv_keys)


@dataclass(frozen=True)
class MultiDescriptor(Descriptor):
    """``multi(k,KEY,...)`` and ``sortedmulti(k,KEY,...)``, BIP383."""

    threshold: int
    keys: tuple[KeyExpression, ...]
    # BIP67 ordering, which is the whole difference between the two
    # functions: the keys of a sortedmulti() are sorted in the script, so
    # the participants need not agree on an order to agree on an address
    sort: bool = False

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        if not is_integer(self.threshold):
            err_msg = f"invalid threshold type: {type(self.threshold).__name__}"
            raise BTClibTypeError(err_msg)
        assert_type(self.keys, tuple, "keys")
        for key in self.keys:
            assert_type(key, KeyExpression, "key")
        assert_type(self.sort, bool, "sort")

    @override
    def __str__(self) -> str:
        name = "sortedmulti" if self.sort else "multi"
        return _expression(name, str(self.threshold), *map(str, self.keys))

    @property
    @override
    def key_expressions(self) -> tuple[KeyExpression, ...]:
        """Return the KEY expressions, in descriptor order."""
        return self.keys

    def _pub_keys(self, index: int, prv_keys: PrvKeys | None) -> list[bytes]:
        """Return the keys in the order the script holds them.

        `sorted` and not `p2ms`'s own `lexicographic_sorting`, which
        sorts identically: the order is also the order the signatures of
        a satisfaction go in, so one of the two has somewhere to ask for
        it rather than a second copy of the rule.
        """
        pub_keys = [key.sec(index, self.network, prv_keys) for key in self.keys]
        return sorted(pub_keys) if self.sort else pub_keys

    @override
    def _scripts(self, index: int, prv_keys: PrvKeys | None) -> list[bytes]:
        script_pub_key = ScriptPubKey.p2ms(
            self.threshold,
            [
                _pub_key_data(sec, self.network)
                for sec in self._pub_keys(index, prv_keys)
            ],
            lexicographic_sorting=False,
        )
        return [script_pub_key.script]

    @override
    def _stack(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> list[bytes]:
        """Return the dummy element and `threshold` signatures, in key order.

        OP_CHECKMULTISIG walks the signatures and the keys in one pass
        and never goes back, so the signatures have to be in the order
        the script holds the keys in. More signatures than the threshold
        is not an error and not all of them are used: the script pops
        exactly as many as it was built for, and the rest are the other
        keys of the same descriptor having signed too.

        The first element is the one OP_CHECKMULTISIG pops without
        reading, which BIP147 requires to be the empty push.
        """
        offered = [
            (sec, _offered_signature(signatures, sec, x_only=False))
            for sec in self._pub_keys(index, prv_keys)
        ]
        found = [signature for _, signature in offered if signature is not None]
        if len(found) < self.threshold:
            missing = ", ".join(sec.hex() for sec, sig in offered if sig is None)
            err_msg = f"{len(found)} signatures of {self.threshold}, missing {missing}"
            raise BTClibValueError(err_msg)
        return [b"", *found[: self.threshold]]


@dataclass(frozen=True)
class ComboDescriptor(Descriptor):
    """``combo(KEY)``: the scripts an old wallet would have used, BIP384.

    p2pk and p2pkh, plus p2wpkh and p2sh-p2wpkh when the key is
    compressed -- an uncompressed key is not allowed in a witness
    program.
    """

    key: KeyExpression

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        assert_type(self.key, KeyExpression, "key")

    @override
    def __str__(self) -> str:
        return _expression("combo", str(self.key))

    @property
    @override
    def key_expressions(self) -> tuple[KeyExpression, ...]:
        """Return the one KEY expression, as the base class's tuple."""
        return (self.key,)

    @override
    def _scripts(self, index: int, prv_keys: PrvKeys | None) -> list[bytes]:
        pub_key = _pub_key_data(
            self.key.sec(index, self.network, prv_keys), self.network
        )
        scripts = [
            ScriptPubKey.p2pk(pub_key).script,
            ScriptPubKey.p2pkh(pub_key).script,
        ]
        if self.key.is_compressed:
            p2wpkh = ScriptPubKey.p2wpkh(pub_key).script
            scripts += [p2wpkh, ScriptPubKey.p2sh(p2wpkh).script]
        return scripts

    @override
    def _satisfy(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> tuple[bytes, Witness]:
        """Refuse: four scripts, and each of them spent differently.

        Which one is being spent is a question the caller answers, by
        satisfying the descriptor of that script -- ``pk()``, ``pkh()``,
        ``wpkh()`` or ``sh(wpkh())`` of the same key -- and it is a
        question `script_pub_keys` can leave open where this cannot.
        """
        err_msg = "combo() is four scripts: satisfy the one being spent"
        raise BTClibValueError(err_msg)

    @override
    def _expansion(self, index: int, prv_keys: PrvKeys | None) -> Expansion:
        """Refuse: the four scripts are updated into an input differently.

        One of them is p2sh and wants a redeem script, the other three
        want none, and the input is spending one output: an Updater that
        wrote the key origin and left the script to the caller would have
        filled in the half that is the same for all four and hidden the
        half that is not.
        """
        err_msg = "combo() is four scripts: update the psbt with the one spent"
        raise BTClibValueError(err_msg)


@dataclass(frozen=True)
class AddrDescriptor(Descriptor):
    """``addr(ADDR)``: the script the address expands to, BIP385."""

    addr: str

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        assert_type(self.addr, str, "address")

    @override
    def __str__(self) -> str:
        return _expression("addr", self.addr)

    @property
    @override
    def key_expressions(self) -> tuple[KeyExpression, ...]:
        """Return no KEY expression, the descriptor fixing none."""
        return ()

    @override
    def _scripts(self, index: int, prv_keys: PrvKeys | None) -> list[bytes]:
        return [ScriptPubKey.from_address(self.addr).script]

    @override
    def _satisfy(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> tuple[bytes, Witness]:
        """Refuse: an address names a script and not what spends it.

        BTClibValueError and not the NotImplementedError the parser
        raises for what a later release adds: there is nothing to add,
        an address being a commitment to a key or a script that the
        descriptor does not carry.
        """
        raise BTClibValueError("addr() cannot be satisfied: it holds no key")

    @override
    def _expansion(self, index: int, prv_keys: PrvKeys | None) -> Expansion:
        """Refuse: there is nothing of an address to write into an input.

        No key, so no origin; no script below the address, so no redeem or
        witness script. An empty expansion would be an Updater that ran and
        a caller told it had been updated.
        """
        raise BTClibValueError("addr() cannot update a psbt: it holds no key")


@dataclass(frozen=True)
class RawDescriptor(Descriptor):
    """``raw(HEX)``: the script those bytes are, BIP385."""

    script: bytes

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        assert_type(self.script, bytes, "script")

    @override
    def __str__(self) -> str:
        return _expression("raw", self.script.hex())

    @property
    @override
    def key_expressions(self) -> tuple[KeyExpression, ...]:
        """Return no KEY expression, the descriptor fixing none."""
        return ()

    @override
    def _scripts(self, index: int, prv_keys: PrvKeys | None) -> list[bytes]:
        return [self.script]

    @override
    def _stack(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> list[bytes]:
        """Refuse, as `_satisfy` does: ``wsh()`` asks for the stack."""
        raise BTClibValueError("raw() cannot be satisfied: it holds no key")

    @override
    def _satisfy(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> tuple[bytes, Witness]:
        """Refuse: a script and no key expression to satisfy it with.

        What ``raw()`` holds is bytes, which say nothing about which key
        signs for them even where they happen to be a script this module
        can otherwise read; the descriptor of that script is what is
        satisfiable.
        """
        raise BTClibValueError("raw() cannot be satisfied: it holds no key")

    @override
    def _expansion(self, index: int, prv_keys: PrvKeys | None) -> Expansion:
        """Refuse, for the reason ``addr()`` does: bytes hold no key origin.

        Those bytes may be the script an input spends, and they are then
        its script_pub_key, which the psbt has from the utxo; what a
        descriptor is asked here is what the utxo does not say. Inside
        ``sh()`` or ``wsh()`` the bytes are the script that function
        embeds, and it writes them itself.
        """
        raise BTClibValueError("raw() cannot update a psbt: it holds no key")


@dataclass(frozen=True)
class RawPkhDescriptor(Descriptor):
    """``rawpkh(HEX)``: a p2pkh output paying to the hash160 HEX, no BIP.

    ``pkh(KEY)`` with the hash of the key and not the key, for an output
    whose key the descriptor does not know. Bitcoin Core does not read it.
    Inside a miniscript the same text is the fragment ``pkh(KEY)`` is, with
    the hash for the key. Inside ``tr()`` it is a c0 leaf, and the hash is
    that of the 32-byte x-only key, as it is in the ``pkh()`` leaf.
    """

    key_hash: bytes

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        assert_type(self.key_hash, bytes, "key hash")

    @override
    def __str__(self) -> str:
        return _expression("rawpkh", self.key_hash.hex())

    @property
    @override
    def key_expressions(self) -> tuple[KeyExpression, ...]:
        """Return no KEY expression, the descriptor fixing none."""
        return ()

    @override
    def _scripts(self, index: int, prv_keys: PrvKeys | None) -> list[bytes]:
        if len(self.key_hash) != _KEY_HASH_SIZE:
            raise BTClibValueError("160 bits digest expected")
        return [
            serialize(
                ["OP_DUP", "OP_HASH160", self.key_hash, "OP_EQUALVERIFY", "OP_CHECKSIG"]
            )
        ]

    @override
    def _stack(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> list[bytes]:
        """Refuse, as `_satisfy` does: ``wsh()`` asks for the stack."""
        raise BTClibValueError("rawpkh() cannot be satisfied: it holds no key")

    @override
    def _satisfy(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> tuple[bytes, Witness]:
        """Refuse: the hash of a key is not the key the spend has to push."""
        raise BTClibValueError("rawpkh() cannot be satisfied: it holds no key")

    @override
    def _expansion(self, index: int, prv_keys: PrvKeys | None) -> Expansion:
        """Refuse, for the reason ``raw()`` does: a hash holds no key origin."""
        raise BTClibValueError("rawpkh() cannot update a psbt: it holds no key")


# the fragments that are a script and nothing else: what ``sh()`` and
# ``wsh()`` embed as it is, with no key origin of its own to write
_SCRIPT_ONLY = (RawDescriptor, RawPkhDescriptor)


def _embedded(
    descriptor: ShDescriptor | WshDescriptor, index: int, prv_keys: PrvKeys | None
) -> bytes:
    """Return the script a ``sh()`` or a ``wsh()`` embeds.

    Refused where the descriptor has no script for it, so that a
    hand-built one over the size limit answers nothing else either.
    """
    descriptor._scripts(index, prv_keys)
    return descriptor.inner.redeem_script(index, prv_keys)


def _inner_expansion(
    inner: Descriptor, index: int, prv_keys: PrvKeys | None
) -> Expansion:
    """Return the expansion of what ``sh()`` or ``wsh()`` wraps.

    Empty for a ``raw()`` or a ``rawpkh()``, which refuse their own: inside
    those two the bytes are the script embedded, and no key origin goes
    with them.
    """
    if isinstance(inner, _SCRIPT_ONLY):
        return Expansion()
    return inner._expansion(index, prv_keys)


def _control_block(x_only: bytes, parity: int, leaf: _TreeLeaf) -> bytes:
    """Return BIP341's control block of a leaf."""
    return bytes([parity + leaf.version]) + x_only + leaf.path


@dataclass(frozen=True)
class TrDescriptor(Descriptor):
    """``tr(KEY)`` or ``tr(KEY,TREE)``: a p2tr output, BIP386."""

    internal_key: KeyExpression
    tree: DescriptorTree | None = None

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        assert_type(self.internal_key, KeyExpression, "internal key")
        if self.tree is not None:
            _assert_tree(self.tree)

    @override
    def __str__(self) -> str:
        if self.tree is None:
            return _expression("tr", str(self.internal_key))
        return _expression("tr", str(self.internal_key), _tree_expression(self.tree))

    @property
    @override
    def key_expressions(self) -> tuple[KeyExpression, ...]:
        """Return the internal key and every leaf key, in tree order."""
        if self.tree is None:
            return (self.internal_key,)
        return (self.internal_key, *_tree_keys(self.tree))

    def _tree(
        self, index: int, prv_keys: PrvKeys | None
    ) -> tuple[list[_TreeLeaf], bytes]:
        """Return the leaves in tree order, and the merkle root."""
        if self.tree is None:
            return [], b""
        return _tree_walk(self.tree, 0, index, self.network, prv_keys)

    def _output(
        self, index: int, prv_keys: PrvKeys | None
    ) -> tuple[bytes, bytes, int, list[_TreeLeaf]]:
        """Return the internal key, the output key, its parity and the leaves.

        The one place the output key is built, a script and a control
        block wanting the same key and the same parity. The internal key is
        asked as `btclib.script.taproot.output_pubkey` asks it, for its
        length, its prefix and its network.
        """
        internal_key = _pub_key_data(
            self.internal_key.sec(index, self.network, prv_keys), self.network
        )
        internal_key.assert_valid()
        leaves, root = self._tree(index, prv_keys)
        x_only = internal_key.sec[1:33]
        output_key, parity = output_pubkey_from_merkle_root_var(x_only, root)
        return x_only, output_key, parity, leaves

    @override
    def _scripts(self, index: int, prv_keys: PrvKeys | None) -> list[bytes]:
        return [serialize(["OP_1", self._output(index, prv_keys)[1]])]

    def taproot_merkle_root(
        self, index: int = 0, prv_keys: PrvKeys | None = None
    ) -> bytes:
        """Return the root the output key commits to, b"" where there is none.

        BIP371's PSBT_IN_TAP_MERKLE_ROOT, and empty is how that field
        says "key path only": a ``tr(KEY)`` tweaks its internal key with
        no tree, which is not the same as tweaking it with an empty one.
        """
        _assert_prv_keys(prv_keys)
        self._assert_index(index)
        return self._tree(index, prv_keys)[1]

    def taproot_leaf_scripts(
        self, index: int = 0, prv_keys: PrvKeys | None = None
    ) -> dict[bytes, tuple[bytes, int]]:
        """Return every leaf script and its version, keyed by control block.

        The shape of BIP371's PSBT_IN_TAP_LEAF_SCRIPT, and the field an
        Updater is needed for rather than convenient: a control block
        holds the merkle path from its leaf to the root, which is the
        whole tree seen from that leaf, and a psbt carrying one leaf's
        script has no way to compute another's. A `RawNode` has no leaf,
        and sits in the path of the control blocks of its siblings.
        """
        _assert_prv_keys(prv_keys)
        self._assert_index(index)
        if self.tree is None:
            return {}
        x_only, _, parity, leaves = self._output(index, prv_keys)
        return {
            _control_block(x_only, parity, leaf): (leaf.script, leaf.version)
            for leaf in leaves
        }

    def _taproot_hd_key_paths(
        self, index: int, prv_keys: PrvKeys | None
    ) -> dict[bytes, tuple[list[bytes], BIP32KeyOrigin]]:
        """Return each key's origin and leaf hashes, keyed by x-only key.

        BIP371 gives a taproot key a field of its own, keyed by the 32
        bytes a tapscript holds and carrying the tapleaf hash of every
        leaf the key appears in: none for a key that is only the internal
        one, no leaf committing to it, and one entry naming each of them
        for a key written into several, the field being keyed by key.

        Named once each: a key in two leaves of the same script is in two
        places of the tree and in one leaf of it, the tapleaf hash being
        of the script, and what a signer reads here is which scripts it
        has to sign for.

        The leaves are walked rather than `taproot_leaf_scripts`, which is
        keyed by control block: which keys a leaf commits to is what the
        leaf says and no longer what its script bytes show, a
        ``multi_a()`` leaf holding as many keys as it names.
        """
        leaf_hashes: dict[bytes, list[bytes]] = {}
        if self.tree is not None:
            walked = self._tree(index, prv_keys)[0]
            for leaf, record in zip(_tree_leaves(self.tree), walked, strict=True):
                hash_ = leaf_hash(record.version, record.script)
                for key in _leaf_keys(leaf):
                    hashes = leaf_hashes.setdefault(
                        key.sec(index, self.network, prv_keys)[1:], []
                    )
                    if hash_ not in hashes:
                        hashes.append(hash_)
        return _taproot_derivations(
            self.key_expressions, leaf_hashes, index, self.network, prv_keys
        )

    @override
    def _satisfy(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> tuple[bytes, Witness]:
        """Return the witness of a key path spend, or of a script path one.

        The key path whenever a signature for the internal key is
        offered, which is the preference Bitcoin Core's finalizer has:
        it is the cheaper spend and the one the output key commits to
        directly. That signature is one the *output* key verifies, the
        signer having tweaked the key it holds, and it is looked up
        under the internal key because that is the key the descriptor
        names.

        A script path witness is what satisfies the leaf, then the leaf
        script and the control block, which is BIP341's order: one
        signature for a ``pk()`` leaf, one element per key for a
        ``multi_a()`` one, and for a miniscript leaf whatever its
        non-malleable satisfaction is -- which is where `spend` is read, a
        branch of one wanting a preimage or a lock time.

        Both the parity bit and the merkle path in that
        control block are the descriptor's to compute, holding the whole
        tree as it does, where a psbt has to be handed them: it is the one
        thing satisfaction here knows that finalization there cannot work
        out.

        The first leaf the signatures satisfy, left to right, where they
        satisfy several: they are all valid spends of the same output, and
        which is the cheapest is a question about weights that this module
        does not answer.

        The script_sig is empty whichever path is taken: BIP341 spends
        a witness v1 program with the witness alone.
        """
        internal_key = self.internal_key.sec(index, self.network, prv_keys)
        signature = _offered_signature(signatures, internal_key, x_only=True)
        if signature is not None:
            return b"", Witness([signature])
        if self.tree is None:
            raise BTClibValueError("no signature for the tr() internal key")
        x_only, _, parity, walked = self._output(index, prv_keys)
        for leaf, record in zip(_tree_leaves(self.tree), walked, strict=True):
            stack = _leaf_stack(leaf, signatures, index, self.network, prv_keys, spend)
            if stack is not None:
                control_block = _control_block(x_only, parity, record)
                return b"", Witness([*stack, record.script, control_block])
        err_msg = "no signature for the tr() internal key or for any of its leaves"
        raise BTClibValueError(err_msg)

    def taproot_tree(
        self, index: int = 0, prv_keys: PrvKeys | None = None
    ) -> list[tuple[int, int, bytes]]:
        """Return every leaf with its depth: BIP371's PSBT_OUT_TAP_TREE.

        The whole tree, where an input publishes the one leaf it spends and
        the control block that proves it: an output has no leaf being spent
        yet, so what it carries is each script with the depth it sits at,
        in the order a depth-first walk reaches them. A reader rebuilds the
        tree from those two facts and can then check the output key itself
        -- which is why the field is the tree and not the merkle root, a
        root proving nothing about the scripts underneath it.

        Empty for a ``tr(KEY)``, whose output key commits to no script at
        all, and which BIP371 says so about by leaving the field out.
        Refused where a ``rawnode()`` is in the tree: the field is the
        whole tree, and a node known by its hash has no leaf to publish.
        """
        _assert_prv_keys(prv_keys)
        self._assert_index(index)
        if self.tree is None:
            return []
        if _has_raw_node(self.tree):
            err_msg = "a tr() with a rawnode() has no whole tree to publish"
            raise BTClibValueError(err_msg)
        return [
            (leaf.depth, leaf.version, leaf.script)
            for leaf in self._tree(index, prv_keys)[0]
        ]

    @override
    def _expansion(self, index: int, prv_keys: PrvKeys | None) -> Expansion:
        """Return the taproot fields, and no 33-byte key origin.

        A taproot key origin belongs in `taproot_hd_key_paths`, keyed by the
        x-only key, and a 33-byte entry in `hd_key_paths` beside it would be
        the same key twice in two spellings, for a signer that signs with
        neither.

        The participant list of BIP373 is here too where a key of the
        descriptor is a ``musig()``: it tells a signer that one of the keys
        it holds is in the group, which is as true of an output being paid
        as of an input being spent.

        The tree is None where a ``rawnode()`` is in it, which
        `taproot_tree` refuses: an input is still told its merkle root and
        the leaves it can be spent by. Such an expansion is an input's
        only, and an output's Updater has to refuse it, as `Expansion`
        says.
        """
        has_tree = self.tree is None or not _has_raw_node(self.tree)
        return Expansion(
            taproot_internal_key=self.internal_key.sec(index, self.network, prv_keys)[
                1:
            ],
            taproot_merkle_root=self.taproot_merkle_root(index, prv_keys),
            taproot_leaf_scripts=self.taproot_leaf_scripts(index, prv_keys),
            taproot_tree=self.taproot_tree(index, prv_keys) if has_tree else None,
            taproot_hd_key_paths=self._taproot_hd_key_paths(index, prv_keys),
            musig2_participant_pub_keys=_musig2_participants(
                self.key_expressions, index, self.network, prv_keys
            ),
        )


@dataclass(frozen=True)
class RawTrDescriptor(Descriptor):
    """``rawtr(KEY)``: the key as the output key itself, no tweak at all.

    BIP394 specifies this function, and carries the warning this
    docstring keeps: an output key whose internal key nobody knows cannot
    be shown to have no hidden script path, so a ``rawtr()`` describes an
    output a wallet already holds rather than one to build.

    The key is BIP341's *output* key, written into ``OP_1 <32 bytes>`` as
    it is. That is the whole difference from ``tr(KEY)``, which tweaks its
    internal key with an empty merkle root, and it is why this is not a
    `TrDescriptor` carrying ``tree=None``.
    """

    key: KeyExpression

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        assert_type(self.key, KeyExpression, "key")

    @override
    def __str__(self) -> str:
        return _expression("rawtr", str(self.key))

    @property
    @override
    def key_expressions(self) -> tuple[KeyExpression, ...]:
        """Return the one KEY expression, as the base class's tuple."""
        return (self.key,)

    @override
    def _scripts(self, index: int, prv_keys: PrvKeys | None) -> list[bytes]:
        # not ScriptPubKey.p2tr, which computes an output key from an
        # internal one: here the key already is the output key, and
        # tweaking it would describe an output nobody named
        output_key = self.key.sec(index, self.network, prv_keys)[1:]
        return [serialize(["OP_1", output_key])]

    @override
    def _satisfy(
        self,
        signatures: Mapping[bytes, bytes],
        index: int,
        prv_keys: PrvKeys | None,
        spend: SpendContext | None,
    ) -> tuple[bytes, Witness]:
        """Return the witness of a BIP341 key path spend: one signature.

        Looked up under the key the descriptor names, as ``tr()`` does,
        and the two lookups mean opposite things: there the signature is
        one the *tweaked* key verifies, made by a signer that tweaked the
        internal key it holds, while here it must verify against the key
        as written, so a signer must not tweak anything.

        The script_sig is empty: BIP341 spends a witness v1 program with
        the witness alone.
        """
        output_key = self.key.sec(index, self.network, prv_keys)
        signature = _offered_signature(signatures, output_key, x_only=True)
        if signature is None:
            raise BTClibValueError("no signature for the rawtr() output key")
        return b"", Witness([signature])

    @override
    def _expansion(self, index: int, prv_keys: PrvKeys | None) -> Expansion:
        """Return the one taproot field a ``rawtr()`` has anything to say in.

        BIP371's PSBT_IN_TAP_BIP32_DERIVATION, keyed by the x-only key,
        which is the origin of the key the script holds. The other three
        fields are `TrDescriptor`'s and not this one's: PSBT_IN_TAP_
        INTERNAL_KEY names the key a verifier tweaks and a ``rawtr()`` has
        none, so it has no merkle root and no leaf script either.

        What that costs is btclib-wallet's `psbt.sign`, which signs a
        taproot input through its internal key and therefore leaves this
        input alone rather than tweaking a key it should not: an input with
        no internal key is one that role skips.

        BIP373's participant list is beside it where the key is a
        ``musig()``, as it is under a ``tr()``: an aggregate key that is
        the output key itself is the first of the four ways BIP373 has of
        reaching what is spent.
        """
        keys = self.key_expressions
        return Expansion(
            taproot_hd_key_paths=_taproot_derivations(
                keys, {}, index, self.network, prv_keys
            ),
            musig2_participant_pub_keys=_musig2_participants(
                keys, index, self.network, prv_keys
            ),
        )


def _assert_position(name: str, context: str, allowed: tuple[str, ...]) -> None:
    if context not in allowed:
        raise BTClibValueError(f"{name}() is not allowed inside {context}")


def _one_argument(arguments: list[str], name: str) -> str:
    if len(arguments) != 1:
        err_msg = f"{name}() takes one argument, {len(arguments)} given"
        raise BTClibValueError(err_msg)
    return arguments[0]


def _parse_multi_a(name: str, text: str, prv_keys: dict[str, str]) -> MultiA:
    """Return the leaf of a BIP387 ``multi_a()`` or ``sortedmulti_a()``.

    `text` is what the parentheses enclose. The keys are read as a
    ``pk()`` leaf's key is, which is what allows BIP387's own vectors to
    name one by its WIF and the next by an xprv: x-only is the spelling a
    tapscript holds and not the only spelling a KEY expression has.
    """
    args = _split_unpaired_arguments(text)
    if len(args) < 2:
        raise BTClibValueError(f"{name}() takes a threshold and at least one key")
    if not _THRESHOLD.fullmatch(args[0]):
        raise BTClibValueError(f"invalid {name}() threshold: digits expected")
    keys, lengths = _read_multipath_keys(
        args[1:],
        lambda key: _parse_key(
            key, prv_keys, x_only=True, compressed=True, musig_allowed=True
        ),
    )
    _assert_multisig_end(name, text, args)
    threshold = _int_from_digits(args[0], f"{name}() threshold")
    if not 1 <= threshold <= len(keys):
        raise BTClibValueError(f"invalid k in k-of-n {name}: {threshold}")
    if len(keys) > _MAX_MULTI_A_KEYS:
        raise BTClibValueError(f"invalid n in k-of-n {name}: {len(keys)}")
    _assert_multipath_keys(lengths)
    return MultiA(threshold, keys, sort=name == "sortedmulti_a")


def _assert_multisig_end(name: str, text: str, args: list[str]) -> None:
    """Refuse the text a multisig's arguments leave, once its keys are read.

    `args` is `text` split as Bitcoin Core reads a multisig: each argument
    ends at a "," or at a closing bracket with nothing open. Core expects
    a "," after each key, so a closing bracket left after one is the
    multisig's fault, which Core names before it checks the number of
    keys or the threshold. The message leaves the text out, since it can
    hold a private key.

    Past that bracket the multisig's own parentheses are closed. A "," or
    a closing bracket there, with nothing open, is where Core's caller
    ends the expression, so Core never reads the rest as the multisig's:
    that text is refused as unpaired brackets.
    """
    end = len(",".join(args))
    rest = text[end + 1 :]
    if end < len(text) and _split_unpaired_arguments(rest) == [rest]:
        err_msg = f"{name}(): expected ',' after a key, got a closing bracket"
        raise BTClibValueError(err_msg)
    _split_arguments(text)


def _parse_leaf_miniscript(expression: str, prv_keys: dict[str, str]) -> Miniscript:
    """Return the miniscript of a tr() leaf, sanity checked as a wsh() one is.

    The tapscript dialect: 32-byte keys, ``multi_a()`` where ``wsh()`` has
    ``multi()``, and a ``d:`` wrapper that is "u" because MINIMALIF is
    consensus under taproot. What is refused is what a descriptor refuses
    anywhere -- an expression that is malleable, needs no signature, mixes
    timelocks, repeats a key, or has a spend past a resource limit -- and
    the leaf is where it is said, a tree being several scripts of which
    this one is unspendable or unsafe.

    On a ``_CoreFallbackError`` Core says "'<leaf>' is not a valid
    descriptor function". The message here leaves the leaf out, since it
    can hold a private key.
    """
    if expression.startswith("multi_a("):
        _read_unclosed_multisig_keys(expression, miniscript.TAPSCRIPT, prv_keys)
    with _steps_compared():
        try:
            node = _parse_miniscript(
                expression, miniscript.TAPSCRIPT, prv_keys, _filed_preimages()
            )
        except miniscript._CoreFallbackError as error:
            err_msg = "tr() leaf is not a valid descriptor function"
            raise BTClibValueError(err_msg) from error
        _assert_sane(node, prv_keys)
    return node


def _parse_leaf(expression: str, prv_keys: dict[str, str]) -> DescriptorLeaf | RawNode:
    """Return a tr() leaf or ``rawnode()``: what ``Expr`` cut, read whole.

    Core's ``Func`` takes a name only where the text ends in ")", so a
    leaf that does not is read as a miniscript, whatever its name.
    """
    if not expression.endswith(")"):
        return _parse_leaf_miniscript(expression, prv_keys)
    name = expression.partition("(")[0]
    if name in _TREE_FUNCTIONS:
        return _parse_multi_a(name, _split_function(expression)[1], prv_keys)
    return _parse_other_leaf(expression, name, prv_keys)


def _parse_other_leaf(
    expression: str, name: str, prv_keys: dict[str, str]
) -> DescriptorLeaf | RawNode:
    """Return the tree of a ``pk()``, a raw function or a miniscript leaf."""
    if name == "musig":
        # allowed inside tr(), and as a key rather than as a leaf: a leaf
        # is a script, and what a musig() aggregates to is one key of one
        err_msg = "musig() is a key expression: pk(musig(...)) is the leaf"
        raise BTClibValueError(err_msg)
    if name in _PARSERS and _P2TR not in _PARSERS[name][0]:
        # a SCRIPT function where a leaf is expected: a position rule and
        # not something a later release adds, which is what the position
        # table says and Bitcoin Core's own message says too. ``pk()``,
        # ``pkh()``, ``raw()`` and ``rawpkh()`` allow tr() among their
        # positions and fall through to be read, ``pkh()`` as BIP379's
        # fragment and ``rawpkh()`` as this package's fragment beside it
        _assert_position(name, _P2TR, _PARSERS[name][0])
    if name == "raw" or name in _RAW_TREE_FUNCTIONS:
        return _read_split(_split_function(expression)[1], _RAW_TREE_PARSERS[name])
    if name != "pk":
        # a leaf that is no BIP386 leaf is a BIP379 miniscript, which is
        # the same order the wsh() half reads its two grammars in
        return _parse_leaf_miniscript(expression, prv_keys)
    key = _split_function(expression)[1]
    return _parse_key(
        key,
        prv_keys,
        x_only=True,
        compressed=True,
        musig_allowed=True,
    )


def _parse_tree(
    text: str, pos: int, prv_keys: dict[str, str]
) -> tuple[DescriptorTree, int]:
    """Return the script tree starting at `pos`, and the index past it.

    Core's ``tr()`` loop: take each "{", which opens a left subtree; cut
    one leaf as ``Expr`` does and read it; take a "}" for each right
    subtree the leaf ends; then a "," after a left one, which turns it
    into a right one. A leaf is read before what follows it, so a leaf
    that runs on into the tree's own "}" or "," is the leaf's fault.

    MAX_TREE_DEPTH bounds how many braces are open at once. A leaf below
    it has no control block to be spent with, so the expression describes
    no output rather than a large one, and it is where Core stops too,
    "tr() supports at most 128 nesting levels".
    """
    # where the subtrees of each open branch start, and which one it is in
    starts: list[int] = []
    in_right: list[bool] = []
    subtrees: list[DescriptorTree] = []
    while True:
        while text.startswith("{", pos):
            pos += 1
            starts.append(pos)
            in_right.append(False)
            if len(starts) > MAX_TREE_DEPTH:
                err_msg = f"tr() supports at most {MAX_TREE_DEPTH} nesting levels"
                raise BTClibValueError(err_msg)
        end = miniscript._leaf_end(text, pos)
        subtrees.append(_parse_leaf(text[pos:end], prv_keys))
        pos = end
        while in_right and in_right[-1]:
            _expect_branch_end(text, pos, starts.pop(), "}")
            pos += 1
            in_right.pop()
            right = subtrees.pop()
            subtrees.append((subtrees.pop(), right))
        if not in_right:
            return subtrees[0], pos
        _expect_branch_end(text, pos, starts[-1], ",")
        pos += 1
        in_right[-1] = True


def _expect_branch_end(text: str, pos: int, start: int, char: str) -> None:
    """Refuse a subtree that `char` does not follow at `pos`.

    The branch's subtrees start at `start`. A "," where its "}" is due
    is a third subtree, and a "}" where its "," is due leaves it one.
    """
    if text.startswith(char, pos):
        return
    if text.startswith(",}".replace(char, ""), pos):
        count = len(_split_unpaired_arguments(text[start:]))
        err_msg = f"a tr() branch takes two subtrees, {count} given"
        raise BTClibValueError(err_msg)
    raise BTClibValueError("unbalanced braces")


# inside a witness program an uncompressed key is unspendable, so
# BIP382 refuses one rather than describing a script nobody can spend;
# inside tr() the keys are x-only to begin with
def _no_uncompressed(context: str) -> bool:
    return context in {_P2WSH, _P2TR}


def _parse_pk(
    args: list[str], context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    key = _parse_key(
        args[0],
        prv_keys,
        x_only=context == _P2TR,
        compressed=_no_uncompressed(context),
        musig_allowed=False,
    )
    return PkDescriptor(key, network=network)


def _parse_pkh(
    args: list[str], context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    key = _parse_key(
        args[0],
        prv_keys,
        x_only=False,
        compressed=_no_uncompressed(context),
        musig_allowed=False,
    )
    return PkhDescriptor(key, network=network)


def _parse_wpkh(
    args: list[str], context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    key = _parse_key(
        args[0],
        prv_keys,
        x_only=False,
        compressed=True,
        musig_allowed=False,
    )
    return WpkhDescriptor(key, network=network)


def _parse_combo(
    args: list[str], context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    return ComboDescriptor(
        _parse_key(
            args[0],
            prv_keys,
            x_only=False,
            compressed=False,
            musig_allowed=False,
        ),
        network=network,
    )


def _parse_inner(
    argument: str, context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    """Return the expression of a ``sh()`` or ``wsh()`` `argument`.

    Core reads the expression up to its first "," or unmatched closing
    bracket before it finds what follows, so a fault of that expression
    comes first.
    """
    head = _split_unpaired_arguments(argument)[0]
    if len(head) < len(argument):
        _parse_expression(head, context, network, prv_keys)
    return _parse_expression(argument, context, network, prv_keys)


def _parse_sh(
    args: list[str], context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    inner = _parse_inner(args[0], _P2SH, network, prv_keys)
    return ShDescriptor(inner, network=network)


def _parse_wsh(
    args: list[str], context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    try:
        inner = _parse_inner(args[0], _P2WSH, network, prv_keys)
    except miniscript._CoreFallbackError as error:
        raise BTClibValueError("A function is needed within P2WSH") from error
    return WshDescriptor(inner, network=network)


def _parse_multi(
    name: str,
    text: str,
    context: str,
    network: str,
    prv_keys: dict[str, str],
) -> Descriptor:
    """Return the multisig `name` names, `text` what its parentheses enclose."""
    args = _split_unpaired_arguments(text)
    threshold = _read_multi_threshold(name, args[0])
    if len(args) < 2:
        raise BTClibValueError(f"{name}() takes a threshold and at least one key")
    keys, lengths = _read_multipath_keys(
        args[1:],
        lambda key: _parse_key(
            key,
            prv_keys,
            x_only=False,
            compressed=_no_uncompressed(context),
            musig_allowed=False,
        ),
    )
    _assert_multisig_end(name, text, args)
    if not 1 <= threshold <= len(keys):
        raise BTClibValueError(f"invalid k in k-of-n {name}: {threshold}")
    _assert_multi_size(name, keys, context)
    _assert_multipath_keys(lengths)
    return MultiDescriptor(threshold, keys, sort=name == "sortedmulti", network=network)


def _read_multi_threshold(name: str, text: str) -> int:
    """Return the threshold of a ``multi()`` or ``sortedmulti()``.

    Bitcoin Core reads it as a uint32 before it reads or counts the keys,
    so a threshold it cannot read is the fault named, whatever the keys
    hold. Leading zeros are allowed, as Core allows them. No refusal here
    quotes the threshold, which past 2**32-1 may be a private key in
    decimal.
    """
    if not _THRESHOLD.fullmatch(text):
        raise BTClibValueError(f"invalid {name}() threshold: digits expected")
    threshold = _int_from_digits(text, f"{name}() threshold")
    if threshold > 0xFFFFFFFF:
        raise BTClibValueError(f"invalid {name}() threshold: not in 0..2**32-1")
    return threshold


def _assert_multi_size(
    name: str, keys: tuple[KeyExpression, ...], context: str
) -> None:
    """Refuse the keys of a ``multi()`` that Bitcoin Core refuses where it sits.

    OP_CHECKMULTISIG's own bound first, which holds everywhere; then the
    bare output IsStandard relays, and the redeem script a ``sh()`` has to
    push in one element, which is what spending it takes. ``wsh()`` adds
    nothing: twenty keys are a witness script well inside its bound. The
    size is Core's own sum, a key and its push byte each, plus one byte
    each for the threshold, the count and OP_CHECKMULTISIG: the script's
    exact size up to sixteen keys, and over the limit past them anyway.
    """
    if len(keys) > MAX_PUBKEYS_PER_MULTISIG:
        err_msg = f"{name}() takes at most {MAX_PUBKEYS_PER_MULTISIG} keys"
        raise BTClibValueError(f"{err_msg}, {len(keys)} given")
    if context == _TOP and len(keys) > _MAX_BARE_MULTISIG_KEYS:
        err_msg = f"a bare {name}() takes at most {_MAX_BARE_MULTISIG_KEYS} keys"
        raise BTClibValueError(f"{err_msg}, {len(keys)} given")
    if context == _P2SH:
        size = 3 + sum((33 if key.is_compressed else 65) + 1 for key in keys)
        if size > MAX_SCRIPT_ELEMENT_SIZE:
            err_msg = f"{name}() inside sh() is a {size}-byte redeem script"
            limit = f"over the {MAX_SCRIPT_ELEMENT_SIZE}-byte push limit"
            raise BTClibValueError(f"{err_msg}, {limit}")


def _parse_ordered_multi(
    args: list[str], context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    return _parse_multi("multi", args[0], context, network, prv_keys)


def _parse_sorted_multi(
    args: list[str], context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    return _parse_multi("sortedmulti", args[0], context, network, prv_keys)


def _parse_tr(
    args: list[str], context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    """Return the ``tr()`` of `args`, its one argument the whole text.

    Core cuts the key as ``Expr`` does, then reads the tree after a ","
    up to its last "}", and only then finds what follows.
    """
    text = args[0]
    with _steps_compared():
        end = miniscript._leaf_end(text, 0)
        internal_key = _parse_key(
            text[:end], prv_keys, x_only=True, compressed=True, musig_allowed=True
        )
        tree = None
        if end < len(text):
            if text[end] != ",":
                raise BTClibValueError("unbalanced brackets")
            tree, end = _parse_tree(text, end + 1, prv_keys)
        if end < len(text):
            if text[end] == ",":
                count = len(_split_unpaired_arguments(text))
                err_msg = f"tr() takes a key and at most one tree, {count} given"
                raise BTClibValueError(err_msg)
            if text[end] in ")}":
                raise BTClibValueError("unbalanced brackets")
            raise BTClibValueError("unbalanced braces")
    return TrDescriptor(internal_key, tree, network=network)


def _parse_rawtr(
    args: list[str], context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    # one key and no tree: what Core's error says too, "rawtr(): only one
    # key expected", the function having nothing to put a second key in
    key = _parse_key(
        _one_argument(args, "rawtr"),
        prv_keys,
        x_only=True,
        compressed=True,
        musig_allowed=True,
    )
    return RawTrDescriptor(key, network=network)


def _parse_addr(
    args: list[str], context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    address = _one_argument(args, "addr")
    # the network of an addr() descriptor is the address's own: it is
    # written in the prefix, so a parameter could only contradict it
    #
    # `from_address` given no network answers a NETWORKS name, while
    # `ScriptPubKey.network` is typed `str | Network`
    found = cast("str", ScriptPubKey.from_address(address).network)
    return AddrDescriptor(address, network=found)


def _hex_bytes(text: str, fault: str) -> bytes:
    """Return the bytes of a hex argument, refusing an empty one or odd one.

    The hex is read as Bitcoin Core's `IsHex` reads it: whole bytes and
    nothing else. The message is Core's for ``raw()``, PR 30243's for
    ``rawnode()`` and ``rawleaf()``, and worded alike for ``rawpkh()``,
    which Core does not read. PR 30243 reads a ``rawnode()`` hash with
    `TryParseHex`, which skips whitespace and reads an empty text as no
    bytes: it accepts a hash with a space in it, and answers an empty one
    "256 bits digest expected". Both are refused here as not hex.

    The message never carries the text: a descriptor may be handed a
    secret where a script is expected.
    """
    if not _HEX.fullmatch(text):
        raise BTClibValueError(fault)
    return bytes.fromhex(text)


# what a script may weigh where the descriptor embeds it, as
# `ScriptPubKey.p2sh` and `ScriptPubKey.p2wsh` refuse it
_EMBEDDED_SCRIPT_SIZE = {_P2SH: MAX_SCRIPT_ELEMENT_SIZE, _P2WSH: MAX_SCRIPT_SIZE}


def _parse_raw(
    args: list[str], context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    script = _hex_bytes(_one_argument(args, "raw"), "Raw script is not hex")
    limit = _EMBEDDED_SCRIPT_SIZE.get(context)
    if limit is not None and len(script) > limit:
        err_msg = f"raw() inside {context} is {len(script)} bytes"
        raise BTClibValueError(f"{err_msg}, over the {limit}-byte limit")
    return RawDescriptor(script, network=network)


def _parse_rawpkh(
    args: list[str], context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    key_hash = _hex_bytes(_one_argument(args, "rawpkh"), "Rawpkh hash is not hex")
    if len(key_hash) != _KEY_HASH_SIZE:
        raise BTClibValueError("160 bits digest expected")
    return RawPkhDescriptor(key_hash, network=network)


def _parse_bare_leaf(args: list[str]) -> RawLeaf:
    """Return the leaf of a ``raw(HEX)`` inside a tree: version c0."""
    script = _hex_bytes(_one_argument(args, "raw"), "Raw script is not hex")
    return RawLeaf(script, bare=True)


def _parse_rawnode(args: list[str]) -> RawNode:
    """Return the node of a ``rawnode(HEX)``: 32 bytes."""
    digest = _hex_bytes(_one_argument(args, "rawnode"), "Rawnode hash is not hex")
    if len(digest) != _NODE_HASH_SIZE:
        raise BTClibValueError("256 bits digest expected")
    return RawNode(digest)


def _parse_rawleaf(args: list[str]) -> RawLeaf:
    """Return the leaf of a ``rawleaf(HEX)`` or ``rawleaf(HEX,VER)``.

    The messages and their order are those of Bitcoin Core's PR 30243.
    That PR reads the version with `TryParseHex`, which skips whitespace,
    so it accepts ``rawleaf(51, c0)``. Such a version is refused here as
    not hex.

    The version is one byte, and an odd one is refused: its low bit is the
    parity of the output key in a control block. Version 50 is accepted, as
    PR 30243 accepts it: consensus spends it, through a control block
    starting with 51, or with 50 when an annex follows, and BIP341 rules it
    out of a script tree only in a footnote.
    """
    script = _hex_bytes(args[0], "Leaf Script is not hex")
    if len(args) == 1:
        return RawLeaf(script)
    text = args[1]
    if text and not _HEX.fullmatch(text):
        raise BTClibValueError("Leaf Version is not hex")
    if len(text) > _LEAF_VERSION_DIGITS:
        raise BTClibValueError("Leaf Version is too large")
    if not text:
        raise BTClibValueError("Expected Leaf Version but not provided")
    version = int(text, 16)
    if version & 1:
        raise BTClibValueError("Leaf Version is invalid")
    if len(args) > _RAWLEAF_ARGUMENTS:
        err_msg = f"rawleaf() takes a script and a leaf version, {len(args)} given"
        raise BTClibValueError(err_msg)
    return RawLeaf(script, version)


# what a tree leaf or node of the raw family is read by
_RAW_TREE_PARSERS: dict[str, Callable[[list[str]], RawLeaf | RawNode]] = {
    "raw": _parse_bare_leaf,
    "rawnode": _parse_rawnode,
    "rawleaf": _parse_rawleaf,
}


# the functions whose one argument Core reads whole, a key or a script,
# "," and brackets included, so that a fault inside it is that argument's;
# and tr(), multi() and sortedmulti(), whose arguments Core cuts from the
# text itself
_WHOLE_ARGUMENT_FUNCTIONS = frozenset(
    {"pk", "pkh", "wpkh", "combo", "sh", "wsh", "tr", "multi", "sortedmulti"}
)

# every SCRIPT function, where BIP381 to BIP386 allow it, and what
# reads it. A table rather than a chain of comparisons because the
# position rule is the interesting half and belongs where it can be read
# beside the others
_PARSERS: dict[
    str,
    tuple[tuple[str, ...], Callable[[list[str], str, str, dict[str, str]], Descriptor]],
] = {
    "pk": ((_TOP, _P2SH, _P2WSH, _P2TR), _parse_pk),
    "pkh": ((_TOP, _P2SH, _P2WSH, _P2TR), _parse_pkh),
    "wpkh": ((_TOP, _P2SH), _parse_wpkh),
    "combo": ((_TOP,), _parse_combo),
    "sh": ((_TOP,), _parse_sh),
    "wsh": ((_TOP, _P2SH), _parse_wsh),
    "multi": ((_TOP, _P2SH, _P2WSH), _parse_ordered_multi),
    "sortedmulti": ((_TOP, _P2SH, _P2WSH), _parse_sorted_multi),
    "tr": ((_TOP,), _parse_tr),
    "rawtr": ((_TOP,), _parse_rawtr),
    "addr": ((_TOP,), _parse_addr),
    # inside tr() it is a leaf of a tree and `_parse_leaf` reads it
    "raw": ((_TOP, _P2SH, _P2WSH, _P2TR), _parse_raw),
    # inside tr() it is read as the miniscript fragment, as pkh() is
    "rawpkh": ((_TOP, _P2SH, _P2WSH, _P2TR), _parse_rawpkh),
}


def _parse_miniscript_expression(
    expression: str, context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    """Return the MiniscriptDescriptor of a BIP379 expression, sanity checked.

    Refused where the miniscript is not sane, which is what Bitcoin Core
    refuses too: a descriptor is what a wallet spends from, and an
    expression that can be satisfied without a signature, or whose witness
    a third party can rewrite, or whose timelocks contradict each other, is
    not one to hand a wallet. `miniscript.parse` on its own answers for the
    language and leaves the judgement to the caller.
    """
    if expression.startswith("multi("):
        _read_unclosed_multisig_keys(
            expression, _MINISCRIPT_CONTEXTS[context], prv_keys
        )
    with _steps_compared():
        node = _parse_miniscript(
            expression, _MINISCRIPT_CONTEXTS[context], prv_keys, _filed_preimages()
        )
        _assert_sane(node, prv_keys)
    return MiniscriptDescriptor(node, network=network)


# what Bitcoin Core names, outside wsh() and tr(), where an expression is
# neither a function nor a miniscript. At the top level Core quotes the
# expression, "'<expression>' is not a valid descriptor function": the
# message here leaves it out, since it can hold a private key
_NOT_A_FUNCTION = {
    _TOP: "top-level expression is not a valid descriptor function",
    _P2SH: "A function is needed within P2SH",
}
# and what it names there for a miniscript it reads
_MINISCRIPT_OUTSIDE = "Miniscript expressions can only be used in wsh or tr."


def _parse_no_function(
    expression: str, context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    """Return the miniscript of an expression no function takes, or refuse it.

    At the top level and inside ``sh()``, Core reads the expression as a
    tapscript miniscript too. It names a key it refuses. It refuses a
    miniscript it reads, of any type, sane or not, as one written outside
    ``wsh()`` and ``tr()``. Otherwise it names its fallback for the
    position.
    """
    if context in _MINISCRIPT_CONTEXTS:
        return _parse_miniscript_expression(expression, context, network, prv_keys)
    if expression.startswith("multi_a("):
        _read_unclosed_multisig_keys(expression, miniscript.TAPSCRIPT, prv_keys)
    try:
        _parse_miniscript(
            expression, miniscript.TAPSCRIPT, prv_keys, _filed_preimages()
        )
    except miniscript._CoreFallbackError as error:
        raise BTClibValueError(_NOT_A_FUNCTION[context]) from error
    except miniscript._TypeFaultError as error:
        raise BTClibValueError(_MINISCRIPT_OUTSIDE) from error
    raise BTClibValueError(_MINISCRIPT_OUTSIDE)


def _parse_expression(
    expression: str, context: str, network: str, prv_keys: dict[str, str]
) -> Descriptor:
    """Return the Descriptor of a SCRIPT expression, in its context.

    A miniscript is what an expression is where it is not one of the
    functions below: the two grammars share ``pk()``, ``pkh()`` and
    ``multi()``, which BIP379 says mean the same thing in both, so those
    are read as the descriptor functions they were before miniscript --
    which is Bitcoin Core's order too, its own parser trying the functions
    it knows and falling through to miniscript for the rest. Core's
    ``Func`` takes a name only where the text ends in ")", so a text that
    does not is read as a miniscript, whatever its name.
    """
    if not expression.endswith(")"):
        return _parse_no_function(expression, context, network, prv_keys)
    name = expression.partition("(")[0]
    if name == "musig":
        # a key expression where a SCRIPT one is expected: BIP390's own
        # invalid vectors write it as sh(musig()) and wsh(musig()), and
        # what is wrong with both is the position rather than the word
        _assert_musig_allowed(musig_allowed=False)
    if name in (*_TREE_FUNCTIONS, *_RAW_TREE_FUNCTIONS):
        # a tree leaf and no SCRIPT expression, so reaching this is the
        # position rule of BIP387 being broken: `_assert_position` says
        # which position it was, where "unknown function" would say the
        # language has no such word. Before the miniscript branch below,
        # which would answer for the same two names as a tapscript
        # fragment written where a p2wsh one belongs
        _assert_position(name, context, (_P2TR,))
    if name not in _PARSERS:
        return _parse_no_function(expression, context, network, prv_keys)
    name, arguments = _split_function(expression)
    allowed, parser = _PARSERS[name]
    _assert_position(name, context, allowed)
    # such a function splits nothing, so that a bracket in its argument is
    # a fault of what the argument holds, as Core reads it
    if name in _WHOLE_ARGUMENT_FUNCTIONS:
        return parser([arguments], context, network, prv_keys)
    return _read_split(arguments, lambda args: parser(args, context, network, prv_keys))


# the `preimages` the `parse` in progress files a ``preimage(HEX)`` in, None
# outside one. A context variable, as `key_expression._SET_ASIDE` is, rather
# than a parameter every SCRIPT expression's reader would have to carry for
# the readers of a miniscript among them
_PREIMAGES: ContextVar[dict[bytes, bytes] | None] = ContextVar(
    "_PREIMAGES", default=None
)


def _filed_preimages() -> dict[bytes, bytes]:
    """Return the mapping the `parse` in progress files a preimage in."""
    preimages = _PREIMAGES.get()
    return {} if preimages is None else preimages


def parse(
    descriptor: str,
    network: str = "mainnet",
    prv_keys: dict[str, str] | None = None,
    preimages: dict[bytes, bytes] | None = None,
) -> Descriptor:
    """Return the Descriptor of a descriptor string, checksum verified.

    A `str`, an output descriptor being text: what was neither reached
    `strip_checksum` untouched and left as an AttributeError about
    `partition`, or as a TypeError about mixing bytes and str -- neither
    of them a word about the descriptor that was passed.

    The network is asked for here rather than where a script is finally
    written: a name no network has was carried into the Descriptor and
    refused by the encoder that came to use it, which is a complaint
    about a key or an address, one call later than the argument that was
    wrong. Normalized as well, so that what the object holds is the name
    `network_from_name` would answer to.

    A WIF or an extended key of another network is refused here too, as
    Bitcoin Core's parser does. The test networks share one WIF prefix and
    one extended-key version.

    `prv_keys` is a mapping, and what is not one was walked anyway: the
    lookups below are `in` and `[]`, so a list of pairs answered "not
    found" for every key rather than saying it is not a mapping. `None`
    is asked for with it, that being the other type the annotation
    declares -- and one call rather than a branch, which is what keeps
    the two spellings of "a declared type" in one place.

    `preimages` is where a hash fragment's ``preimage(HEX)`` is filed,
    under its digest, as the module docstring says; it is checked the same
    way. What either mapping was filed with stays in it where the
    descriptor is then refused.
    """
    assert_type(descriptor, str, "descriptor")
    network = validated_network_name(network)
    assert_type(prv_keys, (Mapping, type(None)), "prv_keys")
    assert_type(preimages, (Mapping, type(None)), "preimages")

    token = _PREIMAGES.set({} if preimages is None else preimages)
    try:
        parsed = _parse_text(strip_checksum(descriptor), network, prv_keys)
    finally:
        _PREIMAGES.reset(token)
    for key in parsed.key_expressions:
        _assert_network(key, network)
    return parsed


def _parse_text(text: str, network: str, prv_keys: dict[str, str] | None) -> Descriptor:
    """Return the Descriptor of a descriptor text, its keys' networks unread."""
    # Core ends the descriptor at its first "," or unmatched closing bracket,
    # reads what comes before, and only then finds the rest
    head = _split_unpaired_arguments(text)[0]
    parsed = _parse_expression(
        head, _TOP, network, {} if prv_keys is None else prv_keys
    )
    if len(head) < len(text):
        if text[len(head)] == ",":
            raise BTClibValueError(
                "not a descriptor expression: expected name(arguments)"
            )
        raise BTClibValueError("unbalanced brackets")
    return parsed


def _normalized_key(key: KeyExpression, prv_keys: PrvKeys | None) -> KeyExpression:
    """Return the key expression re-rooted at its last hardened step.

    What makes a descriptor written with hardened derivation useful to a
    wallet that holds no private key: the extended key becomes the xpub
    at that step, and the hardened prefix moves into the key origin,
    where it is a statement about where the key came from rather than a
    derivation anybody has to perform.

    Three keys are returned as they are, with the symbol normalized and
    nothing else: one that is not extended, one whose path hardens
    nothing, and one whose wildcard is the hardened `/*h`. The last is
    Bitcoin Core's first branch too, and for the same reason -- the step
    that needs the private key is the one taken at every index, so there
    is no point to re-root to.

    A ``musig()`` is its participants normalized: its own path cannot
    harden, BIP390 forbidding it, so there is nothing else of it to
    re-root.
    """
    if key.participants:
        return replace(
            key,
            participants=tuple(
                _normalized_key(participant, prv_keys)
                for participant in key.participants
            ),
            hardening=_HARDENING,
        )
    if key.pub_key is not None or key.wildcard == HARDENED_OFFSET:
        return replace(key, hardening=_HARDENING)
    hardened = [i for i, step in enumerate(key.der_path) if step >= HARDENED_OFFSET]
    if not hardened:
        return replace(key, hardening=_HARDENING)

    xprv = prv_keys.get(key.xkey) if prv_keys else None
    if xprv is None:
        err_msg = "no private key to normalize the hardened derivation of a key"
        raise BTClibValueError(err_msg)
    last = hardened[-1] + 1
    prefix = list(key.der_path[:last])
    return replace(
        key,
        origin=BIP32KeyOrigin(
            key.origin.master_fingerprint if key.origin else fingerprint(key.xkey),
            [*(key.origin.der_path if key.origin else []), *prefix],
        ),
        # `xprv` is a string out of the caller's mapping, so the decode
        # validates it; the base58 round trip the public pair would make
        # between the two steps does not
        xkey=_xpub_from_xprv(
            _derive(key_data_from_bip32_key(xprv), prefix, None)
        ).b58encode(),
        der_path=key.der_path[last:],
        hardening=_HARDENING,
    )


def _mapped_node(
    node: Miniscript, key_map: Callable[[KeyExpression], KeyExpression]
) -> Miniscript:
    """Return the miniscript with `key_map` applied to every key in it.

    The two fields of a node that can hold one: its own KEY expressions
    and the subexpressions under it. What a node derives from those is
    `init=False`, so rebuilding bottom-up is the whole of it -- `replace`
    recomputes the type, the script size and the bounds from the keys
    that are now there.
    """
    return replace(
        node,
        subs=tuple(_mapped_node(sub, key_map) for sub in node.subs),
        keys=tuple(key_map(key) for key in node.keys),
    )


def _mapped_field(
    value: object, key_map: Callable[[KeyExpression], KeyExpression]
) -> object:
    """Return one field of a descriptor with every key in it mapped.

    Where a key can be: the field itself, a key of a ``multi_a()`` leaf, a
    key of a miniscript node or of one nested under it, a key of a
    fragment another one wraps, or an element of a script tree, which is a
    tuple of tuples. Nothing else in a fragment holds one, and a field
    added later that does will be walked here by construction -- which is
    the whole reason this is one function rather than a method per
    fragment.
    """
    if isinstance(value, KeyExpression):
        return key_map(value)
    if isinstance(value, MultiA):
        return replace(value, keys=tuple(key_map(key) for key in value.keys))
    if isinstance(value, Miniscript):
        return _mapped_node(value, key_map)
    if isinstance(value, Descriptor):
        return _mapped_keys(value, key_map)
    if isinstance(value, tuple):
        return tuple(_mapped_field(item, key_map) for item in value)
    return value


def _mapped_keys(
    descriptor: Descriptor, key_map: Callable[[KeyExpression], KeyExpression]
) -> Descriptor:
    """Return the descriptor with `key_map` applied to every key it holds."""
    changed: dict[str, Any] = {
        field.name: _mapped_field(getattr(descriptor, field.name), key_map)
        for field in fields(descriptor)
    }
    return replace(descriptor, **changed)


def normalized(descriptor: Descriptor, prv_keys: PrvKeys | None = None) -> Descriptor:
    """Return the descriptor with the xpub at each last hardened step.

    Bitcoin Core's `ToNormalizedString`, which is what `getdescriptorinfo`
    answers with and what an export to a watch-only wallet wants: every
    key of it derives from an xpub, so a holder of no private key can
    compute every script the descriptor describes.

    The private material is the caller's, as everywhere else here, and is
    needed for exactly the keys that have a hardened step to re-root at.
    Where one of those is missing this raises rather than handing back a
    descriptor that quietly still needs a key.

    The hardening symbol is `h` throughout the result, whichever was
    read: a normalized descriptor is a canonical spelling and not the one
    that came in, which is Core's rule -- "always use h for hardened
    derivation" is how its own interface states it.
    """
    _assert_prv_keys(prv_keys)
    return _mapped_keys(descriptor, lambda key: _normalized_key(key, prv_keys))


@contextmanager
def _private_spellings(
    prv_keys: PrvKeys | None, preimages: Preimages | None
) -> Iterator[None]:
    """Have `str` write the private spellings the two mappings hold."""
    keys_token = _PRINTED_PRV_KEYS.set(prv_keys)
    preimages_token = _PRINTED_PREIMAGES.set(preimages)
    try:
        yield
    finally:
        _PRINTED_PREIMAGES.reset(preimages_token)
        _PRINTED_PRV_KEYS.reset(keys_token)


def private_string(
    descriptor: Descriptor,
    prv_keys: PrvKeys | None = None,
    preimages: Preimages | None = None,
) -> str:
    """Return the descriptor as text, with its private spellings written back.

    Bitcoin Core's `ToPrivateString`, the private twin of `str`: an xpub
    that `prv_keys` names is written as the xprv filed under it, and a
    hash fragment as ``preimage(HEX)`` where `preimages` holds, under its
    digest, a preimage that fragment's hash takes to it. The two mappings
    are what `parse` hands back. What neither names is written as `str`
    writes it. An entry that is no xprv of its xpub is refused, and so is
    a preimage that is no 32 bytes.

    A WIF is written as its public key, as `str` writes it: `parse` files
    no WIF in `prv_keys`. ``preimage(HEX)`` is no BIP's syntax, as the
    `miniscript` module docstring says.

    Without the checksum, as `str`: `add_checksum` adds it.
    """
    assert_type(descriptor, Descriptor, "descriptor")
    _assert_prv_keys(prv_keys)
    assert_type(preimages, (Mapping, type(None)), "preimages")
    with _private_spellings(prv_keys, preimages):
        return str(descriptor)


def at_index(descriptor: Descriptor, index: int = 0) -> Descriptor:
    """Return the descriptor of one index, with no wildcard left in it.

    A ranged descriptor describes a range of scripts and names none of
    them; this names one, by writing the index the wildcard stands for
    into the derivation path -- ``.../0/*`` at index 5 becomes ``.../0/5``.
    The scripts are the same scripts: what changes is that the answer is
    a descriptor of one, which is what a reader wanting *this* script has
    to be given, an external signer displaying an address among them.

    Bitcoin Core's `deriveaddresses` is the same operation with the
    address as its answer rather than the descriptor.

    A descriptor with no wildcard comes back unchanged, index 0 being the
    only index it has; the participants of a ``musig()`` are walked too,
    the range being on either side of the aggregation and never on both.
    """
    descriptor._assert_index(index)

    def fixed(key: KeyExpression) -> KeyExpression:
        if key.participants:
            key = replace(
                key, participants=tuple(fixed(one) for one in key.participants)
            )
        if key.wildcard is None:
            return key
        return replace(
            key, der_path=(*key.der_path, key.wildcard + index), wildcard=None
        )

    return _mapped_keys(descriptor, fixed)


def _expanded_key(
    entries: dict[bytes, BIP32KeyOrigin],
    key: KeyExpression,
    index: int,
    network: str,
    prv_keys: PrvKeys | None,
) -> None:
    """Add a key and its origin to one fragment's entries, as Core does.

    A ``musig()`` adds its participants, then the aggregate. A key spelled
    twice in one fragment gets the entry `Descriptor.provider` describes,
    as Core's key providers do.
    """
    if key.participants:
        for participant in key.participants:
            _expanded_key(entries, participant, index, network, prv_keys)
        sec = key.sec(index, network, prv_keys)
        entries.setdefault(sec, _aggregate_origin(key, index, network, prv_keys))
        return
    sec = key.sec(index, network, prv_keys)
    if key.origin is None:
        entries.setdefault(sec, _derived_origin(key, index))
    else:
        entries[sec] = _derived_origin(key, index)


def _expanded_keys(
    fragment_keys: Iterable[KeyExpression],
    index: int,
    network: str,
    prv_keys: PrvKeys | None,
    keys: dict[bytes, BIP32KeyOrigin | None],
) -> None:
    """Add one fragment's keys to the provider's, an entry there winning."""
    entries: dict[bytes, BIP32KeyOrigin] = {}
    for key in fragment_keys:
        _expanded_key(entries, key, index, network, prv_keys)
    for sec, origin in entries.items():
        keys.setdefault(sec, origin)


def _expand(
    descriptor: Descriptor,
    index: int,
    prv_keys: PrvKeys | None,
    keys: dict[bytes, BIP32KeyOrigin | None],
    scripts: dict[bytes, None],
    trees: dict[bytes, tuple[bytes, bytes, Mapping[bytes, tuple[bytes, int]]]],
) -> None:
    """Fill a provider as Core's `ExpandHelper` and `MakeScripts` do."""
    network = descriptor.network
    if isinstance(descriptor, (ShDescriptor, WshDescriptor)):
        _expand(descriptor.inner, index, prv_keys, keys, scripts, trees)
        scripts[_embedded(descriptor, index, prv_keys)] = None
        return
    if isinstance(descriptor, TrDescriptor):
        _expanded_keys((descriptor.internal_key,), index, network, prv_keys, keys)
        if descriptor.tree is not None:
            for leaf in _tree_leaves(descriptor.tree):
                _expanded_keys(_leaf_keys(leaf), index, network, prv_keys, keys)
        output_key = descriptor._scripts(index, prv_keys)[0][2:]
        trees[output_key] = (
            descriptor.internal_key.sec(index, network, prv_keys)[1:],
            descriptor.taproot_merkle_root(index, prv_keys),
            {
                control: (script, leaf_version)
                for control, (script, leaf_version) in descriptor.taproot_leaf_scripts(
                    index, prv_keys
                ).items()
            },
        )
        return
    _expanded_keys(descriptor.key_expressions, index, network, prv_keys, keys)
    if isinstance(descriptor, ComboDescriptor):
        combo = descriptor._scripts(index, prv_keys)
        # the p2wpkh script, which only a compressed key has
        if len(combo) == 4:
            scripts[combo[2]] = None


# the context of the key inside wpkh(), where Core's `InferPubkey` refuses
# an uncompressed key
_P2WPKH = "wpkh()"

_OP_0 = 0x00
_OP_PUSHDATA1 = 0x4C
_OP_PUSHDATA4 = 0x4E
_OP_1 = 0x51
_OP_16 = 0x60
# what OP_1 to OP_16 and OP_1NEGATE push, which no push op code may
_OP_N_DATA = {bytes([n]) for n in (*range(1, 17), 0x81)}
_OP_CHECKSIG = 0xAC
_OP_CHECKSIGADD = 0xBA
_OP_CHECKMULTISIG = 0xAE
_OP_NUMEQUAL = 0x9C
_X_ONLY_SIZE = 32
_CONTROL_BASE_SIZE = 33
# the most leaves an inferred tree holds once its twins are written out
_MAX_INFERRED_LEAVES = 1024


def _ops(script: bytes) -> list[tuple[int, bytes, int]]:
    """Return each op code with its data and where it ends.

    The ops before a push that runs past the end of the script, where
    Core's `GetOp` stops.
    """
    ops: list[tuple[int, bytes, int]] = []
    for op_code, start, stop in op_code_spans(script):
        prefix = 1
        if _OP_PUSHDATA1 <= op_code <= _OP_PUSHDATA4:
            prefix += 2 ** (op_code - _OP_PUSHDATA1)
        data = script[start + prefix : stop] if op_code <= _OP_PUSHDATA4 else b""
        ops.append((op_code, data, stop))
    return ops


def _number(op_code: int, data: bytes, low: int, high: int) -> int | None:
    """Return Core's `GetScriptNumber`: an OP_n or a minimal number push.

    A number is at most four bytes, which an op code pushes minimally only
    where it is the length of the data and the data is not what an OP_n or
    OP_1NEGATE pushes.
    """
    if _OP_1 <= op_code <= _OP_16:
        number: int | None = op_code - _OP_1 + 1
    elif op_code != len(data) or data in _OP_N_DATA:
        return None
    else:
        number = _script_number((op_code, data))
    return number if number is not None and low <= number <= high else None


def _sec_size(sec: bytes) -> int:
    """Return the size Core's `CPubKey::GetLen` gives the key's first byte."""
    if not sec:
        return -1
    return {2: 33, 3: 33, 4: 65, 6: 65, 7: 65}.get(sec[0], -1)


def _multisig(script: bytes) -> tuple[int, list[bytes]] | None:
    """Return the threshold and keys of a bare multisig: `MatchMultisig`."""
    if not script or script[-1] != _OP_CHECKMULTISIG:
        return None
    ops = _ops(script)
    if not ops:
        return None
    threshold = _number(ops[0][0], ops[0][1], 1, MAX_PUBKEYS_PER_MULTISIG)
    if threshold is None:
        return None
    position = 1
    keys: list[bytes] = []
    while position < len(ops) and _sec_size(ops[position][1]) == len(ops[position][1]):
        keys.append(ops[position][1])
        position += 1
    if position == len(ops):
        return None
    op_code, data, stop = ops[position]
    count = _number(op_code, data, threshold, MAX_PUBKEYS_PER_MULTISIG)
    if count != len(keys) or stop + 1 != len(script):
        return None
    return threshold, keys


def _multi_a(script: bytes) -> tuple[int, list[bytes]] | None:
    """Return a ``multi_a()``'s threshold and x-only keys: `MatchMultiA`."""
    if not script or script[0] != _X_ONLY_SIZE or script[-1] != _OP_NUMEQUAL:
        return None
    keys: list[bytes] = []
    position = 0
    while len(script) - position >= _X_ONLY_SIZE + 2:
        if script[position] != _X_ONLY_SIZE:
            return None
        keys.append(script[position + 1 : position + 33])
        position += 33
        if script[position] != (_OP_CHECKSIGADD if keys[1:] else _OP_CHECKSIG):
            return None
        position += 1
    if not keys or len(keys) > _MAX_MULTI_A_KEYS:
        return None
    ops = _ops(script[position:])
    if not ops or ops[0][2] != len(script) - position - 1:
        return None
    threshold = _number(ops[0][0], ops[0][1], 1, len(keys))
    return None if threshold is None else (threshold, keys)


def _solved(script: bytes) -> tuple[str, list[bytes]]:  # noqa: PLR0911
    """Return the kind of script and what it holds: Core's `Solver`.

    The kinds `infer_descriptor` tells apart. A null data and a
    non-standard script are both "nonstandard" here, and an anchor and a
    witness program of an unknown version are both "witness_unknown".
    """
    size = len(script)
    if size == 23 and script[:2] == b"\xa9\x14" and script[22] == 0x87:
        return "scripthash", [script[2:22]]
    first = script[:1]
    if (
        4 <= size <= 42
        and (first == b"\x00" or _OP_1 <= script[0] <= _OP_16)
        and script[1] + 2 == size
    ):
        version, program = (0 if first == b"\x00" else script[0] - 0x50), script[2:]
        if version == 0 and len(program) in {20, 32}:
            kind = (
                "witness_v0_keyhash" if len(program) == 20 else "witness_v0_scripthash"
            )
            return kind, [program]
        if version == 1 and len(program) == _X_ONLY_SIZE:
            return "witness_v1_taproot", [program]
        return ("witness_unknown" if version else "nonstandard"), []
    if size in {35, 67} and script[0] == size - 2 and script[-1] == _OP_CHECKSIG:
        pub_key = script[1:-1]
        if _sec_size(pub_key) == len(pub_key):
            return "pubkey", [pub_key]
    if size == 25 and script[:3] == b"\x76\xa9\x14" and script[23:] == b"\x88\xac":
        return "pubkeyhash", [script[3:23]]
    multisig = _multisig(script)
    if multisig is not None:
        return "multisig", [bytes([multisig[0]]), *multisig[1]]
    return "nonstandard", []


@dataclass(frozen=True)
class _Known:
    """A provider's entries, indexed the ways `infer_descriptor` asks."""

    keys: Mapping[bytes, BIP32KeyOrigin | None]
    scripts: dict[bytes, bytes]
    # hash160 of a key, and of its x-only form: a tapscript's pkh()
    # hashes the 32 bytes, and Core files a tapscript key under that hash
    by_hash: dict[bytes, bytes]
    by_x_only_hash: dict[bytes, bytes]
    trees: Mapping[bytes, tuple[bytes, bytes, Mapping[bytes, tuple[bytes, int]]]]

    @classmethod
    def of(cls, provider: Provider) -> _Known:
        by_hash: dict[bytes, bytes] = {}
        by_x_only_hash: dict[bytes, bytes] = {}
        for sec in provider.keys:
            by_hash.setdefault(hash160(sec), sec)
            if len(sec) == 33:
                by_x_only_hash.setdefault(hash160(sec[1:]), sec)
        return cls(
            provider.keys,
            {hash160(script): script for script in reversed(provider.scripts)},
            by_hash,
            by_x_only_hash,
            provider.trees,
        )


def _inferred_key(sec: bytes, context: str, known: _Known) -> KeyExpression | None:
    """Return a key behind its origin, Core's `InferPubkey`.

    None for a hybrid key, and for an uncompressed one where only a
    compressed one may be.
    """
    if _sec_size(sec) != len(sec) or sec[0] > 4:
        return None
    if context not in (_TOP, _P2SH) and len(sec) != 33:
        return None
    return KeyExpression(origin=known.keys.get(sec), pub_key=sec)


def _inferred_x_only(x_only: bytes, known: _Known) -> KeyExpression:
    """Return an x-only key behind its origin, Core's `InferXOnlyPubkey`.

    The origin of either key of that x, the even one first.
    """
    origin = known.keys.get(b"\x02" + x_only)
    if origin is None:
        origin = known.keys.get(b"\x03" + x_only)
    return KeyExpression(origin=origin, pub_key=b"\x02" + x_only, x_only=True)


def _inferred_node(node: Miniscript, known: _Known) -> Miniscript | None:
    """Return the miniscript with its keys behind their origins.

    Core's `KeyParser::FromPKBytes` and `FromPKHBytes`. A tapscript
    ``pkh()`` holds the key Core filed under the hash, written whole. The
    tree is walked by `_tree_eval`, which says why it does not recurse.
    """
    tapscript = node.context == miniscript.TAPSCRIPT

    def up(
        _: None, sub: Miniscript, subs: list[Miniscript | None]
    ) -> Miniscript | None:
        inferred_subs = [inferred for inferred in subs if inferred is not None]
        if len(inferred_subs) != len(subs):
            return None
        keys: list[KeyExpression] = []
        for key in sub.keys:
            sec = cast("bytes", key.pub_key)
            inferred: KeyExpression | None
            if tapscript and sub.fragment == "pk_h":
                whole = known.by_x_only_hash[hash160(sec[1:])]
                inferred = _inferred_key(whole, _P2TR, known)
            elif tapscript:
                inferred = _inferred_x_only(sec[1:], known)
            else:
                inferred = _inferred_key(sec, _P2WSH, known)
            if inferred is None:
                return None
            keys.append(inferred)
        return replace(sub, subs=tuple(inferred_subs), keys=tuple(keys))

    return _tree_eval(node, None, lambda *_: None, up)


def _inferred_miniscript(
    script: bytes, context: str, known: _Known
) -> Miniscript | None:
    """Return the sane miniscript a script is, None where it is none."""
    tapscript = context == _P2TR
    held = known.by_x_only_hash if tapscript else known.by_hash
    # only what the script pushes: this runs once per leaf, whatever the
    # number of keys the provider holds
    key_hashes: dict[Octets, Octets] = {
        data: held[data][1:] if tapscript else held[data]
        for _, data, _ in _ops(script)
        if data in held
    }
    try:
        read = _miniscript_from_script(
            script, _MINISCRIPT_CONTEXTS[context], key_hashes
        )
        node = _inferred_node(read, known)
    except BTClibValueError:
        return None
    return node if node is not None and node.is_sane() else None


def _inferred_leaf(script: bytes, known: _Known) -> DescriptorLeaf | None:
    """Return the leaf a tapscript is, Core's `InferScript` in a ``tr()``."""
    if len(script) == 34 and script[0] == _X_ONLY_SIZE and script[33] == _OP_CHECKSIG:
        return _inferred_x_only(script[1:33], known)
    multi_a = _multi_a(script)
    if multi_a is not None:
        threshold, x_only_keys = multi_a
        keys = tuple(_inferred_x_only(x_only, known) for x_only in x_only_keys)
        return MultiA(threshold, keys)
    return _inferred_miniscript(script, _P2TR, known)


def _merkle_root(control: bytes, leaf: bytes) -> bytes:
    """Return the root a control block proves a leaf hash under."""
    node = leaf
    for start in range(_CONTROL_BASE_SIZE, len(control), 32):
        sibling = control[start : start + 32]
        node = tagged_hash(b"TapBranch", min(node, sibling) + max(node, sibling))
    return node


@dataclass
class _TreeNode:
    """A node of the tree `_taproot_tree` rebuilds: Core's `TreeNode`.

    A hash not known is None, where Core's is its null hash: 32 zero bytes
    are a hash a ``rawnode()`` can hold, which a proof has to tell from none.
    """

    hash: bytes | None = None
    sub: list[_TreeNode] = field(default_factory=list)
    leaf: tuple[bytes, int] | None = None
    explored: bool = False
    inner: bool = False


def _proved_leaf(
    script: bytes, leaf_version: int, control: bytes, merkle_root: bytes
) -> bytes | None:
    """Return the leaf hash a control block proves under the root, or None.

    Core skips a record that proves nothing, rather than refusing the tree.
    """
    if not 0 <= leaf_version <= 0xFF or leaf_version & 1:
        return None
    levels, rest = divmod(len(control) - _CONTROL_BASE_SIZE, 32)
    if not 0 <= levels <= MAX_TREE_DEPTH or rest or control[0] & 0xFE != leaf_version:
        return None
    hashed = leaf_hash(leaf_version, script)
    return hashed if _merkle_root(control, hashed) == merkle_root else None


def _placed(
    root: _TreeNode, leaf: tuple[bytes, int], control: bytes, hashed: bytes
) -> bool:
    """Put a proven leaf where its control block says, False on a clash.

    The control block lists the leaf's siblings from the leaf up, and the
    walk goes down from the root.
    """
    node = root
    levels = (len(control) - _CONTROL_BASE_SIZE) // 32
    for depth in range(levels):
        if node.explored and not node.inner:
            return False
        start = _CONTROL_BASE_SIZE + (levels - 1 - depth) * 32
        sibling = control[start : start + 32]
        if not node.sub:
            node.explored = node.inner = True
            node.sub = [_TreeNode(), _TreeNode(sibling)]
            node = node.sub[0]
            continue
        for i in (0, 1):
            if node.sub[i].hash == sibling or (
                node.sub[i].hash is None and node.sub[1 - i].hash != sibling
            ):
                node.sub[i].hash = sibling
                node = node.sub[1 - i]
                break
        else:
            return False
    if node.sub:
        return False
    node.explored, node.inner = True, False
    node.leaf, node.hash = leaf, hashed
    return True


def _reads_back(leaf: DescriptorLeaf) -> bool:
    """Return True where `parse` reads the text of an inferred leaf.

    Core's `InferScript` asks less than its parser does: a key need not be
    a point, nor a sane miniscript satisfiable. The parser's own reading is
    what answers here, so there is no second copy of its rules.
    """
    try:
        _parse_tree(_tree_expression(leaf), 0, {})
    except (BTClibValueError, EccValueError):
        return False
    return True


def _inferred_leaf_or_raw(script: bytes, version: int, known: _Known) -> DescriptorTree:
    """Return the tree a proven leaf is: what Core infers, else a ``rawleaf()``.

    A leaf of another version is a ``rawleaf()`` whatever its script is, the
    version being part of what the output key commits to. So is a leaf of
    version c0 that infers to nothing else, or to what `parse` refuses. A
    leaf with no script is the node of its hash: ``rawleaf()`` with no HEX
    does not parse, and the node commits to the same output key.
    """
    if not script:
        return RawNode(leaf_hash(version, script))
    leaf = _inferred_leaf(script, known) if version == _TAPSCRIPT_LEAF_VERSION else None
    return leaf if leaf is not None and _reads_back(leaf) else RawLeaf(script, version)


def _inferred_subtree(
    node: _TreeNode, known: _Known
) -> tuple[DescriptorTree, bytes, bool]:
    """Return the tree under a rebuilt node, its hash, and if it is whole.

    A node no proof went through is a ``rawnode()`` of its hash.

    Whole is what Core rebuilds: no raw form in the subtree, except a right
    node whose left sibling hashes the same under a parent whose hash a
    proof named. Its control blocks are its sibling's, so only one of them
    was rebuilt. `_with_twins` writes it out.
    """
    if not node.explored:
        # the root or a sibling a control block named, each with its hash
        digest = cast("bytes", node.hash)
        return RawNode(digest), digest, False
    if not node.inner:
        script, version = cast("tuple[bytes, int]", node.leaf)
        leaf = _inferred_leaf_or_raw(script, version, known)
        whole = not isinstance(leaf, (RawLeaf, RawNode))
        return leaf, leaf_hash(version, script), whole
    left_node, right_node = node.sub
    left, left_hash, left_whole = _inferred_subtree(left_node, known)
    right, right_hash, right_whole = _inferred_subtree(right_node, known)
    twin = node.hash is not None and not right_node.explored and right_hash == left_hash
    low, high = sorted((left_hash, right_hash))
    digest = tagged_hash(b"TapBranch", low + high)
    return (left, right), digest, left_whole and (right_whole or twin)


def _with_twins(tree: DescriptorTree) -> DescriptorTree:
    """Return a whole tree with each ``rawnode()`` its left sibling again.

    The only ``rawnode()`` of a whole tree is a twin. The two sides share
    one object, so this takes one step per node rebuilt; what doubles at
    each twin is the text.
    """
    if not isinstance(tree, tuple):
        return tree
    left = _with_twins(tree[0])
    return left, left if isinstance(tree[1], RawNode) else _with_twins(tree[1])


def _written_leaves(tree: DescriptorTree) -> int:
    """Return the number of leaves of a whole tree with its twins written out.

    One step per node rebuilt, as `_with_twins` takes.
    """
    if not isinstance(tree, tuple):
        return 1
    left = _written_leaves(tree[0])
    return left + (left if isinstance(tree[1], RawNode) else _written_leaves(tree[1]))


def _taproot_tree(
    merkle_root: bytes,
    leaf_scripts: Mapping[bytes, tuple[bytes, int]],
    known: _Known,
) -> DescriptorTree | None:
    """Return the tree a merkle root and its proven leaves describe.

    Core's `InferTaprootTree`, with a node it knows by its hash only kept
    as a ``rawnode()`` and not given up on. None where there is no root,
    which is no tree. The root alone where the records contradict each
    other, which only a hash collision does.

    The records are read by script and then by control block, shortest
    first, which is the order of the map and the sets Core holds them in.
    """
    if not merkle_root:
        return None
    by_leaf: dict[tuple[bytes, int], list[bytes]] = {}
    for control, leaf in leaf_scripts.items():
        by_leaf.setdefault(leaf, []).append(control)
    proven: list[tuple[tuple[bytes, int], bytes, bytes]] = []
    for (script, leaf_version), controls in sorted(by_leaf.items()):
        for control in sorted(controls, key=lambda c: (len(c), c)):
            hashed = _proved_leaf(script, leaf_version, control, merkle_root)
            if hashed is not None:
                proven.append(((script, leaf_version), control, hashed))
    root = _rebuilt(merkle_root, proven) or _TreeNode(merkle_root)
    tree, _, whole = _inferred_subtree(root, known)
    if whole and _written_leaves(tree) <= _MAX_INFERRED_LEAVES:
        return _with_twins(tree)
    return tree


def _rebuilt(
    merkle_root: bytes, proven: list[tuple[tuple[bytes, int], bytes, bytes]]
) -> _TreeNode | None:
    """Return the tree proven leaves rebuild under the root, None on a clash.

    Each is a leaf, a control block proving it under `merkle_root`, and its
    leaf hash. Two proofs under one root clash only through a collision of
    hashes.
    """
    root = _TreeNode(merkle_root)
    for leaf, control, hashed in proven:
        if not _placed(root, leaf, control, hashed):
            return None
    return root


def _commits_to(output_key: bytes, internal_key: bytes, merkle_root: bytes) -> bool:
    """Return True where the key and the root tweak to the output key."""
    try:
        tweaked = output_pubkey_from_merkle_root_var(internal_key, merkle_root)[0]
    except ValueError:
        return False
    return tweaked == output_key


def _inferred_tr(
    output_key: bytes, known: _Known, network: str
) -> TrDescriptor | RawTrDescriptor | None:
    """Return the ``tr()`` of an output key that commits to what is known.

    The internal key and the merkle root the provider holds for it, with
    the leaves that can be proved under the root and the nodes that cannot.
    Else the ``rawtr()`` of a point.
    """
    if output_key in known.trees:
        internal_key, merkle_root, leaf_scripts = known.trees[output_key]
        if _commits_to(output_key, internal_key, merkle_root):
            return TrDescriptor(
                _inferred_x_only(internal_key, known),
                _taproot_tree(merkle_root, leaf_scripts, known),
                network=network,
            )
    try:
        point_from_bip340pub_key_var(output_key)
    except ValueError:
        return None
    return RawTrDescriptor(_inferred_x_only(output_key, known), network=network)


def _inferred(  # noqa: C901, PLR0911, PLR0912  # sourcery skip: low-code-quality
    script: bytes, context: str, known: _Known, network: str
) -> Descriptor | None:
    """Return the descriptor of a script in its context, Core's `InferScript`.

    The context being anything but a ``tr()`` leaf, which `_inferred_leaf`
    reads.
    """
    kind, data = _solved(script)
    key_contexts = (_TOP, _P2SH, _P2WSH)
    if kind == "pubkey" and context in key_contexts:
        key = _inferred_key(data[0], context, known)
        if key is not None:
            return PkDescriptor(key, network=network)
    if kind == "pubkeyhash" and context in key_contexts and data[0] in known.by_hash:
        key = _inferred_key(known.by_hash[data[0]], context, known)
        if key is not None:
            return PkhDescriptor(key, network=network)
    if (
        kind == "witness_v0_keyhash"
        and context in (_TOP, _P2SH)
        and data[0] in known.by_hash
    ):
        key = _inferred_key(known.by_hash[data[0]], _P2WPKH, known)
        if key is not None:
            return WpkhDescriptor(key, network=network)
    if kind == "multisig" and context in key_contexts:
        keys = [_inferred_key(sec, context, known) for sec in data[1:]]
        if None not in keys:
            return MultiDescriptor(
                data[0][0], tuple(cast("list[KeyExpression]", keys)), network=network
            )
    if kind == "scripthash" and context == _TOP and data[0] in known.scripts:
        inner = _inferred(known.scripts[data[0]], _P2SH, known, network)
        if inner is not None:
            return ShDescriptor(inner, network=network)
    if kind == "witness_v0_scripthash" and context in (_TOP, _P2SH):
        witness_script = known.scripts.get(ripemd160(data[0]))
        if witness_script is not None:
            inner = _inferred(witness_script, _P2WSH, known, network)
            if inner is not None:
                return WshDescriptor(inner, network=network)
    if kind == "witness_v1_taproot" and context == _TOP:
        tr = _inferred_tr(data[0], known, network)
        if tr is not None:
            return tr
    if context == _P2WSH:
        node = _inferred_miniscript(script, _P2WSH, known)
        if node is not None:
            return MiniscriptDescriptor(node, network=network)
    return _addr_or_raw(script, kind, network) if context == _TOP else None


def _addr_or_raw(script: bytes, kind: str, network: str) -> Descriptor:
    """Return the ``addr()`` of an output of a kind with one, else ``raw()``."""
    if kind.startswith(("witness", "pubkeyhash", "scripthash")):
        return AddrDescriptor(ScriptPubKey(script, network).address, network=network)
    return RawDescriptor(script, network=network)


def _parses_to(text: str, script: bytes, network: str) -> bool:
    """Return True where `parse` reads a descriptor text as the script."""
    try:
        parsed = parse(text, network)
    except (BTClibValueError, EccValueError):
        return False
    return parsed.script_pub_key().script == script


def _assert_provider(provider: Provider) -> None:
    """Refuse a provider whose entries are not of the types it declares."""
    assert_type(provider, Provider, "provider")
    assert_type(provider.keys, Mapping, "provider keys")
    for sec, origin in provider.keys.items():
        assert_type(sec, bytes, "provider key")
        assert_type(origin, (BIP32KeyOrigin, type(None)), "provider key origin")
    assert_type(provider.scripts, tuple, "provider scripts")
    for script in provider.scripts:
        assert_type(script, bytes, "provider script")
    assert_type(provider.trees, Mapping, "provider trees")
    for output_key, spend in provider.trees.items():
        assert_type(output_key, bytes, "taproot output key")
        assert_type(spend, tuple, "taproot spend data")
        if len(spend) != 3:
            raise BTClibValueError(f"invalid taproot spend data: {len(spend)} items")
        internal_key, merkle_root, leaf_scripts = spend
        assert_type(internal_key, bytes, "taproot internal key")
        assert_type(merkle_root, bytes, "taproot merkle root")
        assert_type(leaf_scripts, Mapping, "taproot leaf scripts")
        sizes = (len(output_key), len(internal_key), len(merkle_root) or 32)
        if sizes != (_X_ONLY_SIZE,) * 3:
            raise BTClibValueError("invalid taproot key or merkle root size")
        for control, leaf in leaf_scripts.items():
            assert_type(control, bytes, "control block")
            assert_type(leaf, tuple, "leaf script")
            if len(leaf) != 2:
                raise BTClibValueError(f"invalid leaf script: {len(leaf)} items")
            assert_type(leaf[0], bytes, "leaf script")
            assert_type(leaf[1], int, "leaf version")


def infer_descriptor(
    script: Octets, provider: Provider, network: str = "mainnet"
) -> str:
    """Return a script's descriptor, checksummed: Core's `InferDescriptor`.

    What `scantxoutset` answers in each `unspents[].desc`, at
    bitcoin/bitcoin@f0de87f040 (the v32.1 tag), read from the script and
    from what `provider` knows, except where this says otherwise. Each key
    is the public key the script holds, behind its origin where the
    provider knows one. A sorted multisig is a ``multi()`` of its keys in
    the script's order. A key in a ``tr()`` is x-only, except in a
    ``pkh()``, and the leaves are in the order Core rebuilds them. A
    script nothing else describes is an ``addr()`` where it has an address
    -- a ``rawtr()`` for a p2tr output whose key is a point -- and a
    ``raw()`` otherwise. An empty script is a ``raw()`` that `parse` refuses,
    as Core's parser does.

    Where `parse` does not read the descriptor inferred here back to the
    same script, the answer is the ``addr()`` of the output, or its
    ``raw()`` where it has no address.

    A p2tr output whose internal key and merkle root the provider knows is
    a ``tr()`` of the tree it can rebuild, whatever is missing from it: a
    leaf that infers to nothing else, that has another leaf version, or
    that infers to what `parse` refuses, is a ``rawleaf()``, and a leaf
    with no script, or a subtree none of whose leaves is proven, is a
    ``rawnode()``. So is the whole tree where the records contradict each
    other, which only a hash collision does.

    Two equal subtrees share their control blocks, so one is rebuilt. The
    other is written out in a tree Core rebuilds with no raw form in it,
    where the tree then holds at most 1024 leaves, and is a ``rawnode()``
    of its hash in any other tree. Core writes it out whatever the number
    of leaves, which a twin at every other level of the tree doubles with
    each record.

    At that tag, Core answers a descriptor its own parser refuses, such as
    a ``pkh()`` of a key that is no point, a ``wsh()`` of a miniscript that
    is not satisfiable, or a bare ``multi()`` of more than three keys. It
    answers a ``rawtr()`` for a tree with a ``rawnode()`` in it, or with a
    ``rawleaf()`` that infers to nothing else or has another leaf version.
    For a leaf `parse` refuses, such as a key that is no point or a
    miniscript that is not satisfiable, it answers a ``tr()`` that holds
    the leaf, and that its own parser refuses. Core's PR 30243 infers the
    root of a tree it cannot rebuild as one ``rawnode()``, and drops the
    leaf version of a leaf it infers as another descriptor.
    """
    script = bytes_from_octets(script)
    _assert_provider(provider)
    network = validated_network_name(network)
    inferred = str(_inferred(script, _TOP, _Known.of(provider), network))
    if not _parses_to(inferred, script, network):
        inferred = str(_addr_or_raw(script, _solved(script)[0], network))
    return add_checksum(inferred)


def multipath_descriptors(descriptor: str, network: str | None = None) -> list[str]:
    """Return the single-path descriptors of a BIP389 multipath one.

    A descriptor with no ``<a;b>`` step is one descriptor, returned
    checksummed and otherwise unchanged. One with such steps is as many
    descriptors as a step has elements, the first taking the first
    element of every step, the second the second, and so on -- which is
    what makes the two-element form a receiving chain and a change chain.

    The expansion is textual, as BIP389 defines it. `parse` reads the
    descriptor first, each step on its first path, and then each result,
    so a step Core refuses is refused by `parse` as Core refuses it. That
    is a step that is not a whole path element of a key outside its
    origin, that has fewer than two elements, a repeated one or one that
    is no index (``<2;x>``), that shares its key path with another step
    or with a stray "<" or ">", or that is in a ``musig()`` whose path and
    participants both hold one.

    Steps of different length are refused by `parse` where Core refuses
    them: once it has read a ``multi()``, a ``multi_a()`` or a ``musig()``,
    and at the end of a miniscript or of a ``tr()``.

    Before the expansion, each key with a step has every hardened step
    written in one symbol, ``h`` or ``'``: the one Bitcoin Core writes all
    of the key's paths with, chosen from the whole key. One path alone can
    choose another, and `str` of a result writes the symbol its own path
    chooses.

    The keys are read in `network` as `parse` reads them. With none, the
    network of a key is not checked, which is `parse`'s call to make on the
    result.
    """
    text = strip_checksum(descriptor)

    def read(single: str) -> None:
        if network is None:
            _parse_text(single, "mainnet", None)
        else:
            parse(single, network)

    # a step is read on its first path, so that the text is read whole
    with _steps_set_aside() as set_aside:
        read(text)
    if not set_aside:
        return [add_checksum(text)]
    text = _KEY_WITH_STEP.sub(lambda key: _one_hardening(key[0]), text)
    steps = _multipath_steps(text)
    descriptors = []
    # `parse` has refused steps of different length
    for i in range(len(steps[0][2])):
        pieces = []
        last = 0
        for start, end, items in steps:
            pieces += [text[last:start], items[i]]
            last = end
        pieces.append(text[last:])
        single = "".join(pieces)
        read(single)
        descriptors.append(add_checksum(single))
    return descriptors


_POLICY_TOP_LEVEL = (
    PkhDescriptor,
    WpkhDescriptor,
    ShDescriptor,
    WshDescriptor,
    TrDescriptor,
)


def _raw_name_in(tree: DescriptorTree) -> str | None:
    """Return the name of the first ``raw`` function in a tree, else None."""
    if isinstance(tree, tuple):
        return _raw_name_in(tree[0]) or _raw_name_in(tree[1])
    if isinstance(tree, (RawLeaf, RawNode)):
        return str(tree).partition("(")[0]
    if isinstance(tree, Miniscript) and _has_raw_key_hash(tree):
        return "rawpkh"
    return None


def _assert_policy_no_raw(descriptor: Descriptor) -> None:
    """Refuse a ``raw()``, ``rawpkh()``, ``rawleaf()`` or ``rawnode()`` inside.

    A wallet-policy template is a script with its keys left out, and these
    are the functions that hold a script, a hash or a node where a key
    would be.
    """
    name = None
    wrapped = descriptor
    while isinstance(wrapped, (ShDescriptor, WshDescriptor)):
        wrapped = wrapped.inner
    if wrapped is not descriptor and isinstance(wrapped, _SCRIPT_ONLY):
        name = str(wrapped).partition("(")[0]
    elif isinstance(wrapped, MiniscriptDescriptor) and _has_raw_key_hash(wrapped.node):
        name = "rawpkh"
    elif isinstance(descriptor, TrDescriptor) and descriptor.tree is not None:
        name = _raw_name_in(descriptor.tree)
    if name is not None:
        err_msg = f"{name}() in a wallet policy: BIP388 has no template for it"
        raise BTClibValueError(err_msg)


def _assert_policy_top_level(descriptor: Descriptor) -> None:
    """Refuse a descriptor whose own function BIP388 does not list.

    ``sh``, ``wsh``, ``pkh``, ``wpkh`` and ``tr`` are the SCRIPT functions
    BIP388 allows at the top level, the miniscript templates it also lists
    living inside ``wsh`` or ``tr`` only; ``multi``/``sortedmulti`` are
    SCRIPT functions too, inside ``sh`` or ``wsh`` only, so a top-level one
    is refused. ``combo``, ``addr``, ``raw``, ``rawpkh``, a bare ``pk`` and
    Core's own ``rawtr`` extension are not BIP388's, and none of them is a
    policy an external signer's registration flow reads.
    Two nestings are checked here: a ``pk()`` directly inside ``sh()``, a
    miniscript where BIP388 allows ``wsh`` or ``tr`` only; and the
    functions that take a script or a node as bytes -- ``raw()`` and
    ``rawpkh()`` inside ``sh()`` or ``wsh()``, ``raw()``, ``rawpkh()``,
    ``rawleaf()`` and ``rawnode()`` inside ``tr()`` -- which BIP388 has no
    template for, and which `parse` accepts.
    `parse` refuses every other nesting BIP388 forbids, reading ``pkh``
    under ``tr`` as BIP379's miniscript fragment.
    """
    _assert_policy_no_raw(descriptor)
    if isinstance(descriptor, ShDescriptor) and isinstance(
        descriptor.inner, PkDescriptor
    ):
        err_msg = (
            "pk() inside sh(): BIP388 allows a miniscript inside wsh() or tr() only"
        )
        raise BTClibValueError(err_msg)
    if isinstance(descriptor, MultiDescriptor):
        name = "sortedmulti" if descriptor.sort else "multi"
        err_msg = (
            f"{name}() at the top level: BIP388 allows it inside sh() or wsh() only"
        )
        raise BTClibValueError(err_msg)
    if not isinstance(descriptor, _POLICY_TOP_LEVEL):
        err_msg = f"{type(descriptor).__name__} is not a BIP388 SCRIPT expression"
        raise BTClibValueError(err_msg)


def _assert_policy_wildcard(key: KeyExpression) -> None:
    """Refuse anything but the bare, unhardened wildcard a placeholder takes.

    A ``KEY`` expression of a wallet-policy template is *always* followed
    by a wildcard and never by an explicit step in front of it -- BIP388's
    own invalid examples are ``pkh(@0)``, with none, and ``pkh(@0/0/**)``,
    with one. Hardened is refused too: the trailing step is what a device
    holding only the account xpub still has to compute, which a hardened
    step never lets it. A fixed public key fails this the same way a
    hardened or absent wildcard does -- `_parse_key` never gives one a
    `wildcard`, deriving further from a public key not being a thing -- so
    it is refused here rather than by a check of its own that nothing
    would ever reach: every key BIP390 lets an aggregate's own wildcard
    reach is extended already, `_parse_musig`'s own rule.
    """
    if key.der_path:
        err_msg = f"explicit derivation step before the wildcard: {key}"
        raise BTClibValueError(err_msg)
    if key.wildcard != 0:
        err_msg = f"not an unhardened wildcard, no wallet-policy placeholder: {key}"
        raise BTClibValueError(err_msg)


def _placeholder_index(
    key: KeyExpression,
    pool: dict[tuple[BIP32KeyOrigin | None, str], int],
    key_info: list[KeyExpression],
) -> int:
    """Return `key`'s position in the key-information vector, filing a new one.

    Shared across every occurrence of the same origin and extended key,
    whichever position writes it: a participant read from two ``musig()``
    groups, or a key used once on its own and once inside one, is one
    entry of the vector wherever it is written.
    """
    identity = (key.origin, key.xkey)
    if identity not in pool:
        pool[identity] = len(key_info)
        key_info.append(replace(key, der_path=(), wildcard=None))
    return pool[identity]


def _assert_distinct_participants(indexes: tuple[int, ...], musig: str) -> None:
    """Refuse a `musig()` naming the same key-information entry twice.

    BIP388's *Additional rules*: a placeholder is not allowed to repeat
    inside one aggregate, whether or not the whole group is written more
    than once elsewhere -- that second question is `written`'s, not this
    one's.
    """
    if len(set(indexes)) != len(indexes):
        err_msg = f"musig() repeats a participant: {musig}"
        raise BTClibValueError(err_msg)


def _template_key(
    key: KeyExpression,
    pool: dict[tuple[BIP32KeyOrigin | None, str], int],
    key_info: list[KeyExpression],
    written: set[int | frozenset[int]],
) -> KeyExpression:
    """Return the `@N` placeholder a wallet-policy template writes for `key`.

    A ``musig()`` aggregate numbers its participants and writes none for
    itself, BIP388's placeholder there being the whole ``musig(@i,@j)``;
    a plain key numbers itself. Either way the trailing wildcard this
    `Descriptor` holds is the only shape the placeholder can carry --
    a single, unhardened `/*` -- so a key or a participant set written
    a second time cannot take a different suffix to stay disjoint by, and
    is refused rather than folded into the first: BIP388 lists exactly
    that repetition, ``sh(multi(1,@0/**,@0/**))``, as invalid.

    A participant is never itself a ``musig()``: `_parse_musig` refuses
    the nesting before this is ever reached, so there is no check of that
    here for a test to have to reach past.
    """
    if key.participants:
        for participant in key.participants:
            if participant.der_path or participant.wildcard is not None:
                err_msg = "derivation before aggregation is not allowed in a"
                err_msg += f" wallet policy: {participant}"
                raise BTClibValueError(err_msg)
        _assert_policy_wildcard(key)
        indexes = tuple(
            _placeholder_index(participant, pool, key_info)
            for participant in key.participants
        )
        _assert_distinct_participants(indexes, str(key))
        group = frozenset(indexes)
        if group in written:
            err_msg = f"musig() placeholder used more than once: {key}"
            raise BTClibValueError(err_msg)
        written.add(group)
        return replace(
            key, participants=tuple(KeyExpression(xkey=f"@{i}") for i in indexes)
        )
    _assert_policy_wildcard(key)
    index = _placeholder_index(key, pool, key_info)
    if index in written:
        raise BTClibValueError(f"key expression used more than once: {key}")
    written.add(index)
    return KeyExpression(xkey=f"@{index}", wildcard=key.wildcard)


def _skeleton_key(key: KeyExpression) -> KeyExpression:
    """Return `key` with every wildcard, path and identity blanked out.

    What is left is the shape alone: a plain key becomes the same stand-in
    everywhere, and a ``musig()`` becomes one stand-in per participant, so
    two structures compare equal exactly when they nest the same functions
    over the same count of keys -- never mind which keys, and never mind
    where either one's wildcard is.
    """
    if key.participants:
        return KeyExpression(participants=tuple(map(_skeleton_key, key.participants)))
    return KeyExpression(xkey="K")


def _skeleton(descriptor: Descriptor) -> str:
    """Return `descriptor` as text with every key replaced by the same stand-in.

    Two descriptors with the same skeleton agree on every function, every
    threshold and the shape of every tree and every ``musig()`` -- on
    everything but which keys they name and where each one's wildcard
    sits, which is exactly what a receive and a change descriptor of one
    account are allowed to differ on.
    """
    return str(_mapped_keys(descriptor, _skeleton_key))


def _paired_chain_digits(
    recv_key: KeyExpression, chg_key: KeyExpression
) -> tuple[int, int]:
    """Return the receive and change chain digits a paired suffix picks between.

    Each side is exactly one explicit, unhardened step before an
    unhardened wildcard -- the change and index levels of a BIP44 path,
    and the only trailing path BIP388's `/<M;N>/*` grammar allows in front
    of one, whose own grammar spells `NUM` as "representing unhardened
    derivations". The two digits are BIP388's own requirement too: "two
    distinct decimal numbers", the receive and the change descriptor
    naming the same account key at the same depth being no policy at all.
    """
    for key in (recv_key, chg_key):
        if (
            len(key.der_path) != 1
            or key.wildcard != 0
            or key.der_path[0] >= HARDENED_OFFSET
        ):
            err_msg = f"not a receive/change chain step before the wildcard: {key}"
            raise BTClibValueError(err_msg)
    recv, chg = recv_key.der_path[0], chg_key.der_path[0]
    if recv == chg:
        err_msg = f"receive and change use the same chain step: {recv}"
        raise BTClibValueError(err_msg)
    return recv, chg


def _pair_suffix(recv: int, chg: int) -> str:
    """Return BIP388's `/**`, its `<0;1>` shorthand, or `/<M;N>/*` otherwise.

    `recv` and `chg` are the receive and change digit in that order, not
    a low/high pair: BIP389's `<M;N>` positions M at multipath index 0
    and N at index 1, so `<1;0>` and `<0;1>` are different templates and
    neither is the other sorted.
    """
    return "**" if (recv, chg) == (0, 1) else f"<{recv};{chg}>/*"


def _assert_disjoint_pair(
    placeholder: int | frozenset[int],
    recv: int,
    chg: int,
    seen: dict[int | frozenset[int], set[int]],
    text: str,
) -> None:
    """Refuse a placeholder reused with a chain digit already written for it.

    BIP388's own rule for a repeated placeholder is that its chain
    digits are pairwise *disjoint*, not merely a different pair:
    ``sh(multi(1,@0/<0;1>/*,@0/<1;2>/*))`` -- sharing digit 1 -- is
    BIP388's own invalid example, and the identical pair twice,
    ``sh(multi(1,@0/**,@0/**))``, is the one case that always shares
    both. `seen` accumulates every digit written for `placeholder` so
    far; catching the second is what catches the first too.
    """
    used = seen.setdefault(placeholder, set())
    if used & {recv, chg}:
        err_msg = f"chain digits are not disjoint from an earlier use: {text}"
        raise BTClibValueError(err_msg)
    used.update((recv, chg))


def _paired_key(
    recv_key: KeyExpression,
    chg_key: KeyExpression,
    pool: dict[tuple[BIP32KeyOrigin | None, str], int],
    key_info: list[KeyExpression],
    written: dict[int | frozenset[int], set[int]],
) -> str:
    """Return the placeholder and suffix one paired key position writes.

    A key or a ``musig()`` group may be written more than once, but only
    at chain digits pairwise disjoint from every earlier use of it,
    BIP388's own rule (`_assert_disjoint_pair`): the sortedmulti_a()
    vector reuses one key as `@0/**` (digits 0, 1) and, elsewhere in the
    same tree, as `@0/<2;3>/*` (digits 2, 3) -- disjoint, and allowed.
    """
    if recv_key.participants or chg_key.participants:
        # a participant count mismatch is already refused by `_skeleton`,
        # `wallet_policy`'s own precondition for reaching this at all --
        # `zip`'s `strict=True` is the defense that would fire if that
        # were ever wrong, not a check of its own
        indexes = []
        for recv_participant, chg_participant in zip(
            recv_key.participants, chg_key.participants, strict=True
        ):
            for participant in (recv_participant, chg_participant):
                if participant.der_path or participant.wildcard is not None:
                    err_msg = "derivation before aggregation is not allowed in a"
                    err_msg += f" wallet policy: {participant}"
                    raise BTClibValueError(err_msg)
            if (recv_participant.origin, recv_participant.xkey) != (
                chg_participant.origin,
                chg_participant.xkey,
            ):
                err_msg = "receive and change disagree on a musig() participant:"
                err_msg += f" {recv_participant} / {chg_participant}"
                raise BTClibValueError(err_msg)
            indexes.append(_placeholder_index(recv_participant, pool, key_info))
        _assert_distinct_participants(tuple(indexes), str(recv_key))
        recv, chg = _paired_chain_digits(recv_key, chg_key)
        group = frozenset(indexes)
        _assert_disjoint_pair(group, recv, chg, written, str(recv_key))
        keys = ",".join(f"@{i}" for i in indexes)
        return f"musig({keys})/{_pair_suffix(recv, chg)}"
    if (recv_key.origin, recv_key.xkey) != (chg_key.origin, chg_key.xkey):
        err_msg = f"receive and change disagree on a key: {recv_key} / {chg_key}"
        raise BTClibValueError(err_msg)
    recv, chg = _paired_chain_digits(recv_key, chg_key)
    index = _placeholder_index(recv_key, pool, key_info)
    _assert_disjoint_pair(index, recv, chg, written, f"@{index}")
    return f"@{index}/{_pair_suffix(recv, chg)}"


def wallet_policy(
    descriptor: Descriptor, change: Descriptor | None = None
) -> tuple[str, tuple[KeyExpression, ...]]:
    """Return the BIP388 wallet-policy template of a Descriptor, and its keys.

    Every KEY expression is written as its `@N` placeholder, in the order
    it is first read -- BIP388's own pair, a *wallet descriptor template*
    and the *key information vector* it indexes into, which is what an
    external signer's registration flow reads and what
    `wallet_policy_descriptor` reads back.

    `change` is the account's change descriptor, `descriptor` its receive
    one -- for a BIP44 account, its ``/1/*`` and ``/0/*`` chains. Given
    one, this writes BIP388's own `/<M;N>/*` (`/**` where the pair is
    `<0;1>`), the shorthand its Test Vectors use throughout: `descriptor`
    and `change` must share every function, threshold and tree shape
    (`_skeleton` is the check), and must differ, key by key, in nothing
    but one explicit, unhardened step in front of the wildcard -- BIP389's
    own two-element multipath, read back out of two already single-path
    descriptors rather than out of the `<a;b>` text
    `multipath_descriptors` expands away before either one is parsed.

    Left at its default, `change` is None and `descriptor` is read alone:
    the only placeholder this writes then is the plain, unhardened `/*`
    BIP388's "Optional derivation paths" section allows as an
    implementation-specific pattern, a `Descriptor` holding one
    derivation path and `/<M;N>/*` needing two. What cannot be written
    either way is refused rather than silently dropped: a fixed public
    key, a hardened or explicit step before the wildcard beyond the one
    unhardened chain digit `change` accounts for, a ``musig()`` with
    derivation on its participants, receive and change disagreeing on a
    key or on the shape around it, and a key or a ``musig()`` group
    written more than once with a chain digit that is not disjoint from
    an earlier use -- each with the fragment that was wrong. So is a
    descriptor whose own function is not one of BIP388's SCRIPT
    expressions -- ``combo()``, ``addr()``, ``raw()``, ``rawpkh()``,
    ``rawtr()`` and a bare ``pk()`` among them; so is a top-level
    ``multi()`` or ``sortedmulti()``, or a ``pk()`` directly inside
    ``sh()``; so is a ``raw()``, ``rawpkh()``, ``rawleaf()`` or ``rawnode()``
    nested in ``sh()``, ``wsh()`` or ``tr()``. Not checked: that every key
    is pairwise distinct from every other.
    """
    assert_type(descriptor, Descriptor, "descriptor")
    _assert_policy_top_level(descriptor)
    pool: dict[tuple[BIP32KeyOrigin | None, str], int] = {}
    key_info: list[KeyExpression] = []
    if change is None:
        template_written: set[int | frozenset[int]] = set()
        template = _mapped_keys(
            descriptor,
            lambda key: _template_key(key, pool, key_info, template_written),
        )
        return str(template), tuple(key_info)
    assert_type(change, Descriptor, "change")
    _assert_policy_top_level(change)
    if _skeleton(descriptor) != _skeleton(change):
        err_msg = "receive and change descriptors do not share the same structure"
        raise BTClibValueError(err_msg)
    recv_keys = descriptor.key_expressions
    chg_keys = change.key_expressions
    pair_written: dict[int | frozenset[int], set[int]] = {}
    # a key-count mismatch is already refused by the skeleton check above;
    # `zip`'s `strict=True` is the defense that would fire if that were
    # ever wrong, not a check of its own
    resolved = {
        id(recv_key): _paired_key(recv_key, chg_key, pool, key_info, pair_written)
        for recv_key, chg_key in zip(recv_keys, chg_keys, strict=True)
    }
    template = _mapped_keys(
        descriptor, lambda key: KeyExpression(xkey=resolved[id(key)])
    )
    return str(template), tuple(key_info)


# BIP388's KI index: a non-negative decimal integer, no leading zero
# unless the integer is 0 itself -- so `@0` and `@10` are indexes and
# `@00` is not one, the same digit string BIP388's own grammar spells.
# At most ten digits, so that `int()` never meets more than 4300
_POLICY_INDEX = r"@(?:0|[1-9]\d{0,9})"
# a lone placeholder or a musig() group of them, immediately followed by
# the one trailing wildcard BIP388 allows: the canonical `/**` shorthand,
# BIP389's own `/<M;N>/*` it stands for, or the plain `/*` a `Descriptor`
# writes, `/\*\*` tried first so it is not read as `/\*` with a stray `*`
# left over
_POLICY_PLACEHOLDER = re.compile(
    rf"(?:musig\((?P<musig>{_POLICY_INDEX}(?:,{_POLICY_INDEX})*)\)"
    rf"|@(?P<index>0|[1-9]\d{{0,9}}))"
    r"(?P<suffix>/\*\*|/<(?P<recv>\d+);(?P<chg>\d+)>/\*|/\*)"
)
# every musig() call the template holds, checked before substitution: the
# placeholder grammar allows nothing inside but comma-separated indexes,
# so a participant carrying its own path -- derivation before aggregation,
# which BIP388 forbids and BIP390 does not -- is refused here rather than
# read as a lone placeholder that happens to sit after "musig("
_POLICY_MUSIG_CALL = re.compile(r"musig\([^()]*\)")
_POLICY_MUSIG_GROUP = re.compile(rf"musig\({_POLICY_INDEX}(?:,{_POLICY_INDEX})*\)")


def _assert_multipath_index(multipath_index: int) -> None:
    """Refuse anything but the two branches BIP388's cardinality allows."""
    if multipath_index not in (0, 1):
        raise BTClibValueError(f"invalid multipath index: {multipath_index}")


def _assert_bare_key_info(key: KeyExpression) -> None:
    """Refuse a key-information entry that carries its own derivation.

    BIP388's vector holds an origin and an extended key and nothing past
    it, the trailing path being the template's to write; `wallet_policy`
    hands one back this way, and a caller building its own has to as well.
    """
    if key.der_path or key.wildcard is not None or key.participants:
        raise BTClibValueError(f"not a bare key-information entry: {key}")


def _resolved_placeholder(
    match: re.Match[str], key_info: Sequence[KeyExpression], multipath_index: int
) -> str:
    """Return the text a wallet-policy placeholder and its suffix resolve to."""
    try:
        if match["musig"] is not None:
            indexes = [int(token[1:]) for token in match["musig"].split(",")]
            keys = ",".join(str(key_info[i]) for i in indexes)
            text = f"musig({keys})"
        else:
            text = str(key_info[int(match["index"])])
    except IndexError:
        err_msg = f"key placeholder out of range: {match[0]}"
        raise BTClibValueError(err_msg) from None
    suffix = match["suffix"]
    if suffix == "/**":
        return f"{text}/{multipath_index}/*"
    if suffix == "/*":
        return f"{text}/*"
    branch = match["chg"] if multipath_index else match["recv"]
    return f"{text}/{branch}/*"


def wallet_policy_descriptor(
    template: str,
    key_info: Sequence[KeyExpression],
    multipath_index: int = 0,
    network: str = "mainnet",
) -> Descriptor:
    """Return the ranged Descriptor a BIP388 wallet-policy template describes.

    `template` and `key_info` are the pair `wallet_policy` returns, or the
    same pair read off any other source of them -- BIP388's own test
    vectors, or an external signer's registration flow. Every placeholder
    is replaced with its key-information text, and every trailing wildcard
    is resolved at `multipath_index`: BIP389's `/<M;N>/*` positions M at
    index 0 and N at index 1, in that order and never by which digit is
    the smaller, and `/**` is `/<0;1>/*` by definition; the plain `/*`
    BIP388 also allows takes neither branch and reads the same descriptor
    whatever `multipath_index` is. The result still holds the
    index-selecting wildcard: `Descriptor.address` and the rest of what a
    ranged descriptor answers are what `multipath_index` was resolved
    *for*.

    A template whose own function is not one of BIP388's SCRIPT expressions,
    or is a top-level ``multi()`` or ``sortedmulti()``, or is a ``pk()``
    directly inside ``sh()``, or holds a ``raw()``, ``rawpkh()``,
    ``rawleaf()`` or ``rawnode()``, is refused as `wallet_policy` refuses it.

    No `prv_keys`: every wildcard a wallet-policy template writes is
    unhardened, which is the whole of BIP388's "the seed alone is no
    longer enough" guarantee working in reverse -- the account xpub in
    `key_info` computes every script the policy describes, hardened step
    or not.
    """
    assert_type(template, str, "template")
    _assert_multipath_index(multipath_index)
    for key in key_info:
        _assert_bare_key_info(key)
    for call in _POLICY_MUSIG_CALL.findall(template):
        if not _POLICY_MUSIG_GROUP.fullmatch(call):
            raise BTClibValueError("not a wallet-policy musig() placeholder")
    text, count = _POLICY_PLACEHOLDER.subn(
        lambda match: _resolved_placeholder(match, key_info, multipath_index),
        template,
    )
    if count == 0 or "@" in text:
        raise BTClibValueError("not a BIP388 wallet-policy template")
    descriptor = parse(text, network)
    _assert_policy_top_level(descriptor)
    return descriptor


def wallet_policy_address(
    template: str,
    key_info: Sequence[KeyExpression],
    index: int = 0,
    multipath_index: int = 0,
    network: str = "mainnet",
) -> str:
    """Return the address a BIP388 wallet policy describes at `index`.

    `wallet_policy_descriptor` resolved at `multipath_index`, then
    `Descriptor.address` at `index` -- the derivation and the address
    encoding are answered by the descriptor code every other caller of
    this module uses, a wallet policy being a second way to name one of
    its descriptors and not a second way to compute one.
    """
    descriptor = wallet_policy_descriptor(template, key_info, multipath_index, network)
    return descriptor.address(index)
