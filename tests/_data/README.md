# Vendored test vectors

This file is about `tests/**/_data/`. The package ships no data file of
its own.

The files of `tests/**/_generated_files/` are the opposite kind of thing
and have no entry here: they are this package's own output, `to_dict()`
over fixed input, committed as golden files so that a change to a
serialized form fails a test instead of passing unnoticed. Nothing
upstream to pin, and nothing to compare against but ourselves.

The entries below were taken from btclib-wallet's own
`tests/_data/README.md`, with the files they describe and the code that
reads them: an entry pins where a file came from and whether our copy
still matches it, and a test module names its upstream and points here
for the revision. A citation that names the wrong upstream is corrected
in the module; this file is not where that correction lives.

## Naming

A vendored file carries the name its upstream publishes it under, wherever
upstream publishes a file at all. A name of our own has no upstream name
to be compared against, so the citation in the module that loads it can
drift to a path upstream never had and nobody catches it -- the byte
comparison below is the only check the naming cannot fool.

The files that keep a name of their own do so because there is no upstream
file whose name they could take:

- `bip32_test_vectors.json` and `bip32_invalid_keys.json` are transcribed
  from mediawiki prose.
- `descriptor_checksums.json` is composed from prose, and
  `miniscript_fixed_tests.json` is transcribed from C++ source: no upstream
  file for either, so no upstream name to take.
- `preimage_descriptors.json` is composed here, for a syntax no BIP
  specifies yet.

## Reading an entry

Where an entry pins to a commit, it gives the upstream repository, the
path in it, and the commit. A `blob` line, where the entry carries one,
gives the git blob SHA-1 of what that entry pins; what it pins, and
whether it was compared byte for byte, is the entry's own to say. An
`ours` line gives the blob of the file kept here where that is not the
`blob`, or where the entry has no upstream blob to name: a file with its
line endings or trailing newline changed, a reformatted or transcribed
file. The weekly job holds the file to `ours`, or to `blob` where there
is no `ours`. Most entries close on a verdict; one with nothing upstream
to compare against says so in prose instead. The verdicts used:

- **identical** -- our file and the upstream blob are the same bytes.
- **reformatted** -- same parsed JSON value, different whitespace.
- **transcribed** -- there is no file compared byte for byte. Over prose
  (a BIP, a BOLT) the check is that every value in our copy appears
  verbatim in the pinned text; over a source file the check is the
  entry's own to state.
- **composed locally**, **recorded** -- there is nothing upstream to
  compare, so the entry says what stands in for one. *composed locally*
  is a case written here, naming the third implementation that answered
  it; *recorded* is one reply a program gave, kept verbatim, naming the
  program and the calls that ask it again. A recording another project
  publishes is pinned to that project like any other file, and its entry
  gives both verdicts.

`pulled` is the date the current content was taken from upstream, into
btclib or into this repository. `behind` counts upstream revisions
of that path since the pin. It is a staleness figure, not a defect: a
vector file is a fixed set of cases and refreshing it is a decision, not a
chore. `ref` names the branch a pin's path lives on, where that is not the
repository's own default branch.

A vector this package fails is vendored anyway and marked `xfail`, never
left out: an absent vector hides the defect it would have shown, and
`xfail_strict` turns the marker red the day the defect is fixed.

## Re-checking a pin

The commit stands in a fence of its own, sitting inside the API path
rather than at the end of the command; the fence below reads it as
`${commit:?}`, the shell's must-be-set form, so a paste of that fence
alone fails naming the variable.

```shell
commit=<the pin the entry gives>
```

```shell
git hash-object tests/_data/miniscript_fixed_tests.json
gh api "repos/bitcoin/bitcoin/git/trees/${commit:?}:src/test" \
    --jq '.tree[] | select(.path == "miniscript_tests.cpp") | .sha'
```

The comparison is on git blob SHA-1, not sha256: it is what a tree entry
already carries, so nothing has to be downloaded, and `git hash-object`
reproduces it locally.

The weekly job runs this comparison for every entry whose heading is one
file's path and which carries a `blob` or an `ours` line, and fails,
naming the file, on a mismatch. It compares the file with `ours` (or
`blob`) and the entry's `blob` with upstream's at `commit`, so a file
edited here and a pin whose blob is not the one at its commit both fail.
Add an `ours` line to a new entry whose file is not upstream's bytes,
and a `-text` line for the file to `.gitattributes`.

## bitcoin/bips

### `tests/bip32/_data/bip32_test_vectors.json`

