/* ===================================
   PROFILE PAGE JAVASCRIPT
   =================================== */

const API_URL = '/api';  // Usa proxy nginx
let currentUser = null;

// ===================================
// INITIALIZATION
// ===================================

document.addEventListener('DOMContentLoaded', () => {
  checkAuth();
  setupEventListeners();
});

function checkAuth() {
  const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
  if (!token) {
    window.location.href = 'landing.html';
    return;
  }
  loadUserProfile();
}

function setupEventListeners() {
  // Navigation
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
      const section = item.dataset.section;
      switchSection(section);
    });
  });

  // Forms
  document.getElementById('personal-form').addEventListener('submit', handlePersonalUpdate);
  document.getElementById('password-form').addEventListener('submit', handlePasswordChange);
  document.getElementById('settings-form').addEventListener('submit', handleSettingsUpdate);

  // Avatar upload
  document.getElementById('avatar-upload').addEventListener('change', handleAvatarUpload);
  document.getElementById('delete-avatar-btn').addEventListener('click', handleAvatarDelete);

  // Password strength
  document.getElementById('new-password').addEventListener('input', (e) => {
    updatePasswordStrength(e.target.value);
  });
}

// ===================================
// NAVIGATION
// ===================================

function switchSection(sectionName) {
  // Update nav items
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.remove('active');
  });
  document.querySelector(`[data-section="${sectionName}"]`).classList.add('active');

  // Update content sections
  document.querySelectorAll('.content-section').forEach(section => {
    section.classList.remove('active');
  });
  document.getElementById(`${sectionName}-section`).classList.add('active');
}

// ===================================
// LOAD USER PROFILE
// ===================================

