"""Domain definitions, enums, and constants for ClaimWise."""

from enum import Enum


class PolicyType(str, Enum):
    HEALTH = "health"
    AUTO = "auto"
    HOME = "home"
    LIFE = "life"
    TRAVEL = "travel"
    DISABILITY = "disability"
    OTHER = "other"


class PolicyStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    DRAFT = "draft"


class ClaimStatus(str, Enum):
    DRAFT = "draft"
    EVIDENCE_GATHERING = "evidence_gathering"
    ANALYZED = "analyzed"
    SANDBOX_SUBMITTED = "sandbox_submitted"
    INSURER_REJECTED = "insurer_rejected"
    IN_DISPUTE = "in_dispute"
    APPROVED = "approved"
    CLOSED = "closed"


class DocumentType(str, Enum):
    MEDICAL_BILL = "medical_bill"
    REPAIR_ESTIMATE = "repair_estimate"
    DENIAL_LETTER = "denial_letter"
    RECEIPT = "receipt"
    POLICE_REPORT = "police_report"
    APPEAL_LETTER = "appeal_letter"
    OTHER = "other"


class AuditAction(str, Enum):
    POLICY_UPLOADED = "policy_uploaded"
    POLICY_ANALYZED = "policy_analyzed"
    CLAIM_CREATED = "claim_created"
    CLAIM_ANALYZED = "claim_analyzed"
    CLAIM_SANDBOX_SUBMITTED = "claim_sandbox_submitted"
    RULE_EVALUATED = "rule_evaluated"
    EVIDENCE_EXPORTED = "evidence_exported"


class ConsentType(str, Enum):
    DATA_PROCESSING = "data_processing"
    AI_ANALYSIS = "ai_analysis"
    SANDBOX_CLAIM_SUBMISSION = "sandbox_claim_submission"
    TERMS_OF_SERVICE = "terms_of_service"
