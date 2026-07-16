# SSD-backed model paging and I/O budgets

Phase 7.7 treats model storage, filesystem cache, cgroup memory, and physical I/O
as four related but distinct facts.

## Artifact identity and privacy

The Ollama resolver reads the local library manifest, selects the model-weight
layer, validates its declared size against a non-symlink regular blob, and emits
an opaque artifact ID, SHA-256 digest, byte size, storage tier, and filesystem
type. Serialized evidence never retains the model-store path. The artifact
contract structurally states that SSD bytes are excluded from RAM capacity.

The canonical Llama artifact is 2,019,377,376 bytes on NVMe-backed ext4. FAM
creates a temporary byte-for-byte, digest-verified private Ollama store for cache
control. The store is removed only after the isolated provider stops. The
user-owned downloaded model is never modified, renamed, or deleted.

## Mmap cache observation

`MmapPageCacheObserver` opens only configured-root, non-symlink regular files,
creates a copy-on-write mapping that does not fault pages in, and calls Linux
`mincore` to count resident pages. Its byte value is an upper bound because the
final page may be partial. The contract states that mapped resident pages remain
memory-accounted; they are not free capacity merely because they originated on
SSD.

Cache eviction uses `POSIX_FADV_DONTNEED` on a no-follow read-only descriptor.
The canonical gate requires the following observation to fall below 25% before
it may be labeled cold. Advice against the shared provider blob did not meet
that gate and was rejected; the verified owned clone moved from 100% to 0%.

## I/O budgets and telemetry

Every load has explicit maximum physical read and write bytes. The runner sums
`/proc/<pid>/io` for all surviving processes in the isolated service cgroup and
fails immediately after load if a cumulative budget is exceeded. Logical reads
are retained separately from physical device reads.

FAM also supports per-device `IOReadBandwidthMax` and `IOWriteBandwidthMax` in
the provider-neutral service definition, systemd adapter, cgroup `io.max`
observer, and exact applied-limit verifier. On this workstation, the user
manager accepts the properties but does not expose/delegate `io.max`; canonical
evidence records `kernel_bandwidth_controller_available=false` and does not
claim kernel rate enforcement. The cumulative process-I/O budget remains active.

## Canonical result

| Measurement | Cold | Warm |
|---|---:|---:|
| Cache before load | 0 bytes | 2,019,377,376 bytes |
| Cache after load | 2,019,377,376 bytes | 2,019,377,376 bytes |
| Physical reads | 2,019,602,432 bytes | 0 bytes |
| Logical reads | 2,099,023,919 bytes | 2,098,744,241 bytes |
| Provider load time | 3.237755975 s | 1.928527196 s |

Both trials confirmed unload, stayed below the 4,038,754,752-byte per-load read
budget and 128 MiB write budget, and left the isolated service inactive. This
demonstrates why SSD capacity, cached pages, and actual disk traffic must not be
represented by one “resident memory” number.
