/* Публичные страницы: сводка, групповые отчёты, личный отчёт, FAQ, вход. */
const SOCIO = ['teamwork', 'organizing', 'trust', 'leisure'];

async function homePage(app) {
  const sum = await api('/public/summary');
  const L = sum.labels, latest = sum.latest;
  app.append(hero('Сводка многолетних данных',
    'Здесь собраны результаты социометрии нашей команды: как люди связаны друг с другом, как это меняется со временем и что из этого следует. Опрос проходят все члены группы, и считается он, только когда пройдут все.',
    el('div', {}, noHrNotice(), sum.survey_open && takesSurvey()
      ? el('a', { class: 'cta', href: '#/survey' }, 'Пройти опрос')
      : sum.survey_open && !me ? el('a', { class: 'cta', href: '#/login' }, 'Войти и пройти опрос') : '',
      latest ? el('div', { class: 'meta' }, `Последнее исследование: ${latest.period.title}`) : '')));
  const wrap = el('main', {}, el('div', { class: 'wrap' }));
  const c = wrap.firstChild;
  app.append(wrap);

  if (!latest) {
    c.append(el('div', { class: 'card' }, 'Опубликованных отчётов пока нет. Они появятся после первого закрытого опроса.'));
  } else {
    const yv = Math.max(...Object.values(latest.criteria).map(x => x.Y || 0));
    c.append(section('Ключевые факты', `По данным исследования «${latest.period.title}»`,
      el('div', { class: 'grid' },
        metric(latest.n, 'человек в группе'),
        metric(pct(latest.participation, 0), `прошли опрос (${latest.respondents} чел.)`),
        metric(pct(latest.criteria.teamwork.Gg), 'сплочённость по совместной работе'),
        metric(pct(yv, 2), 'максимальная конфликтность')),
      el('p', {}, el('a', { href: `#/reports/${latest.period.id}` }, 'Открыть полный отчёт →'))));
  }

  c.append(section('Как проходит исследование', 'Опрос занимает около 10 минут и проходит несколько раз в год.',
    el('ol', { class: 'steps' },
      el('li', {}, el('b', {}, 'Вы отвечаете на анкету. '), 'Сначала несколько вопросов от руководства, потом 9 постоянных вопросов: кого вы позвали бы на праздник, с кем хотели бы работать, к кому обратились бы за советом.'),
      el('li', {}, el('b', {}, 'Ответы анонимны. '), 'Руководство не видит, кто кого выбрал. Исходные ответы видит только независимый аналитик.'),
      el('li', {}, el('b', {}, 'Всё считается автоматически. '), 'Графики и индексы строятся сами по ответам, их нельзя подправить вручную. Текст разбора пишет аналитик.'),
      el('li', {}, el('b', {}, 'Результаты публикуются. '), 'Общий отчёт доступен всем без имён, а личный отчёт получает только сам участник.'))));

  if (sum.series.length) {
    const dyn = el('div', { class: 'grid two' });
    const defs = [
      ['Gg', 'Сплочённость (Gg)', 'Доля возможных пар людей, которые выбрали друг друга. Чем выше, тем теснее связи.', SOCIO],
      ['Ag', 'Эмоциональная экспансивность (Ag)', 'Сколько людей в среднем отмечает каждый участник. Показывает общительность группы.', SOCIO],
      ['Y', 'Конфликтность (Y)', 'Доля пар, где люди взаимно отвергли друг друга. Обычно очень мала.', SOCIO],
      ['U', 'Референтность (U)', 'Доля пар, где люди взаимно интересуются ответами друг друга. Показывает связь внутри ядра.', ['referent']],
    ];
    for (const [m, title, hint, keys] of defs) {
      dyn.append(el('div', { class: 'card' }, el('div', { class: 'chart-title' }, title), el('div', { class: 'muted small' }, hint),
        lineChart(sum.series, keys, m, L), keys.length > 1 ? legend(keys, L) : ''));
    }
    c.append(section('Многолетняя динамика',
      sum.series.length > 1 ? 'Как менялись показатели от исследования к исследованию.' : 'Пока есть одно исследование, динамика появится после следующего.', dyn));
  }

  c.append(section('Как читать показатели', null, el('div', { class: 'grid' },
    el('div', { class: 'card' }, el('h3', {}, 'Gg: сплочённость'), el('div', { class: 'muted small' }, 'Доля пар, где оба выбрали друг друга. 100% недостижимо: в реальной группе это единицы процентов по досугу и до трети по совместной работе.')),
    el('div', { class: 'card' }, el('h3', {}, 'Ag: экспансивность'), el('div', { class: 'muted small' }, 'Сколько людей в среднем отмечает каждый. Показывает, насколько группа открыта к общению.')),
    el('div', { class: 'card' }, el('h3', {}, 'Y: конфликтность'), el('div', { class: 'muted small' }, 'Доля пар с взаимным отвержением. Значение выше 1–2% стоит обсудить с группой.')),
    el('div', { class: 'card' }, el('h3', {}, 'S: статус человека'), el('div', { class: 'muted small' }, 'Сколько выборов получил участник относительно возможного максимума. В отчётах показывается диапазонами.')))));
}

