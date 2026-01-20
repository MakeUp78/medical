/**
 * Admin Dashboard JavaScript
 * Kimerika Evolution
 */

const API_URL = '/api';
let currentUser = null;
let selectedUserId = null;
let registrationsChart = null;
let plansChart = null;
let periodChart = null;
let currentUsersPage = 1;
let currentAuditPage = 1;

// ===================================
// INITIALIZATION
// ===================================

document.addEventListener('DOMContentLoaded', () => {
    checkAdminAuth();
    setupEventListeners();
});

async function checkAdminAuth() {
    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
    if (!token) {
        window.location.href = 'landing.html';
        return;
    }

    try {
        const response = await fetch(`${API_URL}/auth/verify`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();

        if (!data.success) {
            window.location.href = 'landing.html';
            return;
        }

        if (data.user.role !== 'admin') {
            showToast('Accesso non autorizzato - richiesto ruolo admin', 'error');
            setTimeout(() => {
                window.location.href = 'index.html';
            }, 2000);
            return;
        }

        currentUser = data.user;
        document.getElementById('admin-name').textContent = `${currentUser.firstname}`;
        loadDashboard();

    } catch (error) {
        console.error('Auth error:', error);
        window.location.href = 'landing.html';
    }
}

function setupEventListeners() {
    // Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const section = item.dataset.section;
            switchSection(section);
        });
    });

    // Search on Enter
    const searchInput = document.getElementById('user-search');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') searchUsers();
        });
    }

    // Period selector
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadPeriodChart(btn.dataset.period);
        });
    });

    // Close modal on outside click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
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

    // Update sections
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById(`${sectionName}-section`).classList.add('active');

    // Load section data
    if (sectionName === 'users') {
        // Svuota i filtri per mostrare tutti gli utenti
        const searchInput = document.getElementById('user-search');
        if (searchInput) searchInput.value = '';
        const planFilter = document.getElementById('plan-filter');
        if (planFilter) planFilter.value = '';
        const statusFilter = document.getElementById('status-filter');
        if (statusFilter) statusFilter.value = '';
        loadUsers(1);
    } else if (sectionName === 'audit') {
        loadAuditLog(1);
    } else if (sectionName === 'analytics') {
        loadAnalytics();
    }
}

// ===================================
// DASHBOARD
// ===================================

async function loadDashboard() {
    await loadStats();
    await loadRegistrationChart();
    await loadRecentUsers();
}

