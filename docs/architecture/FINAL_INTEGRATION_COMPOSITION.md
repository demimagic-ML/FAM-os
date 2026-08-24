# Final integration composition boundaries

`LocalProductService` coordinates lifecycle only. It may start, stop, and expose
health for independently composed units, but it must not implement storage,
routing, scheduling, connector, memory, remote, training, or evidence policy.

Each production unit owns one package under `fam_os.product.composition` and
depends on typed ports from the domain packages. Concrete adapters are injected
at the composition boundary.

| Unit | Owns | Must not own |
|---|---|---|
| `storage` | database, migrations, key access, transactional repositories | Core policy or UI |
| `core` | admission-to-final-result use-case assembly | provider protocols or persistence details |
| `runtimes` | Ollama/model service lifecycle and runtime bindings | expert selection policy |
| `applications` | socket, broker, registry, discovery, adapter assembly | user authority decisions |
| `memory` | session/persistent retrieval and management assembly | implicit indexing authority |
| `console` | authenticated HTTP/session/task presentation | alternate task policy |
| `remote` | peer service and transport adapters | local/remote scheduling policy |
| `factory` | supervised training worker and package lifecycle assembly | automatic training authority |

All units implement the small lifecycle surface `start()`, `health()`, and
`stop()`. Dependencies flow from composition into domain ports, never from
domain policy back to product composition. No unit imports tests, tools,
acceptance harnesses, phase-exit builders, or raw artifact generators.

The modules are introduced with their real implementation phases rather than as
empty placeholders: storage/runtimes in Phase 17, Core in Phase 18,
applications/Console in Phase 19, memory in Phase 20, remote in Phase 21, and
factory in Phase 22. The composition package must remain a set of bounded units;
it may not become a second god service.
