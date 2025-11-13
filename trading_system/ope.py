"""Offline policy evaluation helpers."""
from __future__ import annotations

from typing import Any, Dict

import numpy as np
from d3rlpy.algos import CQL
from d3rlpy.datasets import MDPDataset
from d3rlpy.ope import FQE


def weighted_importance_sampling(policy_probs, behavior_probs, rewards, gamma: float = 0.99) -> float:
    weights = policy_probs / np.clip(behavior_probs, 1e-8, None)
    numer = np.sum((gamma ** np.arange(len(rewards))) * rewards * weights)
    denom = np.sum(weights) + 1e-8
    return float(numer / denom)


def per_decision_importance_sampling(policy_probs, behavior_probs, rewards, gamma: float = 0.99) -> float:
    ratios = policy_probs / np.clip(behavior_probs, 1e-8, None)
    weight = 1.0
    value = 0.0
    for step, reward in enumerate(rewards):
        weight *= ratios[step]
        value += (gamma ** step) * reward * weight
    return float(value)


def doubly_robust(algo: CQL, dataset: MDPDataset, gamma: float = 0.99, n_epochs: int = 200) -> float:
    fqe = FQE(algo=algo, n_epochs=n_epochs)
    fqe.fit(dataset, n_epochs=n_epochs)
    obs, actions, rewards = dataset.observations, dataset.actions, dataset.rewards
    qsa = fqe.predict_value(obs, actions)
    baseline = float(np.mean(qsa))
    return float(np.mean(rewards + qsa - baseline))


def ope_safety_check(
    algo: CQL,
    dataset: MDPDataset,
    policy_probs,
    behavior_probs,
    rewards,
    thresholds: Dict[str, float] | None = None,
) -> Dict[str, Any]:
    thresholds = thresholds or {"dr_min": 0.0}
    wis = weighted_importance_sampling(policy_probs, behavior_probs, rewards)
    pdis = per_decision_importance_sampling(policy_probs, behavior_probs, rewards)
    dr = doubly_robust(algo, dataset)
    passed = (dr >= thresholds["dr_min"]) and (wis >= 0.0) and (pdis >= 0.0)
    return {"wis": wis, "pdis": pdis, "dr": dr, "safety_passed": passed}