async function loadStats() {
    try {
        const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
        const response = await fetch(`${API_URL}/admin/dashboard/stats`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();

        if (data.success) {
            const stats = data.stats;

            // Main stats
            document.getElementById('total-users').textContent = stats.users.total;
            document.getElementById('active-users').textContent = stats.users.active;
            document.getElementById('new-users-month').textContent = stats.users.new_month;
            document.getElementById('total-analyses').textContent = stats.usage.total_analyses.toLocaleString();

            // Quick stats
            document.getElementById('new-today').textContent = stats.users.new_today;
            document.getElementById('new-week').textContent = stats.users.new_week;
            document.getElementById('recent-active').textContent = stats.users.recent_active_24h;

            // Update plans chart
            updatePlansChart(stats.subscriptions);
        }
    } catch (error) {
        console.error('Load stats error:', error);
        showToast('Errore nel caricamento statistiche', 'error');
    }
}

async function loadRegistrationChart() {
    try {
        const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
        const response = await fetch(`${API_URL}/admin/dashboard/registrations?period=month`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();

        if (data.success) {
            const ctx = document.getElementById('registrations-chart').getContext('2d');

            if (registrationsChart) registrationsChart.destroy();

            registrationsChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.data.map(d => formatDateShort(d.date)),
                    datasets: [{
                        label: 'Nuove Registrazioni',
                        data: data.data.map(d => d.count),
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 3,
                        pointBackgroundColor: '#667eea'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: { color: '#888' },
                            grid: { color: 'rgba(255,255,255,0.1)' }
                        },
                        x: {
                            ticks: { color: '#888', maxTicksLimit: 10 },
                            grid: { display: false }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Load chart error:', error);
    }
}

function updatePlansChart(subscriptions) {
    const ctx = document.getElementById('plans-chart').getContext('2d');

    if (plansChart) plansChart.destroy();

    const labels = Object.keys(subscriptions);
    const values = Object.values(subscriptions);
    const colors = {
        'none': '#9e9e9e',
        'monthly': '#2196f3',
        'annual': '#9c27b0'
    };

    plansChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels.map(l => capitalizeFirst(l)),
            datasets: [{
                data: values,
                backgroundColor: labels.map(l => colors[l] || '#667eea'),
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#888', padding: 15 }
                }
            }
        }
    });
}

async function loadRecentUsers() {
    try {
        const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
        const response = await fetch(`${API_URL}/admin/users?per_page=5&sort=created_at&order=desc`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();

        if (data.success) {
            const tbody = document.getElementById('recent-users-tbody');
            tbody.innerHTML = data.users.map(user => `
                <tr>
                    <td>${escapeHtml(user.firstname)} ${escapeHtml(user.lastname)}</td>
                    <td>${escapeHtml(user.email)}</td>
                    <td><span class="plan-badge ${user.plan}">${capitalizeFirst(user.plan)}</span></td>
                    <td>${formatDate(user.created_at)}</td>
                    <td><span class="status-badge ${user.is_active ? 'active' : 'inactive'}">${user.is_active ? 'Attivo' : 'Inattivo'}</span></td>
                </tr>
            `).join('');
        }
    } catch (error) {
        console.error('Load recent users error:', error);
    }
}

// ===================================
// USERS MANAGEMENT
// ===================================

async function loadUsers(page = 1) {
    currentUsersPage = page;

    try {
        const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
        const search = document.getElementById('user-search')?.value || '';
        const plan = document.getElementById('plan-filter')?.value || '';
        const status = document.getElementById('status-filter')?.value || '';

        const params = new URLSearchParams({
            page,
            per_page: 15,
            search,
            plan,
            status,
            sort: 'created_at',
            order: 'desc'
        });

        console.log('Loading users with params:', params.toString());

        const response = await fetch(`${API_URL}/admin/users?${params}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();
        console.log('Users data received:', data);

        if (data.success) {
            console.log(`Rendering ${data.users.length} users`);
            renderUsersTable(data.users);
            renderPagination(data.pagination, 'users-pagination', loadUsers);
        } else {
            console.error('Failed to load users:', data.message);
            showToast(data.message || 'Errore nel caricamento utenti', 'error');
        }
    } catch (error) {
        console.error('Load users error:', error);
        showToast('Errore nel caricamento utenti', 'error');
    }
}

function renderUsersTable(users) {
    const tbody = document.getElementById('users-tbody');

    if (users.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; padding: 2rem;">Nessun utente trovato</td></tr>`;
        return;
    }

    tbody.innerHTML = users.map(user => `
        <tr>
            <td>${user.id}</td>
            <td>${escapeHtml(user.firstname)} ${escapeHtml(user.lastname)}</td>
            <td>${escapeHtml(user.email)}</td>
            <td><span class="role-badge ${user.role}">${user.role}</span></td>
            <td><span class="plan-badge ${user.plan}">${capitalizeFirst(user.plan)}</span></td>
            <td>${user.analyses_count}/${user.analyses_limit === -1 ? '∞' : user.analyses_limit}</td>
            <td>${formatDate(user.created_at)}</td>
            <td><span class="status-badge ${user.is_active ? 'active' : 'inactive'}">${user.is_active ? 'Attivo' : 'Inattivo'}</span></td>
            <td>
                <div class="action-buttons">
                    <button class="btn-action view" onclick="viewUser(${user.id})" title="Visualizza">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn-action edit" onclick="toggleUserStatus(${user.id})" title="${user.is_active ? 'Disattiva' : 'Attiva'}">
                        <i class="fas fa-${user.is_active ? 'ban' : 'check'}"></i>
                    </button>
                    <button class="btn-action edit" onclick="showResetPasswordModal(${user.id})" title="Reset Password">
                        <i class="fas fa-key"></i>
                    </button>
                    ${user.role !== 'admin' ? `
                    <button class="btn-action delete" onclick="showDeleteModal(${user.id}, '${escapeHtml(user.firstname)} ${escapeHtml(user.lastname)}')" title="Elimina">
                        <i class="fas fa-trash"></i>
                    </button>
                    ` : ''}
                </div>
            </td>
        </tr>
    `).join('');
}

function searchUsers() {
    loadUsers(1);
}

// ===================================
// USER ACTIONS
// ===================================

async function viewUser(userId) {
    try {
        const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
        const response = await fetch(`${API_URL}/admin/users/${userId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();

        if (data.success) {
            const user = data.user;
            selectedUserId = userId;

            document.getElementById('user-detail-content').innerHTML = `
                <div class="user-detail-grid">
                    <div class="detail-row"><strong>ID</strong>${user.id}</div>
                    <div class="detail-row"><strong>Ruolo</strong><span class="role-badge ${user.role}">${user.role}</span></div>
                    <div class="detail-row"><strong>Nome</strong>${escapeHtml(user.firstname)} ${escapeHtml(user.lastname)}</div>
                    <div class="detail-row"><strong>Email</strong>${escapeHtml(user.email)}</div>
                    <div class="detail-row"><strong>Piano</strong><span class="plan-badge ${user.plan}">${capitalizeFirst(user.plan)}</span></div>
                    <div class="detail-row"><strong>Stato</strong><span class="status-badge ${user.is_active ? 'active' : 'inactive'}">${user.is_active ? 'Attivo' : 'Inattivo'}</span></div>
                    <div class="detail-row"><strong>Analisi Effettuate</strong>${user.analyses_count}</div>
                    <div class="detail-row"><strong>Limite Analisi</strong>${user.analyses_limit === -1 ? 'Illimitate' : user.analyses_limit}</div>
                    <div class="detail-row"><strong>Data Registrazione</strong>${formatDateTime(user.created_at)}</div>
                    <div class="detail-row"><strong>Ultimo Accesso</strong>${formatDateTime(user.last_login) || 'Mai'}</div>
                    <div class="detail-row"><strong>Telefono</strong>${user.phone || 'N/A'}</div>
                    <div class="detail-row"><strong>Lingua</strong>${user.language || 'it'}</div>
                    <div class="detail-row"><strong>Google</strong>${user.has_google ? '<i class="fas fa-check" style="color:#4caf50"></i> Collegato' : '<i class="fas fa-times" style="color:#f44336"></i> No'}</div>
                    <div class="detail-row"><strong>Apple</strong>${user.has_apple ? '<i class="fas fa-check" style="color:#4caf50"></i> Collegato' : '<i class="fas fa-times" style="color:#f44336"></i> No'}</div>
                </div>
                <div class="user-actions-panel">
                    <h4><i class="fas fa-tools"></i> Azioni Rapide</h4>
                    <select id="change-plan-select">
                        <option value="">Cambia Piano...</option>
                        <option value="none" ${user.plan === 'none' ? 'disabled' : ''}>Nessun Piano</option>
                        <option value="monthly" ${user.plan === 'monthly' ? 'disabled' : ''}>Mensile</option>
                        <option value="annual" ${user.plan === 'annual' ? 'disabled' : ''}>Annuale</option>
                    </select>
                    <button class="btn btn-primary" onclick="changePlan(${user.id})">
                        <i class="fas fa-save"></i> Applica
                    </button>
                </div>
            `;
            document.getElementById('user-detail-modal').classList.add('active');
        }
    } catch (error) {
        console.error('View user error:', error);
        showToast('Errore nel caricamento dettagli', 'error');
    }
}

async function toggleUserStatus(userId) {
    try {
        const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
        const response = await fetch(`${API_URL}/admin/users/${userId}/toggle-status`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message, 'success');
            loadUsers(currentUsersPage);
            loadStats(); // Refresh stats
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        console.error('Toggle status error:', error);
        showToast('Errore durante operazione', 'error');
    }
}

async function changePlan(userId) {
    const newPlan = document.getElementById('change-plan-select').value;
    if (!newPlan) {
        showToast('Seleziona un piano', 'error');
        return;
    }

    try {
        const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
        const response = await fetch(`${API_URL}/admin/users/${userId}/change-plan`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ plan: newPlan })
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message, 'success');
            closeUserModal();
            loadUsers(currentUsersPage);
            loadStats(); // Refresh stats
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        console.error('Change plan error:', error);
        showToast('Errore durante operazione', 'error');
    }
}

// ===================================
// PASSWORD RESET MODAL
// ===================================

function showResetPasswordModal(userId) {
    selectedUserId = userId;
    document.getElementById('new-admin-password').value = '';
    document.getElementById('reset-password-modal').classList.add('active');
}

function closeResetPasswordModal() {
    document.getElementById('reset-password-modal').classList.remove('active');
    selectedUserId = null;
}

async function confirmResetPassword() {
    const newPassword = document.getElementById('new-admin-password').value;

    if (!newPassword || newPassword.length < 8) {
        showToast('Password deve essere almeno 8 caratteri', 'error');
        return;
    }

    try {
        const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
        const response = await fetch(`${API_URL}/admin/users/${selectedUserId}/reset-password`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ new_password: newPassword })
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message, 'success');
            closeResetPasswordModal();
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        console.error('Reset password error:', error);
        showToast('Errore durante operazione', 'error');
    }
}

// ===================================
// DELETE USER MODAL
// ===================================

function showDeleteModal(userId, userName) {
    selectedUserId = userId;
    document.getElementById('delete-user-name').textContent = userName;
    document.getElementById('delete-user-modal').classList.add('active');
}

function closeDeleteModal() {
    document.getElementById('delete-user-modal').classList.remove('active');
    selectedUserId = null;
}

async function confirmDeleteUser() {
    try {
        const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
        const response = await fetch(`${API_URL}/admin/users/${selectedUserId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message, 'success');
            closeDeleteModal();
            loadUsers(currentUsersPage);
            loadStats(); // Refresh stats
        } else {
            showToast(data.message, 'error');
        }
    } catch (error) {
        console.error('Delete user error:', error);
        showToast('Errore durante eliminazione', 'error');
    }
}

function closeUserModal() {
    document.getElementById('user-detail-modal').classList.remove('active');
    selectedUserId = null;
}

// ===================================
// ANALYTICS
// ===================================

async function loadAnalytics() {
    await loadStats();
    await loadPeriodChart('week');
    updateAnalyticsBreakdown();
}

async function loadPeriodChart(period) {
    try {
        const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
        const response = await fetch(`${API_URL}/admin/dashboard/registrations?period=${period}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();

        if (data.success) {
            const ctx = document.getElementById('period-chart').getContext('2d');

            if (periodChart) periodChart.destroy();

            periodChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.data.map(d => formatDateShort(d.date)),
                    datasets: [{
                        label: 'Registrazioni',
                        data: data.data.map(d => d.count),
                        backgroundColor: 'rgba(102, 126, 234, 0.7)',
                        borderColor: '#667eea',
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: { color: '#888' },
                            grid: { color: 'rgba(255,255,255,0.1)' }
                        },
                        x: {
                            ticks: { color: '#888' },
                            grid: { display: false }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Load period chart error:', error);
    }
}

function updateAnalyticsBreakdown() {
    // This would be populated with real data from stats
    // For now showing structure
}

// ===================================
// ANALYTICS
// ===================================

let activityBreakdownChart = null;
let hourlyUsageChart = null;
let dailyActivityChart = null;
let currentAnalyticsPeriod = 'week';

async function loadAnalytics(period = 'week') {
    currentAnalyticsPeriod = period;

    // Update active button
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.period === period);
    });

    try {
        const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
        const response = await fetch(`${API_URL}/admin/analytics/usage?period=${period}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();

        if (data.success) {
            const analytics = data.analytics;

            // Activity Breakdown Chart
            renderActivityBreakdownChart(analytics.activity_breakdown);

            // Hourly Usage Chart
            renderHourlyUsageChart(analytics.hourly_usage);

            // Daily Activity Trend
            renderDailyActivityChart(analytics.daily_trend);

            // Most Active Users Table
            renderMostActiveUsers(analytics.most_active_users);
        }
    } catch (error) {
        console.error('Load analytics error:', error);
        showToast('Errore nel caricamento analytics', 'error');
    }
}

function renderActivityBreakdownChart(activityData) {
    const ctx = document.getElementById('activity-breakdown-chart').getContext('2d');

    if (activityBreakdownChart) activityBreakdownChart.destroy();

    const labels = Object.keys(activityData).map(key => formatActivityType(key));
    const values = Object.values(activityData);
    const colors = ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b', '#fa709a'];

    activityBreakdownChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#888', padding: 15 }
                }
            }
        }
    });
}

