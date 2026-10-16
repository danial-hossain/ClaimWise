import { Check, Circle, AlertCircle } from 'lucide-react';
import type { PolicyExtractionResult } from '@/types/api';

/** A single-response endpoint cannot truthfully expose live internal stage timing. */
export default function PolicyUploadProgress({ pending, result, error }: { pending: boolean; result: PolicyExtractionResult | null; error: string | null }) {
  if (!pending && !result && !error) return null;
  // The existing upload endpoint returns only after indexing nonempty clauses.
  const indexed = Boolean(result?.policy_id && result.status === 'success' && result.has_extractable_text && result.clauses.length > 0);
  const steps = [
    { name: 'Uploading', done: Boolean(result) },
    { name: 'Reading pages', done: Boolean(result && result.total_pages > 0 && result.has_extractable_text) },
    { name: 'Extracting clauses', done: Boolean(result?.has_extractable_text && result.clauses.length > 0) },
    { name: 'Indexing', done: indexed },
  ];
  return <section className="cw-upload-progress" aria-label="Policy upload progress" aria-busy={pending}>
    <ol>{steps.map(({ name, done }, i) => <li key={name} data-complete={done}>{done ? <Check size={15} className="wizard-draw-check" /> : error && i === 0 ? <AlertCircle size={15} /> : <Circle size={15} />}<span>{name}</span><span className="sr-only">: {done ? 'confirmed by response' : pending && i === 0 ? 'request in progress' : 'not confirmed'}</span></li>)}</ol>
    <p role="status">{pending ? 'Upload and processing are in progress. Individual processing stages are not reported live.' : error ? 'The request did not finish. Your selected file is kept for retry.' : indexed ? 'Policy saved. Page and clause counts below come from the extraction response.' : 'Response received. Only confirmed stages are checked; some processing results are unavailable.'}</p>
  </section>;
}
