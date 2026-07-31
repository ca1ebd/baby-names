// @ts-nocheck
// Ported as-is from the JS prototype; not worth retyping a component this dynamic.
import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { useUpdateCheck } from "./lib/useUpdateCheck";

/* ---------------- data ---------------- */

const RAW = {
  girl: {
    c: ["Abigail","Adeline","Alice","Amelia","Anna","Audrey","Ava","Brooke","Caroline","Cecilia","Charlotte","Chloe","Claire","Clara","Eleanor","Elizabeth","Ella","Emily","Emma","Evelyn","Genevieve","Grace","Hannah","Hazel","Isabella","Josephine","Julia","Juliet","Katherine","Lauren","Leah","Lillian","Lucy","Madeline","Maggie","Margaret","Mia","Molly","Natalie","Nora","Olivia","Paige","Rachel","Rose","Sadie","Sarah","Sophia","Stella","Violet","Vivian",
        "Addison","Alexandra","Allison","Amanda","Amy","Andrea","Angela","Annabelle","Annie","April","Ashley","Aubrey","Autumn","Beatrice","Bella","Bridget","Brooklyn","Camille","Carly","Cassandra","Catherine","Chelsea","Christina","Cora","Cordelia","Courtney","Daisy","Danielle","Daphne","Delaney","Delilah","Diana","Eden","Edith","Elena","Eliza","Elise","Ellie","Eloise","Elsie","Erin","Esther","Eva","Faith","Fiona","Florence","Gabrielle","Georgia","Gwendolyn","Harriet","Heidi","Helen","Holly","Hope","Iris","Isla","Ivy","Jane","Jenna","Jessica","Joy","Kate","Kayla","Kelsey","Laura","Lena","Lila","Louisa","Lydia","Mabel","Madison","Mallory","Mary","Matilda","Maya","Megan","Meredith","Miriam","Naomi","Nicole","Ophelia","Penelope","Phoebe","Rebecca","Rosalie","Rosemary","Ruby","Ruth","Savannah","Scarlett","Serena","Sienna","Summer","Sylvia","Tessa","Vanessa","Veronica","Victoria","Willa","Zoe",
        "Aaliyah","Adele","Adelina","Adelaide","Agatha","Agnes","Alba","Alina","Alma","Amara","Amber","Anastasia","Angelina","Anita","Annalise","Annika","Antonia","Ariadne","Ariana","Arielle","Arlene","Astrid","Athena","Aurelia","Aurora","Beatrix","Bernadette","Bianca","Blanche","Blythe","Briar","Brielle","Brigid","Camilla","Candace","Carina","Carmen","Carol","Carolina","Cassia","Catalina","Celeste","Celia","Charissa","Chiara","Clarissa","Claudia","Clementine","Colette","Constance","Cornelia","Cressida","Crystal","Edwina","Elaina","Elaine","Electra","Elin","Elinor","Elissa","Eliana","Elowen","Elyse","Emmeline","Enid","Estelle","Etta","Eugenia","Eunice","Evangeline","Evanna","Fatima","Fern","Fernanda","Filippa","Flora","Frances","Francesca","Freya","Gemma","Georgina","Geraldine","Gianna","Gigi","Gilda","Ginger","Gloria","Golda","Greta","Griselda","Guinevere","Gwen","Gwyneth","Hedda","Helena","Henrietta","Hermione","Hester","Hilda","Honora","Ida","Ilana","Ilse","Imani","Imogen","Ines","Ingrid","Iolanthe","Irene","Irina","Isabel","Isadora","Isolde","Jacinta","Jacqueline","Jael","Jamila","Janelle","Janet","Janice","Jasmine","Jean","Jeanette","Jemima","Jennifer","Jill","Jocelyn","Jolene","Jonquil","Jordana","Juanita","Judith","Julianne","Juniper","Justine","Karina","Karis","Kassandra","Katia","Keziah","Kiera","Kirsten","Klara","Kyra","Laila","Lana","Lara","Larissa","Laurel","Lavinia"],
    u: ["Arden","Avery","Blair","Blakely","Campbell","Charlie","Ellis","Emerson","Emery","Everly","Finley","Frankie","Greer","Hadley","Harper","Hayden","Hollis","Kennedy","Landry","Larkin","Lennon","Logan","London","Marlowe","Merritt","Monroe","Oakley","Palmer","Parker","Peyton","Presley","Quinn","Reagan","Reese","Remi","Riley","Ripley","Rory","Rowan","Sawyer","Scout","Shea","Sloane","Spencer","Sutton","Sydney","Tatum","Teagan","Winter","Wren",
        "Arlo","Aspen","Bowen","Brecken","Briggs","Callan","Carson","Cove","Easton","Elliot","Emberlynn","Ember","Fallon","Fox","Griffin","Harlow","Haven","Indigo","Jagger","Jules","Justice","Kai","Karsyn","Keegan","Lake","Lark","Legend","Lincoln","Marlow","Maverick","Milan","North","Onyx","Phoenix","Piper","River","Salem","Saylor","Sloan","True","Vale","West","Wilder","Zion","Aubree","Blaise","Brynlee","Cairo","Cassius","Cedar"],
  },
  boy: {
    c: ["Abner","Alaric","Alden","Alfred","Alonzo","Amos","Anatole","Angelo","Ansel","Archibald","Armand","Arnold","Aristotle","Arno","Baldwin","Barrett","Bertram","Blaine","Bram","Burke","Cain","Callum","Casimir","Cato","Cecil","Clarence","Corbin","Corwin","Elton","Emil","Errol","Everett","Ewan","Fabius","Faust","Ferris","Finch","Finnian","Flint","Floyd","Fraser","Gerald","Gerard","Gordon","Griffith","Harlan","Harmon","Hobart","Ike","Isham","Ivor","Jarvis","Jensen","Jorah","Kellan","Kip","Lambert","Lars","Leif","Lennox","Leon","Lex","Lior","Lloyd","Lorcan","Lucius","Manfred","Marlon","Maurice","Maynard","Merle","Mervin","Mick","Milton","Monte","Nestor","Newton","Niles","Nolan","Norbert","Norris","Odin","Ogden","Oren","Orville","Osmond","Pablo","Phil","Piers","Powell","Ragnar","Ramon","Rand","Ransom","Rawlins","Reece","Remus","Rene","Roald","Roscoe","Rowland","Rudyard","Sanford","Sargent","Selwyn","Severin","Silvio","Simeon","Sinclair","Skyler","Solon","Stellan","Tobin","Tremaine","Tucker","Tudor","Ulric","Upton","Vance","Vernon","Wallis","Walton","Warwick","Wilbur","Wilfred","Willem","Wilmer","Winfield","Woodrow","Wyndham","Xander","Yale","Zander","Zeb","Zebedee","Aaron","Abel","Abraham","Adrian","Alexander","Alistair","Ambrose","Anders","Andrew","Angus","Anselm","Archer","Arthur","Asher","Atlas","Augustus","Aurelio","Austin","Axel","Bartholomew","Basil","Baxter","Beckett","Benedict","Benjamin","Bennett","Bernard","Bishop","Blake","Boaz","Boris","Brendan","Brennan","Brett","Brian","Broderick","Bruno","Byron","Caesar","Caleb","Calvin","Camden","Carter","Cash","Cedric","Chance","Charles","Christian","Christopher","Clark","Claude","Clement","Clifford","Clive","Colton","Conrad","Constantine","Cormac","Cornelius","Cosmo","Crispin","Curtis","Cyrus","Earl","Edgar","Edmund","Edward","Edwin","Elias","Eli","Elijah","Elliott","Emmett","Enoch","Enzo","Ephraim","Erasmus","Eric","Ernest","Ethan","Eugene","Evan","Ezekiel","Ezra","Fabian","Felix","Fenwick","Ferdinand","Fergus","Finnegan","Fitzgerald","Fletcher","Flynn","Forrest","Francis","Franklin","Frederick","Gabriel","Gareth","Garrison","Gavin","Gideon","Gilbert","Giles","Graham","Grant","Grover","Gulliver","Gunner","Gus","Hamilton","Hamish","Harold","Harrison","Hector","Herbert","Hezekiah","Hiram","Homer","Horace","Howard","Hudson","Hugh","Hugo","Ian","Ignatius","Ingram","Ira","Irving","Isaac","Isaiah","Ivan","Jack","Jackson","Jacob","James","Jared","Jason","Jasper","Jerome","Jesse","Jethro","Job","Joel","Jonah","Jonas","Jonathan","Joseph","Joshua","Judah","Jude","Julian","Julius","Justin","Kenneth","Kingston","Klaus","Knox","Konrad","Lachlan","Lawrence","Lazarus","Leo","Leonard","Leopold","Levi","Lewis","Linus","Lionel","Llewellyn","Lorenzo","Louis","Lucas","Lucian","Ludwig","Magnus","Malachi","Malcolm","Marcus","Mark","Marshall","Martin","Marvin","Mason","Mathias","Matthew","Maximilian","Maxwell","Merrick","Micah","Michael","Miles"],
    u: ["Ace","Ash","Bear","Bo","Boone","Bodhi","Brice","Brooks","Cal","Case","Cassian","Cliff","Colt","Crew","Cruz","Ellison","Fisher","Gage","Hawk","Holt","Huck","Hux","Jace","Jax","Jett","Kase","Kit","Knight","Lane","Rebel","Reign","Rome","Saint","Slater","Stetson","Stryker","Trace","Ranger","Reeve","Ridge","Rocco","Rock","Slate","Steel","Talon","Tex","Thatcher","Wolf","Beau","Cole","Cage","Chase","Emrys","Gunnar","Hank","Hoyt","Kade","Kayce","Keanu","Lev","Maddox","Nash","Nix","Rad","Rain","Raiden","Rio","Roan","Tanner","Wade","Wells","Wyatt","Zeke"],
  },
};

