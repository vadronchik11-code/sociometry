/* Панели аналитика и руководства. */
const trunc = (s, n = 70) => s.length > n ? s.slice(0, n - 1) + '…' : s;
const chips = (names, cls = '') => names.length ? names.map(n => el('span', { class: 'chip ' + cls }, n)) : el('span', { class: 'muted small' }, '—');

/* Режимы частного вопроса: кто видит ответы и знает ли руководство авторов. */
const MODES = {
  named_management: { anonymous: false, visibility: 'management', label: 'Руководство видит ответы и кто ответил', badge: ['pos', 'руководство видит с именами'] },
  anonymous_management: { anonymous: true, visibility: 'management', label: 'Руководство видит только ответы, без имён', badge: ['warn', 'руководство видит без имён'] },
  analyst_only: { anonymous: false, visibility: 'analyst', label: 'Ответы видит только аналитик', badge: ['', 'только аналитик'] },
};
const modeOf = q => q.visibility === 'analyst' ? 'analyst_only' : q.anonymous ? 'anonymous_management' : 'named_management';

function tabs(items, current, onPick) {
  return el('div', { class: 'tabs' }, items.map(([key, label]) => el('button', { class: key === current ? 'on' : '', onclick: () => onPick(key) }, label)));
}

function periodSelect(periods, sel, onPick) {
  const s = el('select', { style: 'max-width:360px', onchange: () => onPick(+s.value) },
    [...periods].reverse().map(p => el('option', { value: p.id }, `${p.title} ${p.status === 'open' ? '· идёт' : '· закрыт'}`)));
  s.value = sel;
  return el('label', { style: 'max-width:360px' }, 'Опрос', s);
}

/* ---- формы создания ---- */
function periodForm(onDone, running) {
  const title = el('input', { type: 'text', placeholder: 'Например: Декабрь 2026' });
  const date = el('input', { type: 'month' });
  return el('div', { class: 'card' }, el('h3', {}, 'Новый опрос'),
    el('p', { class: 'muted small' }, 'В опрос сразу войдут 9 постоянных социометрических вопросов. Частные вопросы добавляются рядом.'),
    running ? el('p', { class: 'small', style: 'color:var(--warn)' }, `Сейчас идёт «${running.title}». Новый опрос можно создать только после его закрытия, иначе у участников пропадёт незаконченная анкета.`) : '',
    el('label', {}, 'Название', title), el('label', {}, 'Месяц исследования', date),
    el('button', { class: 'primary', onclick: async () => {
      if (!title.value.trim()) return toast('Введите название опроса', 'err');
      try { await api('/staff/periods', { method: 'POST', body: { title: title.value, date: date.value || null } }); toast('Опрос создан и открыт'); onDone(); } catch (e) { toast(e.message, 'err'); }
    } }, 'Создать и открыть'));
}

function questionForm(openPeriods, onDone) {
  const text = el('textarea', { rows: '3', placeholder: 'Например: что вам понравилось в последнем мероприятии?' });
  const type = el('select', {}, el('option', { value: 'text' }, 'Свободный текст'), el('option', { value: 'people' }, 'Выбор людей из списка'));
  const per = el('select', {}, openPeriods.map(p => el('option', { value: p.id }, p.title)));
  const preview = el('div', { class: 'hint small' });
  const radios = el('div', {}, Object.entries(MODES).map(([k, m], i) => el('label', { style: 'display:flex;gap:8px;align-items:center;color:var(--text);margin:6px 0' },
    el('input', { type: 'radio', name: 'mode', value: k, checked: i === 0, onchange: () => { preview.textContent = 'Участник увидит: «' + qNote({ ...m, kind: 'custom' }) + '»'; } }), m.label)));
  preview.textContent = 'Участник увидит: «' + qNote({ ...MODES.named_management, kind: 'custom' }) + '»';
  return el('div', { class: 'card' }, el('h3', {}, 'Частный вопрос'),
    el('p', { class: 'muted small' }, 'Появится у участников перед постоянными вопросами. Под вопросом участник увидит, кто прочитает его ответ. Если опрос уже идёт, вопрос получат только те, кто ещё не отправил анкету.'),
    el('label', {}, 'Текст вопроса', text), el('label', {}, 'Тип ответа', type),
    el('div', { class: 'small muted', style: 'margin-top:4px' }, 'Кто видит ответы'), radios, preview,
    el('label', {}, 'В какой опрос', per),
    el('button', { class: 'primary', onclick: async () => {
      if (!openPeriods.length) return toast('Сначала создайте опрос', 'err');
      if (!text.value.trim()) return toast('Введите текст вопроса', 'err');
      const m = MODES[radios.querySelector('input:checked').value];
      try {
        await api('/staff/questions', { method: 'POST', body: { text: text.value, answer_type: type.value, anonymous: m.anonymous, visibility: m.visibility, period_id: Number(per.value) } });
        toast('Вопрос добавлен'); onDone();
      } catch (e) { toast(e.message, 'err'); }
    } }, 'Добавить вопрос'));
}

