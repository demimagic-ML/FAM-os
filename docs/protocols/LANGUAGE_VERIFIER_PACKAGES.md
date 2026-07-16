# JavaScript, TypeScript, and Rust verifier packages

Phase 8.4 adds local package manifests and a shared strict report for real
toolchains. JavaScript uses Node syntax plus tests, TypeScript uses TypeScript
5.9.3 strict no-emit compilation, and Rust uses rustc 1.97 compilation, test
build, and test execution. Every gate retains bounded exit/output evidence and
missing tools are errors.

Candidate execution gates are disabled by default in the adapter. Production
must supply an activated isolation provider satisfying the package manifest.
Only the canonical known-fixture harness explicitly enables direct execution;
that flag is not a release path. Evidence in
`artifacts/verification/phase8.4/language-verifier-packages.json` shows positive
fixtures pass and syntax/type/compiler negative fixtures are withheld.
