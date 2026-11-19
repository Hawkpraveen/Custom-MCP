import {useState} from "react";

export function Brand() {
  return <div className="brand"><span className="brand-mark" aria-hidden="true">G</span> Guardian</div>;
}

export function Login({login, message}) {
  const [token, setToken] = useState("");
  const [connecting, setConnecting] = useState(false);
  async function submit(event) {
    event.preventDefault(); if (connecting) return;
    const value = token.trim(); setToken(""); setConnecting(true);
    try { await login(value); } finally { setConnecting(false); }
  }
  return <section className="signin">
    <div className="intro"><Brand/><h1>A moment to<br/>make the call.</h1>
      <p>Review what your AI is about to do. Release one request, or stop it before it reaches the server.</p>
      <div className="path" aria-label="Your decision gates tool execution"><span>AI request</span><span className="gate">Your decision</span><span>Tool execution</span></div>
      <p className="quiet">Browser approval is an alternative to the desktop popup. Keep this tab active while reviewing requests.</p>
    </div>
    <form className="login-panel" onSubmit={submit}>
      <span className="section-label">Local approval console</span><h2>Connect to Guardian</h2>
      <p>Enter the <code>approver_token</code> from your private configuration file.</p>
      <label htmlFor="token">Approver token</label>
      <input id="token" type="password" value={token} onChange={(event) => setToken(event.target.value)} autoComplete="off" spellCheck={false} required placeholder="Paste your approver token"/>
      <button className="primary" type="submit" disabled={connecting}>{connecting ? "Connecting…" : "Connect dashboard"}</button>
      <p className="message" role="status">{message}</p>
      <p className="quiet">Disconnect the Tkinter app before connecting here. Your token is cleared after sign-in and is never saved in browser storage.</p>
    </form>
  </section>;
}
