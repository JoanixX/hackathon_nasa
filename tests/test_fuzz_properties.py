"""The JSON mutation harness must not create aliases/cycles in its reusable seed dictionary."""
import copy
import importlib.util
import json
import random
from pathlib import Path

from hypothesis import given, settings, strategies as st
from conftest import budget

_spec = importlib.util.spec_from_file_location("boundary_fuzz", Path(__file__).parent/"fuzz/fuzz_boundaries.py")
fuzz = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fuzz)


@settings(max_examples=budget(2000))
@given(st.integers(0, 2**32-1), st.integers(1, 15))
def test_structural_mutations_stay_serializable_and_do_not_corrupt_shared_values(seed, rounds):
    before = copy.deepcopy(fuzz.VALUES)
    data = b'{"nested":{"a":[[],{},[1,2]]},"rows":[{"x":true}]}'
    rng = random.Random(seed)
    for _ in range(rounds):
        data = fuzz.mutate_structure(data, rng)
        assert len(data) <= fuzz.MAX_INPUT
    assert fuzz.VALUES == before
    json.dumps(fuzz.VALUES)
