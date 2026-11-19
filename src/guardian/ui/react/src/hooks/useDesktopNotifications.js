import {useCallback, useEffect, useRef, useState} from "react";

const SW_URL = "/dashboard/service-worker.js";
const EMPTY_GRACE_MS = 3000;
const NOTIFICATION_DELAY_MS = 700;

export function useDesktopNotifications(pending) {
  const [permission, setPermission] = useState(() =>
    typeof window !== "undefined" && "Notification" in window ? Notification.permission : "unsupported");
  const [message, setMessage] = useState("");
  const [registration, setRegistration] = useState(null);
  // Keep one logical batch active across brief gaps between MCP discovery and tool calls.
  const batch = useRef({active: false, notified: false, emptyTimer: null, notificationTimer: null});

  useEffect(() => {
    if (permission !== "granted" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.getRegistration("/dashboard/")
      .then(async (existing) => {
        if (!existing) return;
        try { await existing.update(); } catch {}
        await navigator.serviceWorker.ready;
        setRegistration(existing);
      })
      .catch(() => {});
  }, [permission]);

  const enable = useCallback(async () => {
    setMessage("");
    if (!("Notification" in window) || !("serviceWorker" in navigator)) {
      setPermission("unsupported");
      setMessage("This browser does not support Guardian desktop notifications.");
      return;
    }
    try {
      const result = await Notification.requestPermission();
      setPermission(result);
      if (result !== "granted") {
        setMessage(result === "denied"
          ? "Notifications are blocked for this site. Allow them in browser site settings, then try again."
          : "Notification permission was not granted.");
        return;
      }
      const ready = await navigator.serviceWorker.register(SW_URL, {scope: "/dashboard/"});
      await navigator.serviceWorker.ready;
      setRegistration(ready);
      setMessage("Desktop alerts are enabled. Click Review request in an alert to open Guardian.");
    } catch {
      setMessage("Could not enable desktop alerts. Check browser notification and service-worker permissions.");
    }
  }, []);

  const test = useCallback(async () => {
    setMessage("");
    if (permission !== "granted") {
      setMessage("Enable browser notifications before sending a test alert.");
      return;
    }
    try {
      const target = registration || await navigator.serviceWorker.getRegistration("/dashboard/");
      if (!target) throw new Error("Guardian's notification worker is not registered. Enable notifications again.");
      setRegistration(target);
      await target.showNotification("Guardian test notification", {
        body: "Desktop alerts are reaching this browser. Click to return to Guardian.",
        tag: "guardian-test",
        requireInteraction: true,
        data: {type: "test"}
      });
      setMessage("Test alert sent. If no banner appeared, check Windows and Chrome notification settings.");
    } catch (error) {
      setMessage(`Could not send test alert: ${error?.message || "notification service unavailable"}`);
    }
  }, [permission, registration]);

  useEffect(() => {
    if (permission !== "granted" || !registration) return;
    const state = batch.current;
    state.pending = pending;
    const hasPending = pending.length > 0;

    if (hasPending) {
      if (state.emptyTimer) clearTimeout(state.emptyTimer);
      state.emptyTimer = null;
      if (!state.active) {
        state.active = true;
        state.notified = false;
      }
      if (!state.notified && !state.notificationTimer) {
        state.notificationTimer = setTimeout(() => {
          state.notificationTimer = null;
          if (!state.active || state.notified) return;
          state.notified = true;
          const currentPending = state.pending || [];
          const count = currentPending.length;
          const first = currentPending[0];
          const toolName = first?.message?.params?.name || first?.message?.method || "MCP request";
          registration.showNotification("Guardian: requests awaiting approval", {
            body: count === 1
              ? `${toolName} is waiting. Choose Review request to inspect it in Guardian.`
              : `${count} requests are waiting, including ${toolName}. Choose Review request to inspect the queue.`,
            tag: "guardian-pending",
            renotify: false,
            requireInteraction: true,
            data: {type: "approval"},
            actions: [{action: "review", title: "Review request"}]
          }).catch((error) => { state.notified = false; setMessage(`Could not show approval alert: ${error?.message || "notification service unavailable"}`); });
        }, NOTIFICATION_DELAY_MS);
      }
    } else if (state.active && !state.emptyTimer) {
      state.emptyTimer = setTimeout(() => {
        state.emptyTimer = null;
        state.active = false;
        state.notified = false;
        if (state.notificationTimer) clearTimeout(state.notificationTimer);
        state.notificationTimer = null;
        registration.getNotifications().then((active) => {
          for (const notification of active) {
            if (notification.data?.type === "approval" || notification.tag === "guardian-pending") notification.close();
          }
        }).catch(() => {});
      }, EMPTY_GRACE_MS);
    }

    // Retire legacy per-request alerts left by older dashboard versions.
    registration.getNotifications().then((active) => {
      for (const notification of active) {
        if (notification.tag?.startsWith("guardian-")
          && notification.tag !== "guardian-pending" && notification.tag !== "guardian-test") {
          notification.close();
        }
      }
    }).catch(() => {});
  }, [pending, permission, registration]);

  useEffect(() => () => {
    const state = batch.current;
    if (state.emptyTimer) clearTimeout(state.emptyTimer);
    if (state.notificationTimer) clearTimeout(state.notificationTimer);
  }, []);

  return {permission, message, enable, test};
}

