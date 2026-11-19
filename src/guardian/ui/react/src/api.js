export async function dashboardApi(path, body, csrf) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3000);
  try {
    const response = await fetch(`/dashboard/${path}`, {
      method: body === undefined ? "GET" : "POST", credentials: "same-origin", cache: "no-store",
      headers: {"Content-Type": "application/json", ...(csrf ? {"X-Guardian-CSRF": csrf} : {})},
      body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal
    });
    const result = await response.json();
    if (!response.ok) {
      const error = new Error(result.error || "The request expired or could not be completed. Refresh the queue.");
      error.status = response.status;
      throw error;
    }
    return result;
  } finally { clearTimeout(timeout); }
}

export function errorMessage(error) {
  return error.name === "AbortError" ? "The gateway did not respond. Check that it is running." : error.message;
}