/* ---- частные вопросы идущего опроса ---- */
async function periodQuestions(period, reload) {
  const list = await api(`/staff/periods/${period.id}/questions`);
  return el('div', { class: 'card' }, el('h3', {}, `Частные вопросы опроса «${period.title}»`),
    list.length ? list.map(q => el('div', { class: 'answer row-actions', style: 'justify-content:space-between' },
      el('div', {}, el('div', {}, q.text), el('div', { class: 'badge-row', style: 'margin:4px 0 0' },
        el('span', { class: 'chip ' + MODES[modeOf(q)].badge[0] }, MODES[modeOf(q)].badge[1]), el('span', { class: 'chip' }, q.answer_type === 'text' ? 'текст' : 'выбор людей'),
        el('span', { class: 'chip' }, `ответов: ${q.answers}`))),
      q.answers ? el('span', { class: 'muted small', title: 'На вопрос уже отвечали' }, 'нельзя удалить') :
        el('button', { onclick: async () => {
          if (!confirm(`Убрать вопрос «${q.text}» из опроса?`)) return;
          try { await api(`/staff/periods/${period.id}/questions/${q.id}`, { method: 'DELETE' }); toast('Вопрос убран'); reload(); } catch (e) { toast(e.message, 'err'); }
        } }, 'Убрать')))
      : el('p', { class: 'muted' }, 'Частных вопросов пока нет.'));
}

/* ---- прохождение ---- */
function progressBlock(done, notDone) {
  const total = done + notDone.length;
  return el('div', {}, el('div', { class: 'grid' },
    metric(`${done} из ${total}`, 'прошли опрос'), metric(pct(total ? done / total : 0, 0), 'доля прошедших'), metric(notDone.length, 'ещё не прошли')),
    el('div', { class: 'bar', style: 'margin:14px 0' }, el('div', { style: `width:${total ? done / total * 100 : 0}%` })),
    notDone.length ? el('div', { class: 'card' }, el('div', { class: 'row-actions', style: 'justify-content:space-between' },
      el('h3', {}, `Не прошли: ${notDone.length}`),
      el('button', { onclick: () => { navigator.clipboard.writeText(notDone.join(', ')).then(() => toast('Список скопирован'), () => toast('Не удалось скопировать', 'err')); } }, 'Скопировать список')),
      el('p', { class: 'muted small' }, 'Социометрия считается, только когда пройдут все. Этим людям нужно напомнить об опросе.'), chips(notDone))
      : el('div', { class: 'card ok' }, 'Опрос прошли все: его можно закрывать и считать.'));
}

/* ---- ответы на частные вопросы ---- */
function customAnswersView(rep, isAnalyst) {
  if (!rep.length) return el('div', { class: 'card muted' }, 'В этом опросе нет частных вопросов, ответы на которые доступны вам.');
  return el('div', {}, rep.map(r => {
    const [cls, label] = MODES[modeOf(r)].badge;
    const card = el('div', { class: 'card' }, el('h3', {}, r.text), el('div', { class: 'badge-row' },
      el('span', { class: 'chip ' + cls }, label), el('span', { class: 'chip' }, r.answer_type === 'text' ? 'свободный текст' : 'выбор людей'),
      el('span', { class: 'chip' }, `ответов: ${r.answers.length}`)));
    if (r.hidden) { card.append(el('p', { class: 'muted' }, `Ответов пока ${r.hidden}. Покажем, когда наберётся хотя бы 5, чтобы нельзя было узнать авторов.`)); return card; }
    if (!r.answers.length) { card.append(el('p', { class: 'muted' }, 'Ответов пока нет. Ответы появляются, когда участник отправит анкету.')); return card; }
    if (r.answers.some(a => !a.member)) card.append(el('p', { class: 'muted small' }, 'Авторы ответов скрыты: вопрос анонимный для руководства.'));
    const who = a => a.member
      ? el('div', { class: 'who' }, el('b', {}, a.member), isAnalyst && r.anonymous ? ' · для руководства анонимно' : '')
      : '';
    if (r.answer_type !== 'text') {
      const c = new Map();
      r.answers.forEach(a => a.targets.forEach(t => c.set(t, (c.get(t) || 0) + 1)));
      const top = [...c.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10), max = top.length ? top[0][1] : 1;
      if (top.length) card.append(el('div', { class: 'muted small' }, 'Кого называли чаще всего'), top.map(([n, v]) => hbar(n, v, max, 'var(--accent)')),
        el('div', { class: 'muted small', style: 'margin-top:12px' }, 'Все ответы'));
    }
    card.append(el('div', {}, r.answers.map(a => el('div', { class: 'answer' }, who(a),
      r.answer_type === 'text' ? el('div', {}, a.text) : a.none ? el('span', { class: 'muted' }, 'никого') : chips(a.targets)))));
    return card;
  }));
}

function hbar(name, v, max, color) {
  return el('div', { class: 'hbar' }, el('div', { class: 'name', title: name }, name),
    el('div', { class: 'track' }, el('i', { style: `width:${max ? v / max * 100 : 0}%;background:${color}` })), el('div', { class: 'num' }, v));
}

/* Мини-шкала для z-оценки: от −3 до +3, центр — среднее по группе. */
function axis(v, posColor, negColor) {
  const w = Math.min(Math.abs(v), 3) / 3 * 50;
  return el('span', { class: 'mini-axis', title: `${v >= 0 ? '+' : ''}${v.toFixed(1).replace('.', ',')} ст. откл. от среднего` },
    el('span', { class: 't' }, el('span', { class: 'm' }), el('i', { style: `${v >= 0 ? 'left:50%' : `left:${50 - w}%`};width:${w}%;background:${v >= 0 ? posColor : negColor}` })),
    el('span', { class: 'muted' }, `${v >= 0 ? '+' : ''}${v.toFixed(1).replace('.', ',')}`));
}

