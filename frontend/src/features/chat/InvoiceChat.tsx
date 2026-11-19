import { useState } from "react";
import { apiRequest } from "../../api/client";

type Props = { invoiceId?: string };
type Message = { role: "user" | "assistant"; content: string };

export function InvoiceChat({ invoiceId }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [sessionId, setSessionId] = useState<string>();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = text.trim();
    if (!message || !invoiceId || pending) return;
    setText("");
    setError("");
    setMessages((current) => [...current, { role: "user", content: message }]);
    setPending(true);
    try {
      const activeSession = sessionId ?? (await apiRequest<{ id: string }>("/chat/sessions", { method: "POST", body: JSON.stringify({ invoice_id: invoiceId }) })).id;
      if (!sessionId) setSessionId(activeSession);
      const response = await apiRequest<{ message: string }>(`/chat/sessions/${activeSession}/messages`, { method: "POST", body: JSON.stringify({ message }) });
      setMessages((current) => [...current, { role: "assistant", content: response.message }]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Chat is unavailable.");
    } finally {
      setPending(false);
    }
  }

  return <section className="card chat-panel"><div className="chat-welcome"><span className="chat-orb">✳</span><h2>Ask about this invoice</h2><p>I can explain extracted details, evidence, and checks. I cannot approve or log invoices.</p></div><div className="chat-messages" aria-live="polite">{messages.map((message, index) => <p className={`chat-message ${message.role}`} key={`${message.role}-${index}`}><strong>{message.role === "user" ? "You" : "Ledgerly"}</strong>{message.content}</p>)}</div>{error && <p role="alert" className="setup-status">{error}</p>}<form className="chat-input" onSubmit={submit}><input aria-label="Ask about this invoice" value={text} onChange={(event) => setText(event.target.value)} placeholder="Ask a question about this invoice…" disabled={!invoiceId || pending}/><button type="submit" aria-label="Send message" disabled={!invoiceId || pending || !text.trim()}>↑</button></form><p className="chat-disclaimer">AI can make mistakes. Verify important details against the source.</p></section>;
}
