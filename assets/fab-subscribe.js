/**
 * Floating Subscribe button + popover (main site shared, bilingual).
 *
 * Auto-detects language from <html lang> attribute:
 *   - lang starts with "zh" → ZH dict
 *   - else → EN dict
 *
 * Per-page override (optional, set BEFORE loading this script):
 *   <script>
 *     window.fabSubscribe = {
 *       title: "Save the Date",       // popover header
 *       desc:  "Lorem ipsum...",      // description paragraph
 *       source: "pif12",              // hidden _source value sent to Formspree
 *       cta:    "Save the date →",    // submit button label
 *       hideRss: false,               // true to hide the RSS link block
 *       buttonLabel: "Subscribe",     // FAB chip label
 *     };
 *   </script>
 */
(function () {
  if (document.getElementById('fab-subscribe')) return; // already injected

  const lang = (document.documentElement.lang || 'en').toLowerCase();
  const isZh = lang.startsWith('zh');

  const DICT = isZh ? {
    buttonLabel: '別說我沒揪',
    title: '保持聯繫',
    desc: '訂閱搶先看中英雙語個人動態或活動邀請。保證無垃圾信，隨時取消。',
    cta: '訂閱 →',
    rssLabel: '老派更新：',
    rssAria: 'RSS',
    closeAria: '關閉',
    nameLabel: '姓名（可不填）',
    emailLabel: 'Email',
  } : {
    buttonLabel: 'Count me in',
    title: 'Stay Connected',
    desc: "Drop your email for bilingual (EN/中) personal thoughts & collab invites. No spam, cancel anytime.",
    cta: 'Subscribe →',
    rssLabel: 'Old-school updates:',
    rssAria: 'RSS',
    closeAria: 'Close',
    nameLabel: 'Name (optional)',
    emailLabel: 'Email',
  };

  const opts = (window.fabSubscribe || {});
  const buttonLabel = opts.buttonLabel || DICT.buttonLabel;
  const title       = opts.title       || DICT.title;
  const desc        = opts.desc        || DICT.desc;
  const source      = opts.source      || 'floating-button';
  const cta         = opts.cta         || DICT.cta;
  const hideRss     = !!opts.hideRss;

  function escape(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  const button = document.createElement('button');
  button.id = 'fab-subscribe';
  button.type = 'button';
  button.setAttribute('aria-label', title);
  button.setAttribute('aria-expanded', 'false');
  button.innerHTML = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
    <span>${escape(buttonLabel)}</span>
  `;

  const popover = document.createElement('div');
  popover.id = 'fab-popover';
  popover.setAttribute('role', 'dialog');
  popover.setAttribute('aria-labelledby', 'fab-popover-title');
  popover.innerHTML = `
    <button type="button" class="fab-close" aria-label="${escape(DICT.closeAria)}">×</button>
    <h3 id="fab-popover-title">${escape(title)}</h3>
    <p>${escape(desc)}</p>
    <form action="https://formspree.io/f/xgonbqgr" method="POST" target="_blank">
      <input type="text" name="name" placeholder="${escape(DICT.nameLabel)}" aria-label="${escape(DICT.nameLabel)}">
      <input type="email" name="email" placeholder="your@email.com" required aria-label="${escape(DICT.emailLabel)}">
      <input type="hidden" name="_source" value="${escape(source)}">
      <input type="hidden" name="_gotcha" style="display:none !important">
      <button type="submit">${escape(cta)}</button>
    </form>
    ${hideRss ? '' : `
    <div class="fab-rss">
      ${escape(DICT.rssLabel)}
      <a href="/3pwriting/feed.xml" target="_blank" rel="noopener noreferrer" aria-label="${escape(DICT.rssAria)}">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><path d="M4 11a9 9 0 0 1 9 9"/><path d="M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/></svg>
        RSS
      </a>
    </div>`}
  `;

  document.body.appendChild(button);
  document.body.appendChild(popover);

  const close = popover.querySelector('.fab-close');
  function setOpen(open) {
    popover.classList.toggle('open', open);
    button.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) popover.querySelector('input[type="email"]').focus();
  }
  button.addEventListener('click', e => { e.stopPropagation(); setOpen(!popover.classList.contains('open')); });
  close.addEventListener('click', () => setOpen(false));
  document.addEventListener('click', e => {
    if (!popover.classList.contains('open')) return;
    if (popover.contains(e.target) || button.contains(e.target)) return;
    setOpen(false);
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && popover.classList.contains('open')) setOpen(false);
  });
})();
