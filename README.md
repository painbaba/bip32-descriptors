# bip32-descriptors

BIP32 hierarchical deterministic keys, output script descriptors and
miniscript, in typed Python.

<!-- Section 2 of btclib-org/.github's README.md says which badges sit here. -->
[![PyPI version](https://img.shields.io/pypi/v/bip32-descriptors.svg?logo=pypi)](https://pypi.org/project/bip32-descriptors/)
[![GitHub release](https://img.shields.io/github/v/release/btclib-org/bip32-descriptors.svg)](https://github.com/btclib-org/bip32-descriptors/releases)
[![development status](https://img.shields.io/pypi/status/bip32-descriptors.svg)](https://pypi.org/project/bip32-descriptors/)
[![license](https://img.shields.io/github/license/btclib-org/bip32-descriptors.svg)](https://github.com/btclib-org/bip32-descriptors/blob/main/LICENSE)
[![downloads](https://static.pepy.tech/badge/bip32-descriptors)](https://pepy.tech/projects/bip32-descriptors)
[![supported Python versions](https://img.shields.io/pypi/pyversions/bip32-descriptors.svg?logo=python)](https://pypi.org/project/bip32-descriptors/)
[![implementation](https://img.shields.io/pypi/implementation/bip32-descriptors.svg)](https://pypi.org/project/bip32-descriptors/)
[![wheel](https://img.shields.io/pypi/wheel/bip32-descriptors.svg)](https://pypi.org/project/bip32-descriptors/)

[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/16116/badge)](https://www.bestpractices.dev/projects/16116)
[![OpenSSF Baseline](https://www.bestpractices.dev/projects/16116/baseline)](https://www.bestpractices.dev/projects/16116)

It is fully annotated and ships `py.typed`. It is built on
[btclib](https://github.com/btclib-org/btclib), the protocol package, and
[ecc](https://github.com/btclib-org/ecc), the curve package; its
`secp256k1` extra adds the libsecp256k1 bindings, and without them the
Python arithmetic answers instead.

## What is here

- [BIP32](https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki)
  hierarchical deterministic keys: extended key serialization, private and
  public derivation, derivation paths and key origins (`bip32`)
- [BIP380](https://github.com/bitcoin/bips/blob/master/bip-0380.mediawiki)
  output script descriptors, from `pk()` to `tr()` with its script tree,
  `musig()` key expressions, and
  [BIP388](https://github.com/bitcoin/bips/blob/master/bip-0388.mediawiki)
  wallet policies (`descriptors`)
- [BIP379](https://github.com/bitcoin/bips/blob/master/bip-0379.md)
  miniscript: parsing, type checking, the script it compiles to and the
  witness that satisfies it (`descriptors.miniscript`)

[ARCHITECTURE.md](https://github.com/btclib-org/bip32-descriptors/blob/main/ARCHITECTURE.md)
says how these modules layer and which may import which.

Every refusal is btclib's `BTClibValueError` or `BTClibTypeError`, or
ecc's class of the same kind where an argument reaches that package.

Signing, partially signed transactions and wallets are not here: they
are [btclib-wallet](https://github.com/btclib-org/btclib-wallet)'s.

The suite answers to vectors their authors publish -- the BIPs', Bitcoin
Core's and bitcoin-s's -- and
[tests/_data/README.md](https://github.com/btclib-org/bip32-descriptors/blob/main/tests/_data/README.md)
pins each vendored file to the upstream commit it was copied from.

## Installing

```shell
python -m pip install --upgrade bip32-descriptors
```

and, for the libsecp256k1 bindings,

```shell
python -m pip install --upgrade "bip32-descriptors[secp256k1]"
```

## A key, a descriptor, an address

```python
from bip32_descriptors.bip32 import derive, rootxprv_from_seed, xpub_from_xprv
from bip32_descriptors.descriptors import add_checksum, parse

# BIP32's test vector 1, and its m/0h/1 extended public key
xprv = rootxprv_from_seed("000102030405060708090a0b0c0d0e0f")
xpub = xpub_from_xprv(derive(xprv, "m/0h/1"))
assert xpub.startswith("xpub6ASuArnXKPbfEwhqN6e3mwBcDTgzisQN1wXN9BJcM47s")

# a ranged descriptor with its key origin, checksum included
descriptor = parse(add_checksum(f"wpkh([3442193e/0h/1]{xpub}/0/*)"))
assert descriptor.address(0) == "bc1qw47q2vtlewz7jyx970nvm8wy6p44mqepwqdj27"

# and a miniscript: the key, after 144 blocks
policy = parse(f"wsh(and_v(v:pk({xpub}/0/*),older(144)))")
assert policy.address(0).startswith("bc1q")
```

`tests/readme_test.py` runs every Python block of this file, so the
example above is the one the suite checks.

## Security

[SECURITY.md](https://github.com/btclib-org/bip32-descriptors/blob/main/SECURITY.md)
says how to report a vulnerability, which versions are supported, and
how a published file is traced back to the run that built it.
[ASSURANCE_CASE.md](https://github.com/btclib-org/bip32-descriptors/blob/main/ASSURANCE_CASE.md)
argues why what it promises holds: the threat model, the trust
boundaries, and the weaknesses a package of this kind is exposed to.

## Contributing

Development is LLM-based: humans are welcome, as long as they are
comfortable with agentic development ;-). A contribution must have been
read and understood by the person who submits it.
[`CONTRIBUTING.md`](https://github.com/btclib-org/bip32-descriptors/blob/main/CONTRIBUTING.md#working-with-an-llm)
has the rules.

[CONTRIBUTING.md](https://github.com/btclib-org/bip32-descriptors/blob/main/CONTRIBUTING.md)
has the commands each CI job runs, verbatim. `uv sync` creates the
environment; uv is the only tool that has to be installed.
[REVIEWING.md](https://github.com/btclib-org/bip32-descriptors/blob/main/REVIEWING.md)
is what a pull request is answered against.

How the organization decides, and who holds which role, is its
[GOVERNANCE.md](https://github.com/btclib-org/.github/blob/main/GOVERNANCE.md);
what it intends to do, and what it deliberately does not, is its
[ROADMAP.md](https://github.com/btclib-org/.github/blob/main/ROADMAP.md).

## Links

- Documentation: <https://bip32-descriptors.readthedocs.io/>
- Source: <https://github.com/btclib-org/bip32-descriptors>
- Releases: <https://github.com/btclib-org/bip32-descriptors/releases>
- [CHANGELOG.md](https://github.com/btclib-org/bip32-descriptors/blob/main/CHANGELOG.md),
  and [RELEASE_NOTES.md](https://github.com/btclib-org/bip32-descriptors/blob/main/RELEASE_NOTES.md)
  for what a release asks a user to act on

## Status

<!-- Section 2 of btclib-org/.github's README.md says which badges sit here. -->
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/btclib-org/bip32-descriptors/main.svg)](https://results.pre-commit.ci/latest/github/btclib-org/bip32-descriptors/main)
[![lint workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/lint.yml?query=branch%3Amain)
[![test workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/test.yml?query=branch%3Amain)
[![docs workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/docs.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/docs.yml?query=branch%3Amain)
[![documentation build](https://app.readthedocs.org/projects/bip32-descriptors/badge/?version=latest)](https://bip32-descriptors.readthedocs.io)
[![vendored-vectors workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/vendored-vectors.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/vendored-vectors.yml?query=branch%3Amain)
[![mutation workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/mutation.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/mutation.yml?query=branch%3Amain)
[![qa-assets workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/qa-assets.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/qa-assets.yml?query=branch%3Amain)
[![fuzz workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/fuzz.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/fuzz.yml?query=branch%3Amain)
[![integration-bitcoind workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/integration-bitcoind.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/integration-bitcoind.yml?query=branch%3Amain)
[![deps-latest workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/deps-latest.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/deps-latest.yml?query=branch%3Amain)
[![pypi-install workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/pypi-install.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/pypi-install.yml?query=branch%3Amain)
[![deps-oldest workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/deps-oldest.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/deps-oldest.yml?query=branch%3Amain)
[![os-macos workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/os-macos.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/os-macos.yml?query=branch%3Amain)
[![os-ubuntu workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/os-ubuntu.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/os-ubuntu.yml?query=branch%3Amain)
[![os-windows workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/os-windows.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/os-windows.yml?query=branch%3Amain)
[![links workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/links.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/links.yml?query=branch%3Amain)
[![sdist-rebuild workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/sdist-rebuild.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/sdist-rebuild.yml?query=branch%3Amain)
[![codeql workflow status](https://github.com/btclib-org/bip32-descriptors/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/btclib-org/bip32-descriptors/actions/workflows/codeql.yml?query=branch%3Amain)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/btclib-org/bip32-descriptors/badge)](https://scorecard.dev/viewer/?uri=github.com/btclib-org/bip32-descriptors)

---

The btclib organization and its projects are actively supported by
[DGI](https://dgi.io) and [CheckSig](https://checksig.com).
