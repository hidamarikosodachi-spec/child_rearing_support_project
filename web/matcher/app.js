import { QUESTIONS, SCALE, CONTEXT, TYPES, TYPE_MAP, TYPE_ORDER, AXES, NEUTRAL_THRESHOLD, DISCLAIMER } from "./data.js";

const $ = (id) => document.getElementById(id);
const SAVE_KEY = "hidamari_matcher_v1";
const API = "/api/response"; // Cloudflare Worker（未設定でも診断は動く）

// ---- 状態（localStorage に保持：リロードしても消えない） ----
const blank = { answers: {}, ctx: { age: [], siblings: null }, i: 0, worry: "" };
let S = load();
function load() {
  try { return { ...blank, ...JSON.parse(localStorage.getItem(SAVE_KEY) || "{}") }; }
  catch { return { ...blank }; }
}
function save() {
  try { localStorage.setItem(SAVE_KEY, JSON.stringify(S)); } catch { /* プライベートモード等 */ }
}

// ---- 画面遷移 ----
const SECTIONS = ["intro", "quiz", "free", "result"];
function show(id) {
  SECTIONS.forEach((s) => { $(s).hidden = s !== id; });
  window.scrollTo(0, 0);
}

// ---- ステップ定義：文脈2問 → 設問15問 ----
const STEPS = [
  { kind: "ctx", key: "age" },
  { kind: "ctx", key: "siblings" },
  ...QUESTIONS.map((q) => ({ kind: "q", q })),
];
const TOTAL = STEPS.length + 1; // +1 は自由記述

function render() {
  const st = STEPS[S.i];
  if (!st) { show("free"); return; }
  $("bar").style.width = `${(S.i / TOTAL) * 100}%`;
  $("step").textContent = `${S.i + 1} / ${TOTAL}`;
  $("back").disabled = S.i === 0;
  const opts = $("opts");
  opts.innerHTML = "";

  if (st.kind === "ctx") {
    const c = CONTEXT[st.key];
    $("qtext").textContent = c.label;
    $("abtext").textContent = c.multi ? "あてはまるものをすべて選んでください" : "";
    const box = document.createElement("div");
    box.className = "chips";
    c.options.forEach((o) => {
      const b = document.createElement("button");
      b.className = "chip"; b.type = "button"; b.textContent = o;
      const cur = S.ctx[st.key];
      b.setAttribute("aria-pressed", String(c.multi ? cur.includes(o) : cur === o));
      b.onclick = () => {
        if (c.multi) {
          const a = S.ctx[st.key];
          S.ctx[st.key] = a.includes(o) ? a.filter((x) => x !== o) : [...a, o];
          save(); render();
        } else { S.ctx[st.key] = o; save(); next(); }
      };
      box.appendChild(b);
    });
    opts.appendChild(box);
    if (c.multi) {
      const go = document.createElement("button");
      go.className = "btn"; go.style.marginTop = "18px"; go.textContent = "つぎへ";
      go.disabled = S.ctx[st.key].length === 0;
      go.onclick = next;
      opts.appendChild(go);
    }
    return;
  }

  const { q } = st;
  $("qtext").textContent = q.q;
  $("abtext").innerHTML = `<b>A</b> ${esc(q.a)}<br><b>B</b> ${esc(q.b)}`;
  SCALE.forEach((sc) => {
    const b = document.createElement("button");
    b.className = "opt"; b.type = "button";
    b.setAttribute("aria-pressed", String(S.answers[q.id] === sc.value));
    b.innerHTML = `<span class="k">${sc.label.startsWith("A") || sc.label === "ややA" ? "A" : sc.label.startsWith("B") || sc.label === "ややB" ? "B" : "－"}</span><span>${sc.label}</span>`;
    b.onclick = () => { S.answers[q.id] = sc.value; save(); next(); };
    opts.appendChild(b);
  });
}
const esc = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
function next() { S.i++; save(); S.i >= STEPS.length ? show("free") : render(); }