/* Сильный ярлык без подтверждения прошлым опросом показываем как предварительный. */
function statusChip(cat, conf, titles) {
  const node = catChip(cat, titles);
  if (conf && conf.strong && !conf.confirmed && node) {
    node.classList.add('tentative');
    node.title = (node.title ? node.title + '. ' : '') + (conf.previous ? `В прошлом опросе: ${titles[conf.previous]}. ` : '') + 'Впервые: проверить, прежде чем делать выводы.';
    return el('span', {}, node, el('span', { class: 'muted small' }, ' впервые'));
  }
  if (conf && conf.strong && conf.confirmed) return el('span', {}, node, el('span', { class: 'muted small', title: 'Та же категория в прошлом опросе' }, ' ✓'));
  return node;
}

/* ============ Аналитик ============ */
async function analystPage(app) {
  app.append(hero('Панель аналитика', 'Все ответы и показатели: кто прошёл, кто кого выбрал, у кого какой статус, и итоговый отчёт для публикации.'));
  const c = el('div', { class: 'wrap' });
  app.append(el('main', {}, c));
  const st = { periods: await api('/staff/periods'), tab: 'overview', ov: null, qid: null, view: 'rank', person: null, all: false, sort: ['S', -1], q: '' };
  st.sel = (st.periods[st.periods.length - 1] || {}).id;
  const holder = el('div'); c.append(holder);

  const loadOv = async () => { st.ov = st.sel ? await api(`/analyst/overview/${st.sel}`) : null; };
  const draw = async () => {
    holder.replaceChildren();
    if (st.periods.length) holder.append(periodSelect(st.periods, st.sel, async id => { st.sel = id; st.person = null; st.qid = null; await loadOv(); draw(); }));
    holder.append(tabs([['overview', 'Обзор'], ['people', 'Участники'], ['answers', 'Кто кого выбрал'], ['custom', 'Частные вопросы'], ['personal', 'Личные отчёты'], ['report', 'Групповой отчёт'], ['surveys', 'Опросы и вопросы']], st.tab, k => { st.tab = k; st.person = null; draw(); }));
    const body = el('div'); holder.append(body);
    try {
      if (st.tab === 'surveys') return surveysTab(body, st, async () => { st.periods = await api('/staff/periods'); st.sel = (st.periods[st.periods.length - 1] || {}).id; await loadOv(); draw(); });
      if (!st.ov) return body.append(el('div', { class: 'card muted' }, 'Опросов пока нет. Создайте первый на вкладке «Опросы и вопросы».'));
      if (st.person) body.append(personCard(st.ov, st.person, () => { st.person = null; draw(); }));
      if (st.tab === 'overview') overviewTab(body, st, draw);
      else if (st.tab === 'people') peopleTab(body, st, draw);
      else if (st.tab === 'answers') answersTab(body, st, draw);
      else if (st.tab === 'custom') body.append(customAnswersView(await api(`/analyst/custom-answers/${st.sel}`), true));
      else if (st.tab === 'report') await reportTab(body, st, loadOv, draw);
      else if (st.tab === 'personal') personalTab(body, st);
    } catch (e) { body.append(el('div', { class: 'err' }, e.message)); }
  };
  await loadOv(); draw();
}

const openPerson = (st, draw, id) => { st.person = id; draw(); window.scrollTo({ top: 260, behavior: 'smooth' }); };

