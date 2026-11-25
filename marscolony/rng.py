"""Deterministic PRNG: splitmix64 with integer state stored INSIDE the state dict.

Keeping the RNG state as plain data (not a random.Random object) is what makes
f(state, actions) pure and runs replayable byte-for-byte (ADR-0001).
"""

MASK = (1 << 64) - 1
_GOLDEN = 0x9E3779B97F4A7C15


def next_u64(rng_state: int) -> tuple:
    """Advance splitmix64; returns (new_state, value)."""
    rng_state = (rng_state + _GOLDEN) & MASK
    z = rng_state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    z = z ^ (z >> 31)
    return rng_state, z


def rand_below(state: dict, n: int) -> int:
    """Deterministic integer in [0, n) consuming one draw from state['rng']."""
    if n <= 0:
        raise ValueError("n must be positive")
    state["rng"], value = next_u64(state["rng"])
    return value % n
