type Props = { onSave: (status: string, note: string) => void };

export function ReviewPanel({ onSave }: Props) {
  return <form className="card review-note-card" onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); onSave(String(form.get("status")), String(form.get("note") ?? "")); }}><div className="section-top"><div><h2>Record data review</h2><p>This does not authorize payment.</p></div></div><label className="field"><span>Review status</span><select name="status" defaultValue="needs_review"><option value="not_reviewed">Not reviewed</option><option value="needs_review">Needs review</option><option value="reviewed">Reviewed</option></select></label><label className="field"><span>Reviewer note (optional)</span><textarea name="note" maxLength={4000} placeholder="Add context for the next reviewer…"/></label><button className="secondary-button" type="submit">Save review note</button></form>;
}
