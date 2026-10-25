(() => {
  const html = document.documentElement;
  const langButton = document.querySelector('[data-language-toggle]');
  const textFields = document.querySelectorAll('[data-language-field]');
  const saved = localStorage.getItem('madar-language');
  let lang = saved === 'en' ? 'en' : (saved === 'ar' ? 'ar' : 'ar');

  function applyLanguage(next) {
    lang = next;
    html.lang = lang;
    html.dir = lang === 'ar' ? 'rtl' : 'ltr';
    document.querySelectorAll('[data-ar][data-en]').forEach((el) => {
      const value = el.dataset[lang];
      if (value === undefined) return;
      if (el.hasAttribute('data-html')) el.innerHTML = value;
      else el.textContent = value;
    });
    document.querySelectorAll('[data-placeholder-ar][data-placeholder-en]').forEach((el) => {
      el.placeholder = el.dataset[`placeholder${lang === 'ar' ? 'Ar' : 'En'}`];
    });
    document.querySelectorAll('option[data-ar][data-en]').forEach((el) => { el.textContent = el.dataset[lang]; });
    textFields.forEach((field) => { field.value = lang; });
    if (langButton) langButton.textContent = lang === 'ar' ? 'English' : 'العربية';
    localStorage.setItem('madar-language', lang);
  }
  if (langButton) langButton.addEventListener('click', () => applyLanguage(lang === 'ar' ? 'en' : 'ar'));
  applyLanguage(lang);

  const menuButton = document.querySelector('[data-menu-toggle]');
  const menu = document.querySelector('[data-menu]');
  if (menuButton && menu) {
    menuButton.addEventListener('click', () => {
      const open = menuButton.getAttribute('aria-expanded') === 'true';
      menuButton.setAttribute('aria-expanded', String(!open));
      menu.classList.toggle('is-open', !open);
    });
    menu.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => {
      menu.classList.remove('is-open'); menuButton.setAttribute('aria-expanded', 'false');
    }));
  }

  const revealEls = document.querySelectorAll('[data-reveal]');
  if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const observer = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); }
    }), { threshold: 0.12 });
    revealEls.forEach((el) => observer.observe(el));
  } else revealEls.forEach((el) => el.classList.add('is-visible'));

  const details = document.getElementById('details');
  const count = document.getElementById('details-count');
  if (details && count) {
    const updateCount = () => { count.textContent = `${details.value.length} / 2000`; };
    details.addEventListener('input', updateCount); updateCount();
  }
  const params = new URLSearchParams(window.location.search);
  const preselected = params.get('service');
  const service = document.getElementById('service');
  if (preselected && service && [...service.options].some((o) => o.value === preselected)) service.value = preselected;
})();
