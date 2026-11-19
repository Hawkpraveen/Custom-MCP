export function RequestDetails({item, connected, busy, now, onDecision}) {
  if (!item) return <section className="detail-panel" aria-label="Request details"><div className="empty-detail">
    <div className="pause-symbol" aria-hidden="true">Ⅱ</div><h2>Nothing waiting on you.</h2>
    <p>New requests will appear here before they reach the upstream server. Keep this tab active to stay connected.</p>
    <span className="subtle-pill">All requests require a decision</span>
  </div></section>;
  const disabled = busy || !connected || now >= item.deadline * 1000;
  const rows = [["Server", item.server], ["Source", item.source], ["Method", item.message.method], ["Request ID", item.id]];
  const json = JSON.stringify(item.message, null, 2).replace(/[\u007f-\uffff]/g, (value) => `\\u${value.charCodeAt(0).toString(16).padStart(4, "0")}`);
  return <section className="detail-panel" aria-label="Request details"><div className="request-detail">
    <div className="request-scroll">
    <div className="detail-title"><div><span className="section-label">Pending request</span><h2>{item.message.params?.name || item.message.method}</h2></div>
      <span className="countdown">{Math.max(0, Math.ceil(item.deadline - now / 1000))}s remaining</span></div>
    <dl className="metadata">{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd className={label === "Request ID" ? "identifier" : undefined}>{value}</dd></div>)}</dl>
    <div className="json-heading"><h3>Exact request</h3><span>Untrusted request content</span></div>
    <pre key={item.id} tabIndex={0} aria-label="Exact request JSON">{json}</pre>
    </div>
    <div className="decision-footer">
    <p className="decision-note">Allow releases this request once. Block returns a denial without executing it.</p>
    <div className="actions"><button className="block" disabled={disabled} onClick={() => onDecision(item, false)}>Block request</button>
      <button className="primary" disabled={disabled} onClick={() => onDecision(item, true)}>Allow once</button></div>
    </div>
  </div></section>;
}
