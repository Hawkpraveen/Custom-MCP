import {useEffect, useState} from "react";

export function SettingsDialog({settings, saving, saveMessage, onSave, notifications, onClose}) {
  const [timeout, setTimeoutValue] = useState(() => settings ? String(settings.approval_timeout) : "");
  const [validation, setValidation] = useState("");

  useEffect(() => {
    if (settings) setTimeoutValue(String(settings.approval_timeout));
  }, [settings]);

  function submit(event) {
    event.preventDefault();
    const value = Number(timeout);
    if (!Number.isInteger(value) || value < (settings?.min_timeout ?? 1) || value > (settings?.max_timeout ?? 600)) {
      setValidation(`Enter a whole number from ${settings?.min_timeout ?? 1} to ${settings?.max_timeout ?? 600}.`);
      return;
    }
    setValidation("");
    onSave(value);
  }

  return <div className="settings-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="settings-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-title">
      <header className="settings-heading"><div><span className="section-label">Guardian preferences</span><h2 id="settings-title">Settings</h2></div>
        <button className="text-button" type="button" onClick={onClose} aria-label="Close settings">Close</button></header>
      <form onSubmit={submit}>
        <fieldset disabled={!settings || saving}>
          <label htmlFor="approval-timeout">Approval timeout</label>
          <div className="timeout-input"><input id="approval-timeout" type="number" min={settings?.min_timeout ?? 1}
            max={settings?.max_timeout ?? 600} step="1" value={timeout}
            onChange={(event) => setTimeoutValue(event.target.value)} required/><span>seconds</span></div>
          <p className="settings-help">Requests expire and are blocked if you do not decide in time. This applies immediately to new requests; existing pending requests keep their original deadline. The setting is saved for the next launch. Claude or a network proxy may time out sooner.</p>
          <button className="primary settings-save" type="submit">{saving ? "Saving…" : "Save timeout"}</button>
        </fieldset>
      </form>
      <div className="settings-divider"/>
      <section aria-labelledby="notification-title">
        <h3 id="notification-title">Desktop notifications</h3>
        <p className="settings-help">When Claude sends a request, the browser can show a desktop alert over other tabs. Choose <strong>Review request</strong> in the alert to open Guardian and inspect it. Guardian cannot inject a popup inside the claude.ai page itself.</p>
        <button className="secondary" type="button" onClick={notifications.enable}
          disabled={notifications.permission === "unsupported" || notifications.permission === "granted"}>
          {notifications.permission === "granted" ? "Notifications enabled" : "Enable desktop notifications"}
        </button>
        {notifications.permission === "granted" && <button className="secondary" type="button" onClick={notifications.test}>Send test notification</button>}
        {notifications.permission === "denied" && <p className="settings-help">Notifications are blocked by the browser. Change this site's notification permission in browser settings.</p>}
      </section>
      {(validation || saveMessage || notifications.message) && <p className="settings-status" role="status">{validation || saveMessage || notifications.message}</p>}
      {!settings && <p className="settings-status" role="status">Loading current settings…</p>}
    </section>
  </div>;
}
