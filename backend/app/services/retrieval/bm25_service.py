"""BM25 Lexical Retrieval Service for ClaimWise.

Implements Lucene-standard BM25 ranking:
    IDF(q) = ln(1.0 + (N - n + 0.5) / (n + 0.5))
    score(D, Q) = Σ IDF(q) * (f(q, D) * (k1 + 1)) / (f(q, D) + k1 * (1 - b + b * (|D| / avgdl)))
Guarantees strictly non-negative IDFs across small and large corpora,
exact 0.0 scores for unmatched documents, and strict policy isolation.
"""

from dataclasses import dataclass
import logging
import math
import re
from typing import Dict, List, Optional

from app.schemas.policy import ExtractedClause

logger = logging.getLogger("claimwise.retrieval.bm25")

# Tokenizer pattern preserving clause numbers (e.g. '1.1', 'sec-4.2'),
# hyphenated terms ('in-network', 'out-of-pocket'), and standard words.
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[\.\-][a-z0-9]+)*")

STOP_WORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "for", "with",
    "on", "at", "by", "from", "up", "about", "into", "over", "after",
    "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "what", "which", "who", "whom", "this",
    "that", "these", "those", "am", "it", "its", "under", "how", "much"
}


def tokenize_text(text: str) -> List[str]:
    """Tokenize text preserving clause markers, terms, and numbers."""
    cleaned = text.lower()
    tokens = TOKEN_PATTERN.findall(cleaned)
    # Symmetric vocabulary normalization improves lexical recall when optional
    # embeddings are unavailable. It changes search terms, never source evidence.
    equivalents = (
        {"vehicle", "car", "automobile"},
        {"workshop", "garage", "repairer", "trader"},
        {"repair", "repairs", "repairing", "repaired"},
        {"unattended", "abandoned"},
        {"unroadworthy", "roadworthiness", "unsafe"},
        {"maintenance", "maintained", "maintain"},
    )
    canonical = {word: f"synonym{idx}" for idx, group in enumerate(equivalents) for word in group}
    return tokens + [canonical[token] for token in tokens if token in canonical]


class LuceneBM25Index:
    """
    In-memory BM25 index using the Lucene non-negative IDF formula.
    Prevents negative IDF anomalies on small single/multi-page policy collections.
    """

    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.corpus = corpus
        self.k1 = k1
        self.b = b
        self.N = len(corpus)
        self.doc_lens = [len(doc) for doc in corpus]
        self.avgdl = sum(self.doc_lens) / self.N if self.N > 0 else 1.0

        # Precompute document frequencies
        self.doc_freqs: Dict[str, int] = {}
        for doc in corpus:
            for term in set(doc):
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1

        # Precompute IDFs with Lucene formula: ln(1.0 + (N - n + 0.5)/(n + 0.5))
        self.idfs: Dict[str, float] = {}
        for term, n in self.doc_freqs.items():
            self.idfs[term] = math.log(1.0 + (self.N - n + 0.5) / (n + 0.5))

    def get_scores(self, query_tokens: List[str]) -> List[float]:
        scores = [0.0] * self.N
        if self.N == 0:
            return scores

        for q in query_tokens:
            idf = self.idfs.get(q)
            if idf is None or idf <= 0.0:
                continue

            for i, doc in enumerate(self.corpus):
                f = doc.count(q)
                if f > 0:
                    denom = f + self.k1 * (1.0 - self.b + self.b * (self.doc_lens[i] / self.avgdl))
                    scores[i] += idf * (f * (self.k1 + 1.0)) / denom

        return scores


@dataclass
class IndexedClause:
    """Internal indexed clause representation."""
    clause_id: str
    page_number: int
    policy_id: str
    document_hash: str
    clause_heading: Optional[str]
    text: str
    tokens: List[str]


@dataclass
class LexicalMatch:
    """Result of BM25 lexical query."""
    clause_id: str
    page_number: int
    policy_id: str
    document_hash: str
    clause_heading: Optional[str]
    text: str
    rank: int  # 1-based rank
    score: float