async function reportsPage(app) {
  const list = await api('/public/periods');
  app.append(hero('Групповые отчёты', 'Итоги каждого исследования: цифры, графики и разбор от аналитика.'));
  const c = el('div', { class: 'wrap' });
  app.append(el('main', {}, c));
  if (!list.length) return c.append(el('div', { class: 'card' }, 'Опубликованных отчётов пока нет.'));
  const years = [...new Set(list.map(p => (p.date || '').slice(0, 4)))];
  for (const y of years) {
    c.append(section(y, null, el('div', { class: 'grid' }, list.filter(p => (p.date || '').slice(0, 4) === y).map(p =>
      el('a', { href: `#/reports/${p.id}`, style: 'text-decoration:none;color:inherit' }, el('div', { class: 'card', style: 'margin:0;height:100%' },
        el('h3', {}, p.title), el('div', { class: 'muted small' }, `Прошли ${p.respondents} из ${p.n}`),
        el('div', { class: 'big', style: 'margin-top:10px;color:var(--accent)' }, pct(p.gg_work)), el('div', { class: 'muted small' }, 'сплочённость по совместной работе')))))));
  }
}

async function reportPage(app, id, preview) {
  const [r, sum] = await Promise.all([api(`${preview ? '/analyst' : '/public'}/report/${id}`), api('/public/summary')]);
  const prevS = sum.series.filter(s => s.id !== r.period.id && (s.date || '') < (r.period.date || '')).pop();
  const L = r.labels, cr = r.criteria;
  app.append(hero(r.period.title, null, el('div', { class: 'meta' },
    preview && !r.published ? 'ЧЕРНОВИК: отчёт ещё не опубликован. ' : '', el('a', { href: '#/reports', class: 'no-print' }, '← Все отчёты'))));
  const c = el('div', { class: 'wrap' });
  app.append(el('main', {}, c));

  c.append(el('div', { class: 'toolbar no-print' }, printButton()));
  if (r.low_turnout) c.append(el('div', { class: 'hint', style: 'background:var(--warn-bg);color:var(--warn)' }, el('b', {}, 'Низкая явка. '),
    `Опрос прошли ${pct(r.participation, 0)} группы. Связи тех, кто не ответил, в расчёт не попали, поэтому индексы занижены и сравнивать их с другими опросами нельзя.`));
  const yv = Math.max(...Object.values(cr).map(x => x.Y || 0));
  const yprev = prevS ? Math.max(...Object.values(prevS.criteria).map(x => x.Y || 0)) : null;
  const ym = metric(pct(yv, 2), 'максимальная конфликтность', yprev === null ? null : yv - yprev);
  ym.querySelectorAll('.up,.down').forEach(e => e.classList.toggle('up') & e.classList.toggle('down'));
  c.append(section('Коротко', null, el('div', { class: 'grid' },
    metric(r.n, 'человек в группе'),
    metric(pct(r.participation, 0), `прошли опрос (${r.respondents} чел.)`, prevS ? r.participation - prevS.respondents / prevS.n : null),
    metric(pct(cr.teamwork.Gg), 'сплочённость по совместной работе', prevS && prevS.criteria.teamwork ? cr.teamwork.Gg - prevS.criteria.teamwork.Gg : null),
    ym)));

  c.append(section('Разбор', 'Текст аналитика по итогам исследования.', renderText(r.text)));

  const rows = SOCIO.filter(k => cr[k]).map(k => {
    const x = cr[k], pv = prevS && prevS.criteria[k] ? prevS.criteria[k].Gg : null, d = pv === null ? null : x.Gg - pv;
    return el('tr', {}, el('td', {}, el('span', { class: 'chip', style: `background:${CRIT_COLOR[k]};color:#fff` }, L[k])),
      el('td', {}, el('b', {}, pct(x.Gg)), d === null ? '' : el('span', { class: d >= 0 ? 'up small' : 'down small' }, `  ${d >= 0 ? '▲' : '▼'} ${Math.abs(d * 100).toFixed(1).replace('.', ',')}`)),
      el('td', {}, pct(x.Y, 2)), el('td', {}, pct(x.Ag)), el('td', {}, pct(x.reciprocity, 0)));
  });
  c.append(section('Показатели по критериям', 'Сплочённость, конфликтность и общительность для каждого критерия.',
    el('div', { class: 'card', style: 'overflow:auto' }, el('table', { class: 't' },
      el('thead', {}, el('tr', {}, ['Критерий', 'Сплочённость Gg', 'Конфликтность Y', 'Экспансивность Ag', 'Выборов взаимно'].map(h => el('th', {}, h)))),
      el('tbody', {}, rows))),
    cr.referent ? el('p', { class: 'muted small' }, `Референтность U (взаимный интерес к ответам друг друга): ${pct(cr.referent.U, 1)}.`) : ''));

  const socs = el('div', { class: 'grid two' });
  for (const k of SOCIO) if (r.sociograms[k]) socs.append(el('div', { class: 'card' }, el('div', { class: 'chart-title' }, L[k]), sociogram(r.sociograms[k])));
  c.append(section('Социограммы', 'Каждый кружок — участник, размер кружка — сколько выборов он получил по этому критерию, линия — взаимный выбор двух людей. Имена не показываются.', socs));

  if (r.structure) {
    const keys = ['star', 'preferred', 'accepted', 'controversial', 'rejected', 'isolated'], mx = Math.max(...keys.map(k => r.structure[k] || 0), 1);
    c.append(section('Структура группы', 'Сколько людей в каждой статусной группе. Статус считается по выборам «за» и «против» во всех критериях относительно среднего. Имена не раскрываются.',
      el('div', { class: 'card' }, keys.map(k => el('div', { class: 'hbar' }, el('div', { class: 'name', title: CAT_HINT[k] }, catChip(k, r.categories)),
        el('div', { class: 'track' }, el('i', { style: `width:${(r.structure[k] || 0) / mx * 100}%;background:var(--accent)` })), el('div', { class: 'num' }, fewText(r.structure[k])))),
        el('p', { class: 'muted small' }, keys.map(k => `${r.categories[k]} — ${CAT_HINT[k].toLowerCase()}.`).join(' ')))));
  }
  if (r.microgroups && Object.keys(r.microgroups).length) {
    c.append(section('Микрогруппы', 'Компании, в которых люди взаимно выбирают друг друга. Найдены автоматически по взаимным выборам, имена не раскрываются.',
      el('div', { class: 'grid two' }, Object.entries(r.microgroups).map(([k, g]) => el('div', { class: 'card crit-card', style: `--c:${CRIT_COLOR[k]}` },
        el('h3', {}, g.title),
        g.sizes.length ? el('p', { style: 'margin:4px 0' }, `${g.sizes.length} ${g.sizes.length % 10 === 1 && g.sizes.length % 100 !== 11 ? 'компания' : [2, 3, 4].includes(g.sizes.length % 10) && ![12, 13, 14].includes(g.sizes.length % 100) ? 'компании' : 'компаний'}: `,
          g.sizes.map(n => el('span', { class: 'chip' }, `${n} чел.`))) : el('p', { class: 'muted' }, 'Взаимных компаний не найдено.'),
        el('div', { class: 'muted small' }, g.outside >= 3 ? `Без взаимных выборов: ${g.outside} чел.` : 'Почти у всех есть хотя бы один взаимный выбор.'))))));
  }
  c.append(section('Распределение статуса', 'Сколько участников получили то или иное значение индекса статуса S. Чем правее, тем чаще человека выбирали.',
    el('div', { class: 'card' }, histogram(r.status_hist),
      el('p', { class: 'muted small' }, `Среднее значение S по группе: ${num(r.s_mean)}. В «ядре» группы ${r.core} чел., без положительных выборов: ${r.isolated === null ? 'меньше 3 чел.' : r.isolated + ' чел.'}`))));
}

