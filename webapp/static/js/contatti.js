// Contact Form Handler

// Initialize reCAPTCHA v3 (opzionale)
const RECAPTCHA_SITE_KEY = '6LfYourSiteKey'; // Placeholder - da sostituire con chiave vera
const RECAPTCHA_ENABLED = RECAPTCHA_SITE_KEY && RECAPTCHA_SITE_KEY !== '6LfYourSiteKey';

// Handle contact form submission
async function handleContactSubmit(event) {
  event.preventDefault();

  const form = event.target;
  const submitBtn = document.getElementById('submit-btn');
  const btnText = submitBtn.querySelector('.btn-text');
  const btnLoading = submitBtn.querySelector('.btn-loading');
  const messageDiv = document.getElementById('form-message');

  // Disable submit button
  submitBtn.disabled = true;
  btnText.style.display = 'none';
  btnLoading.style.display = 'flex';
  messageDiv.style.display = 'none';

  try {
    // Get form data
    const formData = {
      firstname: form.firstname.value,
      lastname: form.lastname.value,
      email: form.email.value,
      phone: form.phone.value || '',
      subject: form.subject.value,
      message: form.message.value,
      newsletter: form.newsletter.checked,
      timestamp: new Date().toISOString()
    };

    // Execute reCAPTCHA v3 (solo se configurato)
    let recaptchaToken = '';
    if (RECAPTCHA_ENABLED && typeof grecaptcha !== 'undefined') {
      try {
        recaptchaToken = await grecaptcha.execute(RECAPTCHA_SITE_KEY, { action: 'submit_contact' });
      } catch (error) {
        console.warn('reCAPTCHA error:', error);
        // Continue without reCAPTCHA if it fails
      }
    }

    // Add reCAPTCHA token to form data
    formData.recaptcha_token = recaptchaToken;

    // Send to backend
    const response = await fetch('/api/contact', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(formData)
    });

    const result = await response.json();

    if (response.ok && result.success) {
      // Success
      messageDiv.className = 'form-message success';
      messageDiv.textContent = '✅ Messaggio inviato con successo! Ti risponderemo entro 24 ore.';
      messageDiv.style.display = 'block';

      // Reset form
      form.reset();

      // Track event
      if (typeof gtag !== 'undefined') {
        gtag('event', 'contact_form_submit', {
          'event_category': 'Contact',
          'event_label': formData.subject
        });
      }

      // Scroll to message
      messageDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });

    } else {
      // Error
      throw new Error(result.message || 'Errore nell\'invio del messaggio');
    }

  } catch (error) {
    console.error('Contact form error:', error);
    messageDiv.className = 'form-message error';
    messageDiv.textContent = '❌ Si è verificato un errore. Riprova o contattaci via email: info@ennioorsini.com';
    messageDiv.style.display = 'block';

    // Scroll to message
    messageDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
  } finally {
    // Re-enable submit button
    submitBtn.disabled = false;
    btnText.style.display = 'inline';
    btnLoading.style.display = 'none';
  }
}

// Track WhatsApp clicks
function trackWhatsAppClick(source) {
  if (typeof gtag !== 'undefined') {
    gtag('event', 'whatsapp_click', {
      'event_category': 'Contact',
      'event_label': source
    });
  }
}

// Book demo function (if not already in landing.js)
function bookDemo(plan = '') {
  const message = plan ?
    `Ciao, vorrei prenotare una demo per il piano ${plan}` :
    'Ciao, vorrei prenotare una demo di Kimerika Evolution';

  const whatsappUrl = `https://wa.me/393711441066?text=${encodeURIComponent(message)}`;
  window.open(whatsappUrl, '_blank');

  trackWhatsAppClick('demo-booking');
}

// Mobile menu toggle (if not already in landing.js)
function toggleMobileMenu() {
  const navbar = document.querySelector('.navbar');
  const navLinks = document.querySelector('.nav-links');
  const menuToggle = document.querySelector('.mobile-menu-toggle');

  navbar.classList.toggle('mobile-menu-open');

  if (navbar.classList.contains('mobile-menu-open')) {
    navLinks.style.display = 'flex';
    menuToggle.classList.add('active');
  } else {
    navLinks.style.display = 'none';
    menuToggle.classList.remove('active');
  }
}

// Form validation helpers
document.addEventListener('DOMContentLoaded', function () {
  // Phone number formatting
  const phoneInput = document.getElementById('phone');
  if (phoneInput) {
    phoneInput.addEventListener('input', function (e) {
      let value = e.target.value.replace(/\D/g, '');
      if (value.length > 0 && !value.startsWith('39')) {
        if (value.startsWith('3')) {
          value = '39' + value;
        }
      }
      e.target.value = value ? '+' + value : '';
    });
  }

  // Email validation on blur
  const emailInput = document.getElementById('email');
  if (emailInput) {
    emailInput.addEventListener('blur', function (e) {
      const email = e.target.value;
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (email && !emailRegex.test(email)) {
        e.target.style.borderColor = '#ef4444';
      } else {
        e.target.style.borderColor = '#e5e7eb';
      }
    });
  }

  // Character count for message
  const messageInput = document.getElementById('message');
  if (messageInput) {
    const maxLength = 1000;
    const counterDiv = document.createElement('div');
    counterDiv.className = 'char-counter';
    counterDiv.style.cssText = 'text-align: right; font-size: 0.85rem; color: #888; margin-top: 5px;';
    messageInput.parentElement.appendChild(counterDiv);

    messageInput.addEventListener('input', function (e) {
      const length = e.target.value.length;
      counterDiv.textContent = `${length}/${maxLength} caratteri`;
      if (length > maxLength) {
        e.target.value = e.target.value.substring(0, maxLength);
        counterDiv.style.color = '#ef4444';
      } else {
        counterDiv.style.color = '#888';
      }
    });

    // Initialize counter
    messageInput.dispatchEvent(new Event('input'));
  }
});