function overviewTab(body, st, draw) {
  const ov = st.ov, done = new Set(ov.submitted);
  body.append(progressBlock(ov.submitted.length, ov.members.filter(m => !done.has(m.id)).map(m => m.name)));
  if (ov.period.status === 'open') {
    const left = ov.members.filter(m => !done.has(m.id));
    const reload = async () => { st.ov = await api(`/analyst/overview/${ov.period.id}`); draw(); };
    body.append(el('div', { class: 'card' }, el('h3', {}, 'Ушёл из группы?'),
      el('p', { class: 'muted small' }, 'Если человек больше не в студсовете, исключите его из этого опроса: он пропадёт из списков для выбора, а его ответы не войдут в расчёт. Пропускать тех, кто просто не успел, нельзя.'),
      left.length ? left.map(m => el('div', { class: 'answer row-actions', style: 'justify-content:space-between' }, el('span', {}, m.name),
        el('button', { onclick: async () => { if (!confirm(`Исключить «${m.name}» из опроса «${ov.period.title}»?`)) return; try { await api(`/analyst/periods/${ov.period.id}/exclude/${m.id}`, { method: 'POST' }); toast('Исключён из опроса'); reload(); } catch (e) { toast(e.message, 'err'); } } }, 'Исключить'))) : el('p', { class: 'ok' }, 'Все прошли.'),
      ov.excluded.length ? el('div', { style: 'margin-top:10px' }, el('div', { class: 'muted small' }, 'Исключены из опроса:'),
        ov.excluded.map(m => el('div', { class: 'answer row-actions', style: 'justify-content:space-between' }, el('span', { class: 'muted' }, m.name),
          el('button', { onclick: async () => { try { await api(`/analyst/periods/${ov.period.id}/include/${m.id}`, { method: 'POST' }); toast('Возвращён в опрос'); reload(); } catch (e) { toast(e.message, 'err'); } } }, 'Вернуть')))) : ''));
  }
  if (ov.microgroups && Object.keys(ov.microgroups).length) {
    body.append(section('Микрогруппы', 'Компании, где люди взаимно выбирают друг друга (поиск сообществ по взаимным выборам). Публично видны только размеры, имена — только здесь.',
      el('div', { class: 'grid two' }, Object.entries(ov.microgroups).map(([k, g]) => el('div', { class: 'card crit-card', style: `--c:${CRIT_COLOR[k]}` },
        el('h3', {}, `${g.title}: ${g.groups.length}`),
        g.groups.map((grp, i) => el('div', { class: 'answer' }, el('div', { class: 'who' }, `Компания ${i + 1} · ${grp.length} чел.`), chips(grp))),
        g.outside.length ? el('div', { class: 'answer' }, el('div', { class: 'who' }, `Без взаимных выборов · ${g.outside.length} чел.`), chips(g.outside, 'warn')) : '')))));
  }
  const cats = {};
  Object.values(ov.stats.members).forEach(v => { cats[v.category] = (cats[v.category] || 0) + 1; });
  const max = Math.max(...Object.values(cats), 1);
  body.append(section('Структура группы', 'Статус считается по выборам «за» и «против» во всех критериях, относительно среднего по группе. Нажмите «Участники», чтобы увидеть, кто где.',
    el('div', { class: 'card' }, ['star', 'preferred', 'accepted', 'controversial', 'rejected', 'isolated'].map(k =>
      el('div', { class: 'hbar' }, el('div', { class: 'name' }, catChip(k, ov.categories)), el('div', { class: 'track' }, el('i', { style: `width:${(cats[k] || 0) / max * 100}%;background:var(--accent)` })),
        el('div', { class: 'num' }, cats[k] || 0)))),
    el('p', { class: 'muted small' }, Object.entries(CAT_HINT).map(([k, h]) => `${ov.categories[k]} — ${h.toLowerCase()}.`).join(' '))));

  const by = k => ov.flags.filter(f => f.kind === k);
  const name = (f) => el('b', { style: 'cursor:pointer;color:var(--accent)', onclick: () => openPerson(st, draw, f.member_id) }, f.member);
  const conf = by('conflict'), susp = by('suspicious'), ind = by('individualist');
  const qn = id => ov.questions.findIndex(q => q.id === id) + 1;
  body.append(section('Что проверить перед публикацией', 'Система сама находит ответы, которые могут исказить картину. Они учтены в расчётах.',
    el('div', { class: 'grid two' },
      el('div', { class: 'card' }, el('h3', {}, `Противоречия: ${conf.length}`), el('p', { class: 'muted small' }, 'Один и тот же человек выбран и «за», и «против» в парных вопросах.'),
        conf.length ? conf.map(f => el('div', { class: 'answer' }, name(f), ' → ', el('span', { class: 'chip warn' }, f.target), el('span', { class: 'muted small' }, ` вопросы ${qn(f.question_id)} и ${qn(f.paired_question_id)} анкеты`))) : el('span', { class: 'muted' }, 'Нет')),
      el('div', { class: 'card' }, el('h3', {}, `Слишком много выборов: ${susp.length}`), el('p', { class: 'muted small' }, 'Выбрано больше 80% группы в одном вопросе. Возможно, человек отвечал не задумываясь.'),
        susp.length ? susp.map(f => el('div', { class: 'answer' }, name(f), el('span', { class: 'muted small' }, ` вопрос ${qn(f.question_id)} анкеты: ${f.chosen} чел.`))) : el('span', { class: 'muted' }, 'Нет')),
      el('div', { class: 'card' }, el('h3', {}, `«Индивидуалисты»: ${ind.length}`), el('p', { class: 'muted small' }, 'Выбрали «Никто» во всех постоянных вопросах.'),
        ind.length ? ind.map(f => el('div', { class: 'answer' }, name(f))) : el('span', { class: 'muted' }, 'Нет')))));
}

function memberRows(ov) {
  const done = new Set(ov.submitted), posQ = ov.questions.filter(q => q.kind === 'permanent' && q.polarity === '+').map(q => q.id);
  return ov.members.map(m => {
    const s = ov.stats.members[m.id] || {};
    return { id: m.id, name: m.name, done: done.has(m.id), S: s.S || 0, E: s.E || 0, place: s.place, pos: s.pos_total || 0, neg: s.neg_total || 0,
      mutual: posQ.reduce((a, q) => a + ((s.mutual || {})[q] || 0), 0), category: s.category, history: ov.history[m.id] || [],
      pref: s.pref_total || 0, impact: s.impact_total || 0, conf: (ov.confirmed || {})[m.id] || {} };
  });
}