function faqPage(app) {
  app.append(hero('Вопросы и ответы'));
  const q = (t, a) => el('details', { class: 'card' }, el('summary', { style: 'cursor:pointer;font-weight:600' }, t), el('p', { class: 'muted' }, a));
  app.append(el('main', {}, el('div', { class: 'wrap' },
    q('Повлияют ли мои ответы на чьё-то положение в студсовете?', 'Результаты социометрии не используются для назначений, снятий и других решений о людях. Социометрия нужна, чтобы группе было лучше работать вместе.'),
    q('Почему опрос должны пройти все?', 'Если кто-то не ответил, его выборы выпадают из картины, и индексы искажаются. Поэтому опрос считается, только когда его прошли все члены группы. Если человек ушёл из студсовета, аналитик исключает его из опроса.'),
    q('Что такое социометрия?', 'Метод, который показывает, как люди в группе относятся друг к другу: кого выбирают для общения, работы и поддержки, а кого — нет. Опрос проводится по методике Морено.'),
    q('Кто видит мои ответы?', 'Только аналитик, который не входит в руководство. Руководство видит лишь список, кто прошёл опрос, и ответы на свои частные вопросы, если они именные.'),
    q('Кто увидит мой ответ на вопрос от руководства?', 'Под каждым вопросом написано, кто прочитает ответ. Бывает три варианта: руководство увидит ответ и ваше имя; руководство увидит только ответ, но не узнает, кто его дал; ответ увидит только аналитик. Вопросы социометрии (кого вы выбираете) руководство не видит никогда.'),
    q('Почему нельзя выбрать одного человека и «за», и «против»?', 'Такой ответ противоречив и портит картину. В паре вопросов выбранные ранее люди выделены серым. Выбрать их всё равно можно, но сайт предупредит об этом, а аналитик увидит пометку.'),
    q('Можно ли выбрать «Никто» или сразу многих?', 'Да. Лимита нет: отмечайте столько людей, сколько честно считаете нужным, или «Никто». Важна только искренность ответа.'),
    q('Почему иногда отчёт помечен «низкая явка»?', 'Если опрос прошли меньше 70% группы, связи тех, кто не ответил, не попадают в расчёт, и индексы получаются заниженными. Такие опросы нельзя сравнивать с другими: на графиках динамики они отмечены пустыми кружками.'),
    q('Как узнать свои результаты?', 'После закрытия опроса откройте вкладку «Личный отчёт». Свои выборы показываются точно, а число людей, выбравших вас, диапазоном, чтобы по нему нельзя было вычислить чужие ответы. Взаимные выборы скрыты полностью.'),
    q('Насколько результатам можно верить?', 'Метод субъективен: руководство может выбираться чаще, а отрицательные выборы часто занижаются. Отчёт — повод для разговора, а не оценка личности.'))));
}

