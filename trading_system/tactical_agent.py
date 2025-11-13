"""Offline RL tactical agent using Conservative Q-Learning."""
from __future__ import annotations

import numpy as np
from d3rlpy.algos import CQL
from d3rlpy.datasets import MDPDataset
from typing import Any, Dict


class TacticalAgentCQL:
    """Thin wrapper around d3rlpy's CQL implementation."""

    def __init__(self, seed: int = 42) -> None:
        self.algo = CQL(seed=seed)
        self.is_fitted = False

    def fit(self, dataset: MDPDataset, n_epochs: int = 10_000, verbose: bool = False) -> Dict[str, Any]:
        self.algo.fit(dataset, n_epochs=n_epochs, verbose=verbose)
        self.is_fitted = True
        return {"fitted_epochs": n_epochs}

    def act(self, state: np.ndarray) -> int:
        if not self.is_fitted:
            raise RuntimeError("TacticalAgentCQL no entrenado")
        return int(self.algo.predict([state])[0])

    @staticmethod
    def build_dataset(
        states: np.ndarray,
        actions: np.ndarray,
        rewards: np.ndarray,
        next_states: np.ndarray,
        terminals: np.ndarray,
    ) -> MDPDataset:
        return MDPDataset(
            observations=states,
            actions=actions,
            rewards=rewards,
            terminals=terminals,
            next_observations=next_states,
        )