// fixed-seed shuffle: styles interleave, and both parents see the same order
function shuffled(list) {
  const a = [...list];
  let seed = 20260730;
  for (let k = a.length - 1; k > 0; k--) {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    const j = seed % (k + 1);
    [a[k], a[j]] = [a[j], a[k]];
  }
  return a;
}

const GIRL_NAMES = shuffled([
  ...RAW.girl.c.map((n) => ({ n, s: "c" })),
  ...RAW.girl.u.map((n) => ({ n, s: "u" })),
]);
const BOY_NAMES = shuffled([
  ...RAW.boy.c.map((n) => ({ n, s: "c" })),
  ...RAW.boy.u.map((n) => ({ n, s: "u" })),
]);
const BOTH_NAMES = shuffled([...GIRL_NAMES, ...BOY_NAMES]);

function poolFor(genderFilter) {
  if (genderFilter === "boy") return BOY_NAMES;
  if (genderFilter === "both") return BOTH_NAMES;
  return GIRL_NAMES;
}

// DO NOT CHANGE THIS KEY. Changing it orphans every saved swipe.
// Adding or removing names is safe — picks are keyed by name, not position.
const STORAGE_KEY = "babyname-swipe-v3";

/* ---------------- tokens ---------------- */

const C = {
  ink: "#16202B",
  wash1: "#D3DCE2",
  wash2: "#B4C3CD",
  card: "#FFFDF7",
  band: "#C4392F",
  yes: "#16795E",
  no: "#607080",
  gold: "#C9962B",
  rule: "rgba(22,32,43,0.12)",
};