function loginPage(app) {
  app.append(hero('Вход'));
  const name = el('input', { type: 'text', placeholder: 'Фамилия Имя' });
  const mail = el('input', { type: 'email', placeholder: 'name@example.com', autocomplete: 'email' });
  const pass = el('input', { type: 'password', placeholder: 'Только для аналитика и руководства', autocomplete: 'current-password' });
  const err = el('div', { class: 'err' });
  const go = async () => {
    try {
      me = await api('/register', { method: 'POST', body: { full_name: name.value, email: mail.value, password: pass.value || null } });
      store.set(me);
      location.hash = me.role === 'analyst' ? '#/analyst' : me.role === 'management' ? '#/manage' : '#/survey';
      renderChrome();
    } catch (e) { err.textContent = e.message; }
  };
  const form = el('form', { class: 'card', onsubmit: e => { e.preventDefault(); go(); } },
    el('p', { class: 'muted' }, 'Введите ФИО и почту. Если вы уже входили, используйте ту же почту: ФИО тогда не меняется. Участникам пароль не нужен.'),
    el('label', {}, 'ФИО', name), el('label', {}, 'Почта', mail), el('label', {}, 'Пароль сотрудника', pass), err,
    el('button', { class: 'primary', type: 'submit' }, 'Продолжить'));
  app.append(el('main', {}, el('div', { class: 'wrap', style: 'max-width:520px' }, form)));
}

