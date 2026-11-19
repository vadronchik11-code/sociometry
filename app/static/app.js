/* Маршрутизация и верхнее меню. */
function renderChrome() {
  const path = (location.hash || '#/').replace(/^#/, '') || '/';
  const links = [['/', 'Сводка'], ['/reports', 'Групповые отчёты'], ['/personal', 'Личный отчёт'], ['/faq', 'FAQ']];
  if (takesSurvey()) links.push(['/survey', 'Опрос']);
  if (me && me.role === 'analyst') links.push(['/analyst', 'Аналитик']);
  if (me && me.role === 'management') links.push(['/manage', 'Руководство']);
  const menu = $('#menu'); menu.replaceChildren(); menu.classList.remove('open');
  links.forEach(([to, label]) => {
    const on = to === '/' ? path === '/' : path.startsWith(to);
    menu.append(el('a', { href: '#' + to, class: (on ? 'on ' : '') + (['/analyst', '/manage'].includes(to) ? 'staff' : '') }, label));
  });
  const user = $('#user'); user.replaceChildren();
  if (me) user.append(el('span', {}, me.full_name), el('button', { onclick: () => { store.clear(); me = null; location.hash = '#/'; renderChrome(); render(); } }, 'Выйти'));
  else user.append(el('a', { class: 'btn', href: '#/login' }, 'Войти'));
}

const TITLES = { '': 'Сводка', reports: 'Групповые отчёты', personal: 'Личный отчёт', faq: 'Вопросы и ответы', login: 'Вход', survey: 'Опрос', analyst: 'Аналитик', manage: 'Руководство' };

async function render() {
  renderChrome();
  const load = $('#loadbar'); load.className = ''; void load.offsetWidth; load.className = 'on';
  const app = $('#app'); app.replaceChildren();
  const parts = (location.hash || '#/').replace(/^#\//, '').split('/').filter(Boolean);
  document.title = `${TITLES[parts[0] || ''] || 'Социометрия'} · Социометрия`;
  window.scrollTo(0, 0);
  try {
    const [page, arg, flag] = parts;
    if (!page) await homePage(app);
    else if (page === 'reports' && arg) await reportPage(app, +arg, flag === 'preview');
    else if (page === 'reports') await reportsPage(app);
    else if (page === 'personal') await personalPage(app, arg ? +arg : null);
    else if (page === 'faq') faqPage(app);
    else if (page === 'login') loginPage(app);
    else if (page === 'survey') await surveyPage(app);
    else if (page === 'analyst' && arg === 'personal' && me && me.role === 'analyst') await analystPersonalPage(app, +flag, +parts[3]);
    else if (page === 'analyst' && me && me.role === 'analyst') await analystPage(app);
    else if (page === 'manage' && me && ['management', 'analyst'].includes(me.role)) await managePage(app);
    else if (['analyst', 'manage'].includes(page)) {
      app.append(hero('Нет доступа'), el('main', {}, el('div', { class: 'wrap' }, el('div', { class: 'card' },
        el('p', {}, page === 'analyst' ? 'Эта страница доступна только аналитику.' : 'Эта страница доступна руководству и аналитику.'),
        me ? el('a', { href: '#/' }, 'На главную') : el('a', { href: '#/login' }, 'Войти')))));
    }
    else { app.append(hero('Страница не найдена')); app.append(el('main', {}, el('div', { class: 'wrap' }, el('a', { href: '#/' }, 'На главную'))));  }
  } catch (e) {
    app.append(el('main', {}, el('div', { class: 'wrap' }, el('div', { class: 'card' }, el('h3', {}, 'Не получилось загрузить страницу'), el('p', { class: 'muted' }, e.message)))));
  } finally {
    load.className = 'done';
  }
}

window.addEventListener('hashchange', render);
$('#burger').addEventListener('click', () => { const m = $('#menu'); m.classList.toggle('open'); $('#burger').setAttribute('aria-expanded', m.classList.contains('open')); });
render();
