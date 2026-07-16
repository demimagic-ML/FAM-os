# Reference context profiles

`reference-models.json` selects the currently packaged local experts for live
metadata observation. The model architecture remains adapter-observed; this
file supplies package context ceilings and conservative runtime policy bounds.
It does not contain model weights, measured memory, or placement decisions.

Autoregressive experts reserve prompt plus output KV cache. The Nomic embedding
expert uses the encoder activation bound and therefore reserves no output tokens.
