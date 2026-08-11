// @ts-nocheck
// Ported as-is from the JS prototype; not worth retyping a component this dynamic.
import { useState, useEffect, useLayoutEffect, useMemo, useRef, useCallback } from "react";
import { useUpdateCheck } from "./lib/useUpdateCheck";
import { signInWithEmail, signOut, onAuthStateChange, getSession } from "./lib/auth";
import { warmupBackend, getState, putSettings, postReset, requestNextBlock } from "./lib/api";
import { flushOutbox } from "./lib/syncQueue";

/* ---------------- data ---------------- */

// The name corpus and deck ordering now live on the backend (spec 002) — the
// client no longer computes a pool or shuffles anything itself. What used to
// be a locally-built deck is now `state.swipers[slot].block`: the run of
// as-yet-undecided cards the service has dealt this swiper, fetched via
// POST /v1/deck/next and topped up at a low-water mark (T071).

// Whether a pick belongs in the list for the current filter. A pick whose
// gender we don't know locally (e.g. restored from a backup, or hydrated from
// GET /v1/state, which doesn't carry gender) is always shown — hiding it would
// risk silently dropping a keep or a match, the exact bug spec 001 fixed.
function inActiveView(gender, genderFilter) {
  if (genderFilter === "both") return true;
  if (!gender) return true;
  return gender === genderFilter;
}

// DO NOT CHANGE THIS KEY. Changing it orphans every saved swipe.
// Adding or removing names is safe — picks are keyed by name, not position.
const STORAGE_KEY = "babyname-swipe-v3";

const LOW_WATER_MARK = 20;
const BLOCK_REQUEST_SIZE = 100;

/* ---------------- tokens ---------------- */

const C = {
  ink: "#16202B",
  wash1: "#D3DCE2",
  wash2: "#B4C3CD",
  card: "#FFFDF7",
  alert: "#A8574B",
  girlBand: "#C97B92",
  boyBand: "#5B7FB5",
  neutralBand: "#4A5D70",
  yes: "#16795E",
  no: "#607080",
  gold: "#C9962B",
  rule: "rgba(22,32,43,0.12)",
};

const display = "'Caveat', 'Segoe Script', cursive";
const ui = "'Archivo', ui-sans-serif, system-ui, sans-serif";

const BUILD_ID = import.meta.env.VITE_COMMIT_SHA?.slice(0, 7) || "dev";

const ghost = {
  flex: 1,
  padding: "11px",
  borderRadius: 10,
  border: `1px solid rgba(22,32,43,0.3)`,
  background: "transparent",
  color: "rgba(22,32,43,0.78)",
  fontFamily: ui,
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.16em",
  cursor: "pointer",
};

const chip = (active) => ({
  fontFamily: ui,
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.13em",
  padding: "7px 12px",
  borderRadius: 999,
  cursor: "pointer",
  border: `1px solid ${active ? C.ink : "rgba(22,32,43,0.25)"}`,
  background: active ? C.ink : "transparent",
  color: active ? "#fff" : "rgba(22,32,43,0.75)",
});

/* ---------------- helpers ---------------- */

let segMeasureCtx = null;

// Shrinks a segmented-control label to whatever font size actually fits its
// rendered width, measured with canvas — a fixed char-count threshold can't
// tell "MMM" from "iii", and this control is too narrow to guess wrong.
function useFitSegLabel(ref, text) {
  const [style, setStyle] = useState({ fontSize: 12, letterSpacing: "0.08em" });

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || !text) return;
    const cs = getComputedStyle(el);
    const available = el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    if (!available) return;
    if (!segMeasureCtx) segMeasureCtx = document.createElement("canvas").getContext("2d");

    const fits = (size, trackingEm) => {
      segMeasureCtx.font = `700 ${size}px ${ui}`;
      const w = segMeasureCtx.measureText(text).width + trackingEm * size * (text.length - 1);
      return w <= available;
    };

    if (fits(12, 0.08)) {
      setStyle({ fontSize: 12, letterSpacing: "0.08em" });
      return;
    }
    for (let size = 11.5; size >= 7.5; size -= 0.5) {
      if (fits(size, 0)) {
        setStyle({ fontSize: size, letterSpacing: 0 });
        return;
      }
    }
    setStyle({ fontSize: 7.5, letterSpacing: 0 });
  }, [text]);

  return style;
}

function SegButton({ label, active, onClick }) {
  const ref = useRef(null);
  const { fontSize, letterSpacing } = useFitSegLabel(ref, label);

  return (
    <button
      ref={ref}
      onClick={onClick}
      style={{
        position: "relative",
        zIndex: 1,
        flex: "1 1 0",
        minWidth: 0,
        padding: "8px 8px",
        border: "none",
        background: "transparent",
        color: active ? "#fff" : "rgba(22,32,43,0.75)",
        fontFamily: ui,
        fontWeight: 600,
        fontSize,
        letterSpacing,
        cursor: "pointer",
        whiteSpace: "nowrap",
        overflow: "hidden",
        textOverflow: "ellipsis",
        transition: "color .2s ease, font-size .1s ease",
      }}
    >
      {label}
    </button>
  );
}

// Flattens the picks map into an outbox batch — used both for the one-time
// legacy-shape migration below and for Restore, since neither case knows
// which of these picks the server already has. Re-sending them all is
// wasteful but harmless: POST /v1/picks upserts by decidedAt (FR-020).
function picksToOutbox(picks) {
  const outbox = [];
  for (const name of Object.keys(picks)) {
    for (const slotKey of Object.keys(picks[name])) {
      const p = picks[name][slotKey];
      outbox.push({ slot: Number(slotKey), name, verdict: p.verdict, decidedAt: p.decidedAt });
    }
  }
  return outbox;
}

function emptyCacheShape() {
  return {
    account: { lastName: "", genderFilter: "girl", onboarded: false },
    swipers: [
      { slot: 0, label: "", position: 0, block: [], exhausted: false },
      { slot: 1, label: "", position: 0, block: [], exhausted: false },
    ],
    picks: {},
    outbox: [],
    syncedAt: null,
  };
}

