# Local artifact cleanup

The user explicitly requested removal of the repository-root output files after reference
and exact-path checks. The following files were removed:

- `E:\3.2\FinTech\ClaimWise\output.txt`
- `E:\3.2\FinTech\ClaimWise\output_backup_m5.txt`

Their byte counts and SHA-256 hashes are recorded in [removed-output-files.json](removed-output-files.json).
No content or credentials are copied into that record. Searches found no application, test,
or script consumers of these files. The earlier refactor report's retention statement describes
the state before this subsequent user-authorized cleanup.

Root-anchored ignore rules prevent these exact output names from cluttering future checkouts.
No wildcard rule was added for PDFs, README files, fixtures, or reports.

`E:\3.2\FinTech\ClaimWise\test_pdfs\` was **retained**, because removal was conditional on
having no important dependencies. Active dependencies include:

- `backend/app/services/benchmarks/qa_benchmark_service.py`: loads sample policies A/B and
  raises `FileNotFoundError` when they are absent.
- `backend/scripts/run_qa_benchmark.py` and the QA benchmark API/tests: use that service.
- `backend/app/api/v1/endpoints/coverage.py`: loads sample-policy PDFs on demand.
- `backend/tests/test_comparison.py`: parses sample A/B PDFs for regression checks.
- Claims-guidance and coverage tests: request those sample policies.
- Root and architecture documentation: describe the supplied fixtures and evaluation dataset.

The fixture README identifies the PDFs as fictional test documents, but they are required
test inputs rather than disposable output. Its generator and answer key are also preserved.

No application code, environment file, virtual environment, dependency, cache, user data,
policy PDF, security report, or competition deliverable was otherwise changed or removed.
