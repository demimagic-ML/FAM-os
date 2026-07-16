# FAM Shell and Console

FAM Shell remains the keyboard-first Ask / Plan / Approve / Progress / Result
client over a private peer-authenticated Unix socket. FAM Console is the visual
inspection surface for resources, experts, permissions, memory, audit history,
and offline recovery state. Both are unprivileged projections; neither owns
model routing, grants, acceptance, or action authority.

When the combined product service is running, start the Shell with `fam-shell`.
For local chat, enter `ask YOUR QUESTION`, then `refresh` to wait for and display
the model result. Local chat is intentionally marked completed rather than
verified and cannot invoke application actions. Enter `quit` to leave the client;
the owner service continues running.

Start the Console with an owner-private state and token path:

```bash
fam-console --state-root "$HOME/.local/share/fam-os" \
  --token-file "${XDG_RUNTIME_DIR}/fam-os/console.token"
```

The process prints a one-time fragment URL. The token stays in session storage,
is removed from browser history immediately, and is required only for the JSON
snapshot endpoint. The server rejects non-loopback binds and non-local Host
headers. Uninitialized product areas appear as unavailable with an explicit
reason rather than fake zeroes.
