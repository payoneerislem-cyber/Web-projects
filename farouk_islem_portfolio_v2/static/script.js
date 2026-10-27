(() => {
  const body = document.body;
  const lang = body?.dataset.lang || document.documentElement.lang || 'en';
  const menuButton = document.querySelector('.menu-toggle');
  const nav = document.querySelector('.nav-links');

  if (menuButton && nav) {
    const closeMenu = () => {
      nav.classList.remove('open');
      menuButton.setAttribute('aria-expanded', 'false');
      menuButton.setAttribute('aria-label', lang === 'ar' ? 'فتح القائمة' : 'Open menu');
    };
    menuButton.addEventListener('click', () => {
      const open = nav.classList.toggle('open');
      menuButton.setAttribute('aria-expanded', String(open));
      menuButton.setAttribute('aria-label', open ? (lang === 'ar' ? 'إغلاق القائمة' : 'Close menu') : (lang === 'ar' ? 'فتح القائمة' : 'Open menu'));
    });
    nav.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
    document.addEventListener('click', event => {
      if (!nav.contains(event.target) && !menuButton.contains(event.target)) closeMenu();
    });
  }

  document.querySelectorAll('.text-link[data-service]').forEach(link => link.addEventListener('click', () => {
    const subject = document.getElementById('subject');
    if (subject && !subject.value) subject.value = link.dataset.service;
  }));

  document.querySelectorAll('.language-switch').forEach(link => link.addEventListener('click', () => {
    // Preserve the visitor's current section when switching languages.
    try {
      const target = new URL(link.href, window.location.href);
      const nextPath = window.location.pathname + window.location.hash;
      target.searchParams.set('next', nextPath || '/');
      link.href = target.toString();
    } catch (_error) {
      // Keep the ordinary language switch if URL parsing is unavailable.
    }
  }));

  const themeButton = document.querySelector('[data-theme-toggle]');
  if (themeButton && body) {
    const updateThemeControl = () => {
      const light = body.dataset.theme === 'light';
      const label = light
        ? (lang === 'ar' ? 'التبديل إلى الوضع الداكن' : 'Switch to dark mode')
        : (lang === 'ar' ? 'التبديل إلى الوضع الفاتح' : 'Switch to light mode');
      themeButton.setAttribute('aria-label', label);
      themeButton.setAttribute('title', label);
      const icon = themeButton.querySelector('.theme-icon');
      if (icon) icon.textContent = light ? '◐' : '☼';
      const meta = document.querySelector('meta[name="color-scheme"]');
      if (meta) meta.content = light ? 'light' : 'dark';
      const themeMeta = document.querySelector('meta[name="theme-color"]');
      if (themeMeta) themeMeta.content = light ? '#f7f8fc' : '#0b0d12';
    };
    updateThemeControl();
    themeButton.addEventListener('click', () => {
      const next = body.dataset.theme === 'light' ? 'dark' : 'light';
      body.dataset.theme = next;
      const secure = window.location.protocol === 'https:' ? '; Secure' : '';
      document.cookie = `site_theme=${next}; Max-Age=31536000; Path=/; SameSite=Lax${secure}`;
      updateThemeControl();
    });
  }

  const message = document.getElementById('message');
  const count = document.getElementById('message-count');
  if (message && count) {
    const updateCount = () => { count.textContent = `${message.value.length} / 4000`; };
    message.addEventListener('input', updateCount);
    updateCount();
  }

  const feedbackComment = document.getElementById('feedback-comment');
  const feedbackCommentCount = document.getElementById('feedback-comment-count');
  if (feedbackComment && feedbackCommentCount) {
    const updateFeedbackCount = () => { feedbackCommentCount.textContent = `${feedbackComment.value.length} / 600`; };
    feedbackComment.addEventListener('input', updateFeedbackCount);
    updateFeedbackCount();
  }

  document.querySelectorAll('.rating-choice input[type="radio"]').forEach(input => {
    input.addEventListener('change', () => {
      document.querySelectorAll('.rating-choice').forEach(choice => {
        const radio = choice.querySelector('input');
        choice.classList.toggle('is-selected', Boolean(radio?.checked));
      });
    });
  });

  const projectGrid = document.querySelector('.projects-grid[data-initial-count]');
  const projectToggle = document.querySelector('[data-projects-toggle]');
  if (projectGrid && projectToggle) {
    const cards = Array.from(projectGrid.querySelectorAll('.project-card'));
    const initialCount = Number.parseInt(projectGrid.dataset.initialCount || '2', 10);
    if (cards.length > initialCount) {
      projectToggle.hidden = false;
      let expanded = false;
      const updateProjects = () => {
        cards.forEach((card, index) => {
          card.hidden = !expanded && index >= initialCount;
        });
        projectToggle.setAttribute('aria-expanded', String(expanded));
        projectToggle.innerHTML = expanded
          ? `${lang === 'ar' ? 'عرض مشاريع أقل' : 'Show fewer projects'} <span aria-hidden="true">↑</span>`
          : `${lang === 'ar' ? 'عرض المزيد من المشاريع' : 'Show more projects'} <span aria-hidden="true">↓</span>`;
      };
      updateProjects();
      projectToggle.addEventListener('click', () => {
        expanded = !expanded;
        updateProjects();
      });
    } else {
      projectToggle.hidden = true;
    }
  }

  // Reveal content as it enters the viewport. Content stays visible if motion is
  // disabled or IntersectionObserver is unavailable.
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reduceMotion && 'IntersectionObserver' in window) {
    const revealTargets = document.querySelectorAll(
      '.section-top, .service-card, .project-card, .process-grid article, .feedback-summary, .feedback-card, .feedback-empty, .feedback-form-wrap, .about-heading, .about-copy, .faq-list details, .contact-intro, .contact-form-wrap'
    );
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -36px 0px' });
    revealTargets.forEach((element, index) => {
      element.classList.add('scroll-reveal');
      element.style.setProperty('--reveal-delay', `${Math.min(index % 4, 3) * 70}ms`);
      revealObserver.observe(element);
    });
  }

  document.querySelectorAll('.toast button').forEach(button => button.addEventListener('click', () => button.closest('.toast')?.remove()));
  document.querySelectorAll('.faq-list details').forEach(item => item.addEventListener('toggle', () => {
    if (item.open) document.querySelectorAll('.faq-list details').forEach(other => { if (other !== item) other.open = false; });
  }));
})();
