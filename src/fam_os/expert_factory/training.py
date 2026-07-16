"""Deterministic trainable routing, complexity, and specialist classifiers."""

import re
from dataclasses import dataclass

FACTORY_TRAINING_CONTRACT_VERSION = "fam.factory.training/v1alpha1"


@dataclass(frozen=True, slots=True)
class LabeledExample:
    text: str
    label: str


@dataclass(frozen=True, slots=True)
class TokenWeight:
    token: str
    label: str
    count: int


@dataclass(frozen=True, slots=True)
class TrainedMicroExpert:
    expert_id: str
    capability_id: str
    labels: tuple[str, ...]
    weights: tuple[TokenWeight, ...]
    training_examples: int
    interface_id: str
    contract_version: str = FACTORY_TRAINING_CONTRACT_VERSION

    def predict(self, text: str) -> str:
        scores = {label: 0 for label in self.labels}
        tokens = _tokens(text)
        for weight in self.weights:
            if weight.token in tokens:
                scores[weight.label] += weight.count
        return min(scores, key=lambda label: (-scores[label], label))


def train_micro_expert(expert_id, capability_id, interface_id, examples):
    values = tuple(examples)
    if len(values) < 2:
        raise ValueError("micro-expert training requires at least two examples")
    labels = tuple(sorted({item.label for item in values}))
    counts = {}
    for example in values:
        for token in _tokens(example.text):
            counts[(token, example.label)] = counts.get((token, example.label), 0) + 1
    weights = tuple(TokenWeight(token, label, count)
                    for (token, label), count in sorted(counts.items()))
    return TrainedMicroExpert(expert_id, capability_id, labels, weights, len(values), interface_id)


def _tokens(text):
    return frozenset(re.findall(r"[a-z0-9]+", text.casefold()))
