import torch

from elpis_nanbeige42_host.cache_fingerprint import cache_fingerprint


def test_cache_fingerprint_exact_replay():
    cache = ((torch.arange(12).reshape(1, 1, 3, 4), torch.ones(1, 1, 3, 4)),)
    assert cache_fingerprint(cache) == cache_fingerprint(cache)


def test_cache_fingerprint_detects_single_value_change():
    left = ((torch.zeros(1, 1, 2, 2), torch.zeros(1, 1, 2, 2)),)
    right = ((torch.zeros(1, 1, 2, 2), torch.zeros(1, 1, 2, 2)),)
    right[0][1][0, 0, 0, 0] = 1
    assert cache_fingerprint(left) != cache_fingerprint(right)
