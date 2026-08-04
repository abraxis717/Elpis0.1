import hashlib, torch
from collections import defaultdict

def context_digest(grid, bucket=3):
    return hashlib.sha256(
        (grid // bucket).to(torch.uint8).cpu().numpy().tobytes()
    ).hexdigest()[:12]

class CascadeGraph:
    def __init__(self):
        self.edges = defaultdict(lambda: {"n": 0, "eff": None})
    def record(self, cell, value, digest, effect):
        e = self.edges[(cell, value, digest)]
        e["eff"] = effect.clone() if e["eff"] is None else \
                   e["eff"] + (effect - e["eff"]) / (e["n"] + 1)
        e["n"] += 1
    def predict(self, cell, value, digest):
        e = self.edges.get((cell, value, digest))
        return None if e is None else e["eff"]

def generalization_score(graph, cell, value):
    effs = [v["eff"] for (c, w, _), v in graph.edges.items()
            if c == cell and w == value and v["eff"] is not None]
    if len(effs) < 2: return None
    M = torch.stack(effs)
    return 1.0 - (M.std(0).mean() / (M.abs().mean() + 1e-8)).item()

def calibration(predicted, observed):
    p = predicted - predicted.mean(); o = observed - observed.mean()
    return (p @ o / (p.norm() * o.norm() + 1e-8)).item()
