"""Fictional values generated from stable fixture IDs, never credentials."""

import hashlib


def canary(label: str) -> str:
    return "SYNTH-" + hashlib.sha256(("sentinel-lab-v1/" + label).encode()).hexdigest()[:24]


PRIVATE = {
    label: canary(label)
    for label in ("api_key", "token", "customer", "config", "system", "forecast")
}