// ---- 採点 ----
function score() {
  const out = {};
  for (const ax of ["I", "S", "R"]) {
    const qs = QUESTIONS.filter((q) => q.axis === ax);
    const vals = qs.map((q) => S.answers[q.id]).filter((v) => typeof v === "number");
    out[ax] = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
  }
  const sign = (v) => (v >= 0 ? "+" : "-");
  const key = TYPE_MAP[sign(out.I) + sign(out.S) + sign(out.R)];
  // まんなか（|平均| が閾値未満）の軸は、反転させた近接タイプも併記する
  const near = [];
  for (const ax of ["I", "S", "R"]) {
    if (Math.abs(out[ax]) < NEUTRAL_THRESHOLD) {
      const flip = { I: out.I, S: out.S, R: out.R, [ax]: -out[ax] || (out[ax] >= 0 ? -0.1 : 0.1) };
      const k = TYPE_MAP[sign(flip.I) + sign(flip.S) + sign(flip.R)];
      if (k && k !== key) near.push({ axis: ax, key: k });
    }
  }
  return { axes: out, key, near };
}

// ---- 結果表示 ----
function renderResult(r) {
  const t = TYPES[r.key];
  $("tname").textContent = t.label;
  $("taxes").textContent = t.axes;
  $("tlead").textContent = t.lead;
  $("disclaimer").textContent = DISCLAIMER;
  $("tintro").textContent = t.intro;
  $("tvalue").textContent = t.value;
  $("tstrength").textContent = t.strength;
  $("tstumble").textContent = t.stumble;
  $("ttomorrow").textContent = t.tomorrow;
  $("twith").textContent = t.withOthers;
  $("tease").innerHTML = t.ease.map((e) => {
    const [head, ...rest] = e.split("。");
    return `<div class="theory"><b>${esc(head)}。</b>${esc(rest.join("。"))}</div>`;
  }).join("");
  $("tothers").innerHTML = TYPE_ORDER.filter((k) => k !== t.key).map((k) => {
    const o = TYPES[k];
    return `<a class="other" href="./?type=${k}"><b>${o.label}</b><span>${esc(o.lead)}</span>
      <span class="ax">${o.axes}</span></a>`;
  }).join("") + `<a class="btn sub" href="types.html" style="margin-top:12px">8つのタイプの一覧を見る</a>`;

  // まんなかの軸がある場合は、近いタイプも併記する（無理に1つへ寄せない）
  if (r.near.length === 3) {
    $("tneutral").innerHTML = `<div class="card"><p class="note">3つの軸がどれも<b>まんなか</b>でした。
      その時々で形を変えているか、いまはまだ決めかねている時期なのかもしれません。
      いちばん近いのは <b>${t.label}</b> ですが、${r.near.map((n) => `<b>${TYPES[n.key].label}</b>`).join("・")}
      の景色も、きっと思い当たるところがあります。</p></div>`;
  } else if (r.near.length) {
    const others = r.near.map((n) => `<b>${TYPES[n.key].label}</b>`).join("・");
    $("tneutral").innerHTML = `<div class="card"><p class="note">
      ${r.near.map((n) => AXES[n.axis].name).join("・")}が<b>まんなか</b>でした。
      あなたは <b>${t.label}</b> と ${others} のあいだにいます。${r.near.length === 1 ? "どちらも" : "どれも"}読んでみてください。</p></div>`;
  } else {
    $("tneutral").innerHTML = "";
  }

  $("bars").innerHTML = ["I", "S", "R"].map((ax) => {
    const v = r.axes[ax]; const pct = Math.min(100, Math.max(0, ((v + 2) / 4) * 100));
    return `<div class="bar"><div class="lab"><span>${AXES[ax].minus}</span>
      <span>${AXES[ax].name}</span><span>${AXES[ax].plus}</span></div>
      <div class="track"><span class="dot" style="left:${pct}%"></span></div></div>`;
  }).join("");

  $("ttheories").innerHTML = t.theories.map((th) => `<div class="theory">
      <b>${esc(th.t)}</b> — ${esc(th.d)}<br>
      ${th.url ? `<a href="${th.url}" target="_blank" rel="noopener">記事を読む</a>`
               : `<span class="note">（連載で書く予定です）</span>`}
    </div>`).join("");

  const url = `${location.origin}${location.pathname}?type=${t.key}`;
  const text = `わが家のこそだちタイプは「${t.label}」でした。${t.lead}`;
  $("share").innerHTML = `
    <a href="https://twitter.com/intent/tweet?text=${encodeURIComponent(text + "\n")}&url=${encodeURIComponent(url)}" target="_blank" rel="noopener">X で共有</a>
    <a href="https://www.threads.net/intent/post?text=${encodeURIComponent(text + "\n" + url)}" target="_blank" rel="noopener">Threads で共有</a>
    <a href="https://social-plugins.line.me/lineit/share?url=${encodeURIComponent(url)}" target="_blank" rel="noopener">LINE で送る</a>
    <button type="button" id="copy">URL をコピー</button>`;
  $("copy").onclick = async () => {
    try { await navigator.clipboard.writeText(url); $("copy").textContent = "コピーしました"; }
    catch { $("copy").textContent = url; }
  };
  show("result");
}