function useStore() {
  const [state, setState] = useState(null);
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState("loading"); // loading | saved | offline

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const fallback = emptyCacheShape();
      let loaded = fallback;
      let migrated = false;
      let ok = true;
      try {
        const r = await window.storage.get(STORAGE_KEY, true);
        if (r) {
          const parsed = JSON.parse(r.value);
          if (parsed.account === undefined && Array.isArray(parsed.people)) {
            // Pre-backend shape (people[].picks). There is no account to
            // reconcile — the app was localStorage-only before this feature —
            // but any picks already made in this browser are worth keeping
            // rather than discarding, so they carry into the outbox and sync
            // once signed in.
            const now = new Date().toISOString();
            const picks = {};
            parsed.people.forEach((person, slot) => {
              Object.entries(person.picks || {}).forEach(([name, verdict]) => {
                if (!picks[name]) picks[name] = {};
                picks[name][slot] = { verdict, decidedAt: now };
              });
            });
            loaded = {
              account: {
                lastName: parsed.lastName ?? "",
                genderFilter: parsed.genderFilter ?? "girl",
                onboarded: parsed.onboarded ?? false,
              },
              swipers: [
                { slot: 0, label: parsed.people[0]?.label || "", position: 0, block: [], exhausted: false },
                { slot: 1, label: parsed.people[1]?.label || "", position: 0, block: [], exhausted: false },
              ],
              picks,
              outbox: picksToOutbox(picks),
              syncedAt: null,
            };
            migrated = true;
          } else {
            loaded = parsed;
          }
        }
      } catch {
        // either nothing saved yet, or storage is unavailable — probe to find out which
        try {
          await window.storage.set(STORAGE_KEY, JSON.stringify(fallback), true);
        } catch {
          ok = false;
        }
      }
      if (migrated) {
        try {
          await window.storage.set(STORAGE_KEY, JSON.stringify(loaded), true);
        } catch {
          ok = false;
        }
      }
      if (!cancelled) {
        setState(loaded);
        setStatus(ok ? "saved" : "offline");
        setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const persist = useCallback(async (next) => {
    setState(next);
    try {
      const r = await window.storage.set(STORAGE_KEY, JSON.stringify(next), true);
      setStatus(r ? "saved" : "offline");
    } catch {
      setStatus("offline");
    }
  }, []);

  // Re-reads the cache without writing it — for reconciling React state after
  // something outside this hook (syncQueue's flushOutbox) wrote localStorage
  // directly, e.g. on reconnect (T072).
  const reload = useCallback(async () => {
    try {
      const r = await window.storage.get(STORAGE_KEY, true);
      if (r) setState(JSON.parse(r.value));
    } catch {
      // nothing cached yet, or storage unavailable — leave state as-is
    }
  }, []);

  return { state, ready, persist, reload, status };
}

/* ---------------- card ---------------- */

function Badge({ item, dx, fly, depth, lastName, genderFilter }) {
  const nameSize = item.n.length > 9 ? 62 : item.n.length > 6 ? 74 : 86;
  const rot = depth === 0 ? dx * 0.05 : 0;
  const bandColor = genderFilter === "both" ? C.neutralBand : item.g === "boy" ? C.boyBand : C.girlBand;

  let transform = `translate3d(${depth === 0 ? dx : 0}px, 0px, 0) rotate(${rot}deg)`;
  if (depth === 0 && fly) {
    const dir = fly === "like" ? 1 : -1;
    transform = `translate3d(${dir * 720}px, 40px, 0) rotate(${dir * 22}deg)`;
  }

  const stamp = depth === 0 ? Math.min(Math.abs(dx) / 90, 1) : 0;

  return (
    <div
      className="swipe-card"
      style={{
        position: "absolute",
        inset: 0,
        transform,
        opacity: fly && depth === 0 ? 0 : 1,
        zIndex: 10 - depth,
        touchAction: "none",
        willChange: "transform",
      }}
    >
      <div
        style={{
          width: "100%",
          height: "100%",
          background: C.card,
          borderRadius: 20,
          border: `1px solid ${C.rule}`,
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
      {/* badge band */}
      <div style={{ background: bandColor, padding: "16px 18px 12px", flexShrink: 0 }}>
        <div
          style={{
            fontFamily: ui,
            fontWeight: 800,
            fontSize: 34,
            letterSpacing: "0.12em",
            color: "#fff",
            lineHeight: 0.95,
          }}
        >
          HELLO
        </div>
        <div
          style={{
            fontFamily: ui,
            fontWeight: 500,
            fontSize: 12,
            letterSpacing: "0.34em",
            color: "rgba(255,255,255,0.9)",
            marginTop: 6,
          }}
        >
          MY NAME IS
        </div>
      </div>

      {/* ruled writing area */}
      <div
        style={{
          flex: 1,
          position: "relative",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 20px",
          backgroundImage: `repeating-linear-gradient(${C.card} 0 38px, rgba(22,32,43,0.06) 38px 39px)`,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
          <div
            style={{
              fontFamily: display,
              fontWeight: 700,
              color: C.ink,
              fontSize: nameSize,
              lineHeight: 1,
              textAlign: "center",
              transform: "rotate(-1.5deg)",
            }}
          >
            {item.n}
          </div>
          {lastName && (
            <div
              style={{
                fontFamily: display,
                fontWeight: 700,
                color: "rgba(22,32,43,0.38)",
                fontSize: Math.round(nameSize * 0.42),
                lineHeight: 1,
                marginTop: 2,
                textAlign: "center",
                transform: "rotate(-1.5deg)",
              }}
            >
              {lastName}
            </div>
          )}
        </div>

        {/* stamps */}
        <div
          style={{
            position: "absolute",
            top: 22,
            left: 20,
            opacity: dx > 0 ? stamp : 0,
            border: `4px solid ${C.yes}`,
            color: C.yes,
            padding: "4px 12px",
            borderRadius: 8,
            transform: "rotate(-14deg)",
            fontFamily: ui,
            fontWeight: 800,
            letterSpacing: "0.1em",
            fontSize: 22,
          }}
        >
          KEEP
        </div>
        <div
          style={{
            position: "absolute",
            top: 22,
            right: 20,
            opacity: dx < 0 ? stamp : 0,
            border: `4px solid ${C.no}`,
            color: C.no,
            padding: "4px 12px",
            borderRadius: 8,
            transform: "rotate(14deg)",
            fontFamily: ui,
            fontWeight: 800,
            letterSpacing: "0.1em",
            fontSize: 22,
          }}
        >
          NOPE
        </div>
      </div>
      </div>
    </div>
  );
}

/* ---------------- app ---------------- */

export default function BabyNameSwipe() {
  const { state, ready, persist, reload, status } = useStore();
  const updateAvailable = useUpdateCheck();
  const [who, setWho] = useState(0);
  const [view, setView] = useState("swipe");
  const [session, setSession] = useState(null);
  const [authChecking, setAuthChecking] = useState(true);
  // True from the moment a session appears until GET /v1/state resolves (or
  // fails). Without this, a returning user on a fresh device briefly (or, on
  // a slow connection, not so briefly) sees the pre-hydration local fallback
  // — onboarded: false — and flashes the Welcome screen before hydration
  // overwrites it, even though their account is already onboarded (SC-011).
  const [hydrating, setHydrating] = useState(false);

  const [dx, setDx] = useState(0);
  const [fly, setFly] = useState(null);
  const [history, setHistory] = useState([]);
  const [toast, setToast] = useState(null);

  const dragRef = useRef({ active: false, startX: 0, id: null });
  const timerRef = useRef(null);
  const fetchingRef = useRef({});
  const hydratedRef = useRef(false);

  // Mirrors `state` so async work (block fetch, flush) can merge against the
  // latest value instead of a stale closure, without introducing a lost-update
  // race — read this ref, then persist synchronously, no await in between.
  const stateRef = useRef(state);
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  // T043: Fire warmup on app load, before sign-in, silently ignoring failure
  useEffect(() => {
    warmupBackend();
  }, []);

  // Auth state management: check for existing session and listen for changes
  useEffect(() => {
    let cancelled = false;

    getSession().then((existingSession) => {
      if (!cancelled) {
        setSession(existingSession);
        setAuthChecking(false);
      }
    });

    const unsubscribe = onAuthStateChange((newSession) => {
      if (!cancelled) {
        setSession(newSession);
      }
    });

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  // T046: On sign-in, call GET /v1/state and hydrate the cache. Gated by
  // hydratedRef rather than just [session] — Supabase refreshes the access
  // token roughly hourly and fires the same auth-change event with a new
  // session object, which would otherwise re-run this on every refresh and
  // clobber any picks queued locally since the last hydration (T069's whole
  // point is that those survive until flushed).
  useEffect(() => {
    if (!session) {
      hydratedRef.current = false;
      return;
    }
    if (!ready || hydratedRef.current) return;
    hydratedRef.current = true;
    setHydrating(true);

    let cancelled = false;
    (async () => {
      try {
        const accountState = await getState();
        if (cancelled) return;

        const hydrated = {
          account: {
            lastName: accountState.account.lastName || "",
            genderFilter: accountState.account.genderFilter || "girl",
            onboarded: accountState.account.onboarded || false,
          },
          swipers: [0, 1].map((slot) => {
            const s = accountState.swipers.find((sw) => sw.slot === slot);
            return {
              slot,
              label: s?.label || (slot === 0 ? "Parent 1" : "Partner"),
              position: s?.position || 0,
              block: [],
              exhausted: false,
            };
          }),
          picks: {},
          outbox: [],
          syncedAt: new Date().toISOString(),
        };

        for (const pick of accountState.picks) {
          if (pick.slot !== 0 && pick.slot !== 1) continue;
          if (!hydrated.picks[pick.name]) hydrated.picks[pick.name] = {};
          hydrated.picks[pick.name][pick.slot] = { verdict: pick.verdict, decidedAt: pick.decidedAt };
        }

        persist(hydrated);
      } catch (err) {
        console.error("Failed to hydrate state from backend:", err);
      } finally {
        if (!cancelled) setHydrating(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [session, ready, persist]);

  // Reset per-swiper transient UI when switching who's swiping.
  useEffect(() => {
    setDx(0);
    setFly(null);
    setHistory([]);
  }, [who]);

  // keyboard
  const decideRef = useRef(null);
  const undoRef = useRef(null);
  useEffect(() => {
    const onKey = (e) => {
      // Never swallow a keystroke aimed at a text field, full stop — checked
      // before any screen-state guard, not instead of one. This class of bug
      // has already shipped twice: once as Backspace being eaten on Welcome's
      // fields (fixed by adding an onboarded check to the old guard), and
      // again here on the SignIn screen once auth introduced a new
      // pre-swipe screen the guard didn't know to exclude. Enumerating
      // "which screens count as swipe" is exactly the approach that keeps
      // failing when a new screen is added — checking the event's actual
      // target is what makes the next one structurally not a bug.
      const tag = e.target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || e.target?.isContentEditable) return;
      if (!session || !state?.account?.onboarded || view !== "swipe") return;
      if (e.key === "ArrowRight") decideRef.current?.("like");
      else if (e.key === "ArrowLeft") decideRef.current?.("pass");
      else if (e.key === "Backspace") {
        e.preventDefault();
        undoRef.current?.();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [view, state?.account?.onboarded, session]);

  // T071: low-water-mark refill. Also what gets the very first cards after
  // sign-in, since GET /v1/state carries no deck — every swiper starts with
  // an empty block.
  const retryTimerRef = useRef({});
  useEffect(
    () => () => {
      Object.values(retryTimerRef.current).forEach((t) => clearTimeout(t));
    },
    []
  );

  const fetchMore = useCallback(
    async (slot) => {
      if (fetchingRef.current[slot]) return;
      const current = stateRef.current;
      if (!current || current.swipers[slot]?.exhausted) return;
      fetchingRef.current[slot] = true;
      clearTimeout(retryTimerRef.current[slot]);
      try {
        // T072: flush before requesting more, so a device that fell behind
        // uploads its own decisions before asking for new ones.
        await flushOutbox().catch(() => {});
        const result = await requestNextBlock(slot, BLOCK_REQUEST_SIZE);
        const base = stateRef.current;
        if (!base) return;
        const next = structuredClone(base);
        const sw = next.swipers[slot];
        const existing = new Set(sw.block.map((c) => c.name));
        const fresh = result.block.filter((c) => !existing.has(c.name));
        sw.block = [...sw.block, ...fresh];
        sw.exhausted = result.exhausted;
        await persist(next);
      } catch (err) {
        // Offline, waking, rate-limited, or a 5xx — all render as the same
        // friendly waiting state (FR-031). None of those are surfaced as an
        // error, but a one-shot fetch that fails would otherwise strand the
        // swiper on that waiting state until some unrelated state change
        // happens to re-run the low-water-mark effect — so retry on a short
        // timer instead of relying on that. The 'online' handler already
        // covers the case where the browser knows it dropped connectivity;
        // this covers everything else (a cold-starting container, one flaky
        // request) without waiting for a browser-level signal that may never
        // fire.
        console.error("Failed to fetch next block:", err);
        retryTimerRef.current[slot] = setTimeout(() => fetchMore(slot), 4000);
      } finally {
        fetchingRef.current[slot] = false;
      }
    },
    [persist]
  );

  useEffect(() => {
    // Gated on !hydrating: GET /v1/state hydration unconditionally resets
    // block to [] (the server doesn't carry a deck), and it can still be in
    // flight here since this effect only requires `state` to exist, which the
    // pre-hydration fallback already satisfies. Fetching a block before
    // hydration lands means hydration's persist() — which always wins, since
    // it's the source of truth for sign-in — clobbers the freshly-fetched
    // cards the moment it resolves.
    if (!session || !ready || !state || hydrating) return;
    const sw = state.swipers[who];
    if (!sw || sw.exhausted) return;
    if (sw.block.length < LOW_WATER_MARK) {
      fetchMore(who);
    }
  }, [session, ready, state, who, hydrating, fetchMore]);

  // T072: flush on reconnect.
  useEffect(() => {
    const onOnline = () => {
      flushOutbox()
        .then(() => reload())
        .catch(() => {});
    };
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, [reload]);

  // Derived from picks rather than the block: a name both parents kept must
  // stay listed even if it is no longer being dealt. Insertion order = the
  // order names appear in the picks map.
  const matches = useMemo(() => {
    if (!state) return [];
    return Object.keys(state.picks).filter((n) => {
      const p = state.picks[n];
      const a = p[0];
      const b = p[1];
      if (a?.verdict !== "keep" || b?.verdict !== "keep") return false;
      return inActiveView(a.gender ?? b.gender, state.account.genderFilter);
    });
  }, [state]);

  const decide = useCallback(
    (dir) => {
      if (fly) return;
      const current = stateRef.current;
      if (!current) return;
      const sw = current.swipers[who];
      const item = sw?.block?.[0];
      if (!item) return;

      const verdict = dir === "like" ? "keep" : "no";
      const decidedAt = new Date().toISOString();

      const next = structuredClone(current);
      next.swipers[who].block = next.swipers[who].block.slice(1);
      if (!next.picks[item.name]) next.picks[item.name] = {};
      next.picks[item.name][who] = { verdict, decidedAt, gender: item.gender };
      next.outbox.push({ slot: who, name: item.name, verdict, decidedAt });
      persist(next);

      setHistory((h) => [...h, { name: item.name, gender: item.gender, position: item.position }]);

      const otherSlot = who === 0 ? 1 : 0;
      if (dir === "like" && next.picks[item.name][otherSlot]?.verdict === "keep") {
        setToast(item.name);
        setTimeout(() => setToast(null), 2200);
      }

      setFly(dir);
      timerRef.current = setTimeout(() => {
        setFly(null);
        setDx(0);
      }, 260);
    },
    [fly, persist, who]
  );
  decideRef.current = decide;

  const undo = useCallback(() => {
    if (!history.length || fly) return;
    const current = stateRef.current;
    if (!current) return;
    const last = history[history.length - 1];

    const next = structuredClone(current);
    const p = next.picks[last.name];
    if (p) {
      delete p[who];
      if (Object.keys(p).length === 0) delete next.picks[last.name];
    }
    next.swipers[who].block = [
      { position: last.position, name: last.name, gender: last.gender },
      ...next.swipers[who].block,
    ];
    // Drop the most recent matching outbox entry, if it hasn't flushed yet —
    // there is no "undo" verdict server-side, so an already-synced pick just
    // stays until this name is decided again.
    for (let idx = next.outbox.length - 1; idx >= 0; idx--) {
      const entry = next.outbox[idx];
      if (entry.slot === who && entry.name === last.name) {
        next.outbox.splice(idx, 1);
        break;
      }
    }
    persist(next);
    setHistory((h) => h.slice(0, -1));
    setDx(0);
  }, [history, persist, who, fly]);
  undoRef.current = undo;

  const onDown = (e) => {
    if (fly) return;
    dragRef.current = { active: true, startX: e.clientX, id: e.pointerId };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onMove = (e) => {
    if (!dragRef.current.active) return;
    setDx(e.clientX - dragRef.current.startX);
  };
  const onUp = () => {
    if (!dragRef.current.active) return;
    dragRef.current.active = false;
    if (dx > 90) decide("like");
    else if (dx < -90) decide("pass");
    else setDx(0);
  };

  const activeSwiper = state?.swipers?.[who];
  const genderFilter = state?.account?.genderFilter;
  const block = activeSwiper?.block || [];
  const exhausted = activeSwiper?.exhausted || false;

  const keeps = state
    ? Object.keys(state.picks).filter((n) => {
        const p = state.picks[n][who];
        return p?.verdict === "keep" && inActiveView(p.gender, genderFilter);
      })
    : [];

  // Card objects are built only for the handful of visible cards.
  const visible = block.slice(0, 3).map((item) => ({ n: item.name, g: item.gender }));
  const label = state?.swipers?.[who]?.label || "";

  const round = (bg, brd, size) => ({
    width: size,
    height: size,
    borderRadius: "50%",
    border: `2px solid ${brd}`,
    background: bg,
    display: "grid",
    placeItems: "center",
    cursor: "pointer",
    boxShadow: "0 4px 14px rgba(22,32,43,0.16)",
    fontFamily: ui,
    fontWeight: 800,
  });

  const handleSignOut = useCallback(async () => {
    // FR-006: attempt a flush once, then clear the cache regardless of
    // whether it succeeded — a shared device must not show the next person
    // anything left over.
    try {
      await flushOutbox();
    } catch {
      // best-effort — proceed to clear either way
    }
    try {
      await signOut();
    } catch {
      // ignore — clearing local state below still protects the device
    }
    await persist(emptyCacheShape());
    setView("swipe");
    setWho(0);
  }, [persist]);

  return (
    <div
      style={{
        height: "100dvh",
        overflow: "hidden",
        overscrollBehavior: "none",
        background: `linear-gradient(170deg, ${C.wash1}, ${C.wash2})`,
        color: C.ink,
        fontFamily: ui,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "calc(18px + env(safe-area-inset-top)) calc(16px + env(safe-area-inset-right)) calc(18px + env(safe-area-inset-bottom)) calc(16px + env(safe-area-inset-left))",
        boxSizing: "border-box",
      }}
    >
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;800&family=Caveat:wght@700&display=swap');
        .swipe-card { transition: transform .26s cubic-bezier(.2,.8,.3,1), opacity .26s ease; }
        .swipe-card.dragging { transition: none; }
        .seg-thumb { transition: left .25s cubic-bezier(.2,.8,.3,1); }
        button:focus-visible, [role=button]:focus-visible { outline: 2px solid ${C.ink}; outline-offset: 3px; }
        input::placeholder { color: rgba(22,32,43,0.4); }
        input:focus { outline: none; border-color: ${C.ink} !important; box-shadow: 0 0 0 3px rgba(22,32,43,0.12) !important; }
        .field-label { transition: top .18s cubic-bezier(.2,.8,.3,1), font-size .18s cubic-bezier(.2,.8,.3,1), color .18s ease; }
        @media (prefers-reduced-motion: reduce) {
          .swipe-card, .seg-thumb, .field-label { transition-duration: .01ms !important; }
        }
      `}</style>

      <div style={{ width: "100%", maxWidth: 380, height: "100%", display: "flex", flexDirection: "column", minHeight: 0, minWidth: 0, overflowX: "hidden" }}>
        {authChecking || !ready || !state || hydrating ? (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, color: "rgba(22,32,43,0.7)" }}>
            Loading…
          </div>
        ) : !session ? (
          <SignIn />
        ) : !state.account.onboarded ? (
          <Welcome
            onSubmit={async (vals) => {
              const newState = {
                ...state,
                account: { lastName: vals.lastName, genderFilter: vals.genderFilter, onboarded: true },
                swipers: [
                  { ...state.swipers[0], label: vals.yourName || "Parent 1" },
                  { ...state.swipers[1], label: vals.partnerName || "Partner" },
                ],
              };
              persist(newState);

              // T044: Wire Welcome to persist via PUT /v1/settings
              try {
                await putSettings({
                  lastName: vals.lastName || "",
                  genderFilter: vals.genderFilter || "girl",
                  onboarded: true,
                  swiper0Label: vals.yourName || "Parent 1",
                  swiper1Label: vals.partnerName || "Partner",
                });
              } catch (err) {
                console.error("Failed to sync settings to backend:", err);
              }
            }}
          />
        ) : view === "settings" ? (
          <SettingsView
            initial={{
              yourName: state.swipers?.[0]?.label || "",
              partnerName: state.swipers?.[1]?.label || "",
              lastName: state.account.lastName || "",
              genderFilter: state.account.genderFilter || "girl",
            }}
            onChange={async (vals) => {
              const current = stateRef.current;
              const next = {
                ...current,
                account: { ...current.account, lastName: vals.lastName, genderFilter: vals.genderFilter },
                swipers: [
                  { ...current.swipers[0], label: vals.yourName || "Parent 1" },
                  { ...current.swipers[1], label: vals.partnerName || "Partner" },
                ],
              };
              persist(next);

              try {
                await putSettings({
                  lastName: vals.lastName || "",
                  genderFilter: vals.genderFilter || "girl",
                  onboarded: true,
                  swiper0Label: vals.yourName || "Parent 1",
                  swiper1Label: vals.partnerName || "Partner",
                });
              } catch (err) {
                console.error("Failed to sync settings to backend:", err);
              }
            }}
            onBack={() => setView("swipe")}
            onSignOut={handleSignOut}
            onResetEverything={async () => {
              if (
                !window.confirm(
                  "Reset everything? This clears both the account and this device — both swipers' picks, names, and settings will be deleted everywhere."
                )
              )
                return;

              // T045: Wire "RESET EVERYTHING ON THIS DEVICE" to POST /v1/reset
              try {
                await postReset("everything");
              } catch (err) {
                console.error("Failed to reset on backend:", err);
              }

              persist(emptyCacheShape());
              setView("swipe");
            }}
          />
        ) : (
          <>
            {/* header */}
            <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 14, flexShrink: 0, minWidth: 0 }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, letterSpacing: "0.26em", color: "rgba(22,32,43,0.68)", marginBottom: 6 }}>SWIPING AS</div>
                <div
                  style={{
                    position: "relative",
                    display: "flex",
                    minWidth: 176,
                    padding: 3,
                    borderRadius: 999,
                    background: "rgba(22,32,43,0.08)",
                  }}
                >
                  <div
                    className="seg-thumb"
                    style={{
                      position: "absolute",
                      top: 3,
                      bottom: 3,
                      left: who === 0 ? 3 : "50%",
                      width: "calc(50% - 3px)",
                      borderRadius: 999,
                      background: C.ink,
                      boxShadow: "0 1px 3px rgba(22,32,43,0.3)",
                    }}
                  />
                  {[0, 1].map((k) => (
                    <SegButton
                      key={k}
                      label={(state?.swipers?.[k]?.label || `P${k + 1}`).toUpperCase()}
                      active={who === k}
                      onClick={() => setWho(k)}
                    />
                  ))}
                </div>
              </div>
              <div style={{ display: "flex", gap: 10, flexShrink: 0, alignItems: "center" }}>
                <button onClick={() => setView(view === "swipe" ? "list" : "swipe")} style={chip(view === "list")}>
                  {view === "swipe" ? `MATCHES · ${matches.length}` : "BACK"}
                </button>
                <button
                  onClick={() => setView("settings")}
                  aria-label="Settings"
                  style={{
                    background: "transparent",
                    border: `1px solid rgba(22,32,43,0.2)`,
                    borderRadius: 999,
                    width: 34,
                    height: 34,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "pointer",
                    flexShrink: 0,
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={C.ink} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="3" />
                    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                  </svg>
                </button>
              </div>
            </div>

            {view === "swipe" ? (
              <>
                {/* card stack */}
                <div
                  style={{ position: "relative", flex: 1, minHeight: 0, minWidth: 0, marginBottom: 22 }}
                  onPointerDown={onDown}
                  onPointerMove={onMove}
                  onPointerUp={onUp}
                  onPointerCancel={onUp}
                >
                  {visible.length === 0 ? (
                    <Empty
                      text={
                        exhausted
                          ? keeps.length
                            ? `Deck's done. ${keeps.length} kept — check the list, or try another filter.`
                            : "No names left in this filter. Try another one."
                          : "Finding more names… hang tight."
                      }
                    />
                  ) : (
                    visible
                      .map((item, d) => (
                        <div key={item.n} className={d === 0 && dragRef.current.active ? "" : ""}>
                          <Badge
                            item={item}
                            dx={d === 0 ? dx : 0}
                            fly={d === 0 ? fly : null}
                            depth={d}
                            lastName={state.account.lastName}
                            genderFilter={genderFilter}
                          />
                        </div>
                      ))
                      .reverse()
                  )}
                </div>

                {/* controls */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 20, flexShrink: 0 }}>
                  <button onClick={() => decide("pass")} style={{ ...round(C.card, C.no, 62), color: C.no, fontSize: 24 }} aria-label="Pass">✕</button>
                  <button onClick={undo} disabled={!history.length} style={{ ...round("transparent", "rgba(22,32,43,0.25)", 44), color: "rgba(22,32,43,0.5)", fontSize: 15, opacity: history.length ? 1 : 0.35, boxShadow: "none" }} aria-label="Undo">↺</button>
                  <button onClick={() => decide("like")} style={{ ...round(C.card, C.yes, 62), color: C.yes, fontSize: 24 }} aria-label="Keep">♥</button>
                </div>
              </>
            ) : (
              <div style={{ flex: 1, minHeight: 0, minWidth: 0, overflowY: "auto", overflowX: "hidden", overscrollBehavior: "contain" }}>
                <ListView
                  matches={matches}
                  keeps={keeps}
                  label={label}
                  onCopy={() => {
                    const text = JSON.stringify(state);
                    try {
                      navigator.clipboard.writeText(text);
                      setToast("copied");
                      setTimeout(() => setToast(null), 1800);
                    } catch {
                      window.prompt("Copy this and keep it somewhere safe:", text);
                    }
                  }}
                  onRestore={() => {
                    const raw = window.prompt("Paste a backup to restore:");
                    if (!raw) return;
                    try {
                      const parsed = JSON.parse(raw);
                      if (!Array.isArray(parsed?.swipers) || typeof parsed?.picks !== "object") {
                        throw new Error("bad shape");
                      }
                      // Block positions may no longer align with this account's
                      // served_order, so cards are always refetched fresh; every
                      // pick is resent (the server upserts by decidedAt) since a
                      // restore can't know what the server already has.
                      const restored = {
                        account: parsed.account,
                        swipers: parsed.swipers.map((s, slot) => ({
                          slot,
                          label: s.label || "",
                          position: s.position || 0,
                          block: [],
                          exhausted: false,
                        })),
                        picks: parsed.picks,
                        outbox: picksToOutbox(parsed.picks),
                        syncedAt: null,
                      };
                      persist(restored);
                      setHistory([]);
                    } catch {
                      window.alert("That didn't look like a backup from this app.");
                    }
                  }}
                  onReset={async () => {
                    if (!window.confirm(`Clear all of ${label}'s picks?`)) return;

                    // T045: Wire "START [NAME] OVER" to POST /v1/reset
                    try {
                      await postReset("swiper", who);
                    } catch (err) {
                      console.error("Failed to reset swiper on backend:", err);
                    }

                    const current = stateRef.current;
                    const next = structuredClone(current);
                    for (const name of Object.keys(next.picks)) {
                      delete next.picks[name][who];
                      if (Object.keys(next.picks[name]).length === 0) delete next.picks[name];
                    }
                    next.outbox = next.outbox.filter((e) => e.slot !== who);
                    next.swipers[who].block = [];
                    next.swipers[who].position = 0;
                    next.swipers[who].exhausted = false;
                    persist(next);
                    setHistory([]);
                  }}
                />
              </div>
            )}

            {view === "swipe" && status === "offline" && (
              <div style={{ textAlign: "center", marginTop: 8, fontSize: 12, color: C.alert, letterSpacing: "0.06em", flexShrink: 0 }}>
                Not saving. Open Matches and copy a backup before you close this.
              </div>
            )}
          </>
        )}
      </div>

      {updateAvailable && (
        <div
          style={{
            position: "fixed",
            top: "calc(14px + env(safe-area-inset-top))",
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 50,
            background: C.ink,
            color: C.card,
            padding: "10px 12px 10px 16px",
            borderRadius: 999,
            boxShadow: "0 8px 24px rgba(0,0,0,0.28)",
            fontSize: 13,
            display: "flex",
            alignItems: "center",
            gap: 12,
            whiteSpace: "nowrap",
          }}
        >
          <span>New version available — install now?</span>
          <button
            onClick={() => window.location.reload()}
            style={{
              background: C.gold,
              color: C.ink,
              border: "none",
              borderRadius: 999,
              padding: "7px 14px",
              fontFamily: ui,
              fontWeight: 800,
              fontSize: 12,
              letterSpacing: "0.1em",
              cursor: "pointer",
            }}
          >
            INSTALL
          </button>
        </div>
      )}

      {toast && (
        <div
          style={{
            position: "fixed",
            bottom: 26,
            left: "50%",
            transform: "translateX(-50%)",
            background: C.ink,
            color: C.card,
            padding: "12px 20px",
            borderRadius: 999,
            boxShadow: "0 8px 24px rgba(0,0,0,0.28)",
            fontSize: 13,
            letterSpacing: "0.06em",
          }}
        >
          {toast === "copied" ? (
            <span style={{ letterSpacing: "0.12em" }}>BACKUP COPIED</span>
          ) : (
            <>
              <span style={{ color: C.gold, fontWeight: 800 }}>MATCH</span>
              <span style={{ margin: "0 8px", opacity: 0.4 }}>·</span>
              <span style={{ fontFamily: display, fontSize: 22 }}>{toast}</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Empty({ text }) {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        border: `2px dashed rgba(22,32,43,0.22)`,
        borderRadius: 20,
        display: "grid",
        placeItems: "center",
        textAlign: "center",
        padding: 28,
        fontSize: 13,
        lineHeight: 1.6,
        color: "rgba(22,32,43,0.6)",
      }}
    >
      {text}
    </div>
  );
}

function ListView({ matches, keeps, label, onReset, onCopy, onRestore }) {
  const Row = ({ n, gold }) => (
    <div
      style={{
        display: "flex",
        alignItems: "baseline",
        justifyContent: "space-between",
        padding: "10px 14px",
        background: C.card,
        borderRadius: 10,
        border: `1px solid ${gold ? "rgba(201,150,43,0.55)" : C.rule}`,
      }}
    >
      <span style={{ fontFamily: display, fontSize: 30, lineHeight: 1 }}>{n}</span>
    </div>
  );

  return (
    <div style={{ paddingBottom: 20 }}>
      <SectionTitle>Both said yes ({matches.length})</SectionTitle>
      {matches.length ? (
        <div style={{ display: "grid", gap: 8, marginBottom: 26 }}>
          {matches.map((n) => <Row key={n} n={n} gold />)}
        </div>
      ) : (
        <p style={{ fontSize: 13, color: "rgba(22,32,43,0.72)", marginBottom: 26, lineHeight: 1.6 }}>
          Nothing yet. Switch swipers up top and run the deck as the other parent — names you both keep land here.
        </p>
      )}

      <SectionTitle>{label}&apos;s keeps ({keeps.length})</SectionTitle>
      <div style={{ display: "grid", gap: 8 }}>
        {keeps.map((n) => <Row key={n} n={n} />)}
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 24 }}>
        <button onClick={onCopy} style={ghost}>COPY BACKUP</button>
        <button onClick={onRestore} style={ghost}>RESTORE</button>
      </div>

      {keeps.length > 0 && (
        <button
          onClick={onReset}
          style={{
            marginTop: 10,
            width: "100%",
            padding: "11px",
            borderRadius: 10,
            border: `1px solid rgba(196,57,47,0.35)`,
            background: "transparent",
            color: "rgba(196,57,47,0.85)",
            fontFamily: ui,
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: "0.18em",
            cursor: "pointer",
          }}
        >
          START {label.toUpperCase()} OVER
        </button>
      )}
    </div>
  );
}

function SectionTitle({ children }) {  return (
    <div style={{ fontSize: 12, letterSpacing: "0.24em", color: "rgba(22,32,43,0.65)", margin: "0 0 10px", textTransform: "uppercase" }}>
      {children}
    </div>
  );
}

/* ---------------- profile / onboarding ---------------- */

const fieldLabel = {
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.14em",
  color: "rgba(22,32,43,0.7)",
  marginBottom: 6,
  display: "block",
};

const fieldInput = {
  width: "100%",
  minWidth: 0,
  padding: "12px 14px",
  borderRadius: 10,
  border: `1px solid rgba(22,32,43,0.22)`,
  background: C.card,
  color: C.ink,
  fontFamily: ui,
  fontSize: 16,
  boxShadow: "0 1px 3px rgba(22,32,43,0.08)",
  boxSizing: "border-box",
};

let floatingFieldId = 0;

function FloatingField({ label, value, onChange, maxLength }) {
  const [id] = useState(() => `field-${++floatingFieldId}`);
  const [focused, setFocused] = useState(false);
  const floated = focused || value.length > 0;

  return (
    <div style={{ position: "relative", minWidth: 0 }}>
      <input
        id={id}
        style={{ ...fieldInput, paddingTop: 20, paddingBottom: 6 }}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        maxLength={maxLength}
      />
      <label
        htmlFor={id}
        className="field-label"
        style={{
          position: "absolute",
          left: 14,
          top: floated ? 7 : "50%",
          transform: floated ? "none" : "translateY(-50%)",
          fontSize: floated ? 11 : 16,
          fontWeight: 600,
          color: floated ? "rgba(22,32,43,0.6)" : "rgba(22,32,43,0.4)",
          pointerEvents: "none",
        }}
      >
        {label}
      </label>
    </div>
  );
}

function useProfileFields(initial) {
  const [yourName, setYourName] = useState(initial.yourName || "");
  const [partnerName, setPartnerName] = useState(initial.partnerName || "");
  const [lastName, setLastName] = useState(initial.lastName || "");
  const [genderFilter, setGenderFilter] = useState(initial.genderFilter || "girl");

  return {
    yourName, setYourName,
    partnerName, setPartnerName,
    lastName, setLastName,
    genderFilter, setGenderFilter,
    canSubmit: yourName.trim().length > 0,
    values: () => ({
      yourName: yourName.trim(),
      partnerName: partnerName.trim(),
      lastName: lastName.trim(),
      genderFilter,
    }),
  };
}

function ProfileFields({ f }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
      <FloatingField label="Your Name" value={f.yourName} onChange={f.setYourName} maxLength={15} />
      <FloatingField label="Partner's Name" value={f.partnerName} onChange={f.setPartnerName} maxLength={15} />
      <FloatingField label="Last Name" value={f.lastName} onChange={f.setLastName} maxLength={24} />
      <div style={{ minWidth: 0 }}>
        <label style={fieldLabel}>NAMES TO SHOW</label>
        <div style={{ display: "flex", gap: 8, minWidth: 0 }}>
          {[["girl", "GIRL"], ["boy", "BOY"], ["both", "BOTH"]].map(([val, lab]) => (
            <button
              key={val}
              onClick={() => f.setGenderFilter(val)}
              style={{ ...chip(f.genderFilter === val), flex: 1, minWidth: 0, textAlign: "center" }}
            >
              {lab}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function ProfileActions({ canSubmit, submitLabel, onSubmit, onCancel }) {
  return (
    <div style={{ display: "flex", gap: 8, minWidth: 0 }}>
      {onCancel && (
        <button onClick={onCancel} style={{ ...ghost, minWidth: 0 }}>
          CANCEL
        </button>
      )}
      <button
        onClick={onSubmit}
        disabled={!canSubmit}
        style={{
          flex: 2,
          minWidth: 0,
          padding: "12px",
          borderRadius: 10,
          border: "none",
          background: canSubmit ? C.ink : "rgba(22,32,43,0.3)",
          color: "#fff",
          fontFamily: ui,
          fontWeight: 700,
          fontSize: 13,
          letterSpacing: "0.12em",
          cursor: canSubmit ? "pointer" : "not-allowed",
        }}
      >
        {submitLabel}
      </button>
    </div>
  );
}

function SignIn() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!email.trim() || loading) return;
    setLoading(true);
    setError("");
    const { error: err } = await signInWithEmail(email.trim());
    setLoading(false);
    if (err) {
      setError("Failed to send magic link. Please try again.");
    } else {
      setSent(true);
    }
  };

  return (
    <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", justifyContent: "center", gap: 24 }}>
      <div>
        <div style={{ fontFamily: display, fontSize: 44, lineHeight: 1 }}>Baby Name Swipe</div>
        <p style={{ fontSize: 13, opacity: 0.65, marginTop: 10, lineHeight: 1.6 }}>
          Sign in to save your swipes across all your devices.
        </p>
      </div>

      {sent ? (
        <div style={{
          padding: "16px",
          borderRadius: 10,
          background: "rgba(22, 121, 94, 0.1)",
          border: "1px solid rgba(22, 121, 94, 0.3)",
          fontSize: 13,
          lineHeight: 1.6,
          color: C.yes,
        }}>
          Check your email! We sent you a magic link to sign in.
        </div>
      ) : (
        <>
          <div style={{ position: "relative" }}>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              placeholder="your@email.com"
              disabled={loading}
              style={{
                width: "100%",
                padding: "14px",
                borderRadius: 10,
                border: `1px solid ${error ? C.alert : "rgba(22,32,43,0.25)"}`,
                background: "#fff",
                color: C.ink,
                fontFamily: ui,
                fontSize: 16,
                boxSizing: "border-box",
              }}
            />
          </div>

          {error && (
            <div style={{
              padding: "12px 14px",
              borderRadius: 10,
              background: "rgba(168, 87, 75, 0.1)",
              border: "1px solid rgba(168, 87, 75, 0.3)",
              fontSize: 13,
              color: C.alert,
            }}>
              {error}
            </div>
          )}

          <button
            onClick={handleSubmit}
            disabled={!email.trim() || loading}
            style={{
              width: "100%",
              padding: "12px",
              borderRadius: 10,
              border: "none",
              background: !email.trim() || loading ? "rgba(22,32,43,0.3)" : C.ink,
              color: "#fff",
              fontFamily: ui,
              fontWeight: 700,
              fontSize: 13,
              letterSpacing: "0.12em",
              cursor: !email.trim() || loading ? "default" : "pointer",
              opacity: !email.trim() || loading ? 0.5 : 1,
            }}
          >
            {loading ? "SENDING..." : "SEND MAGIC LINK"}
          </button>
        </>
      )}
    </div>
  );
}

function Welcome({ onSubmit }) {
  const f = useProfileFields({});
  return (
    <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", justifyContent: "center", gap: 24 }}>
      <div>
        <div style={{ fontFamily: display, fontSize: 44, lineHeight: 1 }}>Welcome</div>
        <p style={{ fontSize: 13, opacity: 0.65, marginTop: 10, lineHeight: 1.6 }}>
          Quick setup before you start swiping. This is saved to your account.
        </p>
      </div>
      <ProfileFields f={f} />
      <ProfileActions canSubmit={f.canSubmit} submitLabel="START SWIPING" onSubmit={() => onSubmit(f.values())} />
    </div>
  );
}

function SettingsView({ initial, onChange, onBack, onResetEverything, onSignOut }) {
  const f = useProfileFields(initial);

  useEffect(() => {
    const t = setTimeout(() => onChange(f.values()), 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f.yourName, f.partnerName, f.lastName, f.genderFilter]);

  const linkStyle = { color: C.ink, fontSize: 13, textDecoration: "underline" };

  return (
    <div style={{ flex: 1, minHeight: 0, minWidth: 0, display: "flex", flexDirection: "column" }}>
      <div style={{ flex: 1, minHeight: 0, minWidth: 0, overflowY: "auto", overflowX: "hidden", overscrollBehavior: "contain" }}>
        <SectionTitle>Settings</SectionTitle>
        <ProfileFields f={f} />
        <button
          onClick={onResetEverything}
          style={{
            marginTop: 24,
            width: "100%",
            padding: "11px",
            borderRadius: 10,
            border: `1px solid rgba(196,57,47,0.35)`,
            background: "transparent",
            color: "rgba(196,57,47,0.85)",
            fontFamily: ui,
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: "0.18em",
            cursor: "pointer",
          }}
        >
          RESET EVERYTHING ON THIS DEVICE
        </button>

        <button
          onClick={onSignOut}
          style={{
            marginTop: 10,
            width: "100%",
            padding: "11px",
            borderRadius: 10,
            border: `1px solid rgba(22,32,43,0.25)`,
            background: "transparent",
            color: "rgba(22,32,43,0.7)",
            fontFamily: ui,
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: "0.18em",
            cursor: "pointer",
          }}
        >
          SIGN OUT
        </button>

        <div style={{ marginTop: 32 }}>
          <SectionTitle>About</SectionTitle>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <a href="https://calebdudley.dev" target="_blank" rel="noopener noreferrer" style={linkStyle}>
              Created by Caleb Dudley
            </a>
            <a href="https://github.com/ca1ebd/baby-names" target="_blank" rel="noopener noreferrer" style={linkStyle}>
              View source on GitHub
            </a>
          </div>
          <div style={{ fontSize: 12, color: "rgba(22,32,43,0.5)", marginTop: 8 }}>Build {BUILD_ID}</div>
        </div>
      </div>
      <div style={{ paddingTop: 16, flexShrink: 0 }}>
        <button
          onClick={onBack}
          style={{
            width: "100%",
            padding: "12px",
            borderRadius: 10,
            border: "none",
            background: C.ink,
            color: "#fff",
            fontFamily: ui,
            fontWeight: 700,
            fontSize: 13,
            letterSpacing: "0.12em",
            cursor: "pointer",
          }}
        >
          BACK
        </button>
      </div>
    </div>
  );
}
