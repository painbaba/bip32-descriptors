# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Output descriptors: the checksum, the parser, the scripts, the spend.

The flat surface is `descriptors`': `parse` and what a parsed descriptor
answers. Three modules make it up, and each imports the ones before it and
none after:

- `key_expression` is BIP380's KEY expressions, the public keys a
  descriptor names and how they derive;
- `miniscript` is BIP379's language, which is the SCRIPT expressions
  written as a tree of fragments rather than as a function, and the
  non-malleable witness that satisfies one;
- `descriptors` is the rest of BIP380 to BIP390: the checksum, the
  functions, the scripts each describes, and what each tells a psbt.

`miniscript` is named beside the flat surface because a caller reaches it
by name -- `miniscript.parse`, `miniscript.from_script` and the
`Miniscript` a `MiniscriptDescriptor` holds are its own interface, not the
descriptor one -- while `key_expression` is not: `KeyExpression` and
`PrvKeys` are re-exported below, being names a caller reads off a parsed
descriptor. So are `miniscript`'s `Preimages`, for the same reason.
"""

from bip32_descriptors.descriptors import miniscript
from bip32_descriptors.descriptors.descriptors import (
    AddrDescriptor,
    ComboDescriptor,
    Descriptor,
    DescriptorLeaf,
    DescriptorTree,
    Expansion,
    MiniscriptDescriptor,
    MultiA,
    MultiDescriptor,
    PkDescriptor,
    PkhDescriptor,
    Provider,
    RawDescriptor,
    RawLeaf,
    RawNode,
    RawPkhDescriptor,
    RawTrDescriptor,
    ShDescriptor,
    TrDescriptor,
    UnusedDescriptor,
    WpkhDescriptor,
    WshDescriptor,
    add_checksum,
    at_index,
    checksum,
    derived_origin,
    from_address,
    infer_descriptor,
    multipath_descriptors,
    normalized,
    parse,
    private_string,
    strip_checksum,
    wallet_policy,
    wallet_policy_address,
    wallet_policy_descriptor,
)
from bip32_descriptors.descriptors.key_expression import KeyExpression, PrvKeys
from bip32_descriptors.descriptors.miniscript import Miniscript, Preimages, SpendContext

__all__ = [
    "AddrDescriptor",
    "ComboDescriptor",
    "Descriptor",
    "DescriptorLeaf",
    "DescriptorTree",
    "Expansion",
    "KeyExpression",
    "Miniscript",
    "MiniscriptDescriptor",
    "MultiA",
    "MultiDescriptor",
    "PkDescriptor",
    "PkhDescriptor",
    "Preimages",
    "Provider",
    "PrvKeys",
    "RawDescriptor",
    "RawLeaf",
    "RawNode",
    "RawPkhDescriptor",
    "RawTrDescriptor",
    "ShDescriptor",
    "SpendContext",
    "TrDescriptor",
    "UnusedDescriptor",
    "WpkhDescriptor",
    "WshDescriptor",
    "add_checksum",
    "at_index",
    "checksum",
    "derived_origin",
    "from_address",
    "infer_descriptor",
    "miniscript",
    "multipath_descriptors",
    "normalized",
    "parse",
    "private_string",
    "strip_checksum",
    "wallet_policy",
    "wallet_policy_address",
    "wallet_policy_descriptor",
]
