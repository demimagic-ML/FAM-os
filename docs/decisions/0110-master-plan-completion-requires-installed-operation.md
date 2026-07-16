# ADR 0110: Master Plan completion requires installed operation

Status: Accepted

Schema, unit, component-integration, and wheel-content gates are necessary but
cannot establish that FAM_OS works as a product. Completion additionally requires
a fresh isolated installation to start its generated service, execute the actual
Shell binary through authenticated local transport and Core into a real downloaded
Ollama model, load the authenticated Console UI/API, stop cleanly, detect damage,
repair it, and remove all installed artifacts. Missing service entry points or
unexecuted launchers reopen completion even when prior tests pass.
