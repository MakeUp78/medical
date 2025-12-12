// ===================================
// LANDING PAGE JAVASCRIPT
// ===================================

// State management
const state = {
    currentAuthForm: 'login',
    selectedPlan: null,
    user: null
};

// ===================================
// NAVIGATION
// ===================================

function toggleMobileMenu() {
    const navLinks = document.querySelector('.nav-links');
    const navActions = document.querySelector('.nav-actions');

    navLinks.classList.toggle('active');
    navActions.classList.toggle('active');
}

function scrollToSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.scrollIntoView({ behavior: 'smooth' });
    }
}

// Navbar scroll effect
window.addEventListener('scroll', () => {
    const navbar = document.querySelector('.navbar');
    if (window.scrollY > 50) {
        navbar.style.boxShadow = 'var(--shadow)';
    } else {
        navbar.style.boxShadow = 'var(--shadow-sm)';
    }
});

// ===================================
// MODAL MANAGEMENT
// ===================================

function showAuthModal(formType = 'login', plan = null) {
    const modal = document.getElementById('auth-modal');
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');
    const forgotForm = document.getElementById('forgot-form');

    // Hide all forms
    loginForm.style.display = 'none';
    signupForm.style.display = 'none';
    forgotForm.style.display = 'none';

    // Show selected form
    if (formType === 'login') {
        loginForm.style.display = 'block';
    } else if (formType === 'signup') {
        signupForm.style.display = 'block';
    } else if (formType === 'forgot') {
        forgotForm.style.display = 'block';
    }

    state.currentAuthForm = formType;
    state.selectedPlan = plan;

    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeAuthModal() {
    const modal = document.getElementById('auth-modal');
    modal.classList.remove('active');
    document.body.style.overflow = 'auto';
}

// Close modal on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeAuthModal();
    }
});

// ===================================
// FORM VALIDATION
// ===================================

function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

function validatePassword(password) {
    return password.length >= 8;
}

function checkPasswordStrength(password) {
    let strength = 0;

    if (password.length >= 8) strength++;
    if (password.length >= 12) strength++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
    if (/[0-9]/.test(password)) strength++;
    if (/[^a-zA-Z0-9]/.test(password)) strength++;

    if (strength <= 2) return 'weak';
    if (strength <= 4) return 'medium';
    return 'strong';
}

// Password strength indicator
document.addEventListener('DOMContentLoaded', () => {
    const passwordInput = document.getElementById('signup-password');
    const strengthIndicator = document.getElementById('password-strength');

    if (passwordInput && strengthIndicator) {
        passwordInput.addEventListener('input', (e) => {
            const password = e.target.value;
            if (password.length === 0) {
                strengthIndicator.className = 'password-strength';
                return;
            }

            const strength = checkPasswordStrength(password);
            strengthIndicator.className = `password-strength ${strength}`;
        });
    }
});

// ===================================
// AUTHENTICATION HANDLERS
// ===================================

async function handleLogin(event) {
    event.preventDefault();

    const form = event.target;
    const email = form.email.value;
    const password = form.password.value;
    const remember = form.remember.checked;

    // Validate
    if (!validateEmail(email)) {
        showNotification('Email non valida', 'error');
        return;
    }

    if (!validatePassword(password)) {
        showNotification('Password deve essere almeno 8 caratteri', 'error');
        return;
    }

    // Show loading
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Accesso in corso...';
    submitBtn.disabled = true;

    try {
        // Call API
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password, remember })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Store token
            if (remember) {
                localStorage.setItem('auth_token', data.token);
            } else {
                sessionStorage.setItem('auth_token', data.token);
            }

            // Store user data
            state.user = data.user;

            showNotification('Login effettuato con successo!', 'success');

            // Redirect to app
            setTimeout(() => {
                window.location.href = '/index.html';
            }, 1000);
        } else {
            showNotification(data.message || 'Credenziali non valide', 'error');
        }
    } catch (error) {
        console.error('Login error:', error);
        showNotification('Errore di connessione. Riprova.', 'error');
    } finally {
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
    }
}

async function handleSignup(event) {
    event.preventDefault();

    const form = event.target;
    const firstname = form.firstname.value;
    const lastname = form.lastname.value;
    const email = form.email.value;
    const password = form.password.value;
    const terms = form.terms.checked;

    // Validate
    if (!firstname || !lastname) {
        showNotification('Nome e cognome richiesti', 'error');
        return;
    }

    if (!validateEmail(email)) {
        showNotification('Email non valida', 'error');
        return;
    }

    if (!validatePassword(password)) {
        showNotification('Password deve essere almeno 8 caratteri', 'error');
        return;
    }

    if (!terms) {
        showNotification('Devi accettare i termini di servizio', 'error');
        return;
    }

    // Show loading
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Creazione account...';
    submitBtn.disabled = true;

    try {
        // Call API
        const response = await fetch('/api/auth/signup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                firstname,
                lastname,
                email,
                password,
                plan: state.selectedPlan
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showNotification('Account creato con successo!', 'success');

            // Auto login
            if (data.token) {
                localStorage.setItem('auth_token', data.token);
                state.user = data.user;

                setTimeout(() => {
                    window.location.href = '/index.html';
                }, 1000);
            } else {
                // Show login form
                setTimeout(() => {
                    showAuthModal('login');
                    showNotification('Effettua il login per continuare', 'info');
                }, 1500);
            }
        } else {
            showNotification(data.message || 'Errore durante la registrazione', 'error');
        }
    } catch (error) {
        console.error('Signup error:', error);
        showNotification('Errore di connessione. Riprova.', 'error');
    } finally {
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
    }
}

