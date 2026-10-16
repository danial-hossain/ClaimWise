import type { CoverageComponentFinding, CoverageComponentKind, CoverageFactStatus, CoverageVerdictType } from '@/types/api';
import CitationChip from './CitationChip';
import StatusBadge from './StatusBadge';

const groups: { verdict: CoverageVerdictType; title: string }[] = [
  { verdict: 'covered', title: 'Potentially covered' },
  { verdict: 'partially_covered', title: 'Partially covered' },
  { verdict: 'conditional', title: 'Conditional or limited' },
  { verdict: 'excluded', title: 'Potentially excluded' },
  { verdict: 'uncertain', title: 'Unable to determine' },
];
const kindLabels: Record<CoverageComponentKind, string> = {
  insured_loss: 'Insured loss',
  policy_requirement: 'Policy requirement',
  supporting_document: 'Supporting document',
  unresolved_fact: 'Unresolved fact',
};
const factStatusLabels: Record<CoverageFactStatus, string> = {
  satisfied: 'Satisfied',
  not_satisfied: 'Not satisfied',
  unknown: 'Unknown',
  not_applicable: 'Not applicable',
};

function DetailList({ label, values }: { label: string; values: string[] }) {
  if (!values.length) return null;
  return <div><h5 className="font-semibold text-slate-800">{label}</h5><ul className="mt-1 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">{values.map(value => <li key={value}>{value}</li>)}</ul></div>;
}

export default function CoverageComponentFindings({ components, policyName }: { components: CoverageComponentFinding[]; policyName?: string }) {
  if (!components.length) return null;
  const losses = components.filter(item => !item.kind || item.kind === 'insured_loss');
  const requirementsAndFacts = components.filter(item => item.kind && item.kind !== 'insured_loss');
  return <div className="space-y-5" aria-label="Coverage assessment by scenario component">
    {groups.map(group => {
      const findings = losses.filter(item => item.verdict === group.verdict);
      if (!findings.length) return null;
      return <section key={group.verdict} aria-label={group.title}>
        <h4 className="border-b border-slate-200 pb-2 text-sm font-semibold text-slate-900">{group.title} <span className="font-normal text-slate-500">({findings.length})</span></h4>
        <div className="divide-y divide-slate-100">
          {findings.map((finding, index) => <article key={`${finding.part}:${index}`} className="space-y-3 py-4 first:pt-3">
            <header className="flex flex-wrap items-start justify-between gap-2">
              <h5 className="min-w-0 flex-1 text-sm font-semibold text-slate-900">{finding.part}</h5>
              <StatusBadge status={finding.verdict || 'uncertain'} size="sm" label={group.title} />
            </header>
            {finding.coverage_provision && <p className="text-sm leading-6 text-slate-700"><strong>Coverage provision:</strong> {finding.coverage_provision}</p>}
            {finding.payable_amount && <p className="text-sm leading-6 text-emerald-800 bg-emerald-50/60 rounded px-2.5 py-1.5 border border-emerald-200"><strong>Payable amount / Benefit:</strong> {finding.payable_amount}</p>}
            {finding.calculation && <p className="text-sm leading-6 text-slate-700"><strong>Calculation breakdown:</strong> {finding.calculation}</p>}
            <p className="text-sm leading-6 text-slate-700">{finding.explanation}</p>
            <DetailList label="Exclusions and restrictions" values={finding.restrictions} />
            <DetailList label="Conditions and limits" values={finding.conditions_and_limits} />
            <DetailList label="Omitted or dropped context" values={finding.dropped_material || []} />
            <DetailList label="Facts still needed" values={finding.missing_facts} />
            {finding.citations.length > 0 ? <div>
              <h5 className="mb-2 font-semibold text-slate-800">Supporting policy clauses</h5>
              <div className="space-y-2">{finding.citations.map((citation, citationIndex) => <CitationChip key={`${citation.clause_id}:${citation.page_number}:${citationIndex}`} citation={citation} policyName={policyName} defaultExpanded />)}</div>
            </div> : <p role="note" className="text-sm text-slate-600">No matching verified clause was found in the selected policy extract. Coverage cannot be determined from the available wording.</p>}
          </article>)}
        </div>
      </section>;
    })}
    {requirementsAndFacts.length > 0 && <section aria-label="Policy requirements, supporting documents, and unresolved facts">
      <h4 className="border-b border-slate-200 pb-2 text-sm font-semibold text-slate-900">Requirements and evidence</h4>
      <div className="divide-y divide-slate-100">
        {requirementsAndFacts.map((finding, index) => <article key={`${finding.part}:${index}`} className="space-y-3 py-4 first:pt-3">
          <header className="flex flex-wrap items-start justify-between gap-2">
            <div><p className="text-[11px] font-semibold text-slate-500">{kindLabels[finding.kind!]}</p><h5 className="text-sm font-semibold text-slate-900">{finding.part}</h5></div>
            {finding.fact_status && <span className="rounded-full border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-700">{factStatusLabels[finding.fact_status]}</span>}
          </header>
          <p className="text-sm leading-6 text-slate-700">{finding.explanation}</p>
          <DetailList label="Facts still needed" values={finding.missing_facts} />
          {finding.citations.length > 0 ? <div>
            <h5 className="mb-2 font-semibold text-slate-800">Relevant policy clauses</h5>
            <div className="space-y-2">{finding.citations.map((citation, citationIndex) => <CitationChip key={`${citation.clause_id}:${citation.page_number}:${citationIndex}`} citation={citation} policyName={policyName} defaultExpanded />)}</div>
          </div> : <p role="note" className="text-sm text-slate-600">No matching verified clause was found in the selected policy extract.</p>}
        </article>)}
      </div>
    </section>}
  </div>;
}