function renderHourlyUsageChart(hourlyData) {
    const ctx = document.getElementById('hourly-usage-chart').getContext('2d');

    if (hourlyUsageChart) hourlyUsageChart.destroy();

    // Ensure all 24 hours are represented
    const hours = Array.from({ length: 24 }, (_, i) => i);
    const dataMap = {};
    hourlyData.forEach(d => {
        dataMap[d.hour] = d.count;
    });
    const values = hours.map(h => dataMap[h] || 0);

    hourlyUsageChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: hours.map(h => `${h}:00`),
            datasets: [{
                label: 'Attività',
                data: values,
                backgroundColor: 'rgba(102, 126, 234, 0.6)',
                borderColor: '#667eea',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { color: '#888', precision: 0 },
                    grid: { color: 'rgba(255,255,255,0.1)' }
                },
                x: {
                    ticks: { color: '#888', maxTicksLimit: 12 },
                    grid: { display: false }
                }
            }
        }
    });
}

function renderDailyActivityChart(dailyData) {
    const ctx = document.getElementById('daily-activity-chart').getContext('2d');

    if (dailyActivityChart) dailyActivityChart.destroy();

    dailyActivityChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dailyData.map(d => formatDateShort(d.date)),
            datasets: [{
                label: 'Attività Totali',
                data: dailyData.map(d => d.count),
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointBackgroundColor: '#667eea',
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { color: '#888', precision: 0 },
                    grid: { color: 'rgba(255,255,255,0.1)' }
                },
                x: {
                    ticks: { color: '#888', maxTicksLimit: 10 },
                    grid: { display: false }
                }
            }
        }
    });
}

