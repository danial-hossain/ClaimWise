"""Upgrade stored extraction metadata using an integrity-checked original PDF."""
from app.schemas.policy import PolicyExtractionResult
from app.services.document_service import document_service, EXTRACTION_VERSION


def refresh_policy_evidence(record: PolicyExtractionResult, pdf_bytes: bytes) -> PolicyExtractionResult:
    if record.extraction_version >= EXTRACTION_VERSION:
        return record
    if document_service.calculate_sha256(pdf_bytes) != record.document_hash:
        raise ValueError("Original PDF does not match the stored policy hash")
    fresh = document_service.process_pdf(pdf_bytes, filename=record.document_name)
    if fresh.status != "success":
        raise ValueError("The original policy could not be re-extracted")
    return fresh.model_copy(update={"policy_id": record.policy_id, "user_id": record.user_id,
        "persistence_mode": record.persistence_mode, "uploaded_at": record.uploaded_at})
