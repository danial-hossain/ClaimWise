"""Refresh one explicitly named stored policy from its integrity-checked original PDF."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.api.v1.endpoints.policies import _policy_pdf_path
from app.db.local_store import local_store
from app.services.policy_evidence_refresh import refresh_policy_evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("policy_id")
    args = parser.parse_args()
    record = local_store.get_policy(args.policy_id)
    if record is None:
        raise SystemExit("Policy not found")
    pdf = _policy_pdf_path(record.document_hash)
    if not pdf.is_file():
        raise SystemExit("Original PDF unavailable; re-upload the policy")
    backup = Path("data/coverage-debug")
    backup.mkdir(exist_ok=True)
    (backup / (args.policy_id + "-previous-extraction.json")).write_text(record.model_dump_json(indent=2),encoding="utf-8")
    fresh = refresh_policy_evidence(record,pdf.read_bytes())
    local_store.save_policy(args.policy_id,fresh,user_id=record.user_id)
    loaded = local_store.get_policy(args.policy_id)
    if loaded.extraction_version != fresh.extraction_version or loaded.clauses != fresh.clauses:
        raise SystemExit("Persisted extraction verification failed")
    print(f"Refreshed extraction version {loaded.extraction_version}; {len(loaded.clauses)} clauses; read-back verified.")

if __name__ == "__main__":
    main()
