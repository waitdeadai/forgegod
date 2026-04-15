/**
 * Smoothrevenue — Navigation Controller
 * Handles: sticky scroll effect, mobile menu, language toggle, active section, contact form
 */
(function () {
  'use strict';

  // ============================================================
  // State
  // ============================================================
  let currentLang = 'en';
  let isMenuOpen = false;
  let isFormSubmitting = false;

  // ============================================================
  // Translations (loaded from i18n JSON files)
  // ============================================================
  let translations = { en: {}, es: {} };

  async function loadTranslations() {
    try {
      const [enRes, esRes] = await Promise.all([
        fetch('i18n_en.json'),
        fetch('i18n_es.json'),
      ]);
      const enData = await enRes.json();
      const esData = await esRes.json();
      translations = {
        en: enData.en || enData,
        es: esData.es || esData,
      };
    } catch (e) {
      console.warn('Failed to load i18n files, falling back to inline:', e);
      translations = {
        en: { 'lang.es': 'ES', 'lang.en': 'EN' },
        es: { 'lang.es': 'ES', 'lang.en': 'EN' },
      };
    }
  }

  // ============================================================
  // DOM Elements
  // ============================================================
  const nav = document.getElementById('nav');
  const langToggle = document.getElementById('langToggle');
  const hamburger = document.getElementById('hamburger');
  const overlay = document.getElementById('navOverlay');
  const overlayClose = document.getElementById('overlayClose');
  const navLinks = document.querySelectorAll('.nav__link, .nav__overlay-link');
  const leadForm = document.getElementById('leadForm');
  const formSuccess = document.getElementById('formSuccess');

  // ============================================================
  // Sticky Nav on Scroll
  // ============================================================
  function handleScroll() {
    const scrollY = window.scrollY;
    if (scrollY > 20) {
      nav.classList.add('nav--scrolled');
    } else {
      nav.classList.remove('nav--scrolled');
    }
  }

  // ============================================================
  // Active Section Highlighting
  // ============================================================
  const sections = document.querySelectorAll('section[id]');

  function updateActiveLink() {
    const scrollY = window.scrollY + 120;
    let currentSectionId = null;

    sections.forEach((section) => {
      const sectionTop = section.offsetTop;
      const sectionHeight = section.offsetHeight;
      const sectionId = section.getAttribute('id');

      if (scrollY >= sectionTop && scrollY < sectionTop + sectionHeight) {
        currentSectionId = sectionId;
      }
    });

    // Remove active from all links
    document.querySelectorAll('.nav__link').forEach((link) => {
      link.classList.remove('nav__link--active');
    });
    document.querySelectorAll('.nav__overlay-link').forEach((link) => {
      link.classList.remove('nav__link--active');
      link.classList.remove('nav__overlay-link--active');
    });

    // Add active to matching link(s)
    if (currentSectionId) {
      document.querySelectorAll(
        `.nav__link[href="#${currentSectionId}"]`
      ).forEach((activeLink) => {
        activeLink.classList.add('nav__link--active');
      });
      document.querySelectorAll(
        `.nav__overlay-link[href="#${currentSectionId}"]`
      ).forEach((activeLink) => {
        activeLink.classList.add('nav__overlay-link--active');
      });
    }
  }

  // ============================================================
  // Mobile Menu
  // ============================================================
  function openMenu() {
    isMenuOpen = true;
    overlay.classList.add('nav__overlay--open');
    overlay.setAttribute('aria-hidden', 'false');
    hamburger.setAttribute('aria-expanded', 'true');
    hamburger.classList.add('hamburger--active');
    document.body.style.overflow = 'hidden';
    overlayClose.focus();
  }

  function closeMenu() {
    isMenuOpen = false;
    overlay.classList.remove('nav__overlay--open');
    overlay.setAttribute('aria-hidden', 'true');
    hamburger.setAttribute('aria-expanded', 'false');
    hamburger.classList.remove('hamburger--active');
    document.body.style.overflow = '';
  }

  function toggleMenu() {
    if (isMenuOpen) {
      closeMenu();
    } else {
      openMenu();
    }
  }

  // ============================================================
  // Language Toggle
  // ============================================================
  function toggleLanguage() {
    currentLang = currentLang === 'en' ? 'es' : 'en';
    document.documentElement.lang = currentLang;
    applyTranslations();
  }

  function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      if (translations[currentLang] && translations[currentLang][key]) {
        el.textContent = translations[currentLang][key];
      }
    });

    // Update toggle button text
    const toggleSpan = langToggle ? langToggle.querySelector('span') : null;
    if (toggleSpan) {
      toggleSpan.textContent = currentLang === 'en' ? 'ES' : 'EN';
    }

    // Update html lang attribute
    document.documentElement.lang = currentLang;

    // Update placeholder text
    applyPlaceholderTranslations();
  }

  // ============================================================
  // Contact Form Handler
  // ============================================================
  function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  function showFieldError(field, messageKey) {
    if (!field) return;
    const errorSpan = field.parentElement.querySelector('.form-error');
    if (errorSpan) {
      errorSpan.textContent = getTranslation(messageKey, 'Required field');
      errorSpan.classList.add('form-error--visible');
    }
    field.classList.add('input-error');
  }

  function clearFieldError(field) {
    if (!field) return;
    const errorSpan = field.parentElement.querySelector('.form-error');
    if (errorSpan) {
      errorSpan.textContent = '';
      errorSpan.classList.remove('form-error--visible');
    }
    field.classList.remove('input-error');
  }

  function clearAllErrors() {
    document.querySelectorAll('.form-error').forEach((el) => {
      el.textContent = '';
      el.classList.remove('form-error--visible');
    });
    document.querySelectorAll('.input-error').forEach((el) => {
      el.classList.remove('input-error');
    });
  }

  function validateForm(form) {
    clearAllErrors();
    let isValid = true;

    // Name validation
    const nameField = form.querySelector('#name');
    if (!nameField || !nameField.value.trim()) {
      showFieldError(nameField, 'contact.form.required');
      isValid = false;
    }

    // Email validation
    const emailField = form.querySelector('#email');
    if (!emailField || !emailField.value.trim()) {
      showFieldError(emailField, 'contact.form.required');
      isValid = false;
    } else if (!isValidEmail(emailField.value.trim())) {
      showFieldError(emailField, 'contact.form.invalidEmail');
      isValid = false;
    }

    // Message validation (minimum 20 characters)
    const messageField = form.querySelector('#message');
    const minMessageLength = 20;
    if (!messageField || !messageField.value.trim()) {
      showFieldError(messageField, 'contact.form.required');
      isValid = false;
    } else if (messageField.value.trim().length < minMessageLength) {
      showFieldError(messageField, 'contact.form.messageTooShort');
      isValid = false;
    }

    return isValid;
  }

  function getTranslation(key, fallback) {
    return (translations[currentLang] && translations[currentLang][key])
      || (translations['en'] && translations['en'][key])
      || fallback
      || key;
  }

  function handleFormSubmit(event) {
    // Guard: prevent double-submit
    if (isFormSubmitting || !leadForm) return;

    event.preventDefault();
    clearAllErrors();

    if (!validateForm(leadForm)) {
      return;
    }

    isFormSubmitting = true;
    const submitBtn = leadForm.querySelector('button[type="submit"]');
    const btnText = submitBtn ? submitBtn.querySelector('.btn-text') : null;
    const originalText = btnText ? btnText.textContent : '';

    // Show loading state
    if (btnText) {
      btnText.textContent = getTranslation('contact.form.submitting', 'Submitting...');
    }
    if (submitBtn) {
      submitBtn.disabled = true;
    }

    // Simulate form submission (replace with actual API call)
    const formData = new FormData(leadForm);
    const data = Object.fromEntries(formData.entries());

    // Simulate network delay
    setTimeout(() => {
      // Show success message
      if (formSuccess) {
        formSuccess.hidden = false;
        const successText = formSuccess.querySelector('p');
        if (successText) {
          successText.textContent = getTranslation('contact.form.success', "Thank you! We'll review your submission and respond within 24 hours.");
        }
      }

      // Reset form
      leadForm.reset();
      isFormSubmitting = false;

      // Reset button
      if (btnText) {
        btnText.textContent = originalText;
      }
      if (submitBtn) {
        submitBtn.disabled = false;
      }

      // Apply translations to placeholders again after reset
      applyPlaceholderTranslations();

      // Hide success message after 5 seconds
      setTimeout(() => {
        if (formSuccess) {
          formSuccess.hidden = true;
        }
      }, 5000);
    }, 1000);
  }

  function applyPlaceholderTranslations() {
    document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
      const key = el.getAttribute('data-i18n-placeholder');
      if (translations[currentLang] && translations[currentLang][key]) {
        el.placeholder = translations[currentLang][key];
      }
    });
  }

  function initContactForm() {
    if (!leadForm) return;

    leadForm.addEventListener('submit', handleFormSubmit);

    // Real-time validation on blur
    const fields = ['name', 'email', 'message'];
    fields.forEach((fieldId) => {
      const field = leadForm.querySelector(`#${fieldId}`);
      if (field) {
        field.addEventListener('blur', () => {
          // Only validate if field has been touched
          if (field.value.trim()) {
            clearFieldError(field);

            if (fieldId === 'email' && !isValidEmail(field.value.trim())) {
              showFieldError(field, 'contact.form.invalidEmail');
            } else if (fieldId === 'message' && field.value.trim().length < 20) {
              showFieldError(field, 'contact.form.messageTooShort');
            }
          }
        });
      }
    });
  }

  // ============================================================
  // Scroll-Triggered Animations (Methodology Timeline)
  // ============================================================
  function initScrollAnimations() {
    const animatedElements = document.querySelectorAll('[data-animate]');

    if (!animatedElements.length) return;

    const observerOptions = {
      root: null,
      rootMargin: '0px 0px -80px 0px',
      threshold: 0.1,
    };

    const animationObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          animationObserver.unobserve(entry.target);
        }
      });
    }, observerOptions);

    animatedElements.forEach((el) => {
      animationObserver.observe(el);
    });
  }

  // ============================================================
  // Keyboard Navigation
  // ============================================================
  function handleKeyboard(e) {
    // Close menu on Escape
    if (e.key === 'Escape' && isMenuOpen) {
      closeMenu();
      hamburger.focus();
    }
  }

  // ============================================================
  // Event Listeners
  // ============================================================
  function initEventListeners() {
    // Scroll events
    window.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('scroll', updateActiveLink, { passive: true });

    // Mobile menu
    if (hamburger) hamburger.addEventListener('click', toggleMenu);
    if (overlayClose) overlayClose.addEventListener('click', closeMenu);

    // Close menu when clicking overlay links
    if (overlay) {
      overlay.querySelectorAll('a').forEach((link) => {
        link.addEventListener('click', closeMenu);
      });
    }

    // Close menu on resize to desktop
    window.addEventListener('resize', () => {
      if (window.innerWidth > 768 && isMenuOpen) {
        closeMenu();
      }
    });

    // Language toggle
    if (langToggle) langToggle.addEventListener('click', toggleLanguage);

    // Keyboard
    document.addEventListener('keydown', handleKeyboard);
  }

  // ============================================================
  // Initialize
  // ============================================================
  async function init() {
    // Load translations before applying
    await loadTranslations();

    // Set initial scroll state
    handleScroll();
    updateActiveLink();

    // Apply initial translations
    applyTranslations();

    // Bind events
    initEventListeners();

    // Initialize contact form
    initContactForm();

    // Trap focus in mobile menu when open
    if (overlay) {
      overlay.addEventListener('keydown', (e) => {
        if (e.key === 'Tab') {
          const focusableElements = overlay.querySelectorAll(
            'button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
          );
          const firstElement = focusableElements[0];
          const lastElement = focusableElements[focusableElements.length - 1];

          if (e.shiftKey && document.activeElement === firstElement) {
            e.preventDefault();
            lastElement.focus();
          } else if (!e.shiftKey && document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      });
    }
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