/* Личный отчёт: первая страница — об отчёте, без личных данных; дальше результаты. Общий для участника и аналитика. */
const pdfName = (r, name) => `${(r.period.date || '').replace('-', ' ')} ${name}`.trim();

/* Личный отчёт в вёрстке прошлых PDF: листы A4, рамки, крупные цифры, лист на каждый критерий. */
const DOC_ORDER = [['teamwork', 'Совместная работа'], ['organizing', 'Организаторские способности'], ['trust', 'Доверие'], ['leisure', 'Досуг'], ['referent', 'Референтометрия']];
const avgTxt = v => v.toFixed(1).replace('.', ',').replace(',0', '');

function docSheet(page, ...kids) {
  return el('div', { class: 'sheet' }, el('div', { class: 'sheet-body' }, kids), el('div', { class: 'box sheet-foot' }, page));
}
const docBox = (...kids) => el('div', { class: 'box' }, kids);
const docTitle = (text, extra) => el('div', { class: 'box doc-title' }, el('span', {}, text), extra ? el('span', { class: 'doc-ver' }, extra) : '');
function docStat(value, label, avg, hidden) {
  return el('div', { class: 'box stat' }, hidden ? el('div', { class: 'stat-hidden', title: 'Скрыто для сохранения анонимности' }) : el('div', { class: 'stat-v' }, value),
    el('div', { class: 'stat-l' }, label), avg !== undefined ? el('div', { class: 'stat-a' }, avg) : '');
}

