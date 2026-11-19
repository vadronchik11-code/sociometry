/* Анкета участника: по одному вопросу на экране. */
const qNote = q => {
  if (q.kind === 'permanent') return 'Анонимно: кто кого выбрал, видит только аналитик. Руководство этого не узнает.';
  if (q.visibility === 'analyst') return 'Ответ увидит только аналитик. Руководство его не увидит.';
  if (q.anonymous) return 'Руководство увидит только ответы на этот вопрос, но не узнает, кто их дал. Обобщённые итоги без имён могут войти в общий отчёт.';
  return 'Этот вопрос увидит руководство, и оно узнает, кто на него ответил. Обобщённые итоги без имён могут войти в общий отчёт.';
};
const NO_HR = 'Результаты социометрии не используются для назначений, снятий и других решений о людях.';
const noteClass = q => q.kind === 'permanent' || q.visibility === 'analyst' ? 'pos' : q.anonymous ? 'warn' : 'neg';

async function surveyPage(app) {
  app.append(hero('Опрос'));
  const c = el('div', { class: 'wrap', style: 'max-width:820px' });
  app.append(el('main', {}, c));
  if (!me) return c.append(el('div', { class: 'card' }, el('a', { href: '#/login' }, 'Войдите'), ', чтобы пройти опрос.'));
  if (!takesSurvey()) return c.append(el('div', { class: 'card' }, 'Аналитик не входит в группу и опрос не проходит.'));
  let data;
  try { data = await api('/survey/current'); } catch (e) { return c.append(el('div', { class: 'card' }, e.message)); }
  $('.hero h1').textContent = data.period.title;
  if (data.submitted) return c.append(el('div', { class: 'card' }, el('h3', {}, 'Спасибо, ответы отправлены'),
    el('p', { class: 'muted' }, 'Когда опрос закроется и аналитик опубликует итоги, личный отчёт по нему появится на странице «Личный отчёт». Там же лежат отчёты по прошлым опросам.'),
    el('a', { class: 'btn', href: '#/personal', style: 'text-decoration:none' }, 'Открыть личные отчёты')));

  const qs = data.questions, total = qs.length;
  const ans = {};
  for (const [qid, a] of Object.entries(data.answers)) ans[qid] = { targets: new Set(a.targets), none: a.none, text: a.text || '' };
  const isDone = q => { const a = ans[q.id]; return !!a && (a.none || a.targets.size > 0 || (a.text || '').trim().length > 0); };
  let cur = Math.max(0, qs.findIndex(q => !isDone(q)));
  if (cur === -1) cur = 0;
  const names = {};
  try { (await api(`/members?question_id=${qs.find(q => q.answer_type !== 'text').id}`)).forEach(p => { names[p.id] = p.full_name; }); } catch {}

  const nav = el('div', { class: 'steps-nav' }), bar = el('div'), count = el('div', { class: 'muted small' });
  c.append(el('div', { class: 'sticky-bar' }, el('div', { class: 'bar' }, bar), count, nav));
  const stage = el('div'); c.append(stage);

  const drawNav = () => {
    const done = qs.filter(isDone).length;
    bar.style.width = (done / total * 100) + '%';
    count.textContent = cur < total ? `Вопрос ${cur + 1} из ${total} · отвечено ${done}` : `Отвечено ${done} из ${total}`;
    nav.replaceChildren(...qs.map((q, i) => el('button', { class: (i === cur ? 'cur ' : '') + (isDone(q) ? 'done' : ''), title: trunc2(q.text), onclick: () => go(i) }, i + 1)),
      el('button', { class: cur === total ? 'cur' : '', title: 'Проверить и отправить', onclick: () => go(total), style: 'width:auto;padding:0 12px;border-radius:999px' }, 'Итог'));
  };
  const trunc2 = s => s.length > 80 ? s.slice(0, 79) + '…' : s;
  const go = i => { cur = i; drawNav(); draw(); window.scrollTo({ top: 0, behavior: 'smooth' }); };

  const saveState = el('div', { class: 'saved' });
  const save = async (q, body) => {
    saveState.textContent = 'Сохраняем…';
    try { await api(`/survey/answers/${q.id}`, { method: 'PUT', body }); saveState.textContent = 'Сохранено ✓'; drawNav(); }
    catch (e) { saveState.textContent = ''; toast(e.message, 'err'); throw e; }
  };

  const draw = async () => {
    stage.replaceChildren();
    if (cur >= total) return drawReview();
    const q = qs[cur];
    const card = el('div', { class: 'card q-card' });
    stage.append(card);
    if (q.kind === 'permanent' && (cur === 0 || qs[cur - 1].kind !== 'permanent'))
      stage.insertBefore(el('div', { class: 'hint' }, el('b', {}, 'Дальше постоянные вопросы социометрии. '), 'Они анонимны: кто кого выбрал, видит только независимый аналитик. Можно выбрать сколько угодно людей или «Никто».', el('div', { style: 'margin-top:6px' }, NO_HR)), card);
    card.append(el('div', { class: 'qhead' }, el('span', { class: 'qnum' }, cur + 1), el('h3', {}, q.text)),
      el('div', { class: 'badge-row' }, el('span', { class: 'chip ' + noteClass(q) }, qNote(q))));
    saveState.textContent = '';
    if (q.answer_type === 'text') {
      const box = el('textarea', { rows: '5', placeholder: 'Ваш ответ' });
      box.value = (ans[q.id] && ans[q.id].text) || '';
      let t;
      box.addEventListener('input', () => {
        clearTimeout(t);
        t = setTimeout(async () => {
          await save(q, { targets: [], none: false, text: box.value });
          ans[q.id] = { targets: new Set(), none: false, text: box.value }; drawNav();
        }, 600);
      });
      card.append(box, el('p', { class: 'muted small' }, 'Этот вопрос можно пропустить.'));
    } else {
      const a = ans[q.id] || { targets: new Set(), none: false };
      const picked = el('div', { class: 'picked' });
      const search = el('input', { type: 'text', placeholder: 'Начните вводить фамилию или имя' });
      const list = el('div', { class: 'list' });
      const none = el('input', { type: 'checkbox' });
      none.checked = !!a.none;
      const drawPicked = () => {
        const cur = ans[q.id];
        picked.replaceChildren(cur && cur.targets.size
          ? [el('span', { class: 'muted small' }, `Вы выбрали (${cur.targets.size}): `), ...[...cur.targets].map(id => el('button', { class: 'chip btn ' + (q.polarity === '-' ? 'neg' : 'pos'), title: 'Убрать', onclick: () => toggle({ id, state: 'chosen' }) }, (names[id] || '…') + ' ×'))]
          : el('span', { class: 'muted small' }, cur && cur.none ? 'Вы выбрали «Никто».' : 'Пока никого не выбрано.'));
      };
      const refresh = async () => {
        const people = await api(`/members?question_id=${q.id}&q=${encodeURIComponent(search.value)}`);
        people.forEach(p => { names[p.id] = p.full_name; });
        list.replaceChildren(...people.map(p => {
          const cls = ['row']; let tag = '';
          if (p.state === 'chosen') { cls.push('chosen', q.polarity === '-' ? 'neg' : 'pos'); tag = '✓'; }
          if (p.state === 'grey') { cls.push('grey'); tag = `выбран «${q.polarity === '-' ? 'за' : 'против'}» в вопросе ${qs.findIndex(x => x.id === q.pair_with) + 1}`; }
          if (p.id === armed) { cls.push('armed'); tag = 'Это противоречит прошлому ответу. Нажмите ещё раз, чтобы всё равно выбрать'; }
          return el('div', { class: cls.join(' '), onclick: () => toggle(p) }, el('span', {}, p.full_name), el('small', {}, tag));
        }));
        if (!people.length) list.append(el('p', { class: 'muted small' }, 'Никого не нашлось.'));
        drawPicked();
      };
      let armed = null;
      const toggle = async p => {
        const st = ans[q.id] || (ans[q.id] = { targets: new Set(), none: false });
        if (st.targets.has(p.id)) st.targets.delete(p.id);
        else {
          if (p.state === 'grey' && armed !== p.id) { armed = p.id; return refresh(); }
          armed = null;
          st.targets.add(p.id); st.none = false; none.checked = false;
        }
        try { await save(q, { targets: [...st.targets], none: st.none }); } catch { return; }
        if (!st.targets.size && !st.none) delete ans[q.id];
        drawNav(); refresh();
      };
      none.addEventListener('change', async () => {
        if (none.checked) ans[q.id] = { targets: new Set(), none: true }; else delete ans[q.id];
        try { await save(q, { targets: [], none: none.checked }); } catch { return; }
        drawNav(); refresh();
      });
      let t; search.addEventListener('input', () => { clearTimeout(t); t = setTimeout(refresh, 200); });
      card.append(picked, search, list, el('label', { class: 'none', style: 'color:var(--text)' }, none, 'Никто'));
      if (q.polarity === '-') card.append(el('p', { class: 'muted small' }, 'Серым отмечены люди, которых вы выбрали «за» в парном вопросе. Выбрать их здесь можно, но это противоречит прошлому ответу.'));
      await refresh();
      setTimeout(() => search.focus(), 50);
    }
    const required = q.kind === 'permanent';
    card.append(saveState, el('div', { class: 'nav-buttons' },
      el('button', { onclick: () => go(Math.max(0, cur - 1)), disabled: cur === 0 }, '← Назад'),
      el('button', { class: 'primary', onclick: () => {
        if (required && !isDone(q)) return toast('Выберите людей или отметьте «Никто»', 'err');
        go(cur + 1);
      } }, cur === total - 1 ? 'К проверке →' : 'Далее →')));
  };

  const drawReview = () => {
    const missing = qs.filter(q => q.kind === 'permanent' && !isDone(q));
    const conflicts = [];
    qs.filter(q => q.polarity === '-' && q.pair_with).forEach(q => {
      const neg = ans[q.id], pos = ans[q.pair_with];
      if (neg && pos) [...neg.targets].filter(t => pos.targets.has(t)).forEach(t => conflicts.push({ q, t }));
    });
    if (missing.length) stage.append(el('div', { class: 'hint', style: 'background:var(--neg-bg);color:var(--neg)' },
      `Нет ответа на обязательные вопросы: ${missing.map(q => qs.indexOf(q) + 1).join(', ')}. Выберите людей или «Никто».`));
    if (conflicts.length) stage.append(el('div', { class: 'hint', style: 'background:var(--warn-bg);color:var(--warn)' },
      el('b', {}, 'Противоречия. '), 'Эти люди отмечены и «за», и «против» в паре вопросов: ',
      conflicts.map(({ q, t }) => el('button', { class: 'chip btn warn', onclick: () => go(qs.indexOf(q)) }, `${names[t] || '…'} · вопрос ${qs.indexOf(q) + 1}`)),
      ' Отправить так можно, но лучше проверить.'));
    const card = el('div', { class: 'card' }, el('h3', {}, 'Проверьте ответы'),
      el('p', { class: 'muted small' }, 'Нажмите на вопрос, чтобы вернуться к нему. После отправки изменить ответы будет нельзя.'));
    qs.forEach((q, i) => {
      const a = ans[q.id];
      const summary = !a ? el('span', { class: q.kind === 'permanent' ? 'down' : 'muted' }, q.kind === 'permanent' ? 'нет ответа' : 'пропущен')
        : a.none ? 'никто' : a.text ? `«${trunc2(a.text)}»` : chips([...a.targets].map(t => names[t] || '…'), q.polarity === '-' ? 'neg' : 'pos');
      card.append(el('div', { class: 'answer', style: 'cursor:pointer', onclick: () => go(i) }, el('div', { class: 'who' }, `${i + 1}. ${trunc2(q.text)}`), summary));
    });
    stage.append(card);
    stage.append(el('div', { class: 'nav-buttons' }, el('button', { onclick: () => go(total - 1) }, '← Назад'),
      el('button', { class: 'primary', onclick: async () => {
        if (missing.length) { toast(`Сначала ответьте на вопрос ${qs.indexOf(missing[0]) + 1}`, 'err'); return go(qs.indexOf(missing[0])); }
        if (!confirm('Отправить ответы? После отправки изменить их будет нельзя.')) return;
        try { await api('/survey/submit', { method: 'POST' }); toast('Ответы отправлены, спасибо!'); render(); } catch (e) { toast(e.message, 'err'); }
      } }, 'Отправить ответы')));
  };

  drawNav(); draw();
}
