"""Content redaction helpers for completed durable task state."""

from dataclasses import replace

from fam_os.core.lifecycle import CandidateEvidenceRecord
from fam_os.verification import VerificationRunRecord


TERMINAL_CONTENT_REDACTION = "[terminal content removed after result retention]"


def redact_request(request):
    return replace(request, prompt=TERMINAL_CONTENT_REDACTION)


def redact_candidate(candidate: CandidateEvidenceRecord) -> CandidateEvidenceRecord:
    return replace(candidate, content=TERMINAL_CONTENT_REDACTION)


def redact_verification_run(run: VerificationRunRecord) -> VerificationRunRecord:
    return replace(run, feedback=TERMINAL_CONTENT_REDACTION)


def redact_application(application):
    admitted = replace(
        application.routed.admitted,
        request=redact_request(application.routed.admitted.request),
    )
    routed = replace(application.routed, admitted=admitted)
    proposal = _redact_proposal(application.proposal)
    return replace(
        application,
        routed=routed,
        proposal=proposal,
        revision=application.revision + 1,
    )


def redact_action(action):
    return replace(action, proposal=_redact_proposal(action.proposal))


def _redact_proposal(proposal):
    if proposal is None:
        return None
    request = replace(proposal.request, summary=TERMINAL_CONTENT_REDACTION)
    return replace(proposal, request=request)