function personalReportView(r, name) {
  const doc = el('div', { class: 'report-doc' });
  const byQ = (crit, pol) => r.rows.find(x => x.criterion === crit && x.polarity === pol);
  const lvl = c => r.criteria.find(x => x.criterion === c);
  // страницы: 1 — об отчёте, 2 — участник и итоги, 3–7 — критерии, 8 — интерпретация
  const pages = { cover: 1, summary: 2, interp: 3 + DOC_ORDER.length };

  // 1. Об отчёте — без личных данных
  doc.append(docSheet(1,
    el('div', { class: 'box' }, el('div', { class: 'doc-h1' }, 'ПЕРСОНАЛЬНЫЙ ОТЧЁТ'), el('div', {}, 'по социометрическому исследованию'),
      el('div', { class: 'tri small-tri' },
        el('div', { class: 'box mini' }, el('div', {}, (r.period.date || '').split('-').reverse().join(' ') || r.period.title), el('div', { class: 'stat-l' }, 'месяц и год')),
        el('div', { class: 'box mini' }, el('div', {}, r.n), el('div', { class: 'stat-l' }, 'кол-во участников')),
        el('div', { class: 'box mini' }, el('div', {}, r.k), el('div', { class: 'stat-l' }, 'кол-во критериев')))),
    docBox(el('div', { class: 'doc-h2' }, 'Об отчёте'),
      el('p', {}, 'Представленные данные обработаны по методу социометрии Дж. Морено и являются численной оценкой участника по всем заданным критериям. Следует учитывать, что картина не является абсолютно точной, так как подвержена искажениям из-за субъективности мнений участников группы и прочих факторов.'),
      el('p', {}, 'Данные, касающиеся взаимных выборов, скрыты там, где по ним можно было бы понять, кто именно ответил взаимностью (например, если вы выбрали трёх человек и все трое выбрали вас).'),
      el('div', { class: 'doc-h2', style: 'margin-top:14px' }, 'Пояснение терминов, используемых в отчёте:'),
      el('div', { class: 'terms' },
        el('div', { class: 'term-t' }, 'Индекс социометрического статуса (S)'), el('div', {}, 'Показатель, определяющий место индивида в коллективе на основе отданных ему выборов: и «за», и «против», и интереса к его ответам. Показывает, насколько человека замечают.'),
        el('div', { class: 'term-t' }, 'Индекс эмоциональной экспансивности (E)'), el('div', {}, 'Число выборов (положительных и отрицательных), сделанных участником в отношении других членов группы. Характеризует потребность личности в общении.'),
        el('div', { class: 'term-t' }, 'Уровень по критерию'), el('div', {}, 'Какую долю группы участник опережает по выборам «за»: от «пока мало выборов» (меньше 10%) до «один из лидеров группы» (90% и больше).'))),
    docBox(el('div', { class: 'doc-h2' }, 'Содержание'),
      el('div', { class: 'toc' }, el('span', {}, 'Сколько людей выбрали вас'), el('span', {}, `с. ${pages.summary}`),
        DOC_ORDER.map(([c, t], i) => [el('span', {}, `Критерий ${i + 1}: ${t}`), el('span', {}, `с. ${3 + i}`)]),
        el('span', {}, 'Интерпретация результатов'), el('span', {}, `с. ${pages.interp}–${pages.interp + 1}`)))));

  // 2. Участник и итоговые показатели: «N из 59» вместо индексов
  const prof = r.profile;
  const bar = blk => {
    const W = 100, x = v => Math.max(0, Math.min(W, v / Math.max(r.out_of, 1) * W));
    return el('div', { class: 'nbar', title: `вы: ${blk.received}, в среднем: ${avgTxt(blk.avg)}` },
      el('div', { class: 'nbar-band', style: `left:${x(blk.p25)}%;width:${Math.max(x(blk.p75) - x(blk.p25), 1)}%` }),
      el('div', { class: 'nbar-avg', style: `left:${x(blk.avg)}%` }),
      el('div', { class: 'nbar-you', style: `left:${x(blk.received)}%` }));
  };
  const word = blk => blk.received > blk.avg * 1.1 ? 'чаще среднего' : blk.received < blk.avg * 0.9 ? 'реже среднего' : 'как у большинства';
  const nBlock = blk => el('div', { class: 'box stat compact' },
    el('div', { class: 'stat-v' }, blk.received, el('span', { class: 'stat-of' }, ` из ${r.out_of}`)),
    el('div', { class: 'stat-l' }, blk.label),
    bar(blk),
    el('div', { class: 'stat-a' }, `в среднем по группе: ${avgTxt(blk.avg)} · ${word(blk)}`));
  const negs = r.blocks.filter(b => b.neg !== undefined);
  doc.append(docSheet(2,
    el('div', { class: 'box' }, el('div', { class: 'doc-name' }, name), el('div', {}, 'участник группы, для которого сформирован отчёт')),
    el('div', { class: 'box doc-headline' }, r.headline),
    docTitle('Сколько людей выбрали вас'),
    el('div', { class: 'tri' }, r.blocks.slice(0, 3).map(nBlock)),
    el('div', { class: 'tri' }, r.blocks.slice(3, 5).map(nBlock),
      el('div', { class: 'box stat compact' }, el('div', { class: 'stat-v' }, r.above, el('span', { class: 'stat-of' }, ` из ${r.total}`)),
        el('div', { class: 'stat-l' }, 'вопросов, где вас выбирают чаще среднего по группе'))),
    el('div', { class: 'box doc-legend' }, el('span', { class: 'lg' }, el('i', { class: 'nbar-you static' }), ' вы'),
      el('span', { class: 'lg' }, el('i', { class: 'nbar-avg static' }), ' в среднем по группе'),
      el('span', { class: 'lg' }, el('i', { class: 'nbar-band static' }), ' обычный диапазон (средняя половина группы)'),
      el('span', {}, `Шкала от 0 до ${r.out_of} человек.`)),
    negs.length ? el('div', { class: 'box doc-neg' }, el('b', {}, 'Отметки «не хотел бы»: '),
      negs.map(b => `${b.short} ${b.neg}`).join(', '),
      ` (в среднем по группе ${avgTxt(negs.reduce((a, b) => a + b.neg_avg, 0) / negs.length)}). Это ответы на конкретные вопросы, а не оценка вас.`) : '',
    docBox(el('div', { class: 'doc-h2' }, prof.title), el('p', { style: 'margin:6px 0 0' }, prof.text)),
    el('div', { class: 'doc-spec' }, 'Для специалистов: индекс статуса S ', num(r.specialist.S), ' (в среднем ', num(r.specialist.S_group),
      '), индекс экспансивности E ', num(r.specialist.E), ' (в среднем ', num(r.specialist.E_group), '), место по S ', r.specialist.place_range,
      '. S и E — доли от ', 5 * r.out_of, ' возможных выборов; S складывает выборы «за», «против» и интерес к ответам, поэтому это не оценка отношения к вам.')));

  // 3–7. Критерии
  DOC_ORDER.forEach(([c, title], i) => {
    const blocks = [docTitle(`Критерий ${i + 1}: ${title}`)];
    for (const pol of c === 'referent' ? [null] : ['+', '-']) {
      const q = byQ(c, pol);
      if (!q) continue;
      blocks.push(docBox(el('div', {}, 'в вопросе:'), el('div', { class: 'doc-q' }, q.text)),
        el('div', { class: 'tri' },
          docStat(q.given, 'число людей, которых участник отметил сам', `в среднем по группе: ${avgTxt(q.group_avg)}`),
          docStat(q.received, 'число людей, которые отметили участника', `в среднем по группе: ${avgTxt(q.group_avg)}`),
          q.mutual === null
            ? docStat('', 'число получившихся взаимных отметок', 'скрыто: по этому числу можно понять, кто именно ответил взаимностью', true)
            : docStat(q.mutual, 'число получившихся взаимных отметок', `в среднем по группе: ${avgTxt(q.group_avg_mutual)}`)));
    }
    const L = lvl(c);
    if (L) blocks.push(el('div', { class: 'box doc-level' }, el('span', {}, 'Уровень по критерию: ', el('b', {}, L.level_title)),
      el('span', {}, `чаще, чем ${L.percentile}% группы`)));
    doc.append(docSheet(3 + i, blocks));
  });

  // 8–9. Интерпретация: смысловые блоки на двух листах
  const block = x => el('div', { class: 'interp-block' }, el('div', { class: 'interp-h' }, x.title), x.text.split('\n').map(t => el('p', {}, t)));
  const first = r.interpretation.slice(0, 4), rest = r.interpretation.slice(4);
  doc.append(docSheet(pages.interp, docTitle('Интерпретация результатов', 'ver 2.0'), el('div', { class: 'box doc-interp' }, first.map(block))));
  doc.append(docSheet(pages.interp + 1, docTitle('Интерпретация результатов (продолжение)'),
    el('div', { class: 'box doc-interp' }, rest.map(block),
      r.history.length > 1 ? el('div', { class: 'interp-block' }, el('div', { class: 'interp-h' }, 'Сколько человек хотели работать с вами, по опросам'),
        el('div', { style: 'max-width:520px' }, compareChart(r.history, [['teamwork', 'Вы', '#111'], ['teamwork_avg', 'В среднем по группе', '#999']]))) : '',
      el('p', { class: 'doc-note' }, 'Объяснение составлено автоматически по числам с предыдущих страниц и описывает текущее мнение членов коллектива об участнике, а не его личные качества. Из-за субъективности социометрического метода отчёт служит удовлетворению интереса и не является окончательной оценкой личности.'))));
  return doc;
}

