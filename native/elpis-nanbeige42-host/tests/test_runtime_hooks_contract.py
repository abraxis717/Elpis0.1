import torch

from elpis_nanbeige42_host.hooks import default_registry
from elpis_nanbeige42_host.runtime_hooks import resolve_registry, tensor_digest


class FakeBase(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.norm = torch.nn.Identity()
        self.layers = torch.nn.ModuleList([torch.nn.Identity() for _ in range(22)])


class FakeModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.model = FakeBase()
        self.lm_head = torch.nn.Linear(3, 5, bias=False)


def test_runtime_registry_resolves_exact_paths():
    model = FakeModel()
    resolved = resolve_registry(model, default_registry())
    assert resolved["LAYER_21_L1_POST"] is model.model.layers[21]
    assert resolved["POST_LOGIT"] is model.lm_head


def test_tensor_digest_is_byte_exact():
    value = torch.arange(6, dtype=torch.float32).reshape(2, 3)
    assert tensor_digest(value) == tensor_digest(value.clone())
    value[0, 0] = 9
    assert tensor_digest(value) != tensor_digest(torch.arange(6, dtype=torch.float32).reshape(2, 3))
