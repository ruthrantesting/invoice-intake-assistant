export type AuditItem = { id: string; timestamp: string; actor_id: string | null; actor_type: string; action: string; outcome: string };

export function InvoiceHistory({ items }: { items: AuditItem[] }) {
  return <section className="card history-card"><div className="section-top"><div><h2>Processing &amp; action history</h2><p>Attributable record of material invoice activity</p></div></div>{items.length === 0 ? <p className="history-empty">History will appear here as this invoice is processed.</p> : <ol className="history-list">{items.map((item) => <li key={item.id}><span className="history-dot"/><div><strong>{item.action.replaceAll(".", " ")}</strong><small>{new Date(item.timestamp).toLocaleString()} · {item.actor_id ?? item.actor_type} · {item.outcome}</small></div></li>)}</ol>}<p className="chat-disclaimer">Review and logging history records data handling only—not invoice or payment approval.</p></section>;
}