async function loadUserProfile() {
  try {
    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');

    if (!token) {
      console.error('No token found');
      window.location.href = 'landing.html';
      return;
    }

    console.log('Loading profile with token:', token.substring(0, 20) + '...');

    const response = await fetch(`${API_URL}/user/profile`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    console.log('Profile response status:', response.status);

    if (response.status === 401) {
      console.error('Token non valido o scaduto');
      showToast('Sessione scaduta. Effettua nuovamente il login.', 'error');
      setTimeout(() => {
        localStorage.removeItem('auth_token');
        sessionStorage.removeItem('auth_token');
        window.location.href = 'landing.html';
      }, 2000);
      return;
    }

    if (!response.ok) {
      throw new Error('Failed to load profile');
    }

    const data = await response.json();
    currentUser = data.user;

    displayUserProfile(currentUser);
    loadSubscriptionData();

  } catch (error) {
    console.error('Error loading profile:', error);
    showToast('Errore nel caricamento del profilo', 'error');
    // If unauthorized, redirect to login
    if (error.message.includes('401')) {
      localStorage.removeItem('auth_token');
      window.location.href = 'landing.html';
    }
  }
}

function displayUserProfile(user) {
  // Overview section
  document.getElementById('profile-name').textContent = `${user.firstname} ${user.lastname}`;
  document.getElementById('profile-email').textContent = user.email;
  document.getElementById('plan-badge').textContent = getPlanName(user.plan);

  // Avatar
  if (user.profile_image) {
    document.getElementById('avatar-preview').src = user.profile_image;
    document.getElementById('delete-avatar-btn').style.display = 'block';
  }

  // OAuth badges
  if (user.has_google) {
    document.getElementById('google-badge').style.display = 'inline-flex';
    document.getElementById('google-account').querySelector('.account-info p').textContent = 'Collegato';
    document.getElementById('google-account').querySelector('.account-info p').className = 'connected';
  }
  if (user.has_apple) {
    document.getElementById('apple-badge').style.display = 'inline-flex';
    document.getElementById('apple-account').querySelector('.account-info p').textContent = 'Collegato';
    document.getElementById('apple-account').querySelector('.account-info p').className = 'connected';
  }

  // Dates
  if (user.created_at) {
    const createdDate = new Date(user.created_at);
    document.getElementById('member-since').textContent = formatDate(createdDate);
  }
  if (user.last_login) {
    const lastLoginDate = new Date(user.last_login);
    document.getElementById('last-login').textContent = formatDate(lastLoginDate);
  }

  // Usage
  const usagePercent = user.analyses_limit > 0
    ? (user.analyses_count / user.analyses_limit) * 100
    : 0;
  document.getElementById('usage-progress').style.width = `${Math.min(usagePercent, 100)}%`;

  const limitText = user.analyses_limit === -1 ? 'illimitate' : user.analyses_limit;
  document.getElementById('usage-text').textContent =
    `${user.analyses_count} di ${limitText} analisi utilizzate`;

  document.getElementById('analyses-done').textContent =
    `${user.analyses_count} analisi completate`;

  const remaining = user.analyses_limit === -1
    ? 'Illimitate'
    : `${user.analyses_limit - user.analyses_count} analisi rimanenti`;
  document.getElementById('analyses-remaining').textContent = remaining;

  // Personal data form
  document.getElementById('firstname').value = user.firstname || '';
  document.getElementById('lastname').value = user.lastname || '';
  document.getElementById('email-display').value = user.email || '';
  document.getElementById('phone').value = user.phone || '';
  document.getElementById('bio').value = user.bio || '';

  // Settings
  document.getElementById('language').value = user.language || 'it';
  document.getElementById('notifications').checked = user.notifications_enabled !== false;

  // Password form - hide current password if OAuth only user
  if (!user.has_password) {
    document.getElementById('current-password-group').style.display = 'none';
    document.getElementById('current-password').required = false;
    document.getElementById('delete-password-group').style.display = 'none';
  }
}

async function loadSubscriptionData() {
  try {
    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');

    if (!token) {
      console.error('No token found in loadSubscriptionData');
      return;
    }

    console.log('Loading subscription with token...');

    const response = await fetch(`${API_URL}/user/subscription`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    console.log('Subscription response status:', response.status);

    if (response.status === 401) {
      console.error('Token non valido in loadSubscriptionData');
      return;
    }

    if (!response.ok) throw new Error('Failed to load subscription');

    const data = await response.json();
    const sub = data.subscription;

    // Update subscription section
    document.getElementById('current-plan-badge').textContent = sub.plan_name;

    // Status
    if (sub.trial_active) {
      document.getElementById('subscription-status').textContent =
        `Periodo di prova (${sub.trial_days_left} giorni rimanenti)`;
      document.getElementById('trial-card').style.display = 'flex';
      document.getElementById('trial-text').textContent =
        `Ti restano ${sub.trial_days_left} giorni di prova gratuita`;
    } else if (sub.subscription_active) {
      document.getElementById('subscription-status').textContent = 'Attivo';
      document.getElementById('trial-card').style.display = 'none';
    } else {
      document.getElementById('subscription-status').textContent = 'Scaduto';
      document.getElementById('trial-card').style.display = 'none';
    }

    // Expiry
    if (sub.subscription_ends_at) {
      const expiryDate = new Date(sub.subscription_ends_at);
      document.getElementById('subscription-expiry').textContent =
        `Scade il ${formatDate(expiryDate)}`;
    } else if (sub.trial_ends_at) {
      const trialDate = new Date(sub.trial_ends_at);
      document.getElementById('subscription-expiry').textContent =
        `Trial scade il ${formatDate(trialDate)}`;
    } else {
      document.getElementById('subscription-expiry').textContent = 'Nessuna scadenza';
    }

    // Analyses
    const analysesText = sub.analyses_limit === -1
      ? 'Analisi illimitate'
      : `${sub.analyses_limit} analisi al mese`;
    document.getElementById('subscription-analyses').textContent = analysesText;

  } catch (error) {
    console.error('Error loading subscription:', error);
  }
}

// ===================================
// UPDATE PERSONAL DATA
// ===================================

async function handlePersonalUpdate(e) {
  e.preventDefault();

  const data = {
    firstname: document.getElementById('firstname').value.trim(),
    lastname: document.getElementById('lastname').value.trim(),
    phone: document.getElementById('phone').value.trim(),
    bio: document.getElementById('bio').value.trim()
  };

  try {
    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
    const response = await fetch(`${API_URL}/user/profile`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(data)
    });

    const result = await response.json();

    if (result.success) {
      currentUser = result.user;
      displayUserProfile(currentUser);
      showToast('Profilo aggiornato con successo', 'success');
    } else {
      showToast(result.message || 'Errore durante aggiornamento', 'error');
    }
  } catch (error) {
    console.error('Error updating profile:', error);
    showToast('Errore durante aggiornamento profilo', 'error');
  }
}

// ===================================
// CHANGE PASSWORD
// ===================================

async function handlePasswordChange(e) {
  e.preventDefault();

  const currentPassword = document.getElementById('current-password').value;
  const newPassword = document.getElementById('new-password').value;
  const confirmPassword = document.getElementById('confirm-password').value;

  // Validate
  if (newPassword !== confirmPassword) {
    showToast('Le password non corrispondono', 'error');
    return;
  }

  if (newPassword.length < 8) {
    showToast('La password deve essere almeno 8 caratteri', 'error');
    return;
  }

  try {
    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
    const response = await fetch(`${API_URL}/user/change-password`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword
      })
    });

    const result = await response.json();

    if (result.success) {
      showToast('Password aggiornata con successo', 'success');
      document.getElementById('password-form').reset();
      document.getElementById('password-strength').className = 'password-strength';
    } else {
      showToast(result.message || 'Errore durante aggiornamento password', 'error');
    }
  } catch (error) {
    console.error('Error changing password:', error);
    showToast('Errore durante aggiornamento password', 'error');
  }
}

