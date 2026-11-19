import {useEffect, useState} from "react";
import {useApprovals} from "./hooks/useApprovals.js";
import {useDesktopNotifications} from "./hooks/useDesktopNotifications.js";
import {Brand, Login} from "./components/Login.jsx";
import {RequestQueue} from "./components/RequestQueue.jsx";
import {RequestDetails} from "./components/RequestDetails.jsx";
import {ActivityLog} from "./components/ActivityLog.jsx";
import {SettingsDialog} from "./components/SettingsDialog.jsx";

function requestIdFromHash() {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.hash.slice(1)).get("request");
}

export default function App() {
  const approvals = useApprovals();
  const notifications = useDesktopNotifications(approvals.pending);
  const [selectedId, setSelectedId] = useState(requestIdFromHash);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const selected = approvals.pending.find((item) => item.id === selectedId) || approvals.pending[0];
  useEffect(() => {
    const updateSelection = () => setSelectedId(requestIdFromHash());
    window.addEventListener("hashchange", updateSelection);
    return () => window.removeEventListener("hashchange", updateSelection);
  }, []);
  useEffect(() => {
    const reviewRequest = (event) => {
      if (event.data?.type !== "guardian:review-request") return;
      const requestId = typeof event.data.requestId === "string" ? event.data.requestId : null;
      setSelectedId(requestId);
      if (requestId) window.location.hash = `request=${encodeURIComponent(requestId)}`;
      else window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
      approvals.refresh();
    };
    navigator.serviceWorker?.addEventListener("message", reviewRequest);
    return () => navigator.serviceWorker?.removeEventListener("message", reviewRequest);
  }, [approvals.refresh]);
  if (!approvals.signedIn) return <Login login={approvals.login} message={approvals.loginMessage}/>;
  return <div className="console">
    <aside className="sidebar"><Brand/>
      <div className="nav-current">Request approvals <span>{approvals.pending.length}</span></div>
      <div className="sidebar-note"><strong>You control the release.</strong><p>Every request stays paused until you allow it. Closing this tab or losing its connection blocks pending work.</p></div>
      <p className="local-label">Local browser interface</p>
    </aside>
    <main><header className="topbar"><div className={`connection${approvals.connected ? "" : " offline"}`} role="status">
      {approvals.connected ? "Connected · Requests pause for your decision" : "Disconnected · Requests fail closed"}
    </div><div className="topbar-actions"><button className="text-button" onClick={() => setSettingsOpen(true)}>Settings</button>
      <button className="text-button" onClick={approvals.logout}>Disconnect</button></div></header>
    <div className="page-heading"><div><h1>Request approvals</h1><p>Inspect the request. Decide what happens next.</p></div><button className="secondary" onClick={approvals.refresh}>Refresh queue</button></div>
    {approvals.message && <p className="notice" role="status">{approvals.message}</p>}
    {approvals.connected && selectedId && !approvals.pending.some((item) => item.id === selectedId) &&
      <p className="notice" role="status">That notification points to a request that is no longer pending. It may have expired, been blocked, or already received a decision.</p>}
    <div className="workspace"><RequestQueue pending={approvals.pending} selectedId={selected?.id} onSelect={setSelectedId}/>
      <RequestDetails item={selected} connected={approvals.connected} busy={approvals.busy} now={approvals.now} onDecision={approvals.decide}/></div>
    <ActivityLog activity={approvals.activity}/>
    <footer>Only MCP traffic routed through Guardian is controlled. Browser mode does not provide an always-on-top OS popup.</footer>
    </main>
    {settingsOpen && <SettingsDialog settings={approvals.settings} saving={approvals.savingSettings}
      saveMessage={approvals.settingsMessage} onSave={approvals.saveSettings} notifications={notifications}
      onClose={() => setSettingsOpen(false)}/>}
  </div>;
}
