# Derived from Samsung SAIL Montreal TinyRecursiveModels
# Upstream commit: c01103738605ba39d1430519b1ee0c62f4c707f8d
# Copyright (c) 2025. Samsung Electronics Co., Ltd. All Rights Reserved.
# MIT License; see LICENSES/Samsung-TinyRecursiveModels-MIT.txt.

import torch
from torch import nn
from .common import trunc_normal_init_


class CastedSparseEmbedding(nn.Module):
    def __init__(self, num_embeddings: int, embedding_dim: int, batch_size: int, init_std: float, cast_to: torch.dtype):
        super().__init__()
        self.cast_to = cast_to
        self.register_buffer("weights", trunc_normal_init_(torch.empty((num_embeddings, embedding_dim)), std=init_std), persistent=True)
        self.register_buffer("local_weights", torch.zeros(batch_size, embedding_dim, requires_grad=True), persistent=False)
        self.register_buffer("local_ids", torch.zeros(batch_size, dtype=torch.int32), persistent=False)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        if not self.training:
            return self.weights[inputs].to(self.cast_to)
        with torch.no_grad():
            self.local_weights.copy_(self.weights[inputs])
            self.local_ids.copy_(inputs)
        return self.local_weights.to(self.cast_to)
