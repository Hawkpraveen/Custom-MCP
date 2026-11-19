export function RequestQueue({pending, selectedId, onSelect}) {
  return <section className="queue-panel" aria-labelledby="queue-heading">
    <div className="panel-heading"><h2 id="queue-heading">Awaiting your decision</h2><span className="count">{pending.length}</span></div>
    <div className="queue">{pending.map((item) => <button key={item.id}
      className={`queue-item${item.id === selectedId ? " selected" : ""}`} aria-pressed={item.id === selectedId} onClick={() => onSelect(item.id)}>
      <strong>{item.message.params?.name || item.message.method}</strong><span>{item.server}</span><span>{item.message.method}</span>
    </button>)}</div>
    {!pending.length && <div className="queue-empty">No pending requests.<br/><span>Ask your connected AI client to use an MCP tool.</span></div>}
  </section>;
}
