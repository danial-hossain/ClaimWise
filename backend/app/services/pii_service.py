"""Automated PII & PHI Detection and Masking Engine for ClaimWise.

Protects consumer privacy and ensures HIPAA & SOC 2 compliance by detecting,
redacting, and tokenizing sensitive identifiers before LLM ingestion, logging,
or disk persistence:
- Social Security Numbers (SSN)
- Health Plan Member / Policy IDs
- Dates of Birth (DOB)
- Phone Numbers
- Email Addresses
- Credit Card / Financial Account Numbers
- National Provider Identifiers (NPI)
- Patient / Claimant Names
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.schemas.security import (
    PermissionTier,
    PermissionTierDetail,
    PIICategory,
    PIIDetectionItem,
    PIIMaskRequest,
    PIIMaskResult,
)

logger = logging.getLogger("claimwise.pii_service")

# Regular expression patterns for targeted PII entity detection
PATTERNS = {
    PIICategory.SSN: re.compile(
        r"\b(?!000|666|9\d{2})(\d{3})[- ]?(?!00)(\d{2})[- ]?(?!0000)(\d{4})\b"
    ),
    PIICategory.PHONE: re.compile(
        r"\b(?:\+?1[-. ]?)?\(?([2-9]\d{2})\)?[-. ]?([2-9]\d{2})[-. ]?(\d{4})\b"
    ),
    PIICategory.EMAIL: re.compile(
        r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"
    ),
    PIICategory.CREDIT_CARD: re.compile(
        r"\b(?:\d{4}[- ]?){3}(\d{4})\b"
    ),
    PIICategory.DOB: re.compile(
        r"\b(?:DOB|Date of Birth|Birthdate|Birth\s*Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b",
        re.IGNORECASE,
    ),
    PIICategory.MEMBER_ID: re.compile(
        r"\b(?:Member\s*(?:ID|#|Number)?|Policy\s*(?:ID|#|Number)?|Subscriber\s*ID)[:\s]*([A-Z0-9-]{6,16})\b|\b([A-Z]{3}\d{8,10})\b",
        re.IGNORECASE,
    ),
    PIICategory.NPI: re.compile(
        r"\b(?:NPI|Provider\s*NPI|National\s*Provider\s*ID)[:\s]*([1-9]\d{9})\b",
        re.IGNORECASE,
    ),
    PIICategory.PATIENT_NAME: re.compile(
        r"\b(?:Patient\s*(?:Name)?|Claimant|Insured\s*Name|Member\s*Name)[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b",
        re.IGNORECASE,
    ),
}


class PIIMaskingService:
    """Enterprise PII and PHI detection and redaction service."""

    def mask_text(
        self,
        text: str,
        preserve_last_4: bool = True,
        categories: Optional[List[PIICategory]] = None,
    ) -> PIIMaskResult:
        """
        Scan string for sensitive PII and replace with anonymized or tokenized masks.
        Tracks character offsets and returns detailed detection telemetry.
        """
        if not text:
            return PIIMaskResult(
                original_char_count=0,
                masked_text="",
                pii_detected_count=0,
                categories_detected=[],
                detections=[],
            )

        active_categories = categories or list(PATTERNS.keys())
        detections: List[PIIDetectionItem] = []
        unique_categories: Set[PIICategory] = set()

        # Find all match spans across active categories
        # Collect (start, end, category, masked_repr)
        replacements: List[Tuple[int, int, PIICategory, str]] = []

        for cat in active_categories:
            pattern = PATTERNS.get(cat)
            if not pattern:
                continue

            for match in pattern.finditer(text):
                start, end = match.span()
                matched_str = match.group(0)

                masked_repr = self._format_mask(cat, match, matched_str, preserve_last_4)
                replacements.append((start, end, cat, masked_repr))
                unique_categories.add(cat)

        # Sort replacements by start index
        # Resolve any overlapping matches by favoring earlier or longer matches
        replacements.sort(key=lambda r: (r[0], -(r[1] - r[0])))
        non_overlapping: List[Tuple[int, int, PIICategory, str]] = []
        last_end = 0

        for r in replacements:
            start, end, cat, masked_repr = r
            if start >= last_end:
                non_overlapping.append(r)
                last_end = end
                detections.append(
                    PIIDetectionItem(
                        category=cat,
                        masked_value=masked_repr,
                        start_pos=start,
                        end_pos=end,
                        confidence=1.0,
                    )
                )

        # Build final masked string
        masked_builder = []
        curr_idx = 0
        for start, end, cat, masked_repr in non_overlapping:
            masked_builder.append(text[curr_idx:start])
            masked_builder.append(masked_repr)
            curr_idx = end
        masked_builder.append(text[curr_idx:])

        final_masked_text = "".join(masked_builder)

        return PIIMaskResult(
            original_char_count=len(text),
            masked_text=final_masked_text,
            pii_detected_count=len(non_overlapping),
            categories_detected=sorted(list(unique_categories), key=lambda c: c.value),
            detections=detections,
        )

    def _format_mask(
        self,
        category: PIICategory,
        match: re.Match,
        full_match_text: str,
        preserve_last_4: bool,
    ) -> str:
        """Generate appropriate masked string based on entity category."""
        if category == PIICategory.SSN:
            if preserve_last_4:
                # Extract digits
                digits = re.sub(r"\D", "", full_match_text)
                last_4 = digits[-4:] if len(digits) >= 4 else "XXXX"
                return f"***-**-{last_4}"
            return "[REDACTED_SSN]"

        elif category == PIICategory.PHONE:
            if preserve_last_4:
                digits = re.sub(r"\D", "", full_match_text)
                last_4 = digits[-4:] if len(digits) >= 4 else "XXXX"
                return f"(***) ***-{last_4}"
            return "[REDACTED_PHONE]"

        elif category == PIICategory.EMAIL:
            # Mask local part: e.g. j***@example.com
            try:
                local, domain = full_match_text.split("@", 1)
                masked_local = (local[0] + "***") if local else "***"
                return f"{masked_local}@{domain}"
            except Exception:
                return "[REDACTED_EMAIL]"

        elif category == PIICategory.CREDIT_CARD:
            if preserve_last_4:
                digits = re.sub(r"\D", "", full_match_text)
                last_4 = digits[-4:] if len(digits) >= 4 else "XXXX"
                return f"****-****-****-{last_4}"
            return "[REDACTED_CARD]"

        elif category == PIICategory.DOB:
            prefix = full_match_text.split(":")[0] if ":" in full_match_text else "DOB"
            return f"{prefix}: [REDACTED_DOB]"

        elif category == PIICategory.MEMBER_ID:
            if preserve_last_4:
                clean_id = re.sub(r"[^A-Za-z0-9]", "", full_match_text)
                last_4 = clean_id[-4:] if len(clean_id) >= 4 else "XXXX"
                prefix = full_match_text.split(":")[0] if ":" in full_match_text else "Member ID"
                return f"{prefix}: ***-****-{last_4}"
            return "[REDACTED_MEMBER_ID]"

        elif category == PIICategory.NPI:
            return "NPI: [REDACTED_NPI_******]"

        elif category == PIICategory.PATIENT_NAME:
            prefix = full_match_text.split(":")[0] if ":" in full_match_text else "Patient"
            return f"{prefix}: [REDACTED_PATIENT_NAME]"

        return "[REDACTED_PII]"

    def sanitize_dictionary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively scan dictionary keys and values to sanitize sensitive PII/PHI."""
        sanitized: Dict[str, Any] = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(term in k_lower for term in ["ssn", "password", "token", "secret", "credit_card"]):
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, dict):
                sanitized[k] = self.sanitize_dictionary(v)
            elif isinstance(v, list):
                sanitized[k] = [
                    self.sanitize_dictionary(item) if isinstance(item, dict)
                    else self.mask_text(str(item)).masked_text if isinstance(item, str)
                    else item
                    for item in v
                ]
            elif isinstance(v, str):
                sanitized[k] = self.mask_text(v).masked_text
            else:
                sanitized[k] = v
        return sanitized

    def get_permission_tiers(self) -> List[PermissionTierDetail]:
        """Return canonical formal specifications of the 5-Tier Permission Security Model."""
        return [
            PermissionTierDetail(
                tier=0,
                name="read_only",
                title="Tier 0: Read Only",
                description="Browse, inspect, and verify loaded policies and clauses. AI suggestions and drafting are inactive.",
                allowed_actions=[
                    "policy.browse",
                    "policy.view_clauses",
                    "audit.view_events",
                    "health.check",
                ],
                prohibited_actions=[
                    "qa.ask",
                    "appeal.generate",
                    "claims.adjudicate",
                    "sandbox.submit",
                    "policy.delete",
                ],
                requires_human_confirmation=False,
                is_autonomous_external_transmission_allowed=False,
            ),
            PermissionTierDetail(
                tier=1,
                name="suggest_mode",
                title="Tier 1: Suggest Mode (Default)",
                description="AI provides grounded answers, scenario analyses, and coverage gap evaluations citing exact contract clauses. Cannot alter or persist records.",
                allowed_actions=[
                    "qa.ask",
                    "coverage.analyze",
                    "portfolio.analyze",
                    "rules.calculate_illustrative",
                    "claims.guidance.evaluate",
                ],
                prohibited_actions=[
                    "claim.create",
                    "appeal.save",
                    "sandbox.submit",
                    "live_edi.transmit",
                ],
                requires_human_confirmation=False,
                is_autonomous_external_transmission_allowed=False,
            ),
            PermissionTierDetail(
                tier=2,
                name="draft_mode",
                title="Tier 2: Draft Mode",
                description="Generates editable claim statements and denial appeal letters. Requires mandatory human-in-the-loop review before export or use.",
                allowed_actions=[
                    "appeal.generate_draft",
                    "appeal.edit_draft",
                    "claim.create_from_bill",
                    "pdf.export_reviewed_eob",
                    "pdf.export_reviewed_appeal",
                ],
                prohibited_actions=[
                    "appeal.unreviewed_export",
                    "sandbox.submit",
                    "live_edi.transmit",
                ],
                requires_human_confirmation=True,
                is_autonomous_external_transmission_allowed=False,
            ),
            PermissionTierDetail(
                tier=3,
                name="sandbox_submit",
                title="Tier 3: Sandbox Submit",
                description="Safe local EDI 837P simulation against mock payer endpoints. Strictly requires explicit user confirmation dialog and is isolated from real insurer APIs.",
                allowed_actions=[
                    "claim.adjudicate_itemized",
                    "sandbox.simulate_submission",
                    "sandbox.inspect_response",
                ],
                prohibited_actions=[
                    "live_payer.connect",
                    "live_edi.transmit",
                    "unconfirmed_sandbox_submit",
                ],
                requires_human_confirmation=True,
                is_autonomous_external_transmission_allowed=False,
            ),
            PermissionTierDetail(
                tier=4,
                name="blocked_prohibited",
                title="Tier 4: Blocked & Prohibited",
                description="Actions strictly barred by architecture: live carrier transmission, cross-user data access, and unverified AI automated execution.",
                allowed_actions=[],
                prohibited_actions=[
                    "live_carrier.transmission",
                    "cross_tenant.data_access",
                    "unverified_execution",
                    "raw_phi_egress",
                ],
                requires_human_confirmation=False,
                is_autonomous_external_transmission_allowed=False,
            ),
        ]


# Global singleton instance
pii_service = PIIMaskingService()