async function personalPage(app, id) {
  app.append(hero('Личный отчёт', 'Ваши результаты исследования. Их видите только вы.'));
  const c = el('div', { class: 'wrap' });
  app.append(el('main', {}, c));
  if (!me) return c.append(el('div', { class: 'card' }, 'Чтобы увидеть личный отчёт, ', el('a', { href: '#/login' }, 'войдите'), ' с той же почтой, с которой проходили опрос.'));
  if (!takesSurvey()) return c.append(el('div', { class: 'card' }, 'Личные отчёты участников аналитик открывает в своей панели: вкладка «Личные отчёты».'));
  const list = await api('/me/reports');
  if (!list.length) return c.append(el('div', { class: 'card' }, el('h3', {}, 'Пока нет готовых отчётов'), el('p', { class: 'muted' }, 'Личный отчёт появляется после того, как опрос, в котором вы участвовали, закроют и аналитик опубликует итоги.')));
  const cur = id || list[0].id;
  const pick = el('select', { onchange: () => { location.hash = `#/personal/${pick.value}`; } }, list.map(p => el('option', { value: p.id }, p.title)));
  pick.value = cur;
  const r = await api(`/me/report/${cur}`);
  $('.hero h1').textContent = `Личный отчёт · ${r.period.title}`;
  document.title = pdfName(r, me.full_name);
  $('.hero').classList.add('no-print');
  c.append(el('div', { class: 'toolbar no-print' }, el('label', { style: 'min-width:260px' }, 'Исследование', pick), printButton()));
  c.append(personalReportView(r, me.full_name));
}

async function analystPersonalPage(app, pid, mid) {
  const r = await api(`/analyst/personal/${pid}/${mid}`);
  app.append(hero(r.member.name, `Личный отчёт · ${r.period.title}`, el('div', { class: 'meta no-print' }, el('a', { href: '#/analyst' }, '← К панели аналитика'))));
  const c = el('div', { class: 'wrap' });
  app.append(el('main', {}, c));
  document.title = pdfName(r, r.member.name);
  $('.hero').classList.add('no-print');
  c.append(el('div', { class: 'hint no-print' }, 'Нажмите «Скачать PDF», в окне печати выберите «Сохранить как PDF». Имя файла уже подставлено: «', document.title, '». Отправьте файл участнику лично.',
    r.participated ? '' : el('div', { style: 'margin-top:6px;color:var(--warn)' }, 'Этот человек не прошёл опрос: в отчёте только выборы, сделанные о нём другими.')));
  c.append(el('div', { class: 'toolbar no-print' }, printButton()));
  c.append(personalReportView(r, r.member.name));
}
