(() => {
  const root = document.documentElement;
  const langButton = document.querySelector('[data-language-toggle]');
  const languageFields = document.querySelectorAll('[data-language-field]');
  let lang = localStorage.getItem('noor-language') === 'en' ? 'en' : 'ar';
  function applyLanguage(next) {
    lang = next; root.lang = lang; root.dir = lang === 'ar' ? 'rtl' : 'ltr';
    document.querySelectorAll('[data-ar][data-en]').forEach((el) => {
      if (el.dataset[lang] === undefined) return;
      if (el.hasAttribute('data-html')) el.innerHTML = el.dataset[lang];
      else el.textContent = el.dataset[lang];
    });
    document.querySelectorAll('option[data-ar][data-en]').forEach((el) => { el.textContent = el.dataset[lang]; });
    languageFields.forEach((el) => { el.value = lang; });
    if (langButton) langButton.textContent = lang === 'ar' ? 'English' : 'العربية';
    localStorage.setItem('noor-language', lang);
  }
  langButton?.addEventListener('click', () => applyLanguage(lang === 'ar' ? 'en' : 'ar'));
  applyLanguage(lang);

  const menuButton = document.querySelector('[data-menu-toggle]');
  const menu = document.querySelector('[data-menu]');
  if (menuButton && menu) {
    menuButton.addEventListener('click', () => {
      const open = menuButton.getAttribute('aria-expanded') === 'true';
      menuButton.setAttribute('aria-expanded', String(!open)); menu.classList.toggle('is-open', !open);
    });
    menu.querySelectorAll('a').forEach((a) => a.addEventListener('click', () => {
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

  const bookingForm = document.querySelector('[data-booking-form]');
  if (bookingForm) {
    const service = document.getElementById('service_id');
    const date = document.getElementById('appointment_date');
    const staff = document.getElementById('staff_preference');
    const slots = document.querySelector('[data-slot-select]');
    const help = document.getElementById('slot-help');
    const loader = document.querySelector('[data-slot-loader]');
    const translations = {
      ar: { choose: 'اختر التاريخ والخدمة أولًا.', loading: 'نراجع المواعيد...', empty: 'لا توجد أوقات متاحة في هذا اليوم.', error: 'تعذر تحميل المواعيد. حاول مرة أخرى.', pick: 'اختر الوقت المتاح' },
      en: { choose: 'Choose a service and date first.', loading: 'Checking availability...', empty: 'No times are available on this date.', error: 'Could not load availability. Try again.', pick: 'Choose an available time' },
    };
    let currentRequest = 0;
    async function loadSlots() {
      const langNow = root.lang === 'en' ? 'en' : 'ar';
      const t = translations[langNow];
      slots.replaceChildren(new Option(t.choose, ''));
      if (help) help.textContent = t.choose;
      if (!service.value || !date.value) return;
      const requestId = ++currentRequest;
      if (loader) loader.hidden = false;
      if (help) help.textContent = t.loading;
      try {
        const url = new URL(bookingForm.dataset.slotsUrl, window.location.origin);
        url.searchParams.set('service_id', service.value); url.searchParams.set('date', date.value); url.searchParams.set('staff_preference', staff.value || 'any');
        const response = await fetch(url.toString(), { headers: { Accept: 'application/json' } });
        if (!response.ok) throw new Error('availability request failed');
        const data = await response.json();
        if (requestId !== currentRequest) return;
        slots.replaceChildren(new Option(t.pick, ''));
        for (const item of data.slots) {
          const option = new Option(langNow === 'ar' ? item.label_ar : item.label_en, item.value);
          slots.add(option);
        }
        if (help) help.textContent = data.slots.length ? `${data.slots.length} ${langNow === 'ar' ? 'أوقات متاحة' : 'available times'}` : t.empty;
      } catch (_error) {
        if (help) help.textContent = t.error;
      } finally {
        if (requestId === currentRequest && loader) loader.hidden = true;
      }
    }
    [service, date, staff].forEach((el) => el.addEventListener('change', loadSlots));
    langButton?.addEventListener('click', () => { if (service.value && date.value) loadSlots(); });
    if (service.value && date.value) loadSlots();
    document.querySelectorAll('[data-service-link]').forEach((link) => link.addEventListener('click', () => {
      service.value = link.dataset.serviceLink;
      setTimeout(() => { date.focus({ preventScroll: true }); loadSlots(); }, 50);
    }));
    document.querySelectorAll('[data-staff-link]').forEach((link) => link.addEventListener('click', () => {
      staff.value = link.dataset.staffLink; setTimeout(() => loadSlots(), 50);
    }));
  }
})();
