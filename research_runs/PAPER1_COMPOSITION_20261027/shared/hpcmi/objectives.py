"""Prespecified loss candidates, with source-only subject-by-class grouping."""
import math
import torch
from torch.nn import functional as F

METHODS = ("erm", "groupdro", "tail", "consistency", "tail_consistency")


class Objective:
    def __init__(self, method, n_groups, config, device, inclusion_probabilities=None, group_prior=None):
        if method not in METHODS:
            raise ValueError("Unknown method: " + method)
        self.method = method
        self.config = config.get("objective", {})
        self.prior = torch.as_tensor(group_prior if group_prior is not None else [1./n_groups] * n_groups,
                                     dtype=torch.float32, device=device)
        if self.prior.shape != (n_groups,) or not bool((self.prior > 0).all()) or not torch.isclose(self.prior.sum(), torch.tensor(1., device=device)):
            raise ValueError("Group prior must be positive and sum to one")
        self.log_q = self.prior.log()
        self.inclusion = torch.as_tensor(inclusion_probabilities if inclusion_probabilities is not None else [1.] * n_groups,
                                         dtype=torch.float32, device=device)
        if self.inclusion.shape != (n_groups,) or not bool(((self.inclusion > 0) & (self.inclusion <= 1)).all()):
            raise ValueError("Group inclusion probabilities must be in (0,1]")

    def state_dict(self):
        return {"log_q": self.log_q.detach().cpu(), "method": self.method, "inclusion_probabilities": self.inclusion.detach().cpu(), "initial_group_prior": self.prior.detach().cpu()}

    def load_state_dict(self, state):
        if state["method"] != self.method:
            raise ValueError("Objective method mismatch")
        if not torch.equal(state["inclusion_probabilities"].to(self.inclusion.device), self.inclusion):
            raise ValueError("Group sampling probabilities changed")
        if not torch.equal(state["initial_group_prior"].to(self.prior.device), self.prior):
            raise ValueError("Group prior changed")
        self.log_q.copy_(state["log_q"].to(self.log_q.device))

    def __call__(self, logits, labels, groups):
        broad, mu, beta = logits
        individual = F.cross_entropy(broad.float(), labels, reduction="none")
        unique = torch.unique(groups, sorted=True)
        group_losses = torch.stack([individual[groups == g].mean() for g in unique])
        mean = group_losses.mean()
        loss = mean
        details = {"mean_ce": float(mean.detach())}
        if self.method == "groupdro":
            # Horvitz-Thompson estimates correct unequal cohort/person inclusion.
            # Use pre-update q, independent of this batch, for the model gradient.
            # The reference adversary ranges over all source person×class groups.
            pi = self.inclusion[unique]
            weights = torch.softmax(self.log_q.detach(), dim=0)[unique] / pi
            loss = (weights * group_losses).sum()
            with torch.no_grad():
                self.log_q[unique] += float(self.config.get("groupdro_eta", 0.01)) * group_losses.detach() / pi
                self.log_q -= torch.logsumexp(self.log_q, dim=0)
        if self.method in ("tail", "tail_consistency"):
            fraction = float(self.config.get("tail_fraction", 0.5))
            weight = float(self.config.get("tail_weight", 0.5))
            if not 0 < fraction <= 1 or not 0 <= weight <= 1:
                raise ValueError("Tail fraction/mixture weight out of range")
            tail = group_losses.topk(max(1, math.ceil(fraction * len(unique)))).values.mean()
            loss = (1 - weight) * mean + weight * tail
            details["tail_ce"] = float(tail.detach())
        if self.method in ("consistency", "tail_consistency"):
            log_prob = torch.stack([F.log_softmax(z.float(), dim=1) for z in logits])
            prob = log_prob.exp()
            mixture = prob.mean(dim=0).clamp_min(torch.finfo(prob.dtype).tiny)
            js = (prob * (log_prob - mixture.log().unsqueeze(0))).sum(dim=2).mean()
            loss = loss + self.config.get("consistency_weight", 0.1) * js
            details["js"] = float(js.detach())
        if not torch.isfinite(loss):
            raise FloatingPointError("Non-finite training objective")
        details["loss"] = float(loss.detach())
        return loss, details
