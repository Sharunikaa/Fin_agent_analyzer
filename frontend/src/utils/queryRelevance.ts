/**
 * Client-only heuristic: block obvious non–financial-document questions.
 * Prefer false negatives (still call the API) over blocking real finance questions.
 */
export function isLikelyIrrelevantToCorpus(query: string): boolean {
  const trimmed = query.trim();
  if (trimmed.length < 4) return true;

  const offTopic =
    /\b(weather|recipe|\bcook\b|\bjoke\b|poem\b|lottery|tiktok|instagram|snapchat|movie\b|film\b|celebrity|sports score|what\s+time\b|how\s+old\s+are\s+you|who\s+(are|is)\s+you|ignore\s+(all\s+)?(previous|prior)|\bsudo\b|nba\b|nfl\b|world\s+cup)\b/i;
  if (offTopic.test(trimmed)) return true;

  if (/^(hi|hello|hey|thanks?|thank you|thx|ok|okay|yes|no|bye|cool|nice)\s*[!?.]*$/i.test(trimmed)) return true;

  const hasFinanceSignal =
    /[$%]|\b20[12]\d{2}\b/.test(trimmed) ||
    /\b(revenue|margin|profit|ebitda|ebit|earnings|net\s+income|gross|debt|leverage|cash\s*flow|cagr|growth|risk|risks|filing|10-?k|10-?q|annual\s*report|\bsec\b|guidance|outlook|segment|yoy|qoq|balance\s+sheet|md&a|footnote|shareholder|dividend|eps|p\/e|financial|quarter|fiscal|kpi|metric|operating\s+income)\b/i.test(
      trimmed,
    ) ||
    /\b(amd|apple|microsoft|netflix|nvidia|intel|amazon|google|alphabet|meta|tesla|disney|oracle|salesforce|aapl|msft|amzn|nflx|nvda)\b/i.test(trimmed) ||
    /\b(esg|sustainability|climate|supply\s+chain|competition|competitive|strategy|acquisition|merger|lawsuit|litigation)\b/i.test(trimmed) ||
    /\b(compare|versus|\bvs\.?\b|trend|summarize|analyze|explain)\b/i.test(trimmed);

  if (hasFinanceSignal) return false;

  if (trimmed.length < 28) return true;

  return false;
}

export const OFF_TOPIC_REPLY =
  "That doesn’t look related to our financial document data (filings, revenue, risks, companies in this system).\n\n" +
  'Ask about something in the corpus — e.g. “What was AMD’s revenue in 2021?” or “Compare Microsoft and Apple risk factors.” You can also use the quick prompts below.';
