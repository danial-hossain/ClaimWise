"""Evidence-Grounded Claims Guidance and Interactive Incident Questioning Service (F3)."""

from datetime import date, datetime, timedelta, timezone
import calendar
import logging
import re
from typing import Any, Dict, List, Optional
import uuid

from app.schemas.guidance import (
    DocumentChecklistItem,
    DocumentStatus,
    GuidanceRiskLevel,
    IdentifiedObstacle,
    IncidentCategory,
    IncidentGuidanceResult,
    IncidentPresetTemplate,
    IncidentQuestionnaireRequest,
    IncidentQuestionnaireSchema,
    LiabilityType,
    NetworkStatus,
    PriorAuthStatus,
    ProviderInquiry,
    QuestionnaireField,
    QuestionnaireOption,
    ReferralStatus,
    TimelyFilingAnalysis,
)
from app.schemas.policy import PolicyExtractionResult
from app.schemas.qa import VerifiedCitation

logger = logging.getLogger("claimwise.services.claims_guidance")

# Strict regex matching unauthorized guarantee assertions
PROHIBITED_GUARANTEE_REGEX = re.compile(
    r"\b(guarantee|guaranteed|will pay|will be approved|100% covered|certain to be covered)\b",
    re.IGNORECASE,
)


class ClaimsGuidanceService:
    """Evaluates user incident questionnaire responses against policy contract evidence."""

    def get_questionnaire_schema(self) -> IncidentQuestionnaireSchema:
        """Return the structured questionnaire definition, options, and starter templates."""
        fields = [
            QuestionnaireField(
                id="incident_category",
                title="1. Healthcare Setting & Care Classification",
                description="What type of medical care was rendered during this incident?",
                field_type="single_select",
                required=True,
                options=[
                    QuestionnaireOption(
                        id=IncidentCategory.EMERGENCY_ROOM.value,
                        label="Emergency Department Care",
                        description="Acute traumatic injury, severe chest pain, or emergency facility visit.",
                        risk_implication="Advance prior authorization is waived under Clause 1.2.",
                    ),
                    QuestionnaireOption(
                        id=IncidentCategory.INPATIENT_HOSPITAL.value,
                        label="Inpatient Hospital Admission",
                        description="Overnight hospital facility stay for surgery, observation, or illness.",
                        risk_implication="Requires advance prior authorization under Clause 4.1.",
                    ),
                    QuestionnaireOption(
                        id=IncidentCategory.OUTPATIENT_SURGERY.value,
                        label="Outpatient / Ambulatory Surgery",
                        description="Day surgery performed at hospital outpatient or freestanding surgical center.",
                        risk_implication="Facility copay and surgical precertification may apply.",
                    ),
                    QuestionnaireOption(
                        id=IncidentCategory.DIAGNOSTIC_IMAGING.value,
                        label="Advanced Diagnostic Imaging (MRI / CT / PET)",
                        description="Magnetic Resonance Imaging, Computed Tomography, or nuclear scans.",
                        risk_implication="General outpatient coinsurance applies; verify pre-auth with insurer.",
                    ),
                    QuestionnaireOption(
                        id=IncidentCategory.SPECIALIST_CONSULT.value,
                        label="Specialist Physician Consultation",
                        description="Consultation with specialist (cardiology, orthopedics, oncology).",
                        risk_implication="Specialist copay tier applies; check PCP referral requirements.",
                    ),
                    QuestionnaireOption(
                        id=IncidentCategory.PHYSICAL_THERAPY.value,
                        label="Physical / Occupational Therapy",
                        description="Rehabilitative physical, speech, or occupational therapy sessions.",
                        risk_implication="Annual visit caps and referral requirements may apply.",
                    ),
                    QuestionnaireOption(
                        id=IncidentCategory.PRESCRIPTION_DRUG.value,
                        label="Specialty Pharmacy / Biologic Drug",
                        description="Injectable biologic or specialty formulary tier medication.",
                        risk_implication="Requires specialty prior auth and step therapy under Clause 6.3.",
                    ),
                    QuestionnaireOption(
                        id=IncidentCategory.ACCIDENT_INJURY.value,
                        label="Accident or Physical Trauma",
                        description="Bodily injury resulting from vehicular, sports, or external accident.",
                        risk_implication="Coordination of Benefits (COB) / Subrogation questionnaires triggered.",
                    ),
                    QuestionnaireOption(
                        id=IncidentCategory.ROUTINE_PREVENTATIVE.value,
                        label="Routine Preventative Checkup",
                        description="Annual wellness exam, preventative mammography, or immunizations.",
                        risk_implication="ACA preventative services covered at 100% in-network without copay.",
                    ),
                    QuestionnaireOption(
                        id=IncidentCategory.OTHER.value,
                        label="Other Medical Service",
                        description="General outpatient or home healthcare service.",
                        risk_implication="Subject to standard deductible and coinsurance schedule.",
                    ),
                ],
            ),
            QuestionnaireField(
                id="incident_date",
                title="2. Date of Service / Incident Date",
                description="When did the medical service or care event take place?",
                field_type="date",
                required=True,
                help_text="The deadline is checked only when it is explicitly stated in the selected policy document.",
            ),
            QuestionnaireField(
                id="network_status",
                title="3. Provider Network Affiliation",
                description="Was the treating doctor or facility contracted with your health plan?",
                field_type="single_select",
                required=True,
                options=[
                    QuestionnaireOption(
                        id=NetworkStatus.IN_NETWORK.value,
                        label="In-Network Participating Provider",
                        description="Facility and attending physician are contracted in-network.",
                        risk_implication="Lowest cost-sharing; balance billing is prohibited.",
                    ),
                    QuestionnaireOption(
                        id=NetworkStatus.OUT_OF_NETWORK.value,
                        label="Out-of-Network Non-Contracted Provider",
                        description="Elective care rendered by a non-participating provider.",
                        risk_implication="Higher coinsurance; non-covered charges may be balance-billed.",
                    ),
                    QuestionnaireOption(
                        id=NetworkStatus.EMERGENCY_OUT_OF_NETWORK.value,
                        label="Emergency Out-of-Network Facility",
                        description="Emergency care received at the nearest available hospital.",
                        risk_implication="Protected by No Surprises Act and Clause 1.2 in-network cost-sharing.",
                    ),
                    QuestionnaireOption(
                        id=NetworkStatus.UNSURE.value,
                        label="Unsure / Do Not Know",
                        description="Contracted status has not been confirmed with member services.",
                        risk_implication="Requires verification with insurer member services.",
                    ),
                ],
            ),
            QuestionnaireField(
                id="prior_auth_status",
                title="4. Prior Authorization & Precertification",
                description="Did you or your doctor obtain advance pre-service approval before care?",
                field_type="single_select",
                required=True,
                options=[
                    QuestionnaireOption(
                        id=PriorAuthStatus.OBTAINED.value,
                        label="Yes, Authorization Obtained",
                        description="Written approval letter or precertification reference number on file.",
                        risk_implication="Meets policy prerequisite for elective inpatient or specialty care.",
                    ),
                    QuestionnaireOption(
                        id=PriorAuthStatus.NOT_OBTAINED.value,
                        label="No, Not Obtained",
                        description="Care was booked without prior approval from utilization management.",
                        risk_implication="High denial risk if procedure requires prior authorization under Clause 4.1.",
                    ),
                    QuestionnaireOption(
                        id=PriorAuthStatus.EMERGENCY_WAIVED.value,
                        label="Emergency Care (Waived by Policy)",
                        description="Care was an acute emergency; advance authorization was waived under Clause 1.2.",
                        risk_implication="Prior authorization requirement legally waived for bona fide emergencies.",
                    ),
                    QuestionnaireOption(
                        id=PriorAuthStatus.NOT_APPLICABLE.value,
                        label="Not Applicable for this Service",
                        description="Routine office visit or emergency visit that does not require prior approval.",
                        risk_implication="Standard cost-sharing rules apply.",
                    ),
                    QuestionnaireOption(
                        id=PriorAuthStatus.UNSURE.value,
                        label="Unsure / Doctor Managed It",
                        description="Doctor stated they handled it, but you have no written approval letter.",
                        risk_implication="Advisory: request written auth number from physician billing department.",
                    ),
                ],
            ),
            QuestionnaireField(
                id="liability_type",
                title="5. Third-Party Liability & Coordination of Benefits (COB)",
                description="Did this medical incident involve an external accident, vehicle, or workplace event?",
                field_type="single_select",
                required=True,
                options=[
                    QuestionnaireOption(
                        id=LiabilityType.NONE_STANDARD.value,
                        label="No, Standard Illness / Medical Care",
                        description="Regular medical condition unrelated to external accidents or work.",
                        risk_implication="Primary health insurance pays directly without subrogation delays.",
                    ),
                    QuestionnaireOption(
                        id=LiabilityType.MOTOR_VEHICLE.value,
                        label="Motor Vehicle Collision (Auto Accident)",
                        description="Injury sustained in a car accident involving auto PIP / MedPay.",
                        risk_implication="Auto PIP/MedPay is primary; health insurer will require subrogation form.",
                    ),
                    QuestionnaireOption(
                        id=LiabilityType.WORKPLACE_INJURY.value,
                        label="Workplace / Occupational Injury",
                        description="Injury sustained on the job or during employment duties.",
                        risk_implication="Excluded under Clause 8.2; must be billed to Workers' Compensation.",
                    ),
                    QuestionnaireOption(
                        id=LiabilityType.THIRD_PARTY_LIABILITY.value,
                        label="Premises / Slip-and-Fall Liability",
                        description="Injury on commercial property with third-party liability coverage.",
                        risk_implication="Insurer may assert subrogation rights to recover medical payments.",
                    ),
                    QuestionnaireOption(
                        id=LiabilityType.SECONDARY_INSURANCE.value,
                        label="Secondary Health Coverage Exists",
                        description="Patient is covered under a spouse or parent secondary health plan.",
                        risk_implication="Requires primary EOB before secondary payer will process remaining balances.",
                    ),
                ],
            ),
            QuestionnaireField(
                id="documentation_checklist",
                title="6. Available Documentation Checklist",
                description="Which documents do you currently have in your possession?",
                field_type="checkbox_group",
                required=False,
                options=[
                    QuestionnaireOption(id="has_itemized_bill", label="Itemized Hospital or Provider Bill (UB-04 / CMS-1500)"),
                    QuestionnaireOption(id="has_medical_records", label="Attending Physician Clinical Notes / Operative Report"),
                    QuestionnaireOption(id="has_prior_auth_letter", label="Prior Authorization / Precertification Approval Letter"),
                    QuestionnaireOption(id="has_referral_letter", label="Primary Care Physician (PCP) Written Referral"),
                    QuestionnaireOption(id="has_accident_report", label="Police, Accident, or Workplace Incident Report"),
                    QuestionnaireOption(id="has_receipt_of_payment", label="Receipt of Member Copayment or Deductible Deposit"),
                ],
            ),
            QuestionnaireField(
                id="user_notes",
                title="7. Additional Incident Notes / Member Questions",
                description="Enter any specific details, provider names, or billing notes.",
                field_type="text",
                required=False,
                help_text="Treated strictly as untrusted clinical data under prompt-injection defenses.",
            ),
        ]

        presets = [
            IncidentPresetTemplate(
                id="preset-er-emergency",
                title="Emergency Room Visit",
                description="Acute emergency care at hospital emergency department.",
                category=IncidentCategory.EMERGENCY_ROOM,
                default_answers={
                    "incident_category": IncidentCategory.EMERGENCY_ROOM.value,
                    "network_status": NetworkStatus.IN_NETWORK.value,
                    "prior_auth_status": PriorAuthStatus.EMERGENCY_WAIVED.value,
                    "referral_status": ReferralStatus.NOT_REQUIRED.value,
                    "liability_type": LiabilityType.NONE_STANDARD.value,
                    "has_itemized_bill": True,
                    "has_medical_records": True,
                },
            ),
            IncidentPresetTemplate(
                id="preset-inpatient-surgery",
                title="Scheduled Inpatient Surgery",
                description="Elective surgical admission requiring overnight hospital stay.",
                category=IncidentCategory.INPATIENT_HOSPITAL,
                default_answers={
                    "incident_category": IncidentCategory.INPATIENT_HOSPITAL.value,
                    "network_status": NetworkStatus.IN_NETWORK.value,
                    "prior_auth_status": PriorAuthStatus.OBTAINED.value,
                    "referral_status": ReferralStatus.NOT_REQUIRED.value,
                    "liability_type": LiabilityType.NONE_STANDARD.value,
                    "has_itemized_bill": True,
                    "has_medical_records": True,
                    "has_prior_auth_letter": True,
                },
            ),
            IncidentPresetTemplate(
                id="preset-mri-imaging",
                title="Outpatient MRI / CT Imaging",
                description="Diagnostic imaging ordered by treating physician.",
                category=IncidentCategory.DIAGNOSTIC_IMAGING,
                default_answers={
                    "incident_category": IncidentCategory.DIAGNOSTIC_IMAGING.value,
                    "network_status": NetworkStatus.IN_NETWORK.value,
                    "prior_auth_status": PriorAuthStatus.UNSURE.value,
                    "referral_status": ReferralStatus.NOT_REQUIRED.value,
                    "liability_type": LiabilityType.NONE_STANDARD.value,
                    "has_itemized_bill": True,
                    "has_medical_records": False,
                },
            ),
            IncidentPresetTemplate(
                id="preset-auto-accident",
                title="Motor Vehicle Accident Trauma",
                description="Emergency care following a motor vehicle collision.",
                category=IncidentCategory.ACCIDENT_INJURY,
                default_answers={
                    "incident_category": IncidentCategory.ACCIDENT_INJURY.value,
                    "network_status": NetworkStatus.EMERGENCY_OUT_OF_NETWORK.value,
                    "prior_auth_status": PriorAuthStatus.EMERGENCY_WAIVED.value,
                    "referral_status": ReferralStatus.NOT_REQUIRED.value,
                    "liability_type": LiabilityType.MOTOR_VEHICLE.value,
                    "has_itemized_bill": True,
                    "has_medical_records": True,
                    "has_accident_report": True,
                },
            ),
        ]

        return IncidentQuestionnaireSchema(fields=fields, presets=presets)

    def evaluate_incident(
        self,
        request: IncidentQuestionnaireRequest,
        policy: PolicyExtractionResult,
    ) -> IncidentGuidanceResult:
        """Build guidance only from clauses extracted from the selected policy PDF."""
        guidance_id = f"gui-{uuid.uuid4().hex[:12]}"
        policy_id = policy.policy_id or "policy"
        policy_name = policy.document_name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if policy_name.lower().endswith(".pdf"):
            policy_name = policy_name[:-4]

        today = date.today()
        try:
            incident_date = date.fromisoformat(request.incident_date.strip()) if request.incident_date else today
        except ValueError:
            incident_date = today
        try:
            deadline_reference_date = date.fromisoformat(request.deadline_reference_date.strip()) if request.deadline_reference_date else None
        except ValueError:
            deadline_reference_date = None

        clauses = [clause for clause in policy.clauses if clause.is_clause and clause.text.strip()]
        notes = (request.user_notes or "").lower()
        category_terms = {
            IncidentCategory.EMERGENCY_ROOM: "emergency urgent care",
            IncidentCategory.INPATIENT_HOSPITAL: "hospital inpatient admission",
            IncidentCategory.OUTPATIENT_SURGERY: "outpatient surgery procedure",
            IncidentCategory.DIAGNOSTIC_IMAGING: "diagnostic imaging scan",
            IncidentCategory.SPECIALIST_CONSULT: "specialist consultation",
            IncidentCategory.PHYSICAL_THERAPY: "physical therapy rehabilitation",
            IncidentCategory.PRESCRIPTION_DRUG: "prescription medication pharmacy",
            IncidentCategory.ACCIDENT_INJURY: "accident injury incident",
            IncidentCategory.ROUTINE_PREVENTATIVE: "preventive routine care",
            IncidentCategory.OTHER: "",
        }
        context = f"{notes} {category_terms.get(request.incident_category, '')}".lower()
        stop_words = {"about", "after", "before", "claim", "claimwise", "details", "happened", "incident", "location", "policy", "provided", "type", "what", "with", "from", "this", "that", "have", "there", "their", "your", "were", "where", "when", "then", "into", "estimated", "loss", "not", "sure"}
        context_terms = {word for word in re.findall(r"[a-z]{3,}", context) if word not in stop_words}

        # Policy PDFs and incident descriptions often use different everyday terms.
        # Expand only the search vocabulary; every displayed result remains an exact PDF clause.
        synonym_groups = (
            {"car", "auto", "vehicle", "motor", "collision", "crash"},
            {"stolen", "theft", "robbed", "burglary"},
            {"damaged", "damage", "broken", "repair"},
            {"bag", "baggage", "luggage"},
            {"delay", "delayed", "late"},
            {"flight", "airline", "carrier", "transport"},
            {"medical", "health", "hospital", "treatment", "injury", "illness"},
            {"home", "house", "property", "dwelling", "water", "fire"},
        )
        for group in synonym_groups:
            if context_terms & group:
                context_terms.update(group)

        def relevance(clause: Any) -> int:
            text = f"{getattr(clause, 'clause_heading', '') or ''} {clause.text}".lower()
            terms = set(re.findall(r"[a-z]{4,}", text))
            return len(context_terms & terms)

        filing_terms = re.compile(r"claim|filing|submit|submission|notice of loss|proof of loss|benefit", re.I)
        filing_clauses = [c for c in clauses if filing_terms.search(f"{c.clause_heading or ''} {c.text}")]
        deadline_clause = None
        deadline_days = None
        deadline_match = None
        deadline_anchor = "policy reference date"
        for clause in filing_clauses:
            match = re.search(r"\b(?:within|no later than|not later than|before the end of)\s+(\d{1,4})\s+(?:calendar\s+)?(days?|weeks?|months?|years?)\b", clause.text, re.I)
            sentence_start = clause.text.rfind(".", 0, match.start()) + 1 if match else 0
            if match and filing_terms.search(clause.text[sentence_start:match.start()]):
                deadline_clause = clause
                deadline_match = match
                clause_lower = clause.text.lower()
                if re.search(r"\b(return date|date of (your )?return|when you return|journey ends)\b", clause_lower):
                    deadline_anchor = "trip return date"
                elif re.search(r"\b(date of service|service date|treatment date)\b", clause_lower):
                    deadline_anchor = "date of service"
                elif re.search(r"\b(incident date|date of (the )?(incident|accident|loss)|occurrence date)\b", clause_lower):
                    deadline_anchor = "incident date"
                amount = int(match.group(1))
                unit = match.group(2).lower()
                if unit.startswith("day"):
                    deadline_days = amount
                elif unit.startswith("week"):
                    deadline_days = amount * 7
                else:
                    months = amount * (12 if unit.startswith("year") else 1)
                    absolute_month = incident_date.month - 1 + months
                    year = incident_date.year + absolute_month // 12
                    month = absolute_month % 12 + 1
                    day = min(incident_date.day, calendar.monthrange(year, month)[1])
                    deadline_days = (date(year, month, day) - incident_date).days
                break

        def citation(clause: Any) -> VerifiedCitation:
            return VerifiedCitation(
                clause_id=clause.clause_id,
                page_number=clause.page_number,
                exact_quote=clause.text.strip(),
                policy_id=policy_id,
                clause_heading=clause.clause_heading or "Policy provision",
                verified=True,
            )

        timely_citation = citation(deadline_clause) if deadline_clause else None
        anchor_date = deadline_reference_date if deadline_anchor == "trip return date" else incident_date if deadline_anchor in {"incident date", "date of service"} else None
        deadline_date = anchor_date + timedelta(days=deadline_days) if deadline_days is not None and anchor_date else None
        days_elapsed = max(0, (today - anchor_date).days) if anchor_date else 0
        days_remaining = (deadline_days - days_elapsed) if deadline_days is not None and anchor_date else None
        is_timely = days_remaining >= 0 if days_remaining is not None else None
        if deadline_match and deadline_clause:
            deadline_label = deadline_match.group(0)
            if days_remaining is not None and days_remaining < 0:
                timely_warning = (f"CRITICAL: The timely filing deadline of {deadline_label} from the {deadline_anchor} has expired. The calculated due date was {deadline_date.isoformat()} ({days_elapsed} days elapsed).")
            else:
                timely_warning = (f"The selected policy states a filing period of {deadline_label} from the {deadline_anchor}. The calculated due date is {deadline_date.isoformat()}." if deadline_date else f"The selected policy states a filing period of {deadline_label} from the {deadline_anchor}. Enter that date to calculate a due date.")
        else:
            timely_warning = None
        timely_filing = TimelyFilingAnalysis(
            incident_date=incident_date.isoformat(),
            evaluation_date=today.isoformat(),
            days_elapsed=days_elapsed,
            timely_filing_limit_days=deadline_days,
            days_remaining=days_remaining,
            is_timely=is_timely,
            filing_deadline_date=deadline_date.isoformat() if deadline_date else None,
            warning_message=timely_warning,
            deadline_anchor=deadline_anchor if deadline_clause else None,
            citation=timely_citation,
        )

        doc_terms = re.compile(r"\b(documents?|proof|records?|receipts?|invoices?|reports?|certificates?|forms?|evidence|statements?|supporting|charges?|notes?|itemized)\b", re.I)
        obligation_terms = re.compile(r"\b(must|shall|required|furnish|submit|file|include)\b", re.I)
        waiver_pattern = re.compile(r"\b(not required|no .* required|waived|waiver|not applicable)\b", re.I)
        candidates = [
            c for c in clauses
            if doc_terms.search(c.text) and obligation_terms.search(c.text) and not waiver_pattern.search(c.text)
        ]
        if context_terms:
            ranked = sorted(candidates, key=lambda c: (relevance(c), c.page_number), reverse=True)
            context_docs = [c for c in ranked if relevance(c) > 0]
            filing_docs = [c for c in ranked if filing_terms.search(f"{c.clause_heading or ''} {c.text}")]
            seen_clause_ids = set()
            relevant_docs = []
            for c in (context_docs + filing_docs):
                if c.clause_id not in seen_clause_ids:
                    seen_clause_ids.add(c.clause_id)
                    relevant_docs.append(c)
        else:
            relevant_docs = candidates
        relevant_docs = relevant_docs[:12]
        related_clauses = sorted(
            [clause for clause in clauses if relevance(clause) > 0],
            key=lambda clause: (relevance(clause), clause.page_number),
            reverse=True,
        )[:8]
        claim_basis_terms = re.compile(
            r"\b(cover(?:age|ed)?|benefit|reimburse(?:ment|d)?|insured|loss|damage|expense|indemnif\w*|eligible|exclu\w*)\b",
            re.I,
        )
        potential_claim_clauses = [
            citation(clause)
            for clause in related_clauses
            if claim_basis_terms.search(f"{clause.clause_heading or ''} {clause.text}")
        ][:5]
        exclusion_pattern = re.compile(r"\b(exclu\w*|not covered|we will not pay|will not be covered|no cover)\b", re.I)
        positive_pattern = re.compile(r"\b(we will pay|we will reimburse|we will replace|we will provide cover|we cover|covered under|cover is provided|benefit is payable|you can claim|we pay)\b", re.I)
        relevant_exclusions = [c for c in related_clauses if exclusion_pattern.search(c.text)]
        relevant_positive = [c for c in related_clauses if positive_pattern.search(c.text) and not exclusion_pattern.search(c.text)]
        if relevant_positive and not relevant_exclusions:
            claimability_status = "potentially_claimable"
            claimability_reason = "The policy contains a benefit clause that matches the incident description. The insurer must confirm that the policy conditions and exclusions are satisfied."
            claimability_citations = [citation(c) for c in relevant_positive[:3]]
        elif relevant_exclusions and not relevant_positive:
            claimability_status = "not_supported"
            claimability_reason = "The relevant policy wording found is an exclusion or limitation; the selected PDF does not show a matching benefit clause for this incident."
            claimability_citations = [citation(c) for c in relevant_exclusions[:3]]
        else:
            claimability_status = "cannot_determine"
            claimability_reason = "The extracted clauses do not establish whether this incident is covered. The insurer needs to confirm which benefit and conditions apply."
            claimability_citations = [citation(c) for c in (relevant_positive + relevant_exclusions)[:3]]

        provided_titles = [title.strip().lower() for title in request.provided_document_titles if title.strip()]
        if request.has_itemized_bill:
            provided_titles.extend(["itemized bill", "itemized", "charges", "bill", "ub-04", "cms-1500"])
        if request.has_medical_records:
            provided_titles.extend(["medical records", "clinical notes", "clinical", "chart notes", "diagnosis", "report"])
        if request.has_prior_auth_letter:
            provided_titles.extend(["prior authorization", "precertification", "approval letter"])
        doc_checklist: List[DocumentChecklistItem] = []

        for index, clause in enumerate(relevant_docs):
            heading = (clause.clause_heading or "").strip()
            title = heading or f"Policy document requirement {index + 1} (clause {clause.clause_id})"
            lowered = f"{title} {clause.text}".lower()
            is_provided = any(item in lowered or lowered in item for item in provided_titles)
            mandatory = bool(re.search(r"\b(must|shall|required)\b", clause.text, re.I)) and not bool(waiver_pattern.search(clause.text))
            doc_checklist.append(DocumentChecklistItem(
                item_id=f"policy-{clause.clause_id}",
                title=title,
                description=clause.text.strip(),
                is_mandatory=mandatory,
                status=DocumentStatus.PROVIDED if is_provided else DocumentStatus.MISSING if mandatory else DocumentStatus.RECOMMENDED,
                why_needed="This requirement was identified in the selected policy PDF. Review the cited clause to confirm it applies to your claim.",
                policy_citation=citation(clause),
            ))

        obstacles: List[IdentifiedObstacle] = []
        action_steps: List[str] = []
        if deadline_days is not None and days_remaining is not None and days_remaining < 0 and timely_citation:
            obstacles.append(IdentifiedObstacle(
                id="policy-filing-deadline",
                title="Timely Filing Window Expired",
                severity="critical",
                description=f"The selected policy clause states a {deadline_days}-day filing period. Based on the incident date entered, the calculated deadline was {deadline_date.isoformat()} ({days_elapsed} days elapsed).",
                mitigation_strategy="Contact the insurer promptly to request a good-cause extension or appeal based on extenuating circumstances.",
                citation=timely_citation,
            ))
            action_steps.append("Contact the insurer promptly about the expired filing period and ask what appeal options apply to your situation.")
        elif deadline_days is not None and days_remaining is not None and days_remaining <= 21 and timely_citation:
            action_steps.append(f"Review the filing-period clause and contact the insurer before the calculated date {deadline_date.isoformat()}.")

        # Missing Prior Authorization Obstacle Check
        if request.prior_auth_status == PriorAuthStatus.NOT_OBTAINED:
            auth_clause = None
            # Prioritize category-specific prior authorization (e.g. inpatient admissions)
            if request.incident_category == IncidentCategory.INPATIENT_HOSPITAL:
                for clause in clauses:
                    text_lower = clause.text.lower()
                    if "prior authorization" in text_lower and "inpatient" in text_lower:
                        auth_clause = clause
                        break
            if not auth_clause:
                for clause in clauses:
                    text_lower = clause.text.lower()
                    if "prior authorization" in text_lower and re.search(r"requir|inpatient|elective", text_lower) and "not required for emergency" not in text_lower:
                        auth_clause = clause
                        break
            if not auth_clause:
                for clause in clauses:
                    text_lower = clause.text.lower()
                    if "prior authorization" in text_lower and obligation_terms.search(clause.text):
                        auth_clause = clause
                        break
            cit = citation(auth_clause) if auth_clause else None
            obstacles.append(IdentifiedObstacle(
                id=f"policy-auth-{auth_clause.clause_id if auth_clause else 'missing'}",
                title="Missing Prior Authorization Required",
                severity="critical",
                description="Advance prior authorization was not obtained for this inpatient, surgical, or elective healthcare service.",
                mitigation_strategy="Contact the treating provider billing department and insurer immediately to initiate a retrospective review or clinical urgency exception.",
                citation=cit,
            ))
            action_steps.append("Request retrospective prior authorization from your treating physician's administrative office.")

        # Workplace Injury / Workers' Compensation Obstacle Check
        if request.liability_type == LiabilityType.WORKPLACE_INJURY:
            wc_clause = None
            for clause in clauses:
                if re.search(r"worker'?s?['’]?\s+comp|work-related|employment|on the job|occupational", clause.text, re.I):
                    wc_clause = clause
                    break
            cit = citation(wc_clause) if wc_clause else None
            obstacles.append(IdentifiedObstacle(
                id=f"policy-wc-{wc_clause.clause_id if wc_clause else 'exclusion'}",
                title="Workers' Compensation Exclusion / Third-Party Liability",
                severity="critical",
                description="Injuries occurring in the workplace or course of employment are excluded from standard health coverage and must be submitted to Workers' Compensation.",
                mitigation_strategy="File an employer incident report (Form WC-1) with HR and obtain the employer's Workers' Compensation carrier claim details.",
                citation=cit,
            ))
            action_steps.append("Notify employer HR department and obtain Workers' Compensation carrier billing address and claim number.")

        citations = []
        seen_ids = set()
        for clause in ([deadline_clause] if deadline_clause else []) + relevant_docs + related_clauses:
            if clause and clause.clause_id not in seen_ids:
                citations.append(citation(clause))
                seen_ids.add(clause.clause_id)
        for obstacle in obstacles:
            if obstacle.citation and obstacle.citation.clause_id not in seen_ids:
                citations.append(obstacle.citation)
                seen_ids.add(obstacle.citation.clause_id)

        mandatory_items = [item for item in doc_checklist if item.is_mandatory]
        missing_items = [item for item in mandatory_items if item.status == DocumentStatus.MISSING]
        critical_obstacles = [obs for obs in obstacles if obs.severity == "critical"]

        if not clauses:
            score = 0
            risk_level = GuidanceRiskLevel.MEDIUM_RISK
            readiness_summary = "This PDF has no extracted policy clauses to support claim guidance. Re-upload a readable policy document or review the original policy with the insurer."
        else:
            base_score = 100 - (round(50 * len(missing_items) / len(mandatory_items)) if mandatory_items else 0)
            if critical_obstacles:
                score = max(10, base_score - 30 * len(critical_obstacles))
            else:
                score = max(50, base_score)

            if is_timely is False:
                score = min(score, 30)

            if critical_obstacles or is_timely is False:
                risk_level = GuidanceRiskLevel.HIGH_RISK
            elif missing_items:
                risk_level = GuidanceRiskLevel.MEDIUM_RISK
            else:
                risk_level = GuidanceRiskLevel.LOW_RISK

            if critical_obstacles:
                readiness_summary = f"Claim readiness is compromised by {len(critical_obstacles)} critical obstacle(s), including {critical_obstacles[0].title}. Address these items before filing."
            elif missing_items:
                readiness_summary = f"The selected policy requires documentation; {len(missing_items)} mandatory document(s) are still needed before submission."
            else:
                readiness_summary = "All core documentation has been identified as provided. Timely filing and network prerequisites are satisfied."

        if not action_steps:
            action_steps.append("Review each cited policy clause and confirm it applies to the specific incident you described.")
        if doc_checklist:
            action_steps.append("Gather the documents listed from the selected policy and mark what you already have.")
        if not clauses:
            action_steps.append("The PDF text did not provide clauses for this analysis; upload a clearer policy PDF or ask the insurer for the applicable requirements.")

        return IncidentGuidanceResult(
            guidance_id=guidance_id,
            policy_id=policy_id,
            policy_name=policy_name,
            readiness_score_pct=score,
            risk_level=risk_level,
            readiness_summary=readiness_summary,
            incident_category=request.incident_category,
            timely_filing=timely_filing,
            document_checklist=doc_checklist,
            obstacles=obstacles,
            action_plan_steps=action_steps,
            provider_inquiries=[],
            claimability_status=claimability_status,
            claimability_reason=claimability_reason,
            claimability_citations=claimability_citations,
            claim_amount_cents=request.estimated_loss_cents,
            potential_claim_clauses=potential_claim_clauses,
            verified_citations=citations,
            evaluated_at=datetime.now(timezone.utc),
        )

claims_guidance_service = ClaimsGuidanceService()
