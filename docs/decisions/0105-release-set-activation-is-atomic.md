# ADR 0105: Release-set activation is atomic

Status: Accepted

Services, schemas, experts, and connectors form one signed release set. FAM_OS
copies digest-verified inputs into an immutable staging tree, runs a health check,
then changes one active symlink with `os.replace`. A failed stage or health check
does not modify the active release. Rollback switches the same pointer only to a
retained, healthy release, preventing mixed-version runtime states.