function peopleTab(body, st, draw) {
  const ov = st.ov;
  let rows = memberRows(ov);
  const search = el('input', { type: 'text', placeholder: 'Поиск по имени', value: st.q });
  const catSel = el('select', { style: 'max-width:220px;margin:0' }, el('option', { value: '' }, 'Все статусы'), Object.entries(ov.categories).map(([k, t]) => el('option', { value: k }, t)));
  catSel.value = st.cat || '';
  const table = el('div', { class: 'card', style: 'overflow:auto;padding:6px 10px' });
  const cols = [['name', 'Участник'], ['category', 'Статус'], ['pref', 'Принимают'], ['impact', 'Замечают'], ['S', 'S'], ['E', 'E'], ['pos', '«За»*'], ['neg', '«Против»*'], ['mutual', 'Взаимных'], ['history', 'Динамика S'], ['done', 'Прошёл']];
  const paint = () => {
    const q = search.value.trim().toLowerCase(); st.q = search.value; st.cat = catSel.value;
    const [key, dir] = st.sort;
    const list = rows.filter(r => (!q || r.name.toLowerCase().includes(q)) && (!st.cat || r.category === st.cat))
      .sort((a, b) => (key === 'name' || key === 'category' ? String(a[key]).localeCompare(String(b[key]), 'ru') : (a[key] - b[key])) * dir);
    table.replaceChildren(el('table', { class: 't' },
      el('thead', {}, el('tr', {}, cols.map(([k, t]) => el('th', { class: k === 'history' ? '' : 'sort', onclick: () => { if (k === 'history') return; st.sort = [k, st.sort[0] === k ? -st.sort[1] : -1]; paint(); } },
        t, st.sort[0] === k ? (st.sort[1] < 0 ? ' ↓' : ' ↑') : '')))),
      el('tbody', {}, list.map(r => el('tr', { class: 'click', onclick: () => openPerson(st, draw, r.id) },
        el('td', {}, el('b', {}, r.name)), el('td', {}, statusChip(r.category, r.conf, ov.categories)), el('td', {}, axis(r.pref, '#1D9E75', '#E24B4A')), el('td', {}, axis(r.impact, '#7F77DD', '#888780')), el('td', {}, num(r.S)), el('td', {}, num(r.E)),
        el('td', {}, r.pos), el('td', {}, r.neg), el('td', {}, r.mutual), el('td', {}, sparkline(r.history)),
        el('td', {}, r.done ? el('span', { class: 'ok' }, '✓') : el('span', { class: 'muted' }, 'нет')))))),
      el('p', { class: 'muted small' }, `Показано ${list.length} из ${rows.length}. Нажмите на строку, чтобы открыть карточку. * Только по четырём парам вопросов; S включает ещё и референтометрию.`));
  };
  search.addEventListener('input', paint); catSel.addEventListener('change', paint);
  body.append(el('div', { class: 'toolbar' }, search, catSel, el('button', { onclick: () => exportCsv(ov, rows) }, 'Выгрузить в Excel (CSV)')), table);
  paint();
}

function exportCsv(ov, rows) {
  const posQ = ov.questions.filter(q => q.kind === 'permanent');
  const head = ['Участник', 'Прошёл', 'Статус', 'S', 'E', 'Место', 'За', 'Против', 'Взаимных', ...posQ.map(q => `Получено: ${q.id}`), ...posQ.map(q => `Сделано: ${q.id}`)];
  const lines = [head, ...rows.map(r => {
    const s = ov.stats.members[r.id] || { received: {}, given: {} };
    return [r.name, r.done ? 'да' : 'нет', ov.categories[r.category] || '', num(r.S, 3), num(r.E, 3), r.place, r.pos, r.neg, r.mutual,
      ...posQ.map(q => s.received[q.id] || 0), ...posQ.map(q => s.given[q.id] || 0)];
  })];
  const csv = '﻿' + lines.map(l => l.map(v => `"${String(v).replace(/"/g, '""')}"`).join(';')).join('\r\n');
  const a = el('a', { href: URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })), download: `социометрия-${ov.period.title}.csv` });
  document.body.append(a); a.click(); a.remove();
  toast('Файл сохранён');
}