function updatePasswordStrength(password) {
  const strengthIndicator = document.getElementById('password-strength');

  if (password.length === 0) {
    strengthIndicator.className = 'password-strength';
    return;
  }

  let strength = 0;
  if (password.length >= 8) strength++;
  if (password.length >= 12) strength++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
  if (/[0-9]/.test(password)) strength++;
  if (/[^a-zA-Z0-9]/.test(password)) strength++;

  if (strength < 2) {
    strengthIndicator.className = 'password-strength weak';
  } else if (strength < 4) {
    strengthIndicator.className = 'password-strength medium';
  } else {
    strengthIndicator.className = 'password-strength strong';
  }
}

function togglePassword(inputId) {
  const input = document.getElementById(inputId);
  const icon = input.parentElement.querySelector('.toggle-password i');

  if (input.type === 'password') {
    input.type = 'text';
    icon.classList.remove('fa-eye');
    icon.classList.add('fa-eye-slash');
  } else {
    input.type = 'password';
    icon.classList.remove('fa-eye-slash');
    icon.classList.add('fa-eye');
  }
}

// ===================================
// AVATAR UPLOAD
// ===================================

async function handleAvatarUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  // Validate file type
  if (!file.type.startsWith('image/')) {
    showToast('Per favore seleziona un\'immagine', 'error');
    return;
  }

  // Validate file size (5MB)
  if (file.size > 5 * 1024 * 1024) {
    showToast('L\'immagine deve essere inferiore a 5MB', 'error');
    return;
  }

  const formData = new FormData();
  formData.append('avatar', file);

  try {
    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');

    if (!token) {
      showToast('Sessione scaduta. Effettua nuovamente il login.', 'error');
      return;
    }

    const response = await fetch(`${API_URL}/user/upload-avatar`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    });

    const result = await response.json();

    if (result.success) {
      document.getElementById('avatar-preview').src = result.profile_image + '?t=' + Date.now();
      document.getElementById('delete-avatar-btn').style.display = 'block';
      showToast('Avatar caricato con successo', 'success');
    } else {
      showToast(result.message || 'Errore durante upload', 'error');
    }
  } catch (error) {
    console.error('Error uploading avatar:', error);
    showToast('Errore durante upload avatar', 'error');
  }
}