```text
repo    bitcoin/bips
path    bip-0032.mediawiki
commit  c0644a054fd1568ecbfc9c2b656ad5200b16ff74  2026-03-05
ours    eb692228a6fb84a694a699f62937808bc2c640aa
pulled  2020-05-08, vector 4 added 2021-08-25, re-pinned to the tip 2026-08-06
behind  0 revisions; that commit is the tip of the path
```

Verdict: **transcribed**. BIP32 ships its vectors as prose, so there is
no upstream file and no byte comparison to make. All four seeds and all
34 extended keys of test vectors 1 to 4 appear verbatim in the pinned
text, and the derivation counts match: 6, 6, 2, 3.

The original pin was the commit that *added* test vector 4 rather than
the one current when btclib transcribed it: the earliest revision
holding all 34 keys, the parent holding 28, which made that pin checkable
rather than merely plausible. Re-checked against the tip on 2026-07-30
and again on 2026-08-06 — both times still test vectors 1 to 5 and no
sixth, every extended key in it one of ours, 48 matching the key
pattern: our 34 valid plus 14 of the 16 invalid, the other 2 being the
zero-prefix keys of test vector 5, which serialize outside it — the pin
above is now that tip, so the weekly automated check can carry it.

### `tests/bip32/_data/bip32_invalid_keys.json`

```text
repo    bitcoin/bips
path    bip-0032.mediawiki
commit  c0644a054fd1568ecbfc9c2b656ad5200b16ff74  2026-03-05
ours    a510e92e211a87a72ca57ea3b66f85bd4de8fabc
pulled  2020-05-16, error strings last changed 2026-10-14, re-pinned to
        the tip 2026-08-06
behind  0 revisions; that commit is the tip of the path
```

Verdict: **transcribed**. All 16 invalid extended keys are exactly the 16
of BIP32 test vector 5 — no omissions, no local additions — both at the
pinned commit and on master today.

btclib is the upstream here, not the consumer: commit ee2e0598, "added
invalid extended keys vectors", is Ferdinando Ametrano's, and is what
first put these 16 keys into the BIP. The pin above is the tip of the
same path rather than that commit, so the weekly automated check can
carry it too; the second column of the file is btclib's own regardless —
it holds btclib error messages, which the BIP does not and should not
carry, and which change when the messages change. Refreshing from
upstream means refreshing the keys, never the messages.

### Not vendored as a file: BIP386's `tr()` vectors

```text
repo    bitcoin/bips
path    bip-0386.mediawiki
commit  9d735fb36fdd6a5860febe7e84680aa220baad23  2026-09-17
pulled  2026-10-07
behind  0 revisions; that commit is the tip of the path
```

Verdict: **transcribed**, complete for both lists and cited inline, in
`tests/descriptors/descriptors_test.py`'s `BIP386_VECTORS` and
`BIP386_INVALID`: each valid descriptor that gives scripts, with the
script at each index the BIP lists, and each invalid one with the message
it is refused with. The valid `tr(KEY,pkh(KEY))` gives no script:
`test_bip386_pkh_leaf` parses it and asserts the script of the same shape
in Bitcoin Core's `descriptor_test`.

BIP386 lists `tr(KEY,pkh(KEY))` as valid since `d7854890`, `bip386:
update stale sentence`: a `pkh()` leaf is the BIP379 miniscript fragment
of that name.

### Not vendored as a file: BIP387's `multi_a()` vectors

```text
repo    bitcoin/bips
path    bip-0387.mediawiki
commit  3ac7c77174780bea5aa8999b1cf205f98da2ab46  2026-09-17
pulled  2026-08-06, re-pinned to the tip 2026-09-29
behind  0 revisions; that commit is the tip of the path
```

Verdict: **transcribed**, and cited inline rather than vendored: they are
descriptors and scripts read where they are used, in
`tests/descriptors/descriptors_test.py`'s `BIP387_VECTORS` and
`BIP387_INVALID`. Every descriptor of the BIP's Test Vectors section is
there with the scriptPubKey it produces, at each index the BIP lists, and
every invalid one with the message btclib refuses it with — two of those
refusals answering the uncompressed key before the threshold the BIP was
illustrating, which the entries say. Each value was matched against the
pinned text on 2026-08-06.

Re-checked against the tip on 2026-09-29: the Test Vectors section is
unchanged. The only diff is the BIP's own status line, `Type` moving from
Informational to Specification.

### Not vendored as a file: BIP390's `musig()` vectors