function renderMostActiveUsers(users) {
    const tbody = document.getElementById('most-active-users');

    if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; padding: 20px;">Nessun utente attivo nel periodo</td></tr>';
        return;
    }

    tbody.innerHTML = users.map((user, index) => `
        <tr>
            <td>
                <span class="rank-badge">${index + 1}</span>
                ${escapeHtml(user.name)}
            </td>
            <td>${escapeHtml(user.email)}</td>
            <td><strong>${user.activity_count}</strong> attività</td>
        </tr>
    `).join('');
}

function formatActivityType(type) {
    const types = {
        'login': '🔐 Login',
        'analysis': '🔬 Analisi',
        'image_upload': '📷 Upload Immagine',
        'video_upload': '🎥 Upload Video',
        'webcam_start': '📹 Avvio Webcam'
    };
    return types[type] || type;
}

// ===================================
// AUDIT LOG
// ===================================

async function loadAuditLog(page = 1) {
    currentAuditPage = page;

    try {
        const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
        const response = await fetch(`${API_URL}/admin/audit-log?page=${page}&per_page=20`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();

        if (data.success) {
            const tbody = document.getElementById('audit-tbody');

            if (data.logs.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem;">Nessuna attivita registrata</td></tr>`;
                return;
            }

            tbody.innerHTML = data.logs.map(log => `
                <tr>
                    <td>${formatDateTime(log.created_at)}</td>
                    <td>${escapeHtml(log.admin_email)}</td>
                    <td><span class="action-badge">${formatAction(log.action)}</span></td>
                    <td>${log.target_user_email ? escapeHtml(log.target_user_email) : '-'}</td>
                    <td>${log.ip_address || '-'}</td>
                    <td>${log.details ? formatDetails(log.details) : '-'}</td>
                </tr>
            `).join('');

            renderPagination(data.pagination, 'audit-pagination', loadAuditLog);
        }
    } catch (error) {
        console.error('Load audit log error:', error);
        showToast('Errore nel caricamento log', 'error');
    }
}

function formatAction(action) {
    const actions = {
        'user_activated': '<i class="fas fa-user-check" style="color:#4caf50"></i> Utente Attivato',
        'user_deactivated': '<i class="fas fa-user-slash" style="color:#f44336"></i> Utente Disattivato',
        'plan_changed': '<i class="fas fa-exchange-alt" style="color:#ff9800"></i> Piano Modificato',
        'password_reset': '<i class="fas fa-key" style="color:#2196f3"></i> Password Reset',
        'user_deleted': '<i class="fas fa-trash" style="color:#f44336"></i> Utente Eliminato'
    };
    return actions[action] || action;
}

function formatDetails(details) {
    if (typeof details === 'object') {
        const parts = [];
        if (details.old_plan && details.new_plan) {
            parts.push(`${capitalizeFirst(details.old_plan)} → ${capitalizeFirst(details.new_plan)}`);
        }
        if (details.deleted_email) {
            parts.push(`Email: ${details.deleted_email}`);
        }
        return parts.join(', ') || JSON.stringify(details);
    }
    return details;
}

// ===================================
// UTILITIES
// ===================================

function renderPagination(pagination, containerId, loadFunction) {
    const container = document.getElementById(containerId);
    if (!container) return;

    let html = '';

    // Previous button
    html += `<button ${!pagination.has_prev ? 'disabled' : ''} onclick="${loadFunction.name}(${pagination.page - 1})">
        <i class="fas fa-chevron-left"></i> Prec
    </button>`;

    // Page numbers
    const maxVisible = 5;
    let startPage = Math.max(1, pagination.page - Math.floor(maxVisible / 2));
    let endPage = Math.min(pagination.pages, startPage + maxVisible - 1);

    if (endPage - startPage < maxVisible - 1) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }

    if (startPage > 1) {
        html += `<button onclick="${loadFunction.name}(1)">1</button>`;
        if (startPage > 2) html += '<span>...</span>';
    }

    for (let i = startPage; i <= endPage; i++) {
        html += `<button class="${i === pagination.page ? 'active' : ''}" onclick="${loadFunction.name}(${i})">${i}</button>`;
    }

    if (endPage < pagination.pages) {
        if (endPage < pagination.pages - 1) html += '<span>...</span>';
        html += `<button onclick="${loadFunction.name}(${pagination.pages})">${pagination.pages}</button>`;
    }

    // Next button
    html += `<button ${!pagination.has_next ? 'disabled' : ''} onclick="${loadFunction.name}(${pagination.page + 1})">
        Succ <i class="fas fa-chevron-right"></i>
    </button>`;

    container.innerHTML = html;
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function formatDateShort(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit' });
}

function formatDateTime(dateStr) {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    return date.toLocaleString('it-IT', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function capitalizeFirst(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

function logout() {
    localStorage.removeItem('auth_token');
    sessionStorage.removeItem('auth_token');
    window.location.href = 'landing.html';
}