// ---- 送信（失敗しても診断体験は壊さない） ----
function send(r) {
  const body = {
    v: 1,
    answers: S.answers,
    axes: r.axes,
    type: r.key,
    near: r.near.map((n) => n.key),
    age: S.ctx.age,
    siblings: S.ctx.siblings,
    worry: (S.worry || "").slice(0, 200),
    drop_at: null,
    ref: new URLSearchParams(location.search).get("utm_source") || document.referrer || null,
    ua_mobile: matchMedia("(max-width:560px)").matches,
  };
  try {
    const blob = new Blob([JSON.stringify(body)], { type: "application/json" });
    if (!navigator.sendBeacon || !navigator.sendBeacon(API, blob)) {
      fetch(API, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), keepalive: true }).catch(() => {});
    }
  } catch { /* 保存できなくても結果は出す */ }
}

// 途中離脱の記録（どの設問で閉じたか）
addEventListener("pagehide", () => {
  if (S.i > 0 && S.i < STEPS.length) {
    try {
      navigator.sendBeacon?.(API, new Blob([JSON.stringify({ v: 1, drop_at: S.i, answers: S.answers, type: null })],
        { type: "application/json" }));
    } catch { /* noop */ }
  }
});

// ---- 起動 ----
$("start").onclick = () => { S = { ...blank }; save(); show("quiz"); render(); };
$("back").onclick = () => { if (S.i > 0) { S.i--; save(); render(); } };
$("toresult").onclick = () => {
  S.worry = $("worry").value.trim(); save();
  const r = score(); send(r); renderResult(r);
};
$("again").onclick = () => { S = { ...blank }; save(); location.href = location.pathname; };

// 共有URL（?type=engawa）で開かれたら、その結果ページを直接見せる
const shared = new URLSearchParams(location.search).get("type");
if (shared && TYPES[shared]) {
  renderResult({ axes: { I: 0, S: 0, R: 0 }, key: shared, near: [] });
  $("bars").innerHTML = "";
  $("tneutral").innerHTML = `<div class="card"><p class="note">これは共有された結果ページです。
    <a href="${location.pathname}">自分でもやってみる</a></p></div>`;
} else if (S.i >= STEPS.length) {
  // 前回やり終えた状態で戻ってきた場合は、最初の画面から（結果画面に取り残さない）
  S = { ...blank }; save();
} else if (S.i > 0 && Object.keys(S.answers).length) {
  show("quiz"); render(); // 途中から再開
}