```text
repo    bitcoin/bips
path    bip-0390.mediawiki
commit  2a20ce4e8e1c6b941d1a827a287d757a568750d8  2026-09-17
pulled  2026-08-06, re-pinned to the tip 2026-09-29
behind  0 revisions; that commit is the tip of the path
```

Verdict: **transcribed**, complete for both lists and cited inline, in
`tests/descriptors/descriptors_test.py`'s `BIP390_VECTORS` and
`BIP390_INVALID`: the six valid descriptors with the scripts they produce
at each index listed, and all fourteen invalid ones with the message each
is refused with. Five further invalid cases there are btclib's own, for
what the BIP states in prose rather than listing — no nesting, no key
origin in front of one, at least one participant, no x-only participant,
and a `musig()` where a tree leaf belongs.

The original pin was the tip on the day it was taken, and that commit was
`bip390: fix missing parenthesis in test vector`, which closed the last
invalid descriptor's brackets, so a copy taken a day earlier would hold a
descriptor upstream no longer publishes. Ours was the fixed one.

Re-pinned to the tip again on 2026-09-29: that commit,
`bip390: Update to Specification type`, touches only the BIP's own status
header, and the six valid and fourteen invalid descriptors are still the
ones the 2026-08-06 pin held.

The invalid one that holds multipath participants and a multipath path is
refused by `parse` with Bitcoin Core's own message.

### Not vendored as a file: BIP394's `rawtr()` vectors

```text
repo    bitcoin/bips
path    bip-0394.mediawiki
commit  bc8b68c9cf60896bb981aa2d7030a5f2f3d32db8  2026-11-06
pulled  2026-11-07
behind  0 revisions; that commit is the tip of the path
```

Verdict: **transcribed**, complete for both lists and cited inline, in
`tests/descriptors/descriptors_test.py`'s `BIP394_VECTORS` and
`BIP394_INVALID`: each valid descriptor with the script at each index the
BIP lists, and each invalid one with the message it is refused with. The
multipath vector is `BIP394_MULTIPATH`, with the descriptors the BIP
expands it into and their scripts.

The commit is the one bitcoin/bips#2251 adds, and the merge of that pull
request, `55916fd835fae2c57d2afedcc2ebea698e760361`, holds the same blob
of the path. The pin names the pull request's commit because the weekly
re-check compares a pin with the last commit touching its path, and the
merge is not that commit.

### Not vendored as a file: BIP388's wallet-policy vectors

```text
repo    bitcoin/bips
path    bip-0388.mediawiki
commit  cfff9719405fa35113cab637958809824873750f  2026-04-15
pulled  2026-09-02
behind  0 revisions; that commit is the tip of the path
```

Verdict: **transcribed**, complete and cited inline in
`tests/descriptors/descriptors_test.py`'s `BIP388_VECTORS`: every valid
policy of the Test Vectors section, its template, its key-information
vector and the multipath descriptor the two compile to, checked branch by
branch against `wallet_policy_descriptor` and `wallet_policy_address`
rather than restated as an address of its own -- `multipath_descriptors`
and `parse` already answer for what a branch of that descriptor is. The
same vectors are read the other way too, in
`test_wallet_policy_reconstructs_bip388s_own_vectors`: `wallet_policy`,
given the receive and change `Descriptor` `multipath_descriptors` splits
that same descriptor into, rebuilds the vector's own template and
key-information vector, byte for byte. Four
of the Invalid policies section's nine are checked too, in
`test_bip388_invalid_templates`: the no-path, explicit-path,
cardinality-above-two and derivation-before-aggregation ones, each a
property of the template text alone. The other five are not:
out-of-order and skipped placeholders are a canonicalization
`wallet_policy_descriptor` does not need to enforce to compute one
address correctly; repeated keys and non-disjoint multipath steps for the
same placeholder need the two occurrences compared against each other,
which nothing here does across an `re.subn` callback; and a non-KP key
present in a template position is refused anyway, but by `parse`'s own
"use multipath_descriptors first" -- a coincidence of the raw `<0;1>`
text reaching it unconsumed, not a check this module makes. That one is
in the module too, as what it is.

### Not vendored as a file: BIP328's synthetic xpub vectors

```text
repo    bitcoin/bips
path    bip-0328.mediawiki
commit  24e96e870fffaa257b465ce1f0370c14aac588e8  2026-01-12
pulled  2026-08-06
behind  0 revisions; that commit is the tip of the path
```

Verdict: **transcribed**, complete: all three aggregate keys, the
synthetic xpub each becomes and the participant keys each aggregates, in
`tests/bip32/bip32_test.py`'s `BIP328_VECTORS`. The keys of those vectors
aggregate **as written**, unsorted, which is what makes them worth holding
beside BIP390's: sorting before aggregation is BIP390's rule and not
BIP328's, and a `key_sort` applied here reaches none of the three
published keys. Matched against the pinned text on 2026-08-06.

