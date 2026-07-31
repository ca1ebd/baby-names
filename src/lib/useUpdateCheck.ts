import { useEffect, useState } from "react";

const BUILD_SHA = import.meta.env.VITE_COMMIT_SHA ?? "";
const CHECK_INTERVAL_MS = 60_000;

export function useUpdateCheck(): boolean {
  const [available, setAvailable] = useState(false);

  useEffect(() => {
    if (!BUILD_SHA) return;

    let cancelled = false;
    const check = async () => {
      try {
        const res = await fetch(`/version.json?t=${Date.now()}`, { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled && data.sha && data.sha !== BUILD_SHA) setAvailable(true);
      } catch {
        // offline or blocked — silently retry on the next tick
      }
    };

    check();
    const interval = setInterval(check, CHECK_INTERVAL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") check();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);

    return () => {
      cancelled = true;
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, []);

  return available;
}