function answersTab(body, st, redraw) {
  const ov = st.ov;
  const nm = Object.fromEntries(ov.members.map(m => [m.id, m.name]));
  const qs = ov.questions.filter(q => ov.answers[q.id]);
  if (!qs.length) return body.append(el('div', { class: 'card muted' }, 'В этом опросе пока нет ответов на вопросы с выбором людей.'));
  if (!st.qid || !ov.answers[st.qid]) st.qid = (qs.find(x => x.kind === 'permanent') || qs[0]).id;
  const q = ov.questions.find(x => x.id === st.qid);
  const posId = q.polarity === '-' ? q.pair_with : q.id, negId = q.polarity === '+' ? q.pair_with : q.polarity === '-' ? q.id : null;
  const P = ov.answers[posId] || {}, N = negId ? (ov.answers[negId] || {}) : {};
  const members = ov.members, done = new Set(ov.submitted);
  const recv = A => { const r = {}; members.forEach(m => r[m.id] = 0); Object.values(A).forEach(ts => ts.forEach(t => { if (t in r) r[t]++; })); return r; };
  const rp = recv(P), rn = recv(N);
  const order = [...members].sort((a, b) => rp[b.id] - rp[a.id] || a.name.localeCompare(b.name, 'ru'));
  const pick = id => openPerson(st, redraw, id);

  const sel = el('select', { onchange: () => { st.qid = +sel.value; redraw(); } }, qs.map(x => el('option', { value: x.id }, `${ov.questions.indexOf(x) + 1}. ${x.kind === 'permanent' ? '' : 'Частный: '}${trunc(x.text, 90)}`)));
  sel.value = st.qid;
  body.append(el('label', {}, 'Вопрос', sel));
  body.append(tabs([['rank', 'Рейтинг'], ['matrix', 'Матрица «кто кого»'], ['people', 'Ответы по людям']], st.view, k => { st.view = k; redraw(); }));
  if (negId) body.append(el('p', { class: 'muted small' }, 'Показаны оба вопроса пары: зелёное — выборы «за», красное — «против». Нажмите на имя, чтобы открыть карточку.'));

  if (st.view === 'rank') {
    const maxP = Math.max(...Object.values(rp), 1), maxN = Math.max(...Object.values(rn), 1), list = st.all ? order : order.slice(0, 20);
    const card = el('div', { class: 'card' }, el('div', { class: 'legend' }, el('span', { style: '--c:var(--pos)' }, 'выбрали «за»'), negId ? el('span', { style: '--c:var(--neg)' }, 'выбрали «против»') : ''));
    list.forEach(m => card.append(el('div', { class: 'hbar' },
      el('div', { class: 'name', style: 'cursor:pointer;color:var(--accent)', onclick: () => pick(m.id) }, m.name),
      el('div', { class: 'track' }, el('i', { style: `width:${rp[m.id] / maxP * 100}%;background:var(--pos)` })), el('div', { class: 'num', style: 'width:30px' }, rp[m.id]),
      negId ? [el('div', { class: 'track', style: 'max-width:30%' }, el('i', { style: `width:${rn[m.id] / maxN * 100}%;background:var(--neg)` })), el('div', { class: 'num', style: 'width:30px' }, rn[m.id])] : '')));
    if (order.length > 20) card.append(el('button', { class: 'link', style: 'margin-top:8px', onclick: () => { st.all = !st.all; redraw(); } }, st.all ? 'Показать только первых 20' : `Показать всех (${order.length})`));
    body.append(card);
  } else if (st.view === 'matrix') {
    let h = '<table class="hm"><tbody>';
    order.forEach(r => {
      h += `<tr><th data-id="${r.id}">${esc(r.name)}</th>`;
      order.forEach(t => {
        let cls = 'x';
        if (r.id !== t.id && done.has(r.id)) { const p = (P[r.id] || []).includes(t.id), n = (N[r.id] || []).includes(t.id); cls = p && n ? 'b' : p ? 'p' : n ? 'n' : ''; }
        h += `<td class="${cls}" title="${esc(r.name)} → ${esc(t.name)}"></td>`;
      });
      h += '</tr>';
    });
    const wrap = el('div', { class: 'hm-wrap', html: h + '</tbody></table>' });
    wrap.addEventListener('click', e => { const th = e.target.closest('th'); if (th) pick(+th.dataset.id); });
    body.append(el('div', { class: 'legend' }, el('span', { style: '--c:var(--pos)' }, 'выбрал «за»'), el('span', { style: '--c:var(--neg)' }, 'выбрал «против»'), el('span', { style: '--c:var(--warn)' }, 'и «за», и «против»'), el('span', { style: '--c:var(--line)' }, 'не отвечал(а)')),
      el('p', { class: 'muted small' }, 'Строка — кто отвечал, столбец — кого выбрали. Люди упорядочены по числу полученных выборов, наведите на клетку, чтобы увидеть имена.'), wrap);
  } else {
    const card = el('div', { class: 'card' });
    [...members].sort((a, b) => a.name.localeCompare(b.name, 'ru')).forEach(m => {
      card.append(el('div', { class: 'answer' },
        el('b', { style: 'cursor:pointer;color:var(--accent)', onclick: () => pick(m.id) }, m.name), ' ',
        !done.has(m.id) ? el('span', { class: 'chip' }, 'не проходил(а)') : el('div', {},
          el('div', {}, (P[m.id] || []).length ? chips((P[m.id] || []).map(t => nm[t]), 'pos') : el('span', { class: 'muted small' }, 'никого «за»')),
          negId ? el('div', {}, (N[m.id] || []).length ? chips((N[m.id] || []).map(t => nm[t]), 'neg') : el('span', { class: 'muted small' }, 'никого «против»')) : '')));
    });
    body.append(card);
  }
}

