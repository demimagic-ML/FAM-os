# ADR 0106: User roots and recovery are fail closed

Status: Accepted

Every FAM_OS runtime belongs to exactly one Linux UID and lives below a
non-symlink 0700 root with private 0700 state, memory, audit, release, and
recovery areas. A process cannot initialize another UID's runtime. Recovery mode
is offline and permits only diagnosis, export, release rollback, and deterministic
state repair. It denies inference, application effects, memory mutation, expert
training, and network access.