const display = "'Caveat', 'Segoe Script', cursive";
const ui = "'Archivo', ui-sans-serif, system-ui, sans-serif";

const ghost = {
  flex: 1,
  padding: "11px",
  borderRadius: 10,
  border: `1px solid rgba(22,32,43,0.2)`,
  background: "transparent",
  color: "rgba(22,32,43,0.6)",
  fontFamily: ui,
  fontSize: 11,
  letterSpacing: "0.16em",
  cursor: "pointer",
};

const chip = (active) => ({
  fontFamily: ui,
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: "0.14em",
  padding: "7px 12px",
  borderRadius: 999,
  cursor: "pointer",
  border: `1px solid ${active ? C.ink : "rgba(22,32,43,0.2)"}`,
  background: active ? C.ink : "transparent",
  color: active ? "#fff" : "rgba(22,32,43,0.65)",
});

/* ---------------- helpers ---------------- */

function useStore() {
  const [state, setState] = useState(null);
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState("loading"); // loading | saved | offline

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const fallback = {
        people: [
          { label: "", picks: {} },
          { label: "", picks: {} },
        ],
        lastName: "",
        genderFilter: "girl",
        onboarded: false,
      };
      let loaded = fallback;
      let migrated = false;
      let ok = true;
      try {
        const r = await window.storage.get(STORAGE_KEY, true);
        if (r) {
          const parsed = JSON.parse(r.value);
          // Legacy saves (from before profiles/gender filter existed) have no
          // `onboarded` field. Backfill it so existing instances keep working
          // without being sent through the welcome dialog again.
          if (parsed.onboarded === undefined) {
            loaded = {
              ...parsed,
              lastName: parsed.lastName ?? "",
              genderFilter: parsed.genderFilter ?? "girl",
              onboarded: true,
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

  return { state, ready, persist, status };
}

/* ---------------- card ---------------- */

function Badge({ item, index, dx, fly, depth, lastName }) {
  const nameSize = item.n.length > 9 ? 62 : item.n.length > 6 ? 74 : 86;
  const rot = depth === 0 ? dx * 0.05 : 0;
  const lift = depth * 10;
  const scale = 1 - depth * 0.04;

  let transform = `translate3d(${depth === 0 ? dx : 0}px, ${lift}px, 0) rotate(${rot}deg) scale(${scale})`;
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
        background: C.card,
        borderRadius: 20,
        border: `1px solid ${C.rule}`,
        boxShadow: `0 ${8 + depth * 4}px ${28 + depth * 8}px rgba(22,32,43,${0.18 - depth * 0.05})`,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        touchAction: "none",
        willChange: "transform",
      }}
    >
      {/* badge band */}
      <div style={{ background: C.band, padding: "16px 18px 12px", flexShrink: 0 }}>
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

      {/* footer meta */}
      <div
        style={{
          borderTop: `1px solid ${C.rule}`,
          padding: "10px 18px",
          display: "flex",
          justifyContent: "flex-end",
          fontFamily: ui,
          fontSize: 11,
          letterSpacing: "0.2em",
          color: "rgba(22,32,43,0.5)",
          flexShrink: 0,
        }}
      >
        <span>{index}</span>
      </div>
    </div>
  );
}

/* ---------------- app ---------------- */

export default function BabyNameSwipe() {
  const { state, ready, persist, status } = useStore();
  const updateAvailable = useUpdateCheck();
  const [who, setWho] = useState(0);
  const [view, setView] = useState("swipe");

  const [deck, setDeck] = useState([]);
  const [i, setI] = useState(0);
  const [dx, setDx] = useState(0);
  const [fly, setFly] = useState(null);
  const [history, setHistory] = useState([]);
  const [toast, setToast] = useState(null);

  const dragRef = useRef({ active: false, startX: 0, id: null });
  const timerRef = useRef(null);

  const picks = state?.people?.[who]?.picks || {};

  const pool = poolFor(state?.genderFilter);

  // rebuild deck when the filter or the swiper changes
  useEffect(() => {
    if (!ready) return;
    const p = state?.people?.[who]?.picks || {};
    setDeck(pool.filter((x) => !p[x.n]));
    setI(0);
    setDx(0);
    setFly(null);
    setHistory([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pool, who, ready]);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  const matches = useMemo(() => {
    if (!state) return [];
    const [a, b] = state.people;
    return pool.filter((x) => a.picks[x.n] === "keep" && b.picks[x.n] === "keep");
  }, [state, pool]);

  const decide = useCallback(
    (dir) => {
      if (fly || !state || i >= deck.length) return;
      const item = deck[i];
      const next = structuredClone(state);
      next.people[who].picks[item.n] = dir === "like" ? "keep" : "no";
      persist(next);
      setHistory((h) => [...h, item.n]);

      const other = next.people[who === 0 ? 1 : 0];
      if (dir === "like" && other.picks[item.n] === "keep") {
        setToast(item.n);
        setTimeout(() => setToast(null), 2200);
      }

      setFly(dir);
      timerRef.current = setTimeout(() => {
        setFly(null);
        setDx(0);
        setI((v) => v + 1);
      }, 260);
    },
    [deck, i, fly, persist, state, who]
  );

  const undo = useCallback(() => {
    if (!history.length || !state || fly) return;
    const last = history[history.length - 1];
    const next = structuredClone(state);
    delete next.people[who].picks[last];
    persist(next);
    setHistory((h) => h.slice(0, -1));
    setI((v) => Math.max(0, v - 1));
    setDx(0);
  }, [history, persist, state, who, fly]);

  // keyboard
  useEffect(() => {
    const onKey = (e) => {
      if (view !== "swipe") return;
      if (e.key === "ArrowRight") decide("like");
      else if (e.key === "ArrowLeft") decide("pass");
      else if (e.key === "Backspace") {
        e.preventDefault();
        undo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [decide, undo, view]);

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

  const keeps = pool.filter((x) => picks[x.n] === "keep");
  const visible = deck.slice(i, i + 3);
  const label = state?.people?.[who]?.label || "";

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
        @media (prefers-reduced-motion: reduce) {
          .swipe-card, .seg-thumb { transition-duration: .01ms !important; }
        }
      `}</style>

      <div style={{ width: "100%", maxWidth: 380, height: "100%", display: "flex", flexDirection: "column", minHeight: 0, minWidth: 0, overflowX: "hidden" }}>
        {!ready || !state ? (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, opacity: 0.55 }}>
            Loading…
          </div>
        ) : !state.onboarded ? (
          <Welcome
            onSubmit={(vals) => {
              persist({
                people: [
                  { label: vals.yourName || "Parent 1", picks: {} },
                  { label: vals.partnerName || "Partner", picks: {} },
                ],
                lastName: vals.lastName,
                genderFilter: vals.genderFilter,
                onboarded: true,
              });
            }}
          />
        ) : view === "settings" ? (
          <SettingsView
            initial={{
              yourName: state.people?.[0]?.label || "",
              partnerName: state.people?.[1]?.label || "",
              lastName: state.lastName || "",
              genderFilter: state.genderFilter || "girl",
            }}
            onSave={(vals) => {
              const next = structuredClone(state);
              next.people[0].label = vals.yourName || "Parent 1";
              next.people[1].label = vals.partnerName || "Partner";
              next.lastName = vals.lastName;
              next.genderFilter = vals.genderFilter;
              persist(next);
              setView("swipe");
            }}
            onBack={() => setView("swipe")}
          />
        ) : (
          <>
            {/* header */}
            <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 14, flexShrink: 0, minWidth: 0 }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 10, letterSpacing: "0.3em", opacity: 0.55, marginBottom: 6 }}>SWIPING AS</div>
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
                    <button
                      key={k}
                      onClick={() => setWho(k)}
                      style={{
                        position: "relative",
                        zIndex: 1,
                        flex: "1 1 0",
                        minWidth: 0,
                        padding: "8px 12px",
                        border: "none",
                        background: "transparent",
                        color: who === k ? "#fff" : "rgba(22,32,43,0.6)",
                        fontFamily: ui,
                        fontSize: 11,
                        fontWeight: 600,
                        letterSpacing: "0.1em",
                        cursor: "pointer",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        transition: "color .2s ease",
                      }}
                    >
                      {(state?.people?.[k]?.label || `P${k + 1}`).toUpperCase()}
                    </button>
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
                  style={{ background: "none", border: "none", padding: 0, display: "flex", cursor: "pointer", flexShrink: 0 }}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={C.ink} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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
                        keeps.length
                          ? `Deck's done. ${keeps.length} kept — check the list.`
                          : "No names left in this filter. Try another one."
                      }
                    />
                  ) : (
                    visible
                      .map((item, d) => (
                        <div key={item.n} className={d === 0 && dragRef.current.active ? "" : ""}>
                          <Badge
                            item={item}
                            index={`${i + 1} / ${deck.length}`}
                            dx={d === 0 ? dx : 0}
                            fly={d === 0 ? fly : null}
                            depth={d}
                            lastName={state.lastName}
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
                      if (!Array.isArray(parsed?.people)) throw new Error("bad shape");
                      persist(parsed);
                      setDeck(pool.filter((x) => !parsed.people[who].picks[x.n]));
                      setI(0);
                      setHistory([]);
                    } catch {
                      window.alert("That didn't look like a backup from this app.");
                    }
                  }}
                  onReset={() => {
                    if (!window.confirm(`Clear all of ${label}'s picks?`)) return;
                    const next = structuredClone(state);
                    next.people[who].picks = {};
                    persist(next);
                    setDeck(pool);
                    setI(0);
                    setHistory([]);
                  }}
                />
              </div>
            )}

            {view === "swipe" && status === "offline" && (
              <div style={{ textAlign: "center", marginTop: 8, fontSize: 11, color: C.band, letterSpacing: "0.06em", flexShrink: 0 }}>
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
              fontSize: 11,
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
          {matches.map((x) => <Row key={x.n} {...x} gold />)}
        </div>
      ) : (
        <p style={{ fontSize: 13, opacity: 0.6, marginBottom: 26, lineHeight: 1.6 }}>
          Nothing yet. Switch swipers up top and run the deck as the other parent — names you both keep land here.
        </p>
      )}

      <SectionTitle>{label}&apos;s keeps ({keeps.length})</SectionTitle>
      <div style={{ display: "grid", gap: 8 }}>
        {keeps.map((x) => <Row key={x.n} {...x} />)}
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
            color: "rgba(196,57,47,0.8)",
            fontFamily: ui,
            fontSize: 11,
            letterSpacing: "0.2em",
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
    <div style={{ fontSize: 10, letterSpacing: "0.28em", opacity: 0.5, margin: "0 0 10px", textTransform: "uppercase" }}>
      {children}
    </div>
  );
}

/* ---------------- profile / onboarding ---------------- */

const fieldLabel = {
  fontSize: 11,
  letterSpacing: "0.16em",
  opacity: 0.6,
  marginBottom: 6,
  display: "block",
};

const fieldInput = {
  width: "100%",
  minWidth: 0,
  padding: "12px 14px",
  borderRadius: 10,
  border: `1px solid ${C.rule}`,
  background: C.card,
  color: C.ink,
  fontFamily: ui,
  fontSize: 15,
  boxSizing: "border-box",
};

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
      <div style={{ minWidth: 0 }}>
        <label style={fieldLabel}>YOUR NAME</label>
        <input
          style={fieldInput}
          value={f.yourName}
          onChange={(e) => f.setYourName(e.target.value)}
          placeholder="Your name"
          maxLength={14}
        />
      </div>
      <div style={{ minWidth: 0 }}>
        <label style={fieldLabel}>PARTNER'S NAME (OPTIONAL)</label>
        <input
          style={fieldInput}
          value={f.partnerName}
          onChange={(e) => f.setPartnerName(e.target.value)}
          placeholder="Partner's name"
          maxLength={14}
        />
      </div>
      <div style={{ minWidth: 0 }}>
        <label style={fieldLabel}>LAST NAME (OPTIONAL)</label>
        <input
          style={fieldInput}
          value={f.lastName}
          onChange={(e) => f.setLastName(e.target.value)}
          placeholder="Shown on the card"
          maxLength={24}
        />
      </div>
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

function Welcome({ onSubmit }) {
  const f = useProfileFields({});
  return (
    <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", justifyContent: "center", gap: 24 }}>
      <div>
        <div style={{ fontFamily: display, fontSize: 44, lineHeight: 1 }}>Welcome</div>
        <p style={{ fontSize: 13, opacity: 0.65, marginTop: 10, lineHeight: 1.6 }}>
          Quick setup before you start swiping. This is saved on this device only.
        </p>
      </div>
      <ProfileFields f={f} />
      <ProfileActions canSubmit={f.canSubmit} submitLabel="START SWIPING" onSubmit={() => onSubmit(f.values())} />
    </div>
  );
}

function SettingsView({ initial, onSave, onBack }) {
  const f = useProfileFields(initial);
  return (
    <div style={{ flex: 1, minHeight: 0, minWidth: 0, display: "flex", flexDirection: "column" }}>
      <div style={{ flex: 1, minHeight: 0, minWidth: 0, overflowY: "auto", overflowX: "hidden", overscrollBehavior: "contain" }}>
        <SectionTitle>Settings</SectionTitle>
        <ProfileFields f={f} />
      </div>
      <div style={{ paddingTop: 16, flexShrink: 0 }}>
        <ProfileActions canSubmit={f.canSubmit} submitLabel="SAVE" onSubmit={() => onSave(f.values())} onCancel={onBack} />
      </div>
    </div>
  );
}