# General insurance domain synonyms bridging consumer natural language with policy terms
INSURANCE_SYNONYMS: Dict[str, List[str]] = {
    "car": ["vehicle", "motor"],
    "auto": ["vehicle", "motor", "car"],
    "automobile": ["vehicle", "motor", "car"],
    "cover": ["indemnify", "indemnity", "coverage", "covered", "scope"],
    "covered": ["indemnify", "indemnity", "cover", "coverage", "scope"],
    "coverage": ["cover", "covered", "indemnify", "benefit"],
    "damage": ["loss", "repair", "collision"],
    "crash": ["collision", "accident"],
    "theft": ["stolen", "burglary"],
    "stolen": ["theft", "burglary"],
    "lost": ["loss", "missing"],
    "doctor": ["physician", "practitioner"],
    "hospital": ["inpatient", "facility"],
}


class BM25RetrievalService:
    """
    Lexical retrieval index managing extracted clauses partitioned by policy.
    """

    def __init__(self):
        # policy_id -> List[IndexedClause]
        self._policy_clauses: Dict[str, List[IndexedClause]] = {}
        # policy_id -> LuceneBM25Index instance
        self._policy_indexes: Dict[str, LuceneBM25Index] = {}

    def index_policy(
        self,
        policy_id: str,
        clauses: List[ExtractedClause],
        document_hash: str = "",
    ) -> int:
        """
        Index or replace clauses for a specific policy ID.
        """
        indexed_items: List[IndexedClause] = []
        tokenized_corpus: List[List[str]] = []

        for clause in clauses:
            doc_hash = document_hash or clause.document_hash
            combined_text = f"{clause.clause_id} {clause.clause_heading or ''} {clause.text}"
            tokens = tokenize_text(combined_text)

            if not tokens:
                tokens = ["empty_clause"]

            item = IndexedClause(
                clause_id=clause.clause_id,
                page_number=clause.page_number,
                policy_id=policy_id,
                document_hash=doc_hash,
                clause_heading=clause.clause_heading,
                text=clause.text,
                tokens=tokens,
            )
            indexed_items.append(item)
            tokenized_corpus.append(tokens)

        self._policy_clauses[policy_id] = indexed_items

        if tokenized_corpus:
            self._policy_indexes[policy_id] = LuceneBM25Index(tokenized_corpus)
            logger.info("BM25 indexed %d clauses for policy %s.", len(indexed_items), policy_id)
        else:
            self._policy_indexes.pop(policy_id, None)

        return len(indexed_items)

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a policy index from memory."""
        removed_clauses = self._policy_clauses.pop(policy_id, None)
        self._policy_indexes.pop(policy_id, None)
        return removed_clauses is not None

    def query(
        self,
        query_text: str,
        policy_ids: List[str],
        top_k: int = 10,
    ) -> List[LexicalMatch]:
        """
        Execute BM25 search filtered strictly by the authorized policy_ids.
        Guarantees cross-user document isolation.
        """
        raw_tokens = tokenize_text(query_text)
        if not raw_tokens:
            return []

        # Discount generic conversational stop words
        filtered = [t for t in raw_tokens if t not in STOP_WORDS]
        base_tokens = filtered if filtered else raw_tokens

        # General domain synonym expansion to bridge user phrasing with policy terms
        expanded_tokens = list(base_tokens)
        seen_tokens = set(base_tokens)
        for token in base_tokens:
            for syn in INSURANCE_SYNONYMS.get(token, []):
                if syn not in seen_tokens:
                    seen_tokens.add(syn)
                    expanded_tokens.append(syn)
        query_tokens = expanded_tokens

        all_scored_matches: List[tuple[float, IndexedClause]] = []

        for pid in policy_ids:
            bm25_index = self._policy_indexes.get(pid)
            clauses = self._policy_clauses.get(pid)
            if not bm25_index or not clauses:
                continue

            doc_scores = bm25_index.get_scores(query_tokens)

            for score, clause in zip(doc_scores, clauses):
                if score > 0.0:
                    all_scored_matches.append((float(score), clause))

        # Sort descending by BM25 score
        all_scored_matches.sort(key=lambda x: x[0], reverse=True)

        results: List[LexicalMatch] = []
        for idx, (score, clause) in enumerate(all_scored_matches[:top_k]):
            results.append(
                LexicalMatch(
                    clause_id=clause.clause_id,
                    page_number=clause.page_number,
                    policy_id=clause.policy_id,
                    document_hash=clause.document_hash,
                    clause_heading=clause.clause_heading,
                    text=clause.text,
                    rank=idx + 1,
                    score=round(score, 4),
                )
            )

        return results

    def get_indexed_policy_ids(self) -> List[str]:
        """Return list of policy IDs currently present in the index."""
        return list(self._policy_indexes.keys())


bm25_service = BM25RetrievalService()
