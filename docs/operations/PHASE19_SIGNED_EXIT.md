# Phase 19 signed installed exit

Run the complete application-weaving and everyday-UI exit gate with:

```bash
.verification-venv/bin/python -m tools.run_phase19_exit
```

The host must provide:

- `/usr/bin/code` with a working graphical display;
- local Ollama at `http://127.0.0.1:11434` and the packaged model inventory;
- Python build dependencies already present in `.verification-venv`;
- network or a populated pip cache for the temporary dependency wheelhouse.

The runner performs no installation in the user's normal FAM_OS or VS Code
directories. It creates a private temporary root, builds the FAM_OS wheel and
dependency wheelhouse, assembles an ephemeral Ed25519-signed seven-component
release, installs it, installs its signed VSIX into an isolated extension root,
and starts the installed service against external local Ollama.

It then launches an isolated VS Code profile and uses authenticated Console
sessions to:

1. ground a project summary in an observed README;
2. preview, approve, run, and verify a real Python unittest command;
3. preview an exact revision-bound editor change;
4. approve and independently verify the edit;
5. start a deterministic model-free reversal;
6. preview, approve, and verify the undo without exposing its token.

The service, VS Code process group, connector profile, installation, and
temporary signing material are removed even on failure. A passing report is
written to `artifacts/product/phase19/phase19-exit.json`. The report contains
hashes and state claims, not prompt content or reversal tokens.