async function handleAvatarDelete() {
  if (!confirm('Sei sicuro di voler eliminare la tua immagine profilo?')) {
    return;
  }

  try {
    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
    const response = await fetch(`${API_URL}/user/delete-avatar`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    const result = await response.json();

    if (result.success) {
      document.getElementById('avatar-preview').src =
        'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22%3E%3Ccircle cx=%2250%22 cy=%2250%22 r=%2250%22 fill=%22%23e0e0e0%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 dominant-baseline=%22middle%22 text-anchor=%22middle%22 font-size=%2240%22 fill=%22%23666%22%3E%3F%3C/text%3E%3C/svg%3E';
      document.getElementById('delete-avatar-btn').style.display = 'none';
      showToast('Avatar eliminato', 'success');
    } else {
      showToast(result.message || 'Errore durante eliminazione', 'error');
    }
  } catch (error) {
    console.error('Error deleting avatar:', error);
    showToast('Errore durante eliminazione avatar', 'error');
  }
}

// ===================================
// SETTINGS UPDATE
// ===================================

async function handleSettingsUpdate(e) {
  e.preventDefault();

  const data = {
    language: document.getElementById('language').value,
    notifications_enabled: document.getElementById('notifications').checked
  };

  try {
    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
    const response = await fetch(`${API_URL}/user/profile`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(data)
    });

    const result = await response.json();

    if (result.success) {
      showToast('Impostazioni salvate', 'success');
    } else {
      showToast(result.message || 'Errore durante salvataggio', 'error');
    }
  } catch (error) {
    console.error('Error updating settings:', error);
    showToast('Errore durante salvataggio impostazioni', 'error');
  }
}

// ===================================
// UPGRADE PLAN
// ===================================

function upgradePlan(plan) {
  showToast('Funzionalità in arrivo! Contatta il supporto per upgrade', 'warning');
  // TODO: Implement payment integration (Stripe, PayPal, etc.)
}

// ===================================
// DELETE ACCOUNT
// ===================================

function showDeleteAccountModal() {
  document.getElementById('delete-account-modal').classList.add('active');
}

function closeDeleteAccountModal() {
  document.getElementById('delete-account-modal').classList.remove('active');
  document.getElementById('delete-password').value = '';
}

async function confirmDeleteAccount() {
  const password = document.getElementById('delete-password').value;

  if (currentUser.has_password && !password) {
    showToast('Inserisci la password per confermare', 'error');
    return;
  }

  if (!confirm('ULTIMA CONFERMA: Sei assolutamente sicuro di voler eliminare il tuo account? Questa azione è irreversibile!')) {
    return;
  }

  try {
    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
    const response = await fetch(`${API_URL}/user/delete-account`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ password })
    });

    const result = await response.json();

    if (result.success) {
      showToast('Account eliminato. Arrivederci!', 'success');
      setTimeout(() => {
        localStorage.removeItem('auth_token');
        window.location.href = 'landing.html';
      }, 2000);
    } else {
      showToast(result.message || 'Errore durante eliminazione', 'error');
    }
  } catch (error) {
    console.error('Error deleting account:', error);
    showToast('Errore durante eliminazione account', 'error');
  }
}

// ===================================
// LOGOUT
// ===================================

function logout() {
  if (confirm('Sei sicuro di voler uscire?')) {
    localStorage.removeItem('auth_token');
    window.location.href = 'landing.html';
  }
}

// ===================================
// UTILITY FUNCTIONS
// ===================================

function getPlanName(plan) {
  const plans = {
    'starter': 'Starter',
    'professional': 'Professional',
    'enterprise': 'Enterprise'
  };
  return plans[plan] || plan;
}

function formatDate(date) {
  const options = { year: 'numeric', month: 'long', day: 'numeric' };
  return date.toLocaleDateString('it-IT', options);
}

function showToast(message, type = 'info') {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `toast ${type}`;
  toast.classList.add('show');

  setTimeout(() => {
    toast.classList.remove('show');
  }, 3000);
}
