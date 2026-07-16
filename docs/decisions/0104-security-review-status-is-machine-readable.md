# ADR 0104: Security review status is machine-readable

Status: Accepted

Security scanners are independent evidence inputs, not authority to waive their
own findings. FAM_OS records explicit fixed, accepted, or open dispositions and
fails the automated release gate for unresolved high or critical findings. The
report separately records whether a human external review occurred so automated
analysis can never be presented as third-party certification.
