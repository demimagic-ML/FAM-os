# MCP ingress operation

MCP ingress is disabled unless the owner creates:

```text
$XDG_DATA_HOME/fam-os/config/mcp-ingress.json
```

The file must be owned by the service user and mode `0600`:

```json
{
  "contract_version": "fam.product.mcp-ingress/v1alpha1",
  "enabled": true,
  "clients": [
    {
      "client_id": "local-editor",
      "principal_id": "local-editor",
      "capabilities": ["fam.ask", "fam.ask.verified"],
      "session_ttl_seconds": 3600
    }
  ]
}
```

Restart `fam-os.service` after changing the allowlist. A compatible MCP client
should launch the bridge from the active signed installation:

```text
fam-os --prefix $HOME/.local/share/fam-os/install \
  mcp serve --client-id local-editor
```

If `XDG_RUNTIME_DIR` is not inherited by the client, pass the exact runtime
directory using `--runtime-root`. The bridge obtains a one-time credential from
the owner-private daemon socket and then speaks official MCP over stdio. It does
not start another FAM service and cannot call Ollama or application connectors
directly.

`fam.ask` returns the normal Core assurance label and may be unverified.
`fam.ask.verified` fails closed and exposes no generated content unless declared
verification succeeds. Neither capability grants application mutation
authority.