async function handleForgotPassword(event) {
    event.preventDefault();

    const form = event.target;
    const email = form.email.value;

    // Validate
    if (!validateEmail(email)) {
        showNotification('Email non valida', 'error');
        return;
    }

    // Show loading
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Invio in corso...';
    submitBtn.disabled = true;

    try {
        // Call API
        const response = await fetch('/api/auth/forgot-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showNotification('Email inviata! Controlla la tua casella di posta.', 'success');

            // Reset form
            form.reset();

            // Go back to login after 2 seconds
            setTimeout(() => {
                showAuthModal('login');
            }, 2000);
        } else {
            showNotification(data.message || 'Errore durante l\'invio', 'error');
        }
    } catch (error) {
        console.error('Forgot password error:', error);
        showNotification('Errore di connessione. Riprova.', 'error');
    } finally {
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
    }
}

// ===================================
// SOCIAL LOGIN (OAuth)
// ===================================

function loginWithGoogle() {
    showNotification('Reindirizzamento a Google...', 'info');

    // Redirect to Google OAuth
    window.location.href = '/api/auth/google/login';
}

function signupWithGoogle() {
    showNotification('Reindirizzamento a Google...', 'info');

    // Add plan parameter if selected
    const planParam = state.selectedPlan ? `?plan=${state.selectedPlan}` : '';
    window.location.href = `/api/auth/google/signup${planParam}`;
}

function loginWithApple() {
    showNotification('Reindirizzamento a Apple...', 'info');

    // Redirect to Apple Sign In
    window.location.href = '/api/auth/apple/login';
}

function signupWithApple() {
    showNotification('Reindirizzamento a Apple...', 'info');

    // Add plan parameter if selected
    const planParam = state.selectedPlan ? `?plan=${state.selectedPlan}` : '';
    window.location.href = `/api/auth/apple/signup${planParam}`;
}

// Handle OAuth callback
window.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);

    // Check for OAuth success
    if (urlParams.get('auth') === 'success') {
        const token = urlParams.get('token');
        if (token) {
            localStorage.setItem('auth_token', token);
            showNotification('Autenticazione completata!', 'success');

            // Clean URL and redirect
            setTimeout(() => {
                window.location.href = '/index.html';
            }, 1000);
        }
    }

    // Check for OAuth error
    if (urlParams.get('auth') === 'error') {
        const message = urlParams.get('message') || 'Errore durante l\'autenticazione';
        showNotification(message, 'error');

        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
    }
});

// ===================================
// NOTIFICATIONS
// ===================================

function showNotification(message, type = 'info') {
    // Remove existing notifications
    const existing = document.querySelector('.notification');
    if (existing) {
        existing.remove();
    }

    // Create notification
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;

    // Style
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#3b82f6'};
        color: white;
        padding: 16px 24px;
        border-radius: 8px;
        box-shadow: var(--shadow-lg);
        z-index: 3000;
        animation: slideInRight 0.3s ease;
        max-width: 400px;
        font-weight: 600;
    `;

    document.body.appendChild(notification);

    // Auto remove after 5 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 5000);
}

// Add notification animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// ===================================
// SCROLL ANIMATIONS
// ===================================

const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('fade-in');
        }
    });
}, observerOptions);

// Observe elements
window.addEventListener('DOMContentLoaded', () => {
    const elements = document.querySelectorAll('.feature-card, .step, .pricing-card, .testimonial-card');
    elements.forEach(el => observer.observe(el));
});

// ===================================
// UTILITIES
// ===================================

// Check if user is already logged in
function checkAuth() {
    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');

    if (token) {
        // Verify token with backend
        fetch('/api/auth/verify', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                state.user = data.user;

                // Update UI for logged in user
                updateNavForLoggedInUser();
            } else {
                // Invalid token, clear it
                localStorage.removeItem('auth_token');
                sessionStorage.removeItem('auth_token');
            }
        })
        .catch(err => {
            console.error('Auth verification error:', err);
        });
    }
}

function updateNavForLoggedInUser() {
    const navActions = document.querySelector('.nav-actions');
    if (navActions && state.user) {
        navActions.innerHTML = `
            <span style="color: var(--gray); margin-right: 16px;">Ciao, ${state.user.firstname}!</span>
            <button class="btn-primary" onclick="window.location.href='/index.html'">Vai all'App</button>
            <button class="btn-secondary" onclick="logout()">Esci</button>
        `;
    }
}

function logout() {
    localStorage.removeItem('auth_token');
    sessionStorage.removeItem('auth_token');
    state.user = null;

    showNotification('Logout effettuato', 'info');

    // Reload page
    setTimeout(() => {
        window.location.reload();
    }, 1000);
}

// Initialize
checkAuth();

console.log('🚀 Kimerika Evolution Landing Page loaded successfully');