### Not vendored as a file: the draft BIP for raw() inside other descriptors

```text
repo    bitcoin/bips
path    bip-raw-as-subscript.md
ref     3197eb9b27fd0c5aacd833b791399777053cc18b
commit  3197eb9b27fd0c5aacd833b791399777053cc18b  2024-12-27
pulled  2026-10-22
behind  0 revisions; that commit is the tip of the path
```

Verdict: **transcribed**. bitcoin/bips#1721 is a draft BIP, closed, that
specifies `raw()` inside `sh()`, `wsh()` and a `tr()` tree. It is no
branch either, and `ref` is its head.

`BIP_VECTORS` in `tests/descriptors/raw_descriptors_test.py` holds its
valid vectors, and `BIP_INVALID` its invalid ones, with the space after a
comma left out: Core refuses a function name that starts with a space.
The `key` of `tr(raw(asdf), pk(key))` is written as an x-only key. The
invalid vector whose hash the draft leaves as a placeholder is left out.
The draft's other examples are a to-do list.

## bitcoin/bitcoin

### `tests/_data/descriptor_checksums.json`

```text
repo    bitcoin/bitcoin
path    doc/descriptors.md
commit  0f38524c31da4cf69d8e904569fe56292e4325b9  2022-10-30
ours    1741596f31d557718c571d58070812662744f05e
pulled  2023-07-12
```

Verdict: **composed locally**, not vendored. Descriptors appear
verbatim in the pinned document; none of their checksums does, because
Core's document does not list them. They were computed with a third
implementation, `bdk`'s `descriptor::checksum::get_checksum`, as
`tests/descriptors/descriptors_test.py` records — which is the point of
the file: the checksums are an independent oracle, so recomputing them
with btclib would void the test.

Nothing to refresh from upstream. A new descriptor needs a checksum from
somewhere other than btclib.

Checked again on 2026-07-30, against the current document rather than the
pin: ours are still all in it, and it still carries no checksum at
all — not one `descriptor#checksum` pair in the file. It has grown
concrete descriptors we do not hold (a `tr(musig(...))`, a
`wsh(sortedmulti(...))` and a `wsh(thresh(...))`, the rest of what it shows
being syntax templates like `sh(SCRIPT)`), and each would need a checksum
computed by something that is not btclib. That is a decision to take with
a tool at hand, not a refresh.

### `tests/_data/miniscript_fixed_tests.json`

```text
repo    bitcoin/bitcoin
path    src/test/miniscript_tests.cpp
commit  faae016796ed64da493cb175e40fca042fe386e6  2026-10-19
blob    a71e9f9a23e4fdeef8936ee818c89bcb0d0d2441
ours    83f5e24eb6344c973bbe377eae37ff92f34ac430
pulled  2026-08-25, re-pinned to the tip 2026-11-07
behind  0 revisions; that commit is the tip of the path
```

Verdict: **transcribed**, mechanically. One json object per `Test()` call
of the `fixed_tests` case, with the fields that call passes: the
miniscript, the script it compiles to under P2WSH and under tapscript, the
`TESTMODE_*` flags split into booleans, and the ops, stack, witness-size
and execution-stack numbers where the call gives them. The regex that
produced it is not committed -- a one-off pass over C++ source is not a
tool -- and what re-derives the file is reading those calls again.

No revision of the path since `128456b62d5e`, the pin this file had
before `e8691056c014`, touches those calls, so the vendored JSON needs no
change. `e8691056c014` splits each `BOOST_CHECK(a && b && c)` into one
`BOOST_REQUIRE`/`BOOST_CHECK` per condition, outside any `Test(...)` call.
`faae016796ed`, of bitcoin/bitcoin#36579, writes `','` and `')'` for `","`
and `")"` in the lines that build the `multi_a()` call, one of the calls
not here (below).

Not vendored as the file itself because there is no data file upstream:
the vectors are arguments to a C++ function. The blob above is that source
file, so the weekly re-check still reports a case added to it.

Four of the calls are not here, being loops rather than literals: the
`multi_a()` of twenty-one keys, the three `and_b()` chains that pass the
p2wsh ops, stack and script-size limits, and the two nestings that reach a
thousand elements on the stack. `tests/descriptors/miniscript_test.py`
builds those from Core's own key set instead, and asserts the same
formulas its calls pass -- which is why they are missing here rather than
untested.