function personCard(ov, id, close) {
  const nm = Object.fromEntries(ov.members.map(m => [m.id, m.name]));
  const s = ov.stats.members[id], qs = ov.questions.filter(q => q.kind === 'permanent');
  const chosen = qid => (ov.answers[qid] && ov.answers[qid][id] || []).map(t => nm[t]);
  const chosenBy = qid => Object.entries(ov.answers[qid] || {}).filter(([, ts]) => ts.includes(id)).map(([m]) => nm[m]);
  const crit = { leisure: 'Досуг', organizing: 'Организаторские', teamwork: 'Совместная работа', trust: 'Доверие' };
  const rows = qs.map(q => el('tr', {}, el('td', {}, el('span', { class: 'chip ' + (q.polarity === '-' ? 'neg' : q.polarity === '+' ? 'pos' : '') }, q.polarity === '-' ? 'против' : q.polarity === '+' ? 'за' : 'интерес'), ' ', trunc(q.text, 60)),
    el('td', {}, chips(chosen(q.id), q.polarity === '-' ? 'neg' : 'pos')), el('td', {}, chips(chosenBy(q.id), q.polarity === '-' ? 'neg' : 'pos'))));
  const hist = ov.history[id] || [];
  return el('div', { class: 'card', style: 'border:2px solid var(--accent)' },
    el('div', { class: 'row-actions', style: 'justify-content:space-between' }, el('div', {}, el('h3', { style: 'font-size:22px' }, nm[id]), el('div', {}, statusChip(s.category, (ov.confirmed || {})[id], ov.categories), el('span', { class: 'muted small' }, ' ' + (CAT_HINT[s.category] || '')))),
      el('div', { class: 'row-actions' }, el('a', { class: 'btn', style: 'text-decoration:none', href: `#/analyst/personal/${ov.period.id}/${id}` }, 'Личный отчёт'), el('button', { onclick: close }, 'Закрыть карточку'))),
    el('div', { class: 'grid', style: 'margin:12px 0' }, metric(num(s.S), 'индекс статуса S'), metric(num(s.E), 'индекс экспансивности E'), metric(s.place, 'место по статусу'), metric(`${s.pos_total} / ${s.neg_total}`, 'выборов «за» / «против»')),
    el('div', { class: 'grid', style: 'margin:0 0 12px' }, el('div', {}, el('div', { class: 'muted small' }, 'Принимают (за − против)'), axis(s.pref_total || 0, '#1D9E75', '#E24B4A')), el('div', {}, el('div', { class: 'muted small' }, 'Замечают (за + против)'), axis(s.impact_total || 0, '#7F77DD', '#888780'))),
    el('div', { class: 'badge-row' }, Object.entries(s.categories || {}).map(([c, k]) => el('span', { class: 'small muted' }, `${crit[c] || c}: `, catChip(k, ov.categories)))),
    hist.length > 1 ? el('div', { style: 'max-width:520px' }, el('div', { class: 'chart-title' }, 'Статус S по исследованиям'), compareChart(hist, [['S', 'S', 'var(--accent)']])) : '',
    ov.submitted.includes(id) ? '' : el('p', { class: 'muted' }, 'Этот участник ещё не прошёл опрос: показаны только выборы, которые сделали о нём другие.'),
    el('div', { style: 'overflow:auto' }, el('table', { class: 't' }, el('thead', {}, el('tr', {}, ['Вопрос', 'Кого выбрал(а)', 'Кто выбрал(а) его/её'].map(h => el('th', {}, h)))), el('tbody', {}, rows))));
}

async function reportTab(body, st, loadOv, redraw) {
  const p = st.ov.period;
  const area = el('textarea', { rows: '22', style: 'font-family:inherit;line-height:1.5' });

  const rep0 = await api(`/analyst/report/${p.id}`);
  const save = async publish => {
    if (publish && !p.published && rep0.low_turnout && !confirm(`Опрос прошли только ${pct(rep0.participation, 0)} группы. Индексы занижены, а в отчёте будет пометка «низкая явка». Всё равно опубликовать?`)) return;
    try { await api(`/analyst/periods/${p.id}/report`, { method: 'PUT', body: { text: area.value, published: publish } }); toast(publish ? 'Отчёт опубликован' : 'Сохранено'); await loadOv(); redraw(); }
    catch (e) { toast(e.message, 'err'); }
  };
  body.append(el('div', { class: 'card' },
    el('h3', {}, 'Статус: ', p.published ? el('span', { class: 'ok' }, 'опубликован, виден всем') : el('span', { class: 'muted' }, 'не опубликован')),
    el('p', { class: 'muted small' }, 'Графики и индексы считаются автоматически и не редактируются. Вы пишете только текст разбора: нажмите «Сформировать черновик», система составит его по данным, затем поправьте и опубликуйте.'),
    p.status === 'open' ? el('p', { class: 'small', style: 'color:var(--warn)' }, 'Опрос ещё идёт. Публиковать лучше после закрытия, иначе цифры будут меняться.') : '',
    rep0.low_turnout ? el('p', { class: 'small', style: 'color:var(--warn)' }, `Низкая явка: ${pct(rep0.participation, 0)}. Индексы занижены, сравнивать с прошлыми опросами нельзя.`) : '',
    el('div', { class: 'row-actions' },
      el('a', { class: 'btn', href: `#/reports/${p.id}/preview`, style: 'text-decoration:none' }, 'Посмотреть, как увидят все'),
      p.published ? el('button', { onclick: () => save(false) }, 'Снять с публикации') : p.status === 'open' ? el('span', { class: 'muted small' }, 'Опубликовать можно после закрытия опроса, а закрыть его — когда пройдут все.') : el('button', { class: 'primary', onclick: () => save(true) }, 'Сохранить и опубликовать'))));
  area.value = rep0.text || '';
  body.append(el('div', { class: 'card' }, el('div', { class: 'row-actions', style: 'justify-content:space-between;margin-bottom:8px' }, el('h3', {}, 'Текст разбора'),
    el('button', { onclick: async () => { if (area.value.trim() && !confirm('Заменить текущий текст черновиком?')) return; area.value = (await api(`/analyst/periods/${p.id}/report/draft`, { method: 'POST' })).text; toast('Черновик сформирован'); } }, 'Сформировать черновик')),
    el('p', { class: 'muted small' }, 'Разметка: «## Заголовок», строки списка начинаются с «- », жирный текст в **двойных звёздочках**. Уровни сигналов: **Высокий.**, **Средний.**, **Низкий.**'),
    area, el('button', { class: 'primary', onclick: () => save(p.published) }, 'Сохранить текст')));
}

