import pytest

from metrics import edits, fidelity, micro, page_order, precedence


@pytest.mark.parametrize(
    ("a", "b", "s", "d", "i"),
    [
        ("cat", "cut", 1, 0, 0),
        ("a", "", 0, 1, 0),
        ("", "a", 0, 0, 1),
        ("a", "abcd", 0, 0, 3),
        ("", "", 0, 0, 0),
        ("A", "a", 1, 0, 0),
        ("a!", "a?", 1, 0, 0),
        ("a b", "ab", 0, 1, 0),
        ("can't", "cant", 0, 1, 0),
        ("a-b", "ab", 0, 1, 0),
        ("123", "124", 1, 0, 0),
        ("é", "e\u0301", 1, 0, 1),
        ("😀", "🐈", 1, 0, 0),
        ("a\n", "a ", 1, 0, 0),
        ("kitten", "sitting", 2, 0, 1),
    ],
)
def test_counts(a, b, s, d, i):
    got = edits(a, b)
    assert (got["substitutions"], got["deletions"], got["insertions"]) == (s, d, i)
    assert got["rate"] == ((s + d + i) / len(a) if a else None)
    assert got["exact_match"] == (a == b)


def test_words_and_nfc():
    assert fidelity("one two", "one three")["words"]["rate"] == 0.5
    assert fidelity("é", "e\u0301")["nfc_exact_match"]
    for token in ["can't", "re-read", "3.2", "word!"]:
        assert fidelity(token, "")["words"]["reference_units"] == 1


def test_structure_and_micro():
    assert precedence("B A", [("A", "B"), ("B", "C")]) == 0
    assert precedence("A B", []) is None
    assert not page_order(["a", "b"], ["a", "a"])
    assert page_order(["a", "b"], ["a", "b"])
    assert micro([edits("ab", "a"), edits("c", "c")])["rate"] == 1 / 3
    assert micro([edits("", "")])["rate"] is None


@pytest.mark.parametrize(("reference", "hypothesis", "spurious"), [("", "", 0), ("", "😀!", 2)])
def test_undefined_denominator_status(reference, hypothesis, spurious):
    result = edits(reference, hypothesis)
    assert result["rate"] is None
    assert result["metric_status"] == "undefined_zero_reference"
    assert result["spurious_units"] == spurious


def test_rate_above_one_and_micro_zero_reference_insertions():
    assert edits("a", "abcdefgh")["rate"] == 7
    assert micro([edits("a", "a"), edits("", "xyz")])["rate"] == 3


def test_metric_distance_against_small_independent_oracle():
    from itertools import product

    words = ["".join(p) for n in range(4) for p in product("ab", repeat=n)]

    def oracle(a, b):
        if not a:
            return len(b)
        if not b:
            return len(a)
        return min(
            oracle(a[1:], b[1:]) + (a[0] != b[0]), oracle(a[1:], b) + 1, oracle(a, b[1:]) + 1
        )

    for a in words:
        for b in words:
            result = edits(a, b)
            assert sum(result[k] for k in ("substitutions", "deletions", "insertions")) == oracle(
                a, b
            )