Also not here: `random_tests`, which generates expressions from a seeded
RNG and checks the satisfier against the script interpreter. Satisfaction
is not implemented (issue btclib-org/btclib#187), so there is nothing yet
for those to measure.

### Not vendored as a file: Core's descriptor derivation vectors

```text
repo    bitcoin/bitcoin
path    src/test/descriptor_tests.cpp
commit  f5a887c199613be9ddc8a13fbb7934af614fa579  2026-11-06
pulled  2026-09-21, rawtr() added 2026-08-06, re-pinned to the tip 2026-11-07
behind  0 revisions; that commit is the tip of the path
```

Verdict: **transcribed**, a subset by design.
`tests/descriptors/descriptors_test.py` holds the `Check(prv, pub, ...)`
cases of the `descriptor_test` case as `CORE_VECTORS` — the descriptor in
both spellings and the scriptPubKey each expands to, at every index the
case lists — plus the public spellings of those Core expands from the
private form alone, which are `HARDENED_PUBLIC` there, and the `rawtr()`
cases. BIP394 publishes the one whose key is a WIF, as its second
vector; the ranged one, under an xprv, is Core's own.

`tests/descriptors/unused_test.py` holds every case of the
`unused_descriptor_test` case, transcribed from the file at that commit:
its `CheckUnused` cases as `CORE_UNUSED`, and its `CheckUnparsable` and
`CheckSingleUnparsable` cases as `CORE_UNPARSABLE`, with the messages
`parse` gives.

Not vendored as a file because there is no file: the values are literals
in C++ source, so a copy of it would be a copy of a test program. What
this pin buys instead is the upstream re-check: a case added to that
function moves the commit, and the weekly run says so.

The subset is deliberate and is what a refresh would revisit: Core's file
also holds `CheckUnparsable` cases, which this module has as `UNPARSABLE`
and `CORE_UNPARSABLE` with btclib's own messages, and `musig()` cases.
Those BIP390 publishes are transcribed from the BIP itself above rather
than from here; those it does not -- `rawtr(musig(...))` among them -- are
transcribed from neither. Matched against the file as it stood on
2026-08-06.

The cases upstream added after that comparison, other than
bitcoin/bitcoin#35819's below, are not here, and
[ISS 1334](https://github.com/btclib-org/btclib/issues/1334) is where
they were weighed: it measured btclib against both defects they cover --
a `musig()` duplicate-key check that reads distinct participants as the
same key when neither of them derives, and a key origin prepended once
per expression rather than once per participant -- and found neither in
this tree, so none of those cases is owed here.

The last revision to change the cases is bitcoin/bitcoin#35819, *test: add
coverage for untested descriptor parse error paths*: new lines, almost
all new `CheckUnparsable` cases, and one new `Check(...)`-shaped case
asserting that a taptree of exactly 128 nesting levels parses.
The `CheckUnparsable` cases are `CORE_UNPARSABLE`, in both spellings, except
the case of `raw()` inside `sh()`, which that pull request adds and this
tree accepts by the draft BIP of bitcoin/bips#1721, as
`tests/descriptors/raw_descriptors_test.py`'s docstring says. The parse of
the deepest taptree is `test_tr_tree_depth_is_bounded`'s. `CORE_VECTORS`
gains nothing from it.

The revisions after it, of bitcoin/bitcoin#36091 and bitcoin/bitcoin#36772,
change only the file's includes and `DoCheck`, the function every `Check`
case runs through: its assertions and the messages they print. No case
changes, so nothing here does.

### Not vendored as a file: the raw node and raw leaf vectors of a closed pull request

```text
repo    bitcoin/bitcoin
path    src/test/descriptor_tests.cpp
ref     9c4854fa276672ffbd5b82579c0088a2e56b25d0
commit  c9d15420226b6338e4b18f9acf337187203d7b09  2025-08-01
pulled  2026-10-22
behind  0 revisions; that commit is the tip of the path
```

Verdict: **transcribed**, every case the pull request adds.
bitcoin/bitcoin#30243 implements `rawnode()` and `rawleaf()`, and was
closed unmerged until a BIP exists. It is no branch of the repository, so
`ref` is its head: a commit, from which the API walks back to the last one
touching the path.

`tests/descriptors/raw_descriptors_test.py` holds its `Check` cases as
`CORE_CHECKS`, in both spellings with the scripts, and its
`CheckUnparsable` cases as `CORE_UNPARSABLE`. Core reads the error of the
public string alone, so the private one is only held to be refused. The
messages are Core's, except those of a function in a position it is not
allowed in: `parse` words each of them as "NAME() is not allowed inside
CONTEXT". Not here: the functional test of the pull request, which needs a
node and a wallet.

## Other projects

### Not vendored as a file: bitcoin-s's descriptor cases

```text
repo    bitcoin-s/bitcoin-s
path    core-test/src/test/scala/org/bitcoins/core/protocol/script/descriptor
commit  32eaf31e48b092e29edb29cc882aada7d561f606  2025-03-06
pulled  2026-10-11
behind  0 revisions; that commit is the tip of the path
```

Verdict: **transcribed**, and **composed locally** for what bitcoin-s does
not state. `tests/descriptors/bitcoin_s_test.py` holds these cases from
that directory's test files:

- each quoted `name(...)` string, checksum removed, that `git grep -F`
  finds neither elsewhere in this suite's `tests/` nor in Bitcoin Core's
  `src/test` at a8b69bdeafdf;
- the key expressions, not the bare key origins, of `KeyExpressionTest.scala`
  that the same search finds in neither;
- the bad checksums of `DescriptorChecksumTest.scala`.

Only the cases bitcoin-s runs count: its commented-out ones are left out,
among them the public-key cases of `KeyExpressionTest.scala` that derive
hardened steps.

The cases `sh(raw(deadbeef))` and `wsh(raw(deadbeef))` are BIP385's
invalid vectors. The draft BIP of bitcoin/bips#1721 makes `raw()` valid
there, and this tree follows it, so the test holds them as `ACCEPTED_HERE`:
accepted, with the script, where bitcoin-s refuses.

The script of a case in `ACCEPTED` is bitcoin-s's; that of a case in
`ACCEPTED_HERE` is the hash160 or sha256 of `deadbeef`, computed here. The
checksum of an accepted descriptor, and its addresses where bitcoin-s gives no
script, are what `getdescriptorinfo` and `deriveaddresses` answer, run with no
chain on mainnet, at the Bitcoin Core release `integration-bitcoind.yml` pins.
Where bitcoin-s gives a checksum, Core's is the same.
Core's `getdescriptorinfo` refuses every case the test expects refused.

The test's strings are the pinned files' strings. From the repository root,
the first command fetches the files and prints the test's strings that they
do not hold. A key expression is looked for without its `pkh()`, and a
checksum case as its payload and its checksum apart. The scripts of the
accepted cases, the checksum of the ranged one, and each accepted case that
the files write with a checksum are looked for too. It prints an empty list.

```shell
commit=32eaf31e48b092e29edb29cc882aada7d561f606
dir=core-test/src/test/scala/org/bitcoins/core/protocol/script/descriptor
scala=$(mktemp -d)
for f in $(gh api "repos/bitcoin-s/bitcoin-s/contents/${dir}?ref=${commit:?}" \
        --jq '.[].name'); do
    gh api -H 'Accept: application/vnd.github.raw' \
        "repos/bitcoin-s/bitcoin-s/contents/${dir}/${f}?ref=${commit}" \
        > "$scala/$f"
done
uv run python - "$scala" <<'PY'
import sys
from pathlib import Path

from tests.descriptors import bitcoin_s_test as t

text = "".join(f.read_text() for f in Path(sys.argv[1]).glob("*.scala"))
cases = [d for d, *_ in t.ACCEPTED + t.ACCEPTED_HERE + t.REFUSED] + [t.RANGED]
cases += [d[4:-1] for d, *_ in t.KEY_ACCEPTED + t.KEY_REFUSED]
for d, _ in t.CHECKSUM_REFUSED:
    cases += [d[4 : d.index(")")], d.partition(")")[2].lstrip("#")]
cases += [s for *_, s in t.ACCEPTED] + [t.RANGED_CHECKSUM]
cases += [f"{d}#{c}" for d, c, _ in t.ACCEPTED if f"{d}#" in text]
print([c for c in cases if c and c not in text])
PY
```

The second command is the selection, on the same files, in the same
shell. It applies the rule above to each string of the pinned files and
prints the selected ones that the test does not hold. It prints an empty
list. `bitcoin` is a checkout of Bitcoin Core.

```shell
bitcoin=${bitcoin:-../bitcoin}
uv run python - "${scala:?}" "$bitcoin" <<'PY'
import re
import subprocess
import sys
from pathlib import Path

from tests.descriptors import bitcoin_s_test as t


def found(*command):
    return subprocess.run(command, capture_output=True).returncode == 0


def selected(s):
    here = ("git", "grep", "-qF", "--", s, "--", "tests/")
    core = ("git", "-C", sys.argv[2], "grep", "-qF", "--", s)
    return not found(*here, ":!tests/descriptors/bitcoin_s_test.py") and not found(
        *core, "a8b69bdeafdf", "--", "src/test"
    )


held = {d for d, *_ in t.ACCEPTED + t.ACCEPTED_HERE + t.REFUSED} | {t.RANGED}
held |= {d[4:-1] for d, *_ in t.KEY_ACCEPTED + t.KEY_REFUSED}
missing = []
for path in Path(sys.argv[1]).glob("*.scala"):
    source = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
    source = re.sub(r"(?m)^\s*//.*$", "", source)
    for s in re.findall(r'"([^"\n]*)"', source):
        s = re.sub(r"#[a-z0-9]{8}$", "", s)
        key = path.name == "KeyExpressionTest.scala" and " " not in s
        key = key and not s.endswith("]")
        if (key or re.match(r"[a-z]{2,8}\(.*\)", s)) and selected(s):
            missing += [s] * (s not in held)
print(missing)
PY
rm -r "${scala:?}"
```

Core, on a node of its own with no chain, wallet or peers. From the
repository root, the command prints the cases whose checksum or addresses
differ from the test's, and those expected refused that Core accepts; it
prints an empty list.

```shell
datadir=$(mktemp -d)
bitcoind -datadir="$datadir" -rpcport=18999 -disablewallet -connect=0 \
    -listen=0 -dnsseed=0 -daemonwait
uv run python - "$datadir" <<'PY'
import json
import subprocess
import sys

from tests.descriptors import bitcoin_s_test as t


def cli(*args):
    return subprocess.run(
        ["bitcoin-cli", f"-datadir={sys.argv[1]}", "-rpcport=18999", *args],
        capture_output=True,
        text=True,
    )


def info(d):
    done = cli("getdescriptorinfo", d)
    return json.loads(done.stdout)["checksum"] if done.returncode == 0 else None


def addresses(d, count):
    args = ["[0,2]"] if count > 1 else []
    done = cli("deriveaddresses", f"{d}#{info(d)}", *args)
    return json.loads(done.stdout)


wrong = [d for d, checksum, _ in t.ACCEPTED if info(d) != checksum]
wrong += [d for d, _ in t.REFUSED + t.CHECKSUM_REFUSED + t.KEY_REFUSED if info(d)]
wrong += [t.RANGED] * (
    (info(t.RANGED), addresses(t.RANGED, 3)) != (t.RANGED_CHECKSUM, t.RANGED_ADDRESSES)
)
wrong += [d for d, a in t.KEY_ACCEPTED if addresses(d, len(a)) != a]
wrong += [t.TR_PKH_LEAF] * (
    addresses(t.TR_PKH_LEAF, 1) != [t.TR_PKH_LEAF_ADDRESS]
)
print(wrong)
PY
bitcoin-cli -datadir="$datadir" -rpcport=18999 stop
while [ -e "$datadir/bitcoind.pid" ]; do sleep 1; done
rm -r "${datadir:?}"
```

Not vendored as a file because the strings are literals in Scala source.
bitcoin-s is under the MIT licence (its `LICENSE`), the licence of this
package.

## Delving Bitcoin

### `tests/_data/preimage_descriptors.json`

```text
topic     https://delvingbitcoin.org/t/descriptor-syntax-for-hash-preimages/2935
computed  2026-11-07
ours      5ef2141dadb30525744f20a8d036878a1b14aff5
```

Verdict: **composed locally**. The topic proposes ``preimage(HEX)`` as the
private form of a hash fragment's argument. No BIP specifies it, so these
vectors are this package's, for issue btclib-org/bip32-descriptors#11.
Each row is one hash fragment in `wsh(and_v(v:pk(KEY),FRAGMENT(ARG)))`,
where ARG is the digest in the public form and ``preimage(HEX)`` in the
private one. KEY is the generator point in the unranged rows, and a ranged
derivation of the master xpub of BIP32's first test vector in the ranged
ones.

No code of this package or of btclib checks them: `hashlib` checks the
digests, BIP380's reference Python the checksums of both forms, and
Bitcoin Core, on a node of its own with no chain, wallet or peers, the
public forms, their checksums and their scriptPubKeys. Core refuses the
private forms, so BIP380's code is the one check of their checksums made
outside this package. From the repository root, the command prints the
rows any of these checks disagrees with; it prints an empty list.

```shell
datadir=$(mktemp -d)
bip380=$(mktemp)
pin=55916fd835fae2c57d2afedcc2ebea698e760361
gh api -H 'Accept: application/vnd.github.raw' \
    "repos/bitcoin/bips/contents/bip-0380.mediawiki?ref=${pin:?}" > "$bip380"
bitcoind -datadir="$datadir" -rpcport=18999 -disablewallet -connect=0 \
    -listen=0 -dnsseed=0 -daemonwait
uv run --no-project python - "$datadir" "$bip380" <<'PY'
import hashlib
import json
import re
import subprocess
import sys

text = open(sys.argv[2], encoding="utf-8").read()
reference = {}
for block in re.findall(r"<pre>\n(.*?)</pre>", text, re.S):
    if "descsum" in block:
        exec(block, reference)


def cli(*args):
    done = subprocess.run(
        ["bitcoin-cli", f"-datadir={sys.argv[1]}", "-rpcport=18999", *args],
        capture_output=True,
        text=True,
    )
    return json.loads(done.stdout) if done.returncode == 0 else None


def sha256(b):
    return hashlib.sha256(b).digest()


def ripemd160(b):
    return hashlib.new("ripemd160", b).digest()


hashes = {
    "sha256": sha256,
    "hash256": lambda b: sha256(sha256(b)),
    "ripemd160": ripemd160,
    "hash160": lambda b: ripemd160(sha256(b)),
}
wrong = []
with open("tests/_data/preimage_descriptors.json", encoding="ascii") as f:
    rows = json.load(f)
for row in rows:
    preimage = bytes.fromhex(row["preimage"])
    public, private = row["public"], row["private"]
    count = len(row["script_pub_keys"])
    addresses = cli("deriveaddresses", public, *(["[0,2]"] if count > 1 else []))
    scripts = [cli("validateaddress", a)["scriptPubKey"] for a in addresses or []]
    ok = hashes[row["fragment"]](preimage).hex() == row["digest"]
    ok &= private == public.split("#")[0].replace(
        row["digest"], f"preimage({row['preimage']})"
    ) + "#" + private.split("#")[1]
    ok &= all(map(reference["descsum_check"], (public, private)))
    ok &= (cli("getdescriptorinfo", public) or {}).get("checksum") == public[-8:]
    ok &= scripts == row["script_pub_keys"]
    ok &= cli("getdescriptorinfo", private.split("#")[0]) is None
    wrong += [] if ok else [public]
print(wrong)
PY
bitcoin-cli -datadir="$datadir" -rpcport=18999 stop
while [ -e "$datadir/bitcoind.pid" ]; do sleep 1; done
rm -r "${datadir:?}" "${bip380:?}"
```

`tests/descriptors/preimage_test.py` reads the file. The `ours` line
records its blob, and neither the weekly job nor the suite compares the
file with it: `check_vendored_vectors.py` reads only an entry that names
a repository, a path and a commit, and this one has none to name.

## What is not pinned, and why

- **The transcribed files** are pinned to a prose revision, or, where the
  upstream is a source file rather than a document, to that file's blob;
  neither makes "identical" a claim that can be made about them. What was
  checked is stated in each entry.
- **The suite checks the local half, offline.**
  `tests/check_vendored_vectors_test.py` holds each file this ledger names
  to its `ours` line, or its `blob` where there is none. No test asks
  upstream for a blob: a network call in the suite would trade a
  documented drift for a flaky one.
  `.github/workflows/vendored-vectors.yml` asks upstream, weekly, and a
  byte mismatch fails the run.

## Summary

No count here, and no count in front of the lists below: a count is a
line every open branch has to edit, and branches moving it to the same
new number merge with nothing to decide, into a number that is wrong. The
lists *are* the fact the number summarized, and the tree answers
whenever the number is wanted:

```shell
git ls-files 'tests/_data/*' 'tests/*/_data/*' | grep -cvE 'README\.md$'
```

Not checked byte for byte against an upstream blob:

- transcribed, every value matched either in the pinned text or, for a
  source file, by the check the entry itself states:
  `bip32_test_vectors.json`, `bip32_invalid_keys.json`,
  `miniscript_fixed_tests.json`.
- composed here: `preimage_descriptors.json`, for a syntax no BIP
  specifies, its public forms checked against Bitcoin Core.
- not vendored: `descriptor_checksums.json`, composed rather than
  recorded: its checksums come from a third implementation run over
  Core's own descriptors.

### Left for a maintainer to decide

- **Descriptors of Core's `doc/descriptors.md` are not vendored**,
  and cannot be without a checksum from a third implementation. See that
  entry.