function surveysTab(body, st, reload) {
  const open = st.periods.filter(p => p.status === 'open');
  body.append(el('div', { class: 'grid two' }, periodForm(reload, open[0]), questionForm(open, reload)));
  if (open[0]) periodQuestions(open[0], reload).then(n => body.insertBefore(n, body.children[1] || null));
  body.append(section('Все опросы', null, el('div', { class: 'card' }, st.periods.length ? el('table', { class: 't' }, el('tbody', {}, [...st.periods].reverse().map(p => el('tr', {},
    el('td', {}, el('b', {}, p.title)), el('td', {}, p.status === 'open' ? el('span', { class: 'chip pos' }, 'идёт') : el('span', { class: 'chip' }, 'закрыт')),
    el('td', {}, p.status === 'open' ? el('button', { onclick: async () => { if (confirm(`Закрыть опрос «${p.title}»? Ответы больше нельзя будет менять.`)) { await api(`/analyst/periods/${p.id}/close`, { method: 'POST' }); toast('Опрос закрыт'); reload(); } } }, 'Закрыть') : ''))))) : el('span', { class: 'muted' }, 'Опросов пока нет.'))));
}

/* ============ Руководство ============ */
async function managePage(app) {
  const cur = await api('/survey/current').catch(() => null);
  app.append(hero('Панель руководства', 'Кто прошёл опрос, ответы на ваши вопросы и создание новых опросов. Кто кого выбрал в социометрии, руководство не видит.',
    noHrNotice(), cur && !cur.submitted ? el('a', { class: 'cta', href: '#/survey' }, 'Пройти опрос самому') : ''));
  const c = el('div', { class: 'wrap' });
  app.append(el('main', {}, c));
  const st = { periods: await api('/staff/periods'), tab: 'progress' };
  st.sel = (st.periods[st.periods.length - 1] || {}).id;
  const holder = el('div'); c.append(holder);
  const draw = async () => {
    holder.replaceChildren();
    if (st.periods.length) holder.append(periodSelect(st.periods, st.sel, id => { st.sel = id; draw(); }));
    holder.append(tabs([['progress', 'Кто прошёл'], ['custom', 'Ответы на ваши вопросы'], ['create', 'Новый опрос и вопросы']], st.tab, k => { st.tab = k; draw(); }));
    const body = el('div'); holder.append(body);
    try {
      if (st.tab === 'create') {
        const reload = async () => { st.periods = await api('/staff/periods'); st.sel = (st.periods[st.periods.length - 1] || {}).id; draw(); };
        const open = st.periods.filter(p => p.status === 'open');
        body.append(el('div', { class: 'grid two' }, periodForm(reload, open[0]), questionForm(open, reload)));
        if (open[0]) body.append(await periodQuestions(open[0], reload));
      } else if (!st.sel) body.append(el('div', { class: 'card muted' }, 'Опросов пока нет. Создайте первый на вкладке «Новый опрос и вопросы».'));
      else if (st.tab === 'progress') { const r = await api(`/management/completion/${st.sel}`); body.append(progressBlock(r.done.length, r.not_done)); }
      else body.append(el('p', { class: 'muted small' }, 'Показаны ответы из отправленных анкет. В вопросах «без имён» авторы скрыты, порядок ответов не совпадает с порядком отправки.'),
        customAnswersView(await api(`/management/custom-answers/${st.sel}`), false));
    } catch (e) { body.append(el('div', { class: 'err' }, e.message)); }
  };
  draw();
}


function personalTab(body, st) {
  const ov = st.ov, done = new Set(ov.submitted);
  const search = el('input', { type: 'text', placeholder: 'Поиск по имени' });
  const list = el('div', { class: 'card', style: 'padding:6px 10px' });
  const paint = () => {
    const q = search.value.trim().toLowerCase().replace(/ё/g, 'е');
    const rows = [...ov.members].sort((a, b) => a.name.localeCompare(b.name, 'ru')).filter(m => !q || m.name.toLowerCase().replace(/ё/g, 'е').includes(q));
    list.replaceChildren(el('table', { class: 't' }, el('thead', {}, el('tr', {}, ['Участник', 'Статус', 'Прошёл', ''].map(h => el('th', {}, h)))),
      el('tbody', {}, rows.map(m => el('tr', {}, el('td', {}, el('b', {}, m.name)), el('td', {}, catChip((ov.stats.members[m.id] || {}).category, ov.categories)),
        el('td', {}, done.has(m.id) ? el('span', { class: 'ok' }, '✓') : el('span', { class: 'muted' }, 'нет')),
        el('td', {}, el('a', { class: 'btn', style: 'text-decoration:none', href: `#/analyst/personal/${ov.period.id}/${m.id}` }, 'Открыть и скачать')))))));
  };
  search.addEventListener('input', paint);
  body.append(el('p', { class: 'muted small' }, `Личные отчёты всех участников опроса «${ov.period.title}». Откройте отчёт, сохраните его в PDF и отправьте человеку лично.`),
    ov.period.status === 'open' ? el('p', { class: 'small', style: 'color:var(--warn)' }, 'Опрос ещё идёт: цифры в отчётах будут меняться до закрытия.') : '',
    el('div', { class: 'toolbar' }, search), list);
  paint();
}
