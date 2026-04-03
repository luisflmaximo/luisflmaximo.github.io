/* ================================================================
   LUIS MAXIMO - PORTFOLIO - main.js
   ================================================================ */

(function () {
  'use strict';

  const nav = document.getElementById('nav');
  if (nav) {
    const onScroll = () => nav.classList.toggle('nav--scrolled', window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  const burger = document.getElementById('navBurger');
  const navLinks = document.getElementById('navLinks');
  if (nav && burger && navLinks) {
    burger.addEventListener('click', () => {
      const open = navLinks.classList.toggle('nav__links--open');
      burger.classList.toggle('nav__burger--open', open);
      burger.setAttribute('aria-expanded', open);
    });

    navLinks.querySelectorAll('.nav__link').forEach((link) => {
      link.addEventListener('click', () => {
        navLinks.classList.remove('nav__links--open');
        burger.classList.remove('nav__burger--open');
        burger.setAttribute('aria-expanded', 'false');
      });
    });

    document.addEventListener('click', (event) => {
      if (!nav.contains(event.target)) {
        navLinks.classList.remove('nav__links--open');
        burger.classList.remove('nav__burger--open');
        burger.setAttribute('aria-expanded', 'false');
      }
    });
  }

  const profilePhoto = document.getElementById('profilePhoto');
  if (profilePhoto) {
    let count = 0;
    let timer = null;

    const handleTap = () => {
      count += 1;

      if (count === 7) {
        count = 0;
        clearTimeout(timer);
        sessionStorage.setItem('secretUnlocked', '1');
        showSecretTab();
        window.location.href = new URL('../secret/', window.location.href).toString();
        return;
      }

      clearTimeout(timer);
      timer = setTimeout(() => {
        count = 0;
      }, 3000);
    };

    profilePhoto.addEventListener('click', handleTap);
  }

  function showSecretTab() {
    document.querySelectorAll('.nav__secret-link').forEach((element) => {
      element.style.display = '';
    });
  }

  const hasInternalReferrer = (() => {
    if (!document.referrer) return false;

    try {
      return new URL(document.referrer).origin === window.location.origin;
    } catch (_) {
      return false;
    }
  })();

  if (!hasInternalReferrer) {
    sessionStorage.removeItem('secretUnlocked');
  }

  if (sessionStorage.getItem('secretUnlocked') === '1') {
    showSecretTab();
  }

  const reveals = document.querySelectorAll('.reveal');
  if (reveals.length && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('revealed');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08, rootMargin: '0px 0px -32px 0px' }
    );

    reveals.forEach((element) => observer.observe(element));
  } else {
    reveals.forEach((element) => element.classList.add('revealed'));
  }

  const skillBars = document.querySelectorAll('.cv-skill-bar__fill');
  if (skillBars.length && 'IntersectionObserver' in window) {
    const barObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const element = entry.target;
            const target = element.dataset.width || '0%';

            setTimeout(() => {
              element.style.width = target;
            }, 100);

            barObserver.unobserve(element);
          }
        });
      },
      { threshold: 0.5 }
    );

    skillBars.forEach((bar) => {
      bar.style.width = '0%';
      barObserver.observe(bar);
    });
  }

  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav__link').forEach((link) => {
    const href = link.getAttribute('href');
    if (href && currentPath === href) {
      link.classList.add('nav__link--active');
    }
  });

  const linkedinSection = document.querySelector('[data-linkedin-section]');
  const linkedinProfilePanels = Array.from(document.querySelectorAll('[data-linkedin-profile-panel]'));
  const linkedinFrames = Array.from(document.querySelectorAll('.linkedin-post-card__frame'));
  const linkedinPostLoadButtons = Array.from(document.querySelectorAll('[data-linkedin-post-load]'));
  const LINKEDIN_BADGE_SCRIPT_SRC = 'https://platform.linkedin.com/badges/js/profile.js';

  if (linkedinFrames.length) {
    const setLinkedinFrameHeight = () => {
      const viewportW = window.innerWidth || document.documentElement.clientWidth;
      const viewportH = window.innerHeight || document.documentElement.clientHeight;

      linkedinFrames.forEach((frame) => {
        const frameWidth = frame.getBoundingClientRect().width || 320;
        let targetHeight;

        if (viewportW <= 480) {
          targetHeight = Math.max(680, Math.min(880, Math.round(viewportH * 0.84)));
        } else if (viewportW <= 768) {
          targetHeight = Math.max(640, Math.min(820, Math.round(viewportH * 0.8)));
        } else {
          targetHeight = 614;
        }

        if (frameWidth < 340) {
          targetHeight += 28;
        }

        frame.style.height = `${targetHeight}px`;
        frame.style.minHeight = `${targetHeight}px`;
      });
    };

    let resizeTimer;
    const onViewportChange = () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(setLinkedinFrameHeight, 120);
    };

    setLinkedinFrameHeight();
    window.addEventListener('resize', onViewportChange, { passive: true });
    window.addEventListener('orientationchange', onViewportChange, { passive: true });
  }

  if (linkedinPostLoadButtons.length) {
    const loadLinkedinFrame = (frame, card) => {
      if (!frame || frame.getAttribute('src') || !frame.dataset.src) return;
      frame.setAttribute('src', frame.dataset.src);
      if (card) {
        card.classList.add('linkedin-post-card--loaded');
      }
    };

    linkedinPostLoadButtons.forEach((button) => {
      button.addEventListener('click', () => {
        const card = button.closest('.linkedin-post-card');
        const frame = card ? card.querySelector('.linkedin-post-card__frame') : null;
        loadLinkedinFrame(frame, card);
      });
    });
  }

  if (linkedinFrames.length || linkedinProfilePanels.length) {
    const keepOnlyActiveLinkedinProfileEmbed = () => {
      if (!linkedinProfilePanels.length) return;

      const useMobileEmbed = !!(
        window.matchMedia &&
        window.matchMedia('(max-width: 768px)').matches
      );

      linkedinProfilePanels.forEach((panel) => {
        const desktopEmbed = panel.querySelector('.linkedin-profile-embed--desktop');
        const mobileEmbed = panel.querySelector('.linkedin-profile-embed--mobile');
        const inactiveEmbed = useMobileEmbed ? desktopEmbed : mobileEmbed;

        if (inactiveEmbed && inactiveEmbed.parentNode) {
          inactiveEmbed.parentNode.removeChild(inactiveEmbed);
        }
      });
    };

    let linkedinBadgeScriptPromise = null;
    const loadLinkedinBadgeScript = () => {
      if (!linkedinProfilePanels.length) {
        return Promise.resolve();
      }

      if (linkedinBadgeScriptPromise) {
        return linkedinBadgeScriptPromise;
      }

      linkedinBadgeScriptPromise = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = LINKEDIN_BADGE_SCRIPT_SRC;
        script.async = true;
        script.defer = true;
        script.dataset.linkedinBadgeScript = 'true';
        script.addEventListener('load', resolve, { once: true });
        script.addEventListener(
          'error',
          () => {
            reject(new Error('LinkedIn badge script failed to load'));
          },
          { once: true }
        );
        document.body.appendChild(script);
      });

      return linkedinBadgeScriptPromise;
    };

    let linkedinEmbedsLoaded = false;
    const loadLinkedinEmbeds = () => {
      if (linkedinEmbedsLoaded) return;
      linkedinEmbedsLoaded = true;

      linkedinFrames.forEach((frame) => {
        if (frame.dataset.autoload === 'manual') {
          return;
        }

        if (frame.dataset.src && !frame.getAttribute('src')) {
          frame.setAttribute('src', frame.dataset.src);
        }
      });

      if (!linkedinProfilePanels.length) {
        return;
      }

      keepOnlyActiveLinkedinProfileEmbed();

      loadLinkedinBadgeScript()
        .catch(() => {});
    };

    if (linkedinSection && 'IntersectionObserver' in window) {
      const linkedinObserver = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              loadLinkedinEmbeds();
              linkedinObserver.disconnect();
            }
          });
        },
        { rootMargin: '240px 0px' }
      );

      linkedinObserver.observe(linkedinSection);
    } else if (document.readyState === 'complete') {
      loadLinkedinEmbeds();
    } else {
      window.addEventListener('load', loadLinkedinEmbeds, { once: true });
    }
  }
})();
