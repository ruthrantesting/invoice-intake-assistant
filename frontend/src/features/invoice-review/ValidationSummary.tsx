type ValidationItem = {
  check_type: string;
  outcome: "passed" | "flagged" | "not_verifiable";
  reason: string;
  matched_record_id?: string | null;
  comparison_scope?: string | null;
};

const labelFor = (check: string) => ({ arithmetic: "Total arithmetic", missing_po: "Purchase order", duplicate: "Possible duplicate" })[check] ?? check;

export function ValidationSummary({ items }: { items: ValidationItem[] }) {
  if (items.length === 0) {
    return <section className="card checks-card"><div className="section-top"><div><h2>Checks &amp; flags</h2><p>Run deterministic checks before logging.</p></div><span className="pill">Not run</span></div></section>;
  }
  const flagged = items.some((item) => item.outcome === "flagged");
  return <section className="card checks-card" aria-labelledby="checks-heading"><div className="section-top"><div><h2 id="checks-heading">Checks &amp; flags</h2><p>Deterministic checks · review any flagged items</p></div><span className={flagged ? "pill" : "pill clear-pill"}>{flagged ? "Review needed" : "Complete"}</span></div>{items.map((item, index) => <div className="check-row" key={`${item.check_type}-${index}`}><span className={item.outcome === "passed" ? "check-symbol" : "check-symbol needs-check"} aria-hidden="true">{item.outcome === "passed" ? "✓" : item.outcome === "flagged" ? "!" : "?"}</span><span><strong>{labelFor(item.check_type)}</strong><small>{item.reason}{item.comparison_scope ? ` Comparison scope: ${item.comparison_scope}.` : ""}</small>{item.matched_record_id && <small>Potential match: {item.matched_record_id}</small>}</span><span className="row-status">{item.outcome.replaceAll("_", " ")}</span></div>)}</section>;
}
