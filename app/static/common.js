/* Общие помощники: DOM, запросы, графики. */
const $ = (s, r = document) => r.querySelector(s);
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k === 'html') e.innerHTML = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  kids.flat(Infinity).forEach(c => { if (c !== null && c !== undefined && c !== false) e.append(c instanceof Node ? c : document.createTextNode(String(c))); });
  return e;
};
/* append/replaceChildren принимают и массивы: иначе браузер выводит «[object HTMLElement]». */
for (const fn of ['append', 'replaceChildren']) {
  const orig = Element.prototype[fn];
  Element.prototype[fn] = function (...kids) { return orig.apply(this, kids.flat(Infinity).filter(k => k !== null && k !== undefined && k !== false)); };
}
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const store = {
  get: () => { try { return JSON.parse(localStorage.getItem('sm') || 'null'); } catch { return null; } },
  set: v => { try { localStorage.setItem('sm', JSON.stringify(v)); } catch {} },
  clear: () => { try { localStorage.removeItem('sm'); } catch {} },
};
let me = store.get();
const takesSurvey = () => !!me && ['participant', 'management'].includes(me.role);

async function api(path, opts = {}) {
  const r = await fetch(path, {
    method: opts.method || 'GET',
    headers: { 'Content-Type': 'application/json', ...(me ? { 'X-Token': me.token } : {}) },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (r.status === 401 && me) { store.clear(); me = null; setTimeout(() => { location.hash = '#/login'; }, 0); }
  if (!r.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Ошибка запроса');
  return data;
}

const pct = (v, d = 1) => v === null || v === undefined ? '—' : (v * 100).toFixed(d).replace('.', ',') + '%';
const num = (v, d = 2) => v === null || v === undefined ? '—' : v.toFixed(d).replace('.', ',');
const MONTHS = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
const shortDate = d => d && /^\d{4}-\d{2}/.test(d) ? `${MONTHS[+d.slice(5, 7) - 1]} ${d.slice(2, 4)}` : (d || '');
const CRIT_COLOR = { teamwork: 'var(--c-teamwork)', organizing: 'var(--c-organizing)', trust: 'var(--c-trust)', leisure: 'var(--c-leisure)', referent: 'var(--c-referent)' };

/* Мини-разметка отчёта: ## заголовок, - список, **жирный** */
function renderText(text) {
  const inline = s => esc(s).replace(/\*\*(.+?)\*\*/g, (_, t) => {
    const cls = { 'Высокий.': 'hi', 'Средний.': 'mid', 'Низкий.': 'low' }[t];
    return cls ? `<span class="tag ${cls}">${t.replace('.', '')}</span>` : `<b>${t}</b>`;
  });
  const box = el('div', { class: 'report-text' });
  let list = null;
  for (const raw of (text || '').split('\n')) {
    const line = raw.trimEnd();
    if (line.startsWith('## ')) { list = null; box.append(el('h2', {}, line.slice(3))); }
    else if (line.startsWith('- ')) {
      if (!list) { list = el('ul'); box.append(list); }
      list.append(el('li', { html: inline(line.slice(2)) }));
    } else if (line.trim()) { list = null; box.append(el('p', { html: inline(line) })); }
    else list = null;
  }
  if (!box.children.length) box.append(el('p', { class: 'muted' }, 'Текст отчёта пока не написан.'));
  return box;
}

/* ---- графики (SVG) ---- */
function lineChart(series, keys, metric, labels) {
  const W = 460, H = 220, L = 46, R = 28, T = 14, B = 34;
  const vals = series.flatMap(s => keys.map(k => s.criteria[k] && s.criteria[k][metric]).filter(v => v !== null && v !== undefined));
  if (!vals.length) return el('p', { class: 'muted' }, 'Нет данных');
  const max = Math.max(...vals, 0.0001) * 1.2;
  const x = i => series.length === 1 ? (L + W - R) / 2 : L + i * (W - L - R) / (series.length - 1);
  const y = v => T + (H - T - B) * (1 - v / max);
  let g = '';
  for (let i = 0; i <= 4; i++) {
    const v = max * i / 4;
    g += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" style="stroke:var(--line)"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end" font-size="11" style="fill:var(--muted)">${(v * 100).toFixed(metric === 'Y' ? 2 : 0)}%</text>`;
  }
  series.forEach((s, i) => { g += `<text x="${x(i)}" y="${H - 12}" text-anchor="middle" font-size="11" style="fill:var(--muted)">${esc(shortDate(s.date) || s.title)}</text>`; });
  for (const k of keys) {
    const pts = series.map((s, i) => [x(i), s.criteria[k] && s.criteria[k][metric], s]).filter(p => p[1] !== null && p[1] !== undefined);
    if (!pts.length) continue;
    g += `<polyline fill="none" stroke-width="2.4" stroke-linejoin="round" style="stroke:${CRIT_COLOR[k]}" points="${pts.map(p => `${p[0]},${y(p[1])}`).join(' ')}"/>`;
    g += pts.map(p => p[2].low_turnout
      ? `<circle cx="${p[0]}" cy="${y(p[1])}" r="4.5" stroke-width="2" style="fill:var(--card);stroke:${CRIT_COLOR[k]}"><title>${esc(labels[k])}, ${esc(p[2].title)}: ${pct(p[1], 2)} — низкая явка, сравнивать нельзя</title></circle>`
      : `<circle cx="${p[0]}" cy="${y(p[1])}" r="4" style="fill:${CRIT_COLOR[k]}"><title>${esc(labels[k])}, ${esc(p[2].title)}: ${pct(p[1], 2)}</title></circle>`).join('');
  }
  return el('div', { html: `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img">${g}</svg>` });
}

function legend(keys, labels) {
  return el('div', { class: 'legend' }, keys.map(k => el('span', { style: `--c:${CRIT_COLOR[k]}` }, labels[k])));
}

function mulberry(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

/* Социограмма: узлы — люди (размер = статус), линии — взаимные выборы. Раскладка силами. */
function sociogram(soc) {
  const W = 460, H = 380, nodes = soc.nodes, n = nodes.length;
  const rnd = mulberry(7), pos = nodes.map(() => [rnd() * W, rnd() * H]);
  const idx = new Map(nodes.map((nd, i) => [nd.id, i]));
  const edges = soc.edges.map(([a, b]) => [idx.get(a), idx.get(b)]);
  const k = Math.sqrt(W * H / Math.max(n, 1)) * 0.8;
  for (let it = 0; it < 260; it++) {
    const t = 1 - it / 260, disp = pos.map(() => [0, 0]);
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      let dx = pos[i][0] - pos[j][0], dy = pos[i][1] - pos[j][1];
      const d = Math.max(Math.hypot(dx, dy), 0.1), f = k * k / d;
      dx /= d; dy /= d;
      disp[i][0] += dx * f; disp[i][1] += dy * f; disp[j][0] -= dx * f; disp[j][1] -= dy * f;
    }
    for (const [a, b] of edges) {
      let dx = pos[a][0] - pos[b][0], dy = pos[a][1] - pos[b][1];
      const d = Math.max(Math.hypot(dx, dy), 0.1), f = d * d / k * 0.12;
      dx /= d; dy /= d;
      disp[a][0] -= dx * f; disp[a][1] -= dy * f; disp[b][0] += dx * f; disp[b][1] += dy * f;
    }
    for (let i = 0; i < n; i++) {
      disp[i][0] += (W / 2 - pos[i][0]) * 1.6; disp[i][1] += (H / 2 - pos[i][1]) * 1.6;
      const d = Math.max(Math.hypot(disp[i][0], disp[i][1]), 0.1), lim = 12 * t + 0.5;
      pos[i][0] += disp[i][0] / d * Math.min(d, lim); pos[i][1] += disp[i][1] / d * Math.min(d, lim);
    }
  }
  const cx = pos.reduce((a, p) => a + p[0], 0) / n, cy = pos.reduce((a, p) => a + p[1], 0) / n;
  const dist = pos.map(p => Math.hypot(p[0] - cx, p[1] - cy)), sorted = [...dist].sort((a, b) => a - b);
  const r95 = Math.max(sorted[Math.floor(n * 0.9)] || 1, 1), R = Math.min(W, H) / 2 - 22, scale = R / r95;
  const sx = i => W / 2 + (pos[i][0] - cx) * Math.min(scale, R / Math.max(dist[i], 1));
  const sy = i => H / 2 + (pos[i][1] - cy) * Math.min(scale, R / Math.max(dist[i], 1));
  const smax = Math.max(...nodes.map(nd => nd.s), 0.01);
  let g = edges.map(([a, b]) => `<line x1="${sx(a)}" y1="${sy(a)}" x2="${sx(b)}" y2="${sy(b)}" stroke-width="0.7" style="stroke:var(--muted)" opacity="0.45"/>`).join('');
  const order = nodes.map((nd, i) => i).sort((a, b) => nodes[b].s - nodes[a].s);
  g += order.reverse().map(i => {
    const r = 3 + 11 * Math.sqrt(nodes[i].s / smax), strong = nodes[i].s > smax * 0.6;
    return `<circle cx="${sx(i)}" cy="${sy(i)}" r="${r.toFixed(1)}" style="fill:var(--accent);stroke:var(--card)" stroke-width="1.5" opacity="${strong ? 0.95 : 0.65}"><title>Статус: ${nodes[i].s.toFixed(2).replace('.', ',')}</title></circle>`;
  }).join('');
  return el('div', { html: `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Социограмма">${g}</svg>` });
}

function histogram(h) {
  const W = 460, H = 210, L = 30, B = 40, T = 24, max = Math.max(...h.bins, 1), bw = (W - L - 10) / h.bins.length;
  let g = '';
  h.bins.forEach((v, i) => {
    const bh = (H - B - T) * v / max, x = L + i * bw + 4;
    g += `<rect x="${x}" y="${H - B - bh}" width="${bw - 8}" height="${bh}" rx="3" style="fill:var(--accent)" opacity="0.85"><title>${v} чел.</title></rect>`;
    g += `<text x="${x + (bw - 8) / 2}" y="${H - B - bh - 4}" text-anchor="middle" font-size="12" style="fill:var(--text)">${v}</text>`;
    g += `<text x="${x + (bw - 8) / 2}" y="${H - 18}" text-anchor="middle" font-size="11" style="fill:var(--muted)">${h.labels[i]}</text>`;
  });
  return el('div', { html: `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img">${g}</svg>` });
}

function metric(value, label, delta) {
  const d = delta === undefined || delta === null ? null
    : el('div', { class: 'd ' + (delta > 0 ? 'up' : delta < 0 ? 'down' : 'muted') }, (delta > 0 ? '▲ ' : delta < 0 ? '▼ ' : '') + `${Math.abs(delta * 100).toFixed(1).replace('.', ',')} п.п. к прошлому разу`);
  return el('div', { class: 'metric' }, el('div', { class: 'v' }, value), el('div', { class: 'l' }, label), d);
}

function hero(title, lead, extra) {
  return el('div', { class: 'hero' }, el('div', { class: 'wrap' }, el('h1', {}, title), lead ? el('p', {}, lead) : '', extra || ''));
}

function section(title, lead, ...kids) {
  return el('div', { class: 'section' }, title ? el('h2', {}, title) : '', lead ? el('p', { class: 'lead' }, lead) : '', kids);
}

const SPLIT_NAME = n => n;

/* ---- уведомления ---- */
function toast(msg, kind = 'ok') {
  let box = $('#toasts');
  if (!box) { box = el('div', { id: 'toasts', 'aria-live': 'polite' }); document.body.append(box); }
  const t = el('div', { class: 'toast ' + kind }, msg);
  box.append(t);
  setTimeout(() => { t.classList.add('hide'); setTimeout(() => t.remove(), 300); }, kind === 'err' ? 4500 : 2200);
}

/* ---- категории статуса ---- */
const CAT_CLASS = { star: 'cat-star', preferred: 'pos', accepted: '', isolated: 'warn', rejected: 'neg', controversial: 'warn' };
const CAT_HINT = {
  star: 'Выбирают намного чаще других и почти не отвергают',
  preferred: 'Выбирают чаще среднего',
  accepted: 'Обычная позиция в группе',
  isolated: 'Почти никто не выбрал ни «за», ни «против»',
  rejected: 'Отвергают заметно чаще, чем выбирают',
  controversial: 'Многие выбирают и многие отвергают одновременно',
};
const catChip = (key, titles) => key ? el('span', { class: 'chip ' + (CAT_CLASS[key] || ''), title: CAT_HINT[key] || '' }, titles[key] || key) : '';

/* Мини-график значения по исследованиям */
function sparkline(points, w = 120, h = 30) {
  const vals = points.map(p => p.S);
  if (vals.length < 2) return el('span', { class: 'muted small' }, vals.length ? num(vals[0]) : '—');
  const max = Math.max(...vals, 0.01), min = Math.min(...vals, 0);
  const x = i => 3 + i * (w - 6) / (vals.length - 1), y = v => h - 3 - (v - min) / Math.max(max - min, 0.01) * (h - 6);
  const d = vals.map((v, i) => `${x(i)},${y(v)}`).join(' ');
  const last = vals[vals.length - 1], prev = vals[vals.length - 2];
  return el('span', { class: 'spark', title: points.map(p => `${p.title}: ${num(p.S)}`).join('\n'), html:
    `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline fill="none" stroke-width="2" style="stroke:var(--accent)" points="${d}"/>` +
    `<circle cx="${x(vals.length - 1)}" cy="${y(last)}" r="3" style="fill:${last >= prev ? 'var(--pos)' : 'var(--neg)'}"/></svg>` });
}

/* Линии значений по исследованиям. items: [[ключ, подпись, цвет], ...] */
function compareChart(points, items) {
  const series = points.map(p => ({ title: p.title, date: p.date, criteria: Object.fromEntries(items.map(([k]) => [k, { v: p[k] }])) }));
  const labels = Object.fromEntries(items.map(([k, l]) => [k, l]));
  const saved = { ...CRIT_COLOR };
  items.forEach(([k, , c]) => { CRIT_COLOR[k] = c; });
  const node = el('div', {}, lineChartAbs(series, items.map(i => i[0]), 'v', labels), items.length > 1 ? legend(items.map(i => i[0]), labels) : '');
  items.forEach(([k]) => { if (k in saved) CRIT_COLOR[k] = saved[k]; else delete CRIT_COLOR[k]; });
  return node;
}

/* Как lineChart, но значения не в процентах */
function lineChartAbs(series, keys, metric, labels) {
  const W = 460, H = 200, L = 40, R = 28, T = 14, B = 34;
  const vals = series.flatMap(s => keys.map(k => s.criteria[k][metric]));
  const max = Math.max(...vals, 0.01) * 1.2;
  const x = i => series.length === 1 ? (L + W - R) / 2 : L + i * (W - L - R) / (series.length - 1);
  const y = v => T + (H - T - B) * (1 - v / max);
  let g = '';
  for (let i = 0; i <= 4; i++) { const v = max * i / 4; g += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" style="stroke:var(--line)"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end" font-size="11" style="fill:var(--muted)">${num(v)}</text>`; }
  series.forEach((s, i) => { g += `<text x="${x(i)}" y="${H - 12}" text-anchor="middle" font-size="11" style="fill:var(--muted)">${esc(shortDate(s.date) || s.title)}</text>`; });
  for (const k of keys) {
    const pts = series.map((s, i) => [x(i), s.criteria[k][metric], s]);
    g += `<polyline fill="none" stroke-width="2.4" style="stroke:${CRIT_COLOR[k]}" points="${pts.map(p => `${p[0]},${y(p[1])}`).join(' ')}"/>`;
    g += pts.map(p => `<circle cx="${p[0]}" cy="${y(p[1])}" r="4" style="fill:${CRIT_COLOR[k]}"><title>${esc(labels[k])}, ${esc(p[2].title)}: ${num(p[1])}</title></circle>`).join('');
  }
  return el('div', { html: `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img">${g}</svg>` });
}

const printButton = () => el('button', { class: 'no-print', onclick: () => window.print() }, 'Скачать PDF / распечатать');

/* Правило о кадровых решениях: показывается на главной, в анкете и у руководства. */
const noHrNotice = () => el('div', { class: 'notice' }, el('b', {}, 'Важно. '), 'Результаты социометрии не используются для назначений, снятий и других решений о людях.');
const fewText = v => v === null || v === undefined ? 'меньше 3' : `${v} чел.`;
