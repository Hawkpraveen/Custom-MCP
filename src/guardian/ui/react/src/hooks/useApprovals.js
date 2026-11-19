import {useCallback, useEffect, useRef, useState} from "react";
import {dashboardApi, errorMessage} from "../api.js";

const DEV_RELOAD_KEY = "guardian:dev-reload";

export function useApprovals() {
  const [csrf, setCsrf] = useState(null);
  const [pending, setPending] = useState([]);
  const [connected, setConnected] = useState(false);
  const [message, setMessage] = useState("");
  const [loginMessage, setLoginMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [activity, setActivity] = useState([]);
  const [settings, setSettings] = useState(null);
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState("");
  const [now, setNow] = useState(Date.now());
  const polling = useRef(false), lastSuccess = useRef(0), busyRef = useRef(false), csrfRef = useRef(null);
  csrfRef.current = csrf;

  const signedOut = useCallback((reason = "") => {
    setCsrf(null); setPending([]); setConnected(false); setActivity([]); setSettings(null); setLoginMessage(reason);
  }, []);

  useEffect(() => {
    let mounted = true;
    dashboardApi("session").then((result) => { if (mounted) setCsrf(result.csrf); }).catch(() => {});
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    if (!csrf) { setSettings(null); return; }
    let mounted = true;
    dashboardApi("settings", undefined, csrf).then((result) => {
      if (mounted && csrfRef.current === csrf) setSettings(result);
    }).catch((error) => { if (mounted) setSettingsMessage(errorMessage(error)); });
    return () => { mounted = false; };
  }, [csrf]);

  const refresh = useCallback(async () => {
    if (!csrf || polling.current) return;
    polling.current = true;
    try {
      const result = await dashboardApi("pending", undefined, csrf);
      if (csrfRef.current !== csrf) return;
      lastSuccess.current = performance.now(); setPending(result.pending); setConnected(true); setMessage("");
    } catch (error) {
      if (csrfRef.current !== csrf) return;
      setConnected(false); setPending([]); setMessage(errorMessage(error));
      if (error.status === 401) signedOut(error.message);
    } finally { polling.current = false; }
  }, [csrf, signedOut]);

  useEffect(() => {
    if (!csrf) return;
    refresh();
    const timer = setInterval(refresh, 1000);
    const visible = () => { if (!document.hidden) refresh(); };
    const disconnect = () => {
      if (sessionStorage.getItem(DEV_RELOAD_KEY) === "1") {
        sessionStorage.removeItem(DEV_RELOAD_KEY);
        return;
      }
      navigator.sendBeacon("/dashboard/disconnect", new Blob([JSON.stringify({csrf})], {type: "application/json"}));
    };
    document.addEventListener("visibilitychange", visible);
    window.addEventListener("pagehide", disconnect);
    return () => {
      clearInterval(timer); document.removeEventListener("visibilitychange", visible);
      window.removeEventListener("pagehide", disconnect);
    };
  }, [csrf, refresh]);

  useEffect(() => {
    const timer = setInterval(() => {
      setNow(Date.now());
      if (csrfRef.current && performance.now() - lastSuccess.current > 3500) setConnected(false);
    }, 250);
    return () => clearInterval(timer);
  }, []);

  const login = async (token) => {
    setLoginMessage("Connecting…");
    try { const result = await dashboardApi("session", {token}); setCsrf(result.csrf); setLoginMessage(""); }
    catch (error) { setLoginMessage(errorMessage(error)); }
  };

  const saveSettings = async (approval_timeout) => {
    if (!csrf || savingSettings) return;
    setSavingSettings(true); setSettingsMessage("");
    try {
      const result = await dashboardApi("settings", {approval_timeout}, csrf);
      setSettings(result);
      setSettingsMessage(`Timeout saved: new requests will expire after ${result.approval_timeout} seconds.`);
    } catch (error) { setSettingsMessage(errorMessage(error)); }
    finally { setSavingSettings(false); }
  };

  const decide = async (item, allow) => {
    if (!item || busyRef.current || !connected || now >= item.deadline * 1000 || performance.now() - lastSuccess.current > 3500) return;
    busyRef.current = true; setBusy(true);
    try {
      await dashboardApi("decision", {id: item.id, fingerprint: item.fingerprint, allow}, csrf);
      setPending((items) => items.filter((entry) => entry.id !== item.id));
      setActivity((items) => [{id: item.id, name: item.message.params?.name || item.message.method,
        allow, time: new Date().toLocaleTimeString()}, ...items].slice(0, 5));
    } catch (error) { setMessage(errorMessage(error)); }
    finally { busyRef.current = false; setBusy(false); await refresh(); }
  };

  const logout = async () => {
    try { await dashboardApi("logout", {}, csrf); signedOut("Disconnected. Pending requests were blocked."); }
    catch { setMessage("Disconnect could not be confirmed. Close this tab to let the approval lease expire."); }
  };

  return {signedIn: Boolean(csrf), pending, connected, message, loginMessage, busy, activity, now,
    settings, savingSettings, settingsMessage, saveSettings, login, logout, refresh, decide};
}
