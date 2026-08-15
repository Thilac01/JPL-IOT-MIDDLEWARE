// Global limits and handlers
window.currentLoansLimit = 100;
window.currentReturnsLimit = 50;

window.changeLoansLimit = function(val) {
    window.currentLoansLimit = parseInt(val, 10) || 100;
    const tbody = document.querySelector('#active-loans-table tbody');
    if (tbody) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#888;padding:12px;"><i class="fas fa-spinner fa-spin"></i> Fetching ' + window.currentLoansLimit + ' records...</td></tr>';
    }
    fetchLoans();
};

window.changeReturnsLimit = function(val) {
    window.currentReturnsLimit = parseInt(val, 10) || 50;
    const tbody = document.querySelector('#recent-returns-table tbody');
    if (tbody) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#888;padding:12px;"><i class="fas fa-spinner fa-spin"></i> Fetching ' + window.currentReturnsLimit + ' records...</td></tr>';
    }
    fetchReturns();
};

// Enterprise Middle-ware logic
let eventCount = 0;
let eventsThisMin = 0;
let currentTableData = [];
let ws;

// Auth & RBAC State Management
// Auth & RBAC State Management
let currentUser = null;
let authToken = localStorage.getItem('jpl_auth_token') || null;

window.handleLoginSubmit = function(e) {
    if (e) e.preventDefault();
    const user = document.getElementById('login-username').value.trim();
    const pass = document.getElementById('login-password').value.trim();
    handleLogin(user, pass);
};

async function handleLogin(username, password) {
    const errorDiv = document.getElementById('login-error');
    const errorText = document.getElementById('login-error-text');
    const loginBtn = document.getElementById('login-btn');
    
    if (loginBtn) {
        loginBtn.disabled = true;
        loginBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Authenticating...';
    }

    const cleanUser = (username || '').trim();
    const cleanPass = (password || '').trim();

    if (!cleanUser || !cleanPass) {
        if (errorDiv) {
            errorDiv.style.display = 'flex';
            if (errorText) errorText.textContent = 'Please enter both username and password.';
        }
        if (loginBtn) {
            loginBtn.disabled = false;
            loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> SIGN IN';
        }
        return;
    }

    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: cleanUser, password: cleanPass })
        });

        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                authToken = data.token;
                currentUser = data.user;
                localStorage.setItem('jpl_auth_token', authToken);
                localStorage.setItem('jpl_user_data', JSON.stringify(currentUser));

                if (errorDiv) errorDiv.style.display = 'none';
                applyUserSession(currentUser);
                showToast('Login Successful', `Signed in as ${currentUser.name} (${currentUser.role.toUpperCase()})`, 'success');
                return;
            }
        }

        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Invalid username or password');
    } catch (err) {
        if (errorDiv) {
            errorDiv.style.display = 'flex';
            if (errorText) errorText.textContent = err.message || 'Invalid username or password';
        }
    } finally {
        if (loginBtn) {
            loginBtn.disabled = false;
            loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> SIGN IN';
        }
    }
}


function applyUserSession(user) {
    const loginOverlay = document.getElementById('login-overlay');
    const appContainer = document.getElementById('app-container');
    const displayName = document.getElementById('user-display-name');
    const roleBadge = document.getElementById('user-role-badge');
    const headerAvatar = document.getElementById('header-avatar');

    if (loginOverlay) loginOverlay.style.display = 'none';
    if (appContainer) appContainer.style.display = 'flex';

    if (displayName) displayName.textContent = user.username;
    if (roleBadge) {
        roleBadge.textContent = user.role === 'superuser' ? 'SUPER USER' : user.role.toUpperCase();
        roleBadge.className = `role-badge role-${user.role}`;
    }
    if (headerAvatar) {
        if (user.role === 'superuser') {
            headerAvatar.innerHTML = '<i class="fas fa-crown" style="color: #c084fc;"></i>';
        } else if (user.role === 'technical') {
            headerAvatar.innerHTML = '<i class="fas fa-user-shield"></i>';
        } else {
            headerAvatar.innerHTML = '<i class="fas fa-user"></i>';
        }
    }

    // Set body role class for CSS-based element gating
    document.body.classList.remove('role-superuser', 'role-technical', 'role-staff');
    document.body.classList.add(`role-${user.role}`);

    // If non-superuser is on superuser tab, switch to dashboard
    const activeTab = document.querySelector('.nav-item.active')?.getAttribute('data-tab');
    if (user.role !== 'superuser' && (activeTab === 'user-management' || activeTab === 'analytics')) {
        switchTab('dashboard');
    }
    if (user.role === 'staff' && (activeTab === 'live-tables' || activeTab === 'iot-maps' || activeTab === 'audit')) {
        switchTab('dashboard');
    }

    // Connect WebSocket if not active
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        initWebSocket();
    }

    // Start background heartbeats & uptime tickers
    startHeartbeat();
    initUptimeTicker();

    // Sync all data
    syncAllData();
}

window.logout = async function() {
    try {
        await fetch('/api/auth/logout', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
    } catch(e) {}

    authToken = null;
    currentUser = null;
    localStorage.removeItem('jpl_auth_token');
    localStorage.removeItem('jpl_user_data');

    document.body.classList.remove('role-superuser', 'role-technical', 'role-staff');
    const loginOverlay = document.getElementById('login-overlay');
    const appContainer = document.getElementById('app-container');
    if (loginOverlay) loginOverlay.style.display = 'flex';
    if (appContainer) appContainer.style.display = 'none';

    // Reset tab to dashboard
    switchTab('dashboard');
    showToast('Signed Out', 'You have been safely signed out.', 'info');
};

function switchTab(targetTab) {
    const navItems = document.querySelectorAll('.nav-item');
    const tabPanes = document.querySelectorAll('.tab-pane');
    const breadcrumbPath = document.getElementById('breadcrumb-path');

    navItems.forEach(i => i.classList.remove('active'));
    tabPanes.forEach(pane => pane.classList.remove('active'));

    const targetNav = document.querySelector(`.nav-item[data-tab="${targetTab}"]`);
    const targetPane = document.getElementById(targetTab);

    if (targetNav) targetNav.classList.add('active');
    if (targetPane) targetPane.classList.add('active');
    if (breadcrumbPath) breadcrumbPath.innerHTML = `<b>${targetTab.toUpperCase().replace('-', ' ')}</b>`;
}

function checkAuthOnLoad() {
    const storedToken = localStorage.getItem('jpl_auth_token');
    const storedUser = localStorage.getItem('jpl_user_data');

    if (storedToken && storedUser) {
        try {
            currentUser = JSON.parse(storedUser);

            authToken = storedToken;
            applyUserSession(currentUser);
            return;
        } catch (e) {}
    }

    // Default: Show login overlay
    const loginOverlay = document.getElementById('login-overlay');
    const appContainer = document.getElementById('app-container');
    if (loginOverlay) loginOverlay.style.display = 'flex';
    if (appContainer) appContainer.style.display = 'none';
}

// Inject Toast Alert Container into DOM
(function() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = 'position:fixed;top:60px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:10px;pointer-events:none;';
    document.body.appendChild(container);
})();

function showToast(title, msg, level = 'info') {
    const colors = {
        success: { bg: '#e8f5e9', border: '#28a745', icon: '✅' },
        info:    { bg: '#e3f2fd', border: '#2196f3', icon: 'ℹ️' },
        warning: { bg: '#fff8e1', border: '#ffc107', icon: '⚠️' },
        error:   { bg: '#ffebee', border: '#dc3545', icon: '🚨' }
    };
    const c = colors[level] || colors.info;
    const toast = document.createElement('div');
    toast.style.cssText = `
        background: ${c.bg}; border-left: 4px solid ${c.border};
        padding: 12px 16px; border-radius: 6px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        min-width: 320px; max-width: 400px;
        animation: slideIn 0.3s ease; pointer-events: all;
        font-family: 'Open Sans', sans-serif;
    `;
    toast.innerHTML = `
        <div style="font-weight:700;font-size:0.85rem;color:#333;margin-bottom:4px;">${c.icon} ${title}</div>
        <div style="font-size:0.8rem;color:#555;">${msg}</div>
        <div style="font-size:0.7rem;color:#999;margin-top:4px;">${new Date().toLocaleTimeString()}</div>
    `;
    document.getElementById('toast-container').appendChild(toast);
    // Auto-remove after 6 seconds
    setTimeout(() => toast.remove(), 6000);
}

// Reset events per minute counter
setInterval(() => {
    const statEvents = document.getElementById('stat-events');
    if (statEvents) statEvents.textContent = `${eventsThisMin}/min`;
    eventsThisMin = 0;
}, 60000);

document.addEventListener('DOMContentLoaded', () => {
    // Attach explicit change listeners to limit dropdowns
    const loansSelect = document.getElementById('loans-limit-select');
    if (loansSelect) {
        loansSelect.addEventListener('change', (e) => window.changeLoansLimit(e.target.value));
    }
    const returnsSelect = document.getElementById('returns-limit-select');
    if (returnsSelect) {
        returnsSelect.addEventListener('change', (e) => window.changeReturnsLimit(e.target.value));
    }

    initClock();
    initTabs();
    checkAuthOnLoad();

    // Make static canvas nodes draggable once DOM is ready
    setTimeout(() => {
        ['node-koha', 'node-mid'].forEach(id => {
            const nd = document.getElementById(id);
            if (nd) makeDraggable(nd);
        });
    }, 300);
});

function initTabs() {
    const navItems = document.querySelectorAll('.nav-item');
    const tabPanes = document.querySelectorAll('.tab-pane');
    const breadcrumbPath = document.getElementById('breadcrumb-path');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const targetTab = item.getAttribute('data-tab');

            // Access control check for Super User tabs
            if (currentUser && currentUser.role !== 'superuser') {
                if (targetTab === 'user-management' || targetTab === 'analytics') {
                    showToast('Access Restricted', 'Super User role required to access ' + targetTab.toUpperCase() + '.', 'warning');
                    return;
                }
            }

            // Access control check for normal staff
            if (currentUser && currentUser.role === 'staff') {
                const technicalTabs = ['live-tables', 'iot-maps', 'audit', 'user-management', 'analytics'];
                if (technicalTabs.includes(targetTab)) {
                    showToast('Access Restricted', 'Staff account does not have permission to access ' + targetTab.toUpperCase() + '.', 'warning');
                    return;
                }
            }

            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            tabPanes.forEach(pane => {
                pane.classList.remove('active');
                if (pane.id === targetTab) pane.classList.add('active');
            });

            breadcrumbPath.innerHTML = `<b>${targetTab.toUpperCase().replace('-', ' ')}</b>`;
            
            if (targetTab === 'user-management') {
                fetchUsersList();
            }
            if (targetTab === 'analytics') {
                fetchAnalyticsData();
                fetchActivityLogs();
            }
            if (targetTab === 'live-tables' && document.getElementById('table-selector').options.length <= 1) {
                fetchTableList();
            }
            if (targetTab === 'iot-maps') {
                fetchIotNodes();
                setTimeout(drawLines, 100);
            }
            if (targetTab === 'alerts') {
                fetchStats();
            }
            if (targetTab === 'audit') {
                fetchAuditLogs();
            }
            if (targetTab === 'whitelist') {
                fetchLoans();
            }
        });
    });
}

function initClock() {
    const clock = document.getElementById('clock');
    setInterval(() => {
        clock.textContent = new Date().toLocaleTimeString('en-US', { hour12: false });
    }, 1000);
}

function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    const statusBadge = document.getElementById('connection-status');

    if (ws) ws.close();
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log("Enterprise Sync Service Connected");
        statusBadge.textContent = "CONNECTED";
        statusBadge.className = "status-badge online";
        addLogEntry('SYSTEM', 'Real-time CDC pipeline operational');
    };

    ws.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data);
            handleLiveEvent(payload);
        } catch (e) {
            console.error("Payload Sync Error", e);
        }
    };

    ws.onclose = () => {
        statusBadge.textContent = "DISCONNECTED";
        statusBadge.className = "status-badge offline";
        addLogEntry('SYSTEM', 'Middleware connection lost. Retrying...', 'danger');
        setTimeout(initWebSocket, 2000);
    };
}

function handleLiveEvent(event) {
    eventCount++;
    eventsThisMin++;
    document.getElementById('total-events').textContent = eventCount;
    document.getElementById('stat-events').textContent = `${eventsThisMin}/min`;

    let category = event.table.toUpperCase();
    let message = `Mod detected on [${event.table}]`;
    
    if (event.table === 'issues') {
        category = 'LOAN-OUT';
        message = `Live Transaction: Asset ${event.data?.barcode || event.data?.issue_id} checked out`;
        fetchLoans();
        fetchStats();
    } else if (event.table === 'old_issues') {
        category = 'RETURN-IN';
        message = `Recovery: Asset ${event.data?.barcode || event.data?.issue_id} returned to shelf`;
        fetchReturns();
        fetchStats();
    }

    // Fire real-time popup alert if backend included alert metadata
    if (event.alert) {
        showToast(event.alert.title, event.alert.msg, event.alert.level);
    }
    
    addLogEntry(category, message, category.toLowerCase());

    // Update Live View if selected
    const selectedTable = document.getElementById('table-selector').value;
    if (selectedTable === event.table) {
        if (event.type === 'INSERT') {
            currentTableData.unshift(event.data);
            renderTableData(currentTableData);
        } else if (event.type === 'UPDATE') {
            // Industrial Standard: In-place update to reduce bandwidth
            const oldData = event.old_data || {};
            // Find the index of the row matching old_data
            const rowIndex = currentTableData.findIndex(row => {
                // Heuristic: check if at least keys match. If there is an 'id' or primary key, match that. Otherwise match all possible.
                // Simple primary key guess:
                const pk = Object.keys(row).find(k => k.toLowerCase().includes('id') || k.toLowerCase().includes('number')) || Object.keys(row)[0];
                return row[pk] === oldData[pk] || row[pk] === event.data[pk];
            });
            
            if (rowIndex !== -1) {
                currentTableData[rowIndex] = { ...currentTableData[rowIndex], ...event.data };
                renderTableData(currentTableData);
            } else {
                // Fallback: unshift if not found
                currentTableData.unshift(event.data);
                renderTableData(currentTableData);
            }
        } else if (event.type === 'DELETE') {
            // Industrial Standard: In-place deletion
            const rowIndex = currentTableData.findIndex(row => {
                const pk = Object.keys(row).find(k => k.toLowerCase().includes('id') || k.toLowerCase().includes('number')) || Object.keys(row)[0];
                return row[pk] === event.data[pk];
            });
            if (rowIndex !== -1) {
                currentTableData.splice(rowIndex, 1);
                renderTableData(currentTableData);
            }
        }
    }
}

function addLogEntry(tag, message, category = '') {
    const stream = document.getElementById('event-stream');
    if (!stream) return;
    const entry = document.createElement('div');
    const catLower = (category || tag || '').toLowerCase();
    entry.className = `log-line ${catLower}`;
    const time = new Date().toLocaleTimeString('en-US', { hour12: false });
    
    // Tag class determination
    let tagClass = 'tag-default';
    if (catLower.includes('loan') || catLower === 'issues') tagClass = 'tag-loan-out';
    else if (catLower.includes('return') || catLower === 'old_issues') tagClass = 'tag-return-in';
    else if (catLower.includes('system')) tagClass = 'tag-system';
    else if (catLower.includes('danger') || catLower.includes('error')) tagClass = 'tag-danger';
    else if (catLower.includes('warning')) tagClass = 'tag-warning';

    entry.innerHTML = `
        <span class="log-time">[${time}]</span>
        <span class="log-tag ${tagClass}">${tag}</span>
        <span class="log-msg">${message}</span>
    `;

    // Apply active log filter if not 'all'
    const activeBtn = document.querySelector('.log-filter-btn.active');
    if (activeBtn) {
        const filter = activeBtn.getAttribute('data-filter');
        if (filter && filter !== 'all') {
            if (filter === 'loan' && !(catLower.includes('loan') || catLower === 'issues')) entry.style.display = 'none';
            else if (filter === 'return' && !(catLower.includes('return') || catLower === 'old_issues')) entry.style.display = 'none';
            else if (filter === 'system' && !catLower.includes('system')) entry.style.display = 'none';
            else if (filter === 'danger' && !(catLower.includes('danger') || catLower.includes('error'))) entry.style.display = 'none';
        }
    }

    stream.prepend(entry);
    if (stream.children.length > 250) stream.lastChild.remove();
}

window.clearEventStream = function() {
    const stream = document.getElementById('event-stream');
    if (stream) {
        stream.innerHTML = '';
        addLogEntry('SYSTEM', 'Log stream cleared by operator.', 'system');
    }
};

window.filterLogs = function(filterType) {
    const stream = document.getElementById('event-stream');
    if (!stream) return;
    const filterBtns = document.querySelectorAll('.log-filter-btn');
    filterBtns.forEach(btn => {
        if (btn.getAttribute('data-filter') === filterType) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    const lines = stream.querySelectorAll('.log-line');
    lines.forEach(line => {
        if (filterType === 'all') {
            line.style.display = 'flex';
        } else if (filterType === 'loan' && (line.classList.contains('loan-out') || line.classList.contains('issues') || line.classList.contains('loan'))) {
            line.style.display = 'flex';
        } else if (filterType === 'return' && (line.classList.contains('return-in') || line.classList.contains('old_issues') || line.classList.contains('return'))) {
            line.style.display = 'flex';
        } else if (filterType === 'system' && line.classList.contains('system')) {
            line.style.display = 'flex';
        } else if (filterType === 'danger' && (line.classList.contains('danger') || line.classList.contains('error'))) {
            line.style.display = 'flex';
        } else {
            line.style.display = 'none';
        }
    });
};

// Data Services
async function syncAllData() {
    fetchStats();
    fetchLoans();
    fetchReturns();
}

async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        
        // 1. Total Check Out
        const statLoans = document.getElementById('stat-loans');
        if (statLoans) statLoans.textContent = data.active_loans ?? 0;

        // 2. Check Out - Last 30 days
        const statCo30 = document.getElementById('stat-checkout-30d');
        if (statCo30) statCo30.textContent = data.checkout_30_days ?? 0;

        // 3. Check Out - Last 7 days
        const statCo7 = document.getElementById('stat-checkout-7d');
        if (statCo7) statCo7.textContent = data.checkout_7_days ?? 0;

        // 4. Check out - Today
        const statCoToday = document.getElementById('stat-checkout-today');
        if (statCoToday) statCoToday.textContent = data.checkout_today ?? 0;

        // 5. Total returns - Last 30 days
        const statRet30 = document.getElementById('stat-returns-30d');
        if (statRet30) statRet30.textContent = data.returns_30_days ?? 0;

        // 6. Total returns - Last 7 days
        const statRet7 = document.getElementById('stat-returns-7d');
        if (statRet7) statRet7.textContent = data.returns_7_days ?? 0;

        // 7. Total returns - Today
        const statRetToday = document.getElementById('stat-returns-today');
        if (statRetToday) statRetToday.textContent = data.returns_today ?? 0;

        // 8. Total past due date
        const statPastDue = document.getElementById('stat-past-due');
        if (statPastDue) statPastDue.textContent = data.past_due_date ?? data.overdue ?? 0;

        // 9. Total due - Today
        const statDueToday = document.getElementById('stat-due-today');
        if (statDueToday) statDueToday.textContent = data.due_today ?? 0;

        // 10. Unacknowledged Alerts
        const overdue = data.overdue || 0;
        const statAlerts = document.getElementById('stat-alerts');
        if (statAlerts) statAlerts.textContent = overdue;
        
        // Update Alerts content in Alerts tab
        const alertsContent = document.getElementById('alerts-content');
        if (alertsContent) {
            if (overdue > 0) {
                alertsContent.innerHTML = `
                    <div class="alert-item warning">
                        <div class="alert-icon"><i class="fas fa-exclamation-triangle"></i></div>
                        <div class="alert-details">
                            <div class="alert-title">Overdue Item Notice (${overdue} Unacknowledged)</div>
                            <div class="alert-desc">There are currently <strong>${overdue}</strong> overdue circulation items requiring recall or borrower notification.</div>
                        </div>
                        <div class="alert-time">${new Date().toLocaleTimeString()}</div>
                    </div>
                `;
            } else {
                alertsContent.innerHTML = `
                    <div class="alert-item normal">
                        <div class="alert-icon"><i class="fas fa-check-circle"></i></div>
                        <div class="alert-details">
                            <div class="alert-title">All Systems Nominal</div>
                            <div class="alert-desc">Zero unacknowledged security anomalies or overdue circulation alerts.</div>
                        </div>
                        <div class="alert-time">${new Date().toLocaleTimeString()}</div>
                    </div>
                `;
            }
        }

        // Update Audit Log Content
        fetchAuditLogs();

    } catch (e) { console.error(e); }
}

let currentAuditData = [];

async function fetchAuditLogs() {
    const tbody = document.getElementById('audit-tbody');
    try {
        const res = await fetch('/api/audit-logs');
        const data = await res.json();
        currentAuditData = data;
        renderAuditLogs(data);
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 2rem; color: var(--error);">Security protocol restricted access or connection timeout.</td></tr>';
    }
}

function renderAuditLogs(data) {
    const tbody = document.getElementById('audit-tbody');
    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 2rem;">No audit records found in secure storage.</td></tr>';
        return;
    }

    const moduleIcons = {
        'MEMBERS': 'fa-users',
        'CIRCULATION': 'fa-sync-alt',
        'SYSTEM': 'fa-cogs',
        'RESERVES': 'fa-bookmark',
        'PREFERENCES': 'fa-sliders-h',
        'CATALOGUE': 'fa-book'
    };

    tbody.innerHTML = data.map(log => {
        const typeClass = `badge-${log.type.toLowerCase()}`;
        const icon = moduleIcons[log.module] || 'fa-info-circle';
        
        // Pretty format the action text
        let actionDisplay = log.action;
        if (actionDisplay.length > 60) actionDisplay = actionDisplay.substring(0, 57) + '...';
        
        return `
            <tr>
                <td style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #888;">
                    <div style="display:flex; flex-direction:column;">
                        <span>${new Date(log.timestamp).toLocaleDateString()}</span>
                        <span style="font-weight:700; color:#555;">${new Date(log.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                    </div>
                </td>
                <td>
                    <div style="display:flex; align-items:center; gap:10px;">
                        <div style="width:32px; height:32px; border-radius:8px; background:linear-gradient(135deg, #eef2f8 0%, #d1d9e6 100%); display:flex; align-items:center; justify-content:center; font-size:0.8rem; font-weight:700; color:var(--primary); border: 1px solid rgba(0,0,0,0.05);">
                            ${log.user_name ? log.user_name.charAt(0) : 'U'}
                        </div>
                        <div>
                            <div style="font-weight:700; color:var(--primary); font-size:0.85rem;">${log.user_name || 'System'}</div>
                            <div style="font-size:0.6rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; font-weight:600;">${log.user_type || 'INTERNAL'}</div>
                        </div>
                    </div>
                </td>
                <td>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span class="badge-action ${typeClass}" style="width: 70px; text-align:center;">${log.type}</span>
                    </div>
                </td>
                <td>
                    <div style="display:flex; flex-direction:column; gap:2px;">
                        <div style="font-weight: 600; color: #445; font-size:0.85rem;">${actionDisplay}</div>
                        <div style="font-size:0.7rem; color: #99a;">Performed on secure shard ${log.module || 'CORE'}</div>
                    </div>
                </td>
                <td>
                    <div style="display:flex; align-items:center; gap:6px; color: #666; font-size:0.75rem;">
                        <i class="fas ${icon}" style="width:14px; color:var(--accent);"></i>
                        <span style="font-weight:600;">${log.module}</span>
                    </div>
                </td>
                <td>
                    <span style="font-family: 'JetBrains Mono', monospace; font-weight:700; background:#f0f2f5; padding: 4px 8px; border-radius:4px; font-size:0.75rem; color:var(--primary); border: 1px solid #e0e4e9;">
                        ${log.object_id || '—'}
                    </span>
                </td>
            </tr>
        `;
    }).join('');
}

function filterAuditLogs() {
    const term = document.getElementById('audit-search').value.toLowerCase();
    const filtered = currentAuditData.filter(log => 
        String(log.user_name).toLowerCase().includes(term) ||
        String(log.action).toLowerCase().includes(term) ||
        String(log.module).toLowerCase().includes(term) ||
        String(log.object_id).toLowerCase().includes(term)
    );
    renderAuditLogs(filtered);
}

async function fetchLoans() {
    const tbody = document.querySelector('#active-loans-table tbody');
    const whitelistTbody = document.querySelector('#whitelist-table tbody');
    try {
        const res = await fetch(`/api/active-loans?limit=${window.currentLoansLimit || 100}&t=${Date.now()}`);
        const data = await res.json();
        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center">No active streams</td></tr>';
            if (whitelistTbody) whitelistTbody.innerHTML = '<tr><td colspan="5" style="text-align:center">No assets currently whitelisted for exit.</td></tr>';
            return;
        }
        tbody.innerHTML = data.map(d => `
            <tr>
                <td><span style="font-family: 'JetBrains Mono', monospace; font-weight:700; color:var(--primary);"><i class="fas fa-barcode" style="margin-right: 4px; color: #888;"></i>${d.barcode || '—'}</span></td>
                <td><b>${d.firstname || ''} ${d.surname || ''}</b></td>
                <td>${d.title || '—'}</td>
                <td><span style="font-family: 'JetBrains Mono', monospace; font-weight:600; color:#555;">${d.publication_year || '—'}</span></td>
                <td>${formatDate(d.issuedate)}</td>
                <td style="color: ${isOverdue(d.date_due)?'#dc3545':'inherit'}; font-weight:600;">${formatDate(d.date_due)}</td>
            </tr>
        `).join('');
        
        if (whitelistTbody) {
            whitelistTbody.innerHTML = data.map(d => `
                <tr style="background-color: #f8fff9; border-left: 3px solid #28a745;">
                    <td style="font-family: 'JetBrains Mono', monospace; font-weight: bold; color: var(--primary);"><i class="fas fa-barcode" style="margin-right: 5px; color: #888;"></i>${d.barcode || 'N/A'}</td>
                    <td style="font-weight: 600;">${d.title}</td>
                    <td>${d.firstname} ${d.surname}</td>
                    <td style="color: ${isOverdue(d.date_due)?'#dc3545':'inherit'};">${formatDate(d.date_due)}</td>
                    <td>${formatDate(d.issuedate)}</td>
                </tr>
            `).join('');
        }
    } catch (e) { 
        tbody.innerHTML = '<tr><td colspan="6">Sync Error</td></tr>'; 
        if (whitelistTbody) whitelistTbody.innerHTML = '<tr><td colspan="5">Integration Error with RFID Gate module</td></tr>';
    }
}

async function fetchReturns() {
    const tbody = document.querySelector('#recent-returns-table tbody');
    try {
        const res = await fetch(`/api/recent-returns?limit=${window.currentReturnsLimit || 50}&t=${Date.now()}`);
        const data = await res.json();
        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center">Waiting...</td></tr>';
            return;
        }
        tbody.innerHTML = data.map(d => `
            <tr>
                <td><span style="font-family: 'JetBrains Mono', monospace; font-weight:700; color:var(--primary);"><i class="fas fa-barcode" style="margin-right: 4px; color: #888;"></i>${d.barcode || '—'}</span></td>
                <td><b>${d.title || '—'}</b></td>
                <td><span style="font-family: 'JetBrains Mono', monospace; font-weight:600; color:#555;">${d.publication_year || '—'}</span></td>
                <td>${d.firstname || ''} ${d.surname || ''}</td>
                <td>${formatDate(d.returndate)}</td>
            </tr>
        `).join('');
    } catch (e) { tbody.innerHTML = '<tr><td colspan="5">Sync Error</td></tr>'; }
}

// Table Discovery Logic
async function fetchTableList() {
    const selector = document.getElementById('table-selector');
    if (!selector) return;

    try {
        const res = await fetch('/api/tables');
        if (!res.ok) throw new Error("API Unreachable");
        
        const tables = await res.json();
        populateSelector(selector, tables);
    } catch (e) { 
        console.warn("Table discovery failed", e);
        addLogEntry('SYSTEM', 'Database connection unavailable for discovery', 'error');
    }
}

function populateSelector(selector, tables) {
    if (!tables || tables.length === 0) {
        selector.innerHTML = '<option value="">Service Initializing...</option>';
        return;
    }
    selector.innerHTML = '<option value="">Select a table...</option>';
    tables.sort().forEach(t => {
        const opt = document.createElement('option');
        opt.value = opt.textContent = t;
        selector.appendChild(opt);
    });
}

async function onTableChange() {
    const table = document.getElementById('table-selector').value;
    if (!table) return;
    document.getElementById('current-table-name').textContent = `VIEWER: ${table.toUpperCase()}`;
    await fetchTableData(table);
}

async function refreshTableData() {
    const table = document.getElementById('table-selector').value;
    if (table) await fetchTableData(table);
}

async function fetchTableData(tableName) {
    const tbody = document.getElementById('dynamic-tbody');
    const thead = document.getElementById('dynamic-thead');
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 2rem;">Loading stream...</td></tr>';
    
    try {
        const res = await fetch(`/api/table-data/${tableName}`);
        const data = await res.json();
        currentTableData = data;
        renderTableData(data);
    } catch (e) { tbody.innerHTML = '<tr><td colspan="5">Sync error</td></tr>'; }
}

function renderTableData(data) {
    const tbody = document.getElementById('dynamic-tbody');
    const thead = document.getElementById('dynamic-thead');
    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center">No records in target table</td></tr>';
        return;
    }
    const headers = Object.keys(data[0]);
    thead.innerHTML = `<tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr>`;
    tbody.innerHTML = data.map(row => `
        <tr>${headers.map(h => `<td>${row[h] !== null ? row[h] : 'NULL'}</td>`).join('')}</tr>
    `).join('');
}

function filterCurrentTable() {
    const term = document.getElementById('table-search').value.toLowerCase();
    const filtered = currentTableData.filter(row => Object.values(row).some(v => String(v).toLowerCase().includes(term)));
    renderTableData(filtered);
}

function formatDate(dateStr) {
    if (!dateStr) return '—';
    try {
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return String(dateStr);
        return d.toLocaleDateString('en-GB', { 
            day: '2-digit', 
            month: 'short', 
            year: 'numeric', 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    } catch (e) {
        return String(dateStr);
    }
}

function isOverdue(dateStr) {
    if (!dateStr) return false;
    return new Date(dateStr) < new Date();
}

// node credential cache (set when user connects)
const nodeCredentials = {};

// --- IoT Node Map Logic ---
async function fetchIotNodes() {
    try {
        const res = await fetch('/api/iot/nodes');
        const nodes = await res.json();
        const container = document.getElementById('dynamic-gates-container');
        container.innerHTML = '';
        
        nodes.forEach((n, idx) => {
            const top = 10 + (idx * 28);
            const isOnline = Date.now() / 1000 - n.last_seen < 30;
            const cpu  = n.cpu  !== undefined && n.cpu  >= 0 ? n.cpu  : null;
            const mem  = n.mem  !== undefined && n.mem  >= 0 ? n.mem  : null;
            const temp = n.temp !== undefined && n.temp >= 0 ? n.temp : null;
            
            function bar(val, max, color) {
                if (val === null) return '<div style="font-size:0.65rem;color:#aaa;">Awaiting stats…</div>';
                const pct = Math.min(100, (val / max) * 100);
                const alertColor = pct > 80 ? '#dc3545' : pct > 60 ? '#ffc107' : color;
                return `<div style="background:#e9ecef;border-radius:3px;height:6px;width:100%;margin-top:2px;">
                    <div style="background:${alertColor};width:${pct}%;height:6px;border-radius:3px;transition:width 0.5s;"></div>
                </div><div style="font-size:0.65rem;color:#666;text-align:right;">${val.toFixed(1)}${max===100?'%':'°C'}</div>`;
            }

            const el = document.createElement('div');
            el.className = 'node-box';
            el.id = `node-gate-${idx}`;
            el.setAttribute('data-ip', n.ip);
            el.style.cssText = `top:${top}%;left:68%;width:240px;`;
            el.innerHTML = `
                <div class="node-port in-port" style="left:-6px;top:40%;"></div>
                <div class="node-header gate-node-header" style="justify-content:space-between;">
                    <span><i class="fas fa-satellite-dish"></i> Security Gate #${idx+1}</span>
                    <span style="font-size:0.6rem;background:${isOnline?'#28a745':'#ffc107'};color:white;padding:1px 5px;border-radius:3px;">${isOnline?'LIVE':'IDLE'}</span>
                </div>
                <div class="node-body" style="gap:6px;">
                    <div style="font-size:0.75rem;font-weight:600;color:#333;">${n.ip}</div>
                    ${n.uptime ? `<div style="font-size:0.65rem;color:#888;"><i class="fas fa-clock"></i> ${n.uptime}</div>` : ''}
                    
                    <div style="margin-top:4px;">
                        <div style="font-size:0.65rem;color:#666;font-weight:600;text-transform:uppercase;">CPU</div>
                        ${bar(cpu, 100, '#2196f3')}
                    </div>
                    <div>
                        <div style="font-size:0.65rem;color:#666;font-weight:600;text-transform:uppercase;">Memory</div>
                        ${bar(mem, 100, '#9c27b0')}
                    </div>
                    <div>
                        <div style="font-size:0.65rem;color:#666;font-weight:600;text-transform:uppercase;">Temperature</div>
                        ${bar(temp, 85, '#ff5722')}
                    </div>

                    <div style="margin-top:6px;display:flex;gap:6px;">
                        <button onclick="openTerminal('${n.ip}', ${idx})" style="flex:1;background:#343a40;color:#fff;border:none;padding:4px 0;border-radius:3px;font-size:0.7rem;cursor:pointer;">
                            <i class="fas fa-terminal"></i> Terminal
                        </button>
                        <button onclick="refreshNodeStats('${n.ip}')" style="flex:1;background:#eef2f8;color:#333;border:1px solid #d1d5db;padding:4px 0;border-radius:3px;font-size:0.7rem;cursor:pointer;">
                            <i class="fas fa-sync"></i> Stats
                        </button>
                    </div>
                </div>
            `;
            container.appendChild(el);
            makeDraggable(el);  // ← enable drag on this node
        });

        // Also make the two static nodes draggable
        ['node-koha','node-mid'].forEach(id => {
            const nd = document.getElementById(id);
            if (nd && !nd.dataset.draggable) makeDraggable(nd);
        });

        setTimeout(drawLines, 80);

    } catch (e) {
        console.error("Error fetching IoT nodes", e);
    }
}

async function refreshNodeStats(ip) {
    const creds = nodeCredentials[ip];
    if (!creds) { showToast('🔑 No credentials', `Connect to ${ip} first via the Deploy panel.`, 'warning'); return; }
    try {
        const res = await fetch('/api/iot/stats', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ip, username: creds.user, password: creds.pass})
        });
        const data = await res.json();
        if (data.status === 'ok') {
            fetchIotNodes(); // Re-render with fresh stats
        }
    } catch(e) { console.error(e); }
}

// Auto-poll stats for all connected nodes every 8s
setInterval(() => {
    Object.keys(nodeCredentials).forEach(ip => refreshNodeStats(ip));
}, 8000);

// ─── Draggable Nodes ─────────────────────────────────────────────────────────
function makeDraggable(el) {
    if (el.dataset.draggable) return; // already set up
    el.dataset.draggable = '1';

    // Convert from % to px on first drag so movement is precise
    function toPx() {
        const canvas = document.getElementById('node-canvas');
        const cw = canvas.offsetWidth;
        const ch = canvas.offsetHeight;
        const curLeft = parseFloat(el.style.left);
        const curTop  = parseFloat(el.style.top);
        // If still in %, convert to px
        if (el.style.left.includes('%')) {
            el.style.left = (curLeft / 100 * cw) + 'px';
            el.style.top  = (curTop  / 100 * ch) + 'px';
        }
    }

    let startX, startY, startLeft, startTop;

    // Use mousedown on the header so body buttons still work
    const handle = el.querySelector('.node-header') || el;
    handle.style.cursor = 'grab';

    handle.addEventListener('mousedown', e => {
        // Don't drag when clicking buttons inside header
        if (e.target.closest('button')) return;
        e.preventDefault();

        toPx();
        startX    = e.clientX;
        startY    = e.clientY;
        startLeft = parseFloat(el.style.left);
        startTop  = parseFloat(el.style.top);
        handle.style.cursor = 'grabbing';
        el.style.zIndex = '10';

        const canvas = document.getElementById('node-canvas');
        const cw = canvas.offsetWidth;
        const ch = canvas.offsetHeight;

        function onMove(me) {
            const dx = me.clientX - startX;
            const dy = me.clientY - startY;
            // Clamp inside canvas
            const newLeft = Math.max(0, Math.min(cw - el.offsetWidth,  startLeft + dx));
            const newTop  = Math.max(0, Math.min(ch - el.offsetHeight, startTop  + dy));
            el.style.left = newLeft + 'px';
            el.style.top  = newTop  + 'px';
            drawLines(); // live redraw of bezier connections
        }

        function onUp() {
            handle.style.cursor = 'grab';
            el.style.zIndex = '2';
            window.removeEventListener('mousemove', onMove);
            window.removeEventListener('mouseup',   onUp);
        }

        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup',   onUp);
    });
}

function drawLines() {
    const svg = document.getElementById('node-lines');
    if (!svg) return;
    svg.innerHTML = '';

    const canvas = document.getElementById('node-canvas');
    if (!canvas) return;
    const cr = canvas.getBoundingClientRect();

    // Get the center of the right edge of a node (output port)
    function outXY(el) {
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { x: r.right - cr.left, y: r.top - cr.top + r.height / 2 };
    }

    // Get the center of the left edge of a node (input port)
    function inXY(el) {
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { x: r.left - cr.left, y: r.top - cr.top + r.height / 2 };
    }

    function bezier(p1, p2, color, dashed) {
        if (!p1 || !p2) return;
        const cx = (p1.x + p2.x) / 2;

        // Base shadow/muted track
        const track = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        track.setAttribute('d', `M ${p1.x} ${p1.y} C ${cx} ${p1.y}, ${cx} ${p2.y}, ${p2.x} ${p2.y}`);
        track.setAttribute('fill', 'none');
        track.setAttribute('stroke', '#c5cdd8');
        track.setAttribute('stroke-width', '2');
        svg.appendChild(track);

        // Animated active line
        const active = track.cloneNode();
        active.setAttribute('stroke', color);
        active.setAttribute('stroke-width', '2.5');
        if (dashed) {
            active.setAttribute('stroke-dasharray', '8,6');
            const anim = document.createElementNS('http://www.w3.org/2000/svg', 'animate');
            anim.setAttribute('attributeName', 'stroke-dashoffset');
            anim.setAttribute('from', '28'); anim.setAttribute('to', '0');
            anim.setAttribute('dur', '0.8s'); anim.setAttribute('repeatCount', 'indefinite');
            active.appendChild(anim);
        }
        svg.appendChild(active);
    }

    const koha = document.getElementById('node-koha');
    const mid  = document.getElementById('node-mid');

    // ① Koha → Middleware (orange, solid)
    bezier(outXY(koha), inXY(mid), 'var(--secondary)', false);

    // ② Middleware → every gate node simultaneously (blue, dashed animated)
    const gates = document.querySelectorAll('[id^="node-gate-"]');
    gates.forEach(g => bezier(outXY(mid), inXY(g), 'var(--accent)', true));
}


// Ensure lines redraw on window resize or occasional ticks
window.addEventListener('resize', drawLines);
setInterval(() => {
    if(document.getElementById('iot-maps').classList.contains('active')) {
        fetchIotNodes(); // Refresh map including status
    }
}, 5000);

async function runArpScan() {
    const resBox = document.getElementById('arp-results');
    resBox.innerHTML = '<div style="text-align:center"><i class="fas fa-spinner fa-spin"></i> Scanning subnets...</div>';
    try {
        const req = await fetch('/api/iot/scan', {method: 'POST'});
        const data = await req.json();
        
        resBox.innerHTML = '<ul style="list-style:none; padding:0;">' + data.nodes.map(n => `
            <li style="padding: 10px; border-bottom: 1px solid #eee; cursor:pointer;" onclick="fillDeployIp('${n.ip}')">
                <div style="font-weight:600; color:${n.is_pi ? 'var(--secondary)' : 'var(--text-main)'};">
                    <i class="fas fa-${n.is_pi ? 'microchip' : 'network-wired'}"></i> ${n.ip}
                </div>
                <div style="font-size:0.7rem; color:var(--text-muted);">${n.mac} - ${n.type}</div>
            </li>
        `).join('') + '</ul>';
        
    } catch(e) {
        resBox.innerHTML = '<div style="color:red; font-size:0.8rem;">ARP Broadcast restrictions active. Check network privileges.</div>';
    }
}

function fillDeployIp(ip) {
    document.getElementById('deploy-ip').value = ip;
}

async function deployToNode() {
    const ip = document.getElementById('deploy-ip').value;
    const user = document.getElementById('deploy-user').value;
    const pass = document.getElementById('deploy-pwd').value;
    const status = document.getElementById('deploy-status');
    
    if(!ip || !user || !pass) {
        status.style.display = 'block';
        status.style.background = '#ffe5e5';
        status.style.color = '#dc3545';
        status.textContent = 'Please fill all connection details.';
        return;
    }
    
    status.style.display = 'block';
    status.style.background = '#eef2f8';
    status.style.color = 'var(--accent)';
    status.innerHTML = '<i class="fas fa-cog fa-spin"></i> Authenticating and injecting gateway code...';
    
    try {
        const req = await fetch('/api/iot/deploy', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ip, username: user, password: pass})
        });
        const res = await req.json();
        
        if(res.status === 'success') {
            status.style.background = '#e8f5e9';
            status.style.color = '#28a745';
            status.textContent = res.message;
            // Cache credentials for stats + terminal
            nodeCredentials[ip] = { user, pass };
            fetchIotNodes();
            refreshNodeStats(ip);
        } else {
            status.style.background = '#ffe5e5';
            status.style.color = '#dc3545';
            status.textContent = res.message;
        }
    } catch (e) {
        status.style.background = '#ffe5e5';
        status.style.color = '#dc3545';
        status.textContent = 'Network delivery failed entirely.';
    }
}

// ─── In-Page SSH Terminal Modal ─────────────────────────────────────────────
let _termIp = null; // active terminal target

function openTerminal(ip, idx) {
    // Remove existing if open
    const existing = document.getElementById('ssh-terminal-modal');
    if (existing) existing.remove();

    _termIp = ip;

    const modal = document.createElement('div');
    modal.id = 'ssh-terminal-modal';
    modal.style.cssText = [
        'position:fixed', 'bottom:0', 'left:240px', 'right:0', 'height:320px',
        'background:#1a1d23', 'border-top:2px solid var(--accent)',
        'display:flex', 'flex-direction:column', 'z-index:9000',
        "font-family:'JetBrains Mono',monospace"
    ].join(';');

    const creds = nodeCredentials[ip];

    modal.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 14px;background:#12141a;border-bottom:1px solid #2d3139;">
            <span style="color:#4fc3f7;font-size:0.78rem;font-weight:700;">
                <i class="fas fa-terminal" style="margin-right:6px;"></i>
                SSH Terminal — ${ip} ${creds ? '' : '<span style="color:#ffc107;font-size:0.65rem;">(enter credentials below)</span>'}
            </span>
            <div style="display:flex;gap:8px;">
                <button id="term-clear-btn" style="background:#2d3139;color:#aaa;border:none;padding:2px 8px;border-radius:3px;font-size:0.7rem;cursor:pointer;">Clear</button>
                <button id="term-close-btn" style="background:#dc3545;color:#fff;border:none;padding:2px 8px;border-radius:3px;font-size:0.7rem;cursor:pointer;">✕ Close</button>
            </div>
        </div>
        ${!creds ? `
        <div id="term-creds-bar" style="display:flex;gap:8px;padding:6px 14px;background:#12141a;border-bottom:1px solid #2d3139;align-items:center;">
            <span style="color:#aaa;font-size:0.7rem;white-space:nowrap;">SSH Auth:</span>
            <input id="term-user" placeholder="username" value="pi"
                style="background:#1e2230;border:1px solid #2d3139;color:#e0e0e0;padding:3px 8px;border-radius:3px;font-size:0.72rem;width:90px;outline:none;">
            <input id="term-pass" type="password" placeholder="password"
                style="background:#1e2230;border:1px solid #2d3139;color:#e0e0e0;padding:3px 8px;border-radius:3px;font-size:0.72rem;width:110px;outline:none;">
            <button id="term-auth-btn" style="background:var(--success);color:#fff;border:none;padding:3px 10px;border-radius:3px;font-size:0.72rem;cursor:pointer;">Connect</button>
        </div>` : ''}
        <div id="term-output" style="flex:1;overflow-y:auto;padding:10px 14px;font-size:0.75rem;line-height:1.6;"></div>
        <div style="display:flex;align-items:center;padding:6px 10px;border-top:1px solid #2d3139;gap:8px;">
            <span style="color:#4fc3f7;font-size:0.78rem;white-space:nowrap;">${ip} $</span>
            <input id="term-input" type="text" placeholder="${creds ? 'Enter command…' : 'Connect first ↑'}"
                style="flex:1;background:#12141a;border:1px solid #2d3139;color:#e0e0e0;padding:5px 10px;border-radius:3px;font-family:inherit;font-size:0.75rem;outline:none;" ${!creds ? 'disabled' : ''}>
            <button id="term-run-btn" style="background:${creds ? 'var(--accent)' : '#555'};color:white;border:none;padding:5px 12px;border-radius:3px;font-size:0.75rem;cursor:pointer;" ${!creds ? 'disabled' : ''}>Run</button>
        </div>
    `;

    document.body.appendChild(modal);

    // Wire events with addEventListener (NOT inline strings)
    document.getElementById('term-clear-btn').addEventListener('click', () => {
        document.getElementById('term-output').innerHTML = '';
    });
    document.getElementById('term-close-btn').addEventListener('click', () => modal.remove());

    if (!creds) {
        document.getElementById('term-auth-btn').addEventListener('click', () => {
            const u = document.getElementById('term-user').value.trim();
            const p = document.getElementById('term-pass').value;
            if (!u || !p) return;
            nodeCredentials[ip] = { user: u, pass: p };
            termLog(`<span style="color:#81c784">✔ Credentials saved for ${ip}. Verifying…</span>`);
            // Re-open to activate inputs
            openTerminal(ip, idx);
        });
        document.getElementById('term-pass').addEventListener('keydown', e => {
            if (e.key === 'Enter') document.getElementById('term-auth-btn').click();
        });
    } else {
        const input = document.getElementById('term-input');
        const runBtn = document.getElementById('term-run-btn');
        input.focus();
        input.addEventListener('keydown', e => { if (e.key === 'Enter') _execCommand(); });
        runBtn.addEventListener('click', _execCommand);
        termLog(`<span style="color:#4fc3f7">Connected to ${ip}.</span> Type a command and press <b>Enter</b>.`);
    }
}

function termLog(html) {
    const out = document.getElementById('term-output');
    if (!out) return;
    const line = document.createElement('div');
    line.innerHTML = html;
    out.appendChild(line);
    out.scrollTop = out.scrollHeight;
}

function clearTerminal() {
    const out = document.getElementById('term-output');
    if (out) out.innerHTML = '';
}

async function _execCommand() {
    const ip = _termIp;
    const input = document.getElementById('term-input');
    if (!input) return;
    const cmd = input.value.trim();
    if (!cmd) return;
    input.value = '';

    const creds = nodeCredentials[ip];
    if (!creds) { termLog('<span style="color:#ffc107">No credentials. Connect first.</span>'); return; }

    termLog(`<span style="color:#81c784">$ ${cmd.replace(/</g,'&lt;')}</span>`);

    // Disable input while running
    input.disabled = true;
    const btn = document.getElementById('term-run-btn');
    if (btn) { btn.disabled = true; btn.textContent = '…'; }

    try {
        const res = await fetch('/api/iot/exec', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ip, username: creds.user, password: creds.pass, command: cmd })
        });
        const data = await res.json();

        if (data.stdout) {
            data.stdout.split('\n').forEach(l => {
                if (l !== undefined) termLog(`<span style="color:#e0e0e0">${l.replace(/</g,'&lt;')}</span>`);
            });
        }
        if (data.stderr && data.stderr.trim()) {
            data.stderr.split('\n').forEach(l => {
                if (l.trim()) termLog(`<span style="color:#ef5350">${l.replace(/</g,'&lt;')}</span>`);
            });
        }
        if (data.status === 'error') {
            termLog(`<span style="color:#ef5350">SSH Error: ${(data.stderr || 'Connection failed').replace(/</g,'&lt;')}</span>`);
        }
    } catch(e) {
        termLog(`<span style="color:#ef5350">Network error: ${e.message}</span>`);
    } finally {
        if (input) { input.disabled = false; input.focus(); }
        if (btn) { btn.disabled = false; btn.textContent = 'Run'; }
    }
}

// Keep old name for any other callers
function execCommand(ip) { _execCommand(); }

// ==========================================================================
// System Audit Log Services
// ==========================================================================
let currentAuditLogs = [];

window.fetchAuditLogs = async function() {
    const tbody = document.getElementById('audit-tbody');
    if (tbody) {
        tbody.innerHTML = '<tr class="loading"><td colspan="6" style="text-align: center; padding: 2rem;"><i class="fas fa-spinner fa-spin"></i> Accessing secure Koha audit storage...</td></tr>';
    }

    try {
        const res = await fetch('/api/audit-logs?limit=100');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        currentAuditLogs = Array.isArray(data) ? data : [];
        renderAuditLogs(currentAuditLogs);
    } catch (err) {
        console.error('Error fetching audit logs:', err);
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #e53e3e; padding: 2rem;"><i class="fas fa-exclamation-triangle"></i> Failed to load audit records: ${err.message}</td></tr>`;
        }
    }
};

window.renderAuditLogs = function(logs) {
    const tbody = document.getElementById('audit-tbody');
    if (!tbody) return;

    if (!logs || logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #888; padding: 2rem;"><i class="fas fa-info-circle"></i> No audit log records found.</td></tr>';
        return;
    }

    tbody.innerHTML = logs.map(row => {
        const actionType = (row.type || 'LOG').toUpperCase();
        let badgeClass = 'badge-access';
        if (actionType === 'INSERT' || actionType === 'ISSUE' || actionType === 'CREATE') badgeClass = 'badge-insert';
        else if (actionType === 'UPDATE' || actionType === 'MODIFY') badgeClass = 'badge-update';
        else if (actionType === 'DELETE' || actionType === 'CANCEL') badgeClass = 'badge-delete';
        else if (actionType === 'RETURN' || actionType === 'CHECKIN') badgeClass = 'badge-insert';

        const rawTime = row.timestamp ? new Date(row.timestamp).toLocaleString() : '--';
        const userName = row.user_name && row.user_name.trim() ? row.user_name : 'System / Staff';
        const userType = row.user_type || 'STAFF';
        const module = row.module || 'CIRCULATION';
        const actionInfo = row.action || '--';
        const objectId = row.object_id ?? '--';

        return `
            <tr>
                <td style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #475569;">${rawTime}</td>
                <td>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <i class="fas fa-user-circle" style="color: #64748b;"></i>
                        <span style="font-weight: 600; color: #1e293b;">${userName}</span>
                        <span style="font-size: 0.6rem; background: #e2e8f0; padding: 1px 5px; border-radius: 3px; color: #475569;">${userType}</span>
                    </div>
                </td>
                <td><span class="badge-action ${badgeClass}">${actionType}</span></td>
                <td style="font-family: 'JetBrains Mono', monospace; font-size: 0.78rem;">${actionInfo}</td>
                <td><span style="font-size: 0.72rem; font-weight: 700; color: #0284c7; background: #e0f2fe; padding: 2px 6px; border-radius: 4px;">${module}</span></td>
                <td style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #64748b;">#${objectId}</td>
            </tr>
        `;
    }).join('');
};

window.filterAuditLogs = function() {
    const input = document.getElementById('audit-search');
    if (!input) return;
    const query = input.value.trim().toLowerCase();
    if (!query) {
        renderAuditLogs(currentAuditLogs);
        return;
    }

    const filtered = currentAuditLogs.filter(row => {
        const text = [
            row.timestamp,
            row.user_name,
            row.user_type,
            row.type,
            row.action,
            row.module,
            row.object_id
        ].join(' ').toLowerCase();
        return text.includes(query);
    });

    renderAuditLogs(filtered);
};

/* ==========================================================================
   Super User Suite: User Management, Uptime, Activity & Interactive Charts
   ========================================================================== */

let allUsersList = [];
let currentActivityLogs = [];
let activeActivityCategory = 'all';
let userToDeleteTarget = null;
let systemBootEpoch = Date.now() / 1000 - 3600; // default 1 hour ago fallback

let chartActivityTimeline = null;
let chartSystemResources = null;
let chartUserRoles = null;
let chartTopUsers = null;
let heartbeatInterval = null;
let uptimeTickerInterval = null;

// Format seconds into readable string (e.g. "2d 4h 15m 30s" or "04:15:30")
function formatDuration(seconds) {
    if (!seconds || seconds <= 0) return '0s';
    const s = Math.floor(seconds);
    const days = Math.floor(s / 86400);
    const hours = Math.floor((s % 86400) / 3600);
    const mins = Math.floor((s % 3600) / 60);
    const secs = s % 60;
    
    if (days > 0) {
        return `${days}d ${hours}h ${mins}m ${secs}s`;
    }
    const pad = (n) => String(n).padStart(2, '0');
    return `${pad(hours)}:${pad(mins)}:${pad(secs)}`;
}

// Live ticking clock for system uptime
function initUptimeTicker() {
    if (uptimeTickerInterval) clearInterval(uptimeTickerInterval);
    
    const updateTick = () => {
        const now = Date.now() / 1000;
        const elapsed = Math.max(0, now - systemBootEpoch);
        const formatted = formatDuration(elapsed);
        
        const suUptime = document.getElementById('su-stat-sys-uptime');
        const stripKernel = document.getElementById('strip-kernel-uptime');
        if (suUptime) suUptime.textContent = formatted;
        if (stripKernel) stripKernel.textContent = formatted;
    };
    
    updateTick();
    uptimeTickerInterval = setInterval(updateTick, 1000);
}

// Periodic user session heartbeat
function startHeartbeat() {
    if (heartbeatInterval) clearInterval(heartbeatInterval);
    
    const sendPulse = async () => {
        if (!currentUser || !currentUser.username) return;
        try {
            await fetch('/api/superuser/heartbeat', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({ username: currentUser.username })
            });
        } catch (e) {}
    };

    sendPulse();
    heartbeatInterval = setInterval(sendPulse, 15000);
}

/* --------------------------------------------------------------------------
   User Management Functions
   -------------------------------------------------------------------------- */

window.fetchUsersList = async function() {
    const tbody = document.getElementById('users-tbody');
    if (tbody && allUsersList.length === 0) {
        tbody.innerHTML = '<tr class="loading"><td colspan="8" style="text-align: center; padding: 2rem;"><i class="fas fa-spinner fa-spin"></i> Fetching user database...</td></tr>';
    }

    try {
        const res = await fetch('/api/superuser/users', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });

        
        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                allUsersList = data.users || [];
                if (data.system_boot_time) {
                    systemBootEpoch = data.system_boot_time;
                }
                updateUserKPIs(data.stats, allUsersList);
                renderUsersTable(allUsersList);
                return;
            }
        }
    } catch (e) {
        console.error('Failed to fetch users from server:', e);
    }
};

function updateUserKPIs(stats, users) {
    const totalEl = document.getElementById('su-stat-total-users');
    const breakdownEl = document.getElementById('su-stat-role-breakdown');
    const onlineEl = document.getElementById('su-stat-online-users');
    const loginsEl = document.getElementById('su-stat-total-logins');
    const bootEl = document.getElementById('su-stat-boot-time');

    const total = users.length;
    const online = users.filter(u => u.is_online).length;
    const superCount = users.filter(u => u.role === 'superuser').length;
    const techCount = users.filter(u => u.role === 'technical').length;
    const staffCount = users.filter(u => u.role === 'staff').length;
    const totalLogins = users.reduce((acc, u) => acc + (u.total_logins || 0), 0);

    if (totalEl) totalEl.textContent = total;
    if (breakdownEl) breakdownEl.innerHTML = `<span style="color:#8b5cf6;font-weight:700;">${superCount} Super</span> &bull; <span style="color:#0284c7;font-weight:700;">${techCount} Tech</span> &bull; <span style="color:#10b981;font-weight:700;">${staffCount} Staff</span>`;
    if (onlineEl) onlineEl.textContent = `${online} / ${total} Online`;
    if (loginsEl) loginsEl.textContent = totalLogins;
    if (bootEl) {
        const bootDate = new Date(systemBootEpoch * 1000);
        bootEl.textContent = `Booted: ${bootDate.toLocaleTimeString()}`;
    }
}

function renderUsersTable(users) {
    const tbody = document.getElementById('users-tbody');
    if (!tbody) return;

    if (!users || users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #888; padding: 2rem;"><i class="fas fa-user-slash"></i> No user accounts matching filter criteria.</td></tr>';
        return;
    }

    tbody.innerHTML = users.map(user => {
        const isOnline = user.is_online;
        const uptimeStr = formatDuration(user.session_uptime_seconds);
        const lastLoginStr = user.last_login ? new Date(user.last_login * 1000).toLocaleString() : 'Never';
        const lastIp = user.last_ip || '127.0.0.1';
        
        let roleClass = 'staff';
        let roleLabel = 'STAFF';
        if (user.role === 'superuser') { roleClass = 'super'; roleLabel = 'SUPER USER'; }
        else if (user.role === 'technical') { roleClass = 'tech'; roleLabel = 'TECHNICAL'; }

        const initial = (user.name || user.username || 'U').charAt(0).toUpperCase();
        const isSelf = currentUser && currentUser.username === user.username;

        return `
            <tr>
                <td>
                    <div class="user-cell">
                        <div class="user-avatar-circle ${roleClass}">${initial}</div>
                        <div>
                            <div style="font-weight: 700; color: #0f172a;">${user.username} ${isSelf ? '<span style="font-size:0.6rem;background:#ede9fe;color:#7c3aed;padding:1px 4px;border-radius:3px;">YOU</span>' : ''}</div>
                            <div style="font-size: 0.7rem; color: #64748b;">ID: #${btoa(user.username).substring(0, 6)}</div>
                        </div>
                    </div>
                </td>
                <td>
                    <div style="font-weight: 600; color: #1e293b;">${user.name || '--'}</div>
                    <div style="font-size: 0.72rem; color: #64748b;">${user.email || '--'}</div>
                </td>
                <td>
                    <span class="badge-role-tag ${roleClass}">${roleLabel}</span>
                </td>
                <td>
                    <button class="status-pill ${user.status === 'active' ? 'active' : 'disabled'}" onclick="toggleUserStatus('${user.username}', '${user.status}')" title="Click to toggle status">
                        <i class="fas fa-${user.status === 'active' ? 'check-circle' : 'ban'}"></i> ${user.status.toUpperCase()}
                    </button>
                </td>
                <td>
                    <div class="presence-badge ${isOnline ? 'online' : 'offline'}">
                        <span class="${isOnline ? 'pulse-indicator' : ''}" style="${!isOnline ? 'width:7px;height:7px;border-radius:50%;background:#cbd5e1;' : ''}"></span>
                        <span>${isOnline ? 'ONLINE' : 'OFFLINE'}</span>
                    </div>
                </td>
                <td>
                    <div style="font-family:'JetBrains Mono', monospace; font-size: 0.76rem; font-weight: 600; color: #0f172a;">
                        <i class="fas fa-stopwatch" style="color: #8b5cf6; margin-right: 3px;"></i> ${uptimeStr}
                    </div>
                    <div style="font-size: 0.68rem; color: #64748b;">Logins: ${user.total_logins || 0}</div>
                </td>
                <td>
                    <div style="font-size: 0.74rem; color: #334155;">${lastLoginStr}</div>
                    <div style="font-family:'JetBrains Mono', monospace; font-size: 0.68rem; color: #94a3b8;"><i class="fas fa-network-wired"></i> ${lastIp}</div>
                </td>
                <td style="text-align: center;">
                    <div style="display: inline-flex; gap: 4px;">
                        <button class="btn-tbl-action" onclick="openEditUserModal('${user.username}')" title="Edit User">
                            <i class="fas fa-edit" style="color: #0284c7;"></i>
                        </button>
                        ${!isSelf ? `
                            <button class="btn-tbl-action btn-tbl-del" onclick="openDeleteUserModal('${user.username}')" title="Delete User">
                                <i class="fas fa-trash-alt"></i>
                            </button>
                        ` : `
                            <button class="btn-tbl-action" disabled style="opacity: 0.4; cursor: not-allowed;" title="Cannot delete your own active account">
                                <i class="fas fa-lock"></i>
                            </button>
                        `}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

window.filterUsersTable = function() {
    const search = (document.getElementById('user-search-input')?.value || '').toLowerCase().trim();
    const roleFilter = document.getElementById('user-role-filter')?.value || 'all';
    const statusFilter = document.getElementById('user-status-filter')?.value || 'all';

    const filtered = allUsersList.filter(user => {
        const matchesSearch = !search || [
            user.username,
            user.name,
            user.email,
            user.role
        ].some(val => (val || '').toLowerCase().includes(search));

        const matchesRole = roleFilter === 'all' || user.role === roleFilter;
        const matchesStatus = statusFilter === 'all' || user.status === statusFilter;

        return matchesSearch && matchesRole && matchesStatus;
    });

    renderUsersTable(filtered);
};

// Add User Modal
window.openAddUserModal = function() {
    const modal = document.getElementById('modal-add-user');
    const form = document.getElementById('form-add-user');
    const err = document.getElementById('add-user-error');
    if (form) form.reset();
    if (err) err.style.display = 'none';
    if (modal) modal.style.display = 'flex';
};

window.closeAddUserModal = function() {
    const modal = document.getElementById('modal-add-user');
    if (modal) modal.style.display = 'none';
};

window.submitAddUser = async function(e) {
    if (e) e.preventDefault();
    const err = document.getElementById('add-user-error');
    const btn = document.getElementById('btn-save-add-user');

    const username = document.getElementById('add-username').value.trim();
    const name = document.getElementById('add-name').value.trim();
    const email = document.getElementById('add-email').value.trim();
    const role = document.getElementById('add-role').value;
    const password = document.getElementById('add-password').value.trim();
    const status = document.getElementById('add-status').value;

    if (!username || !password || !name) {
        if (err) { err.textContent = 'Please fill in all required fields.'; err.style.display = 'flex'; }
        return;
    }

    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating...'; }

    try {
        const res = await fetch('/api/superuser/users', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({ username, password, name, email, role, status })
        });

        if (res.ok) {
            const data = await res.json();
            showToast('User Created', `User account '${username}' created successfully.`, 'success');
            closeAddUserModal();
            fetchUsersList();
            fetchActivityLogs();
            return;
        } else {
            const errData = await res.json();
            throw new Error(errData.detail || 'Failed to create user');
        }
    } catch (apiErr) {
        if (err) { err.textContent = apiErr.message || 'Failed to create user'; err.style.display = 'flex'; }
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-check"></i> Create Account'; }
    }
};

// Edit User Modal
window.openEditUserModal = function(username) {
    const user = allUsersList.find(u => u.username === username);
    if (!user) return;

    document.getElementById('edit-username-hidden').value = user.username;
    document.getElementById('edit-username-display').value = user.username;
    document.getElementById('edit-name').value = user.name || '';
    document.getElementById('edit-email').value = user.email || '';
    document.getElementById('edit-role').value = user.role || 'staff';
    document.getElementById('edit-status').value = user.status || 'active';
    document.getElementById('edit-password').value = '';

    const err = document.getElementById('edit-user-error');
    if (err) err.style.display = 'none';

    document.getElementById('modal-edit-user').style.display = 'flex';
};

window.closeEditUserModal = function() {
    const modal = document.getElementById('modal-edit-user');
    if (modal) modal.style.display = 'none';
};

window.submitEditUser = async function(e) {
    if (e) e.preventDefault();
    const err = document.getElementById('edit-user-error');
    const btn = document.getElementById('btn-save-edit-user');

    const username = document.getElementById('edit-username-hidden').value;
    const name = document.getElementById('edit-name').value.trim();
    const email = document.getElementById('edit-email').value.trim();
    const role = document.getElementById('edit-role').value;
    const status = document.getElementById('edit-status').value;
    const password = document.getElementById('edit-password').value.trim();

    const payload = { name, email, role, status };
    if (password) payload.password = password;

    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...'; }

    try {
        const res = await fetch(`/api/superuser/users/${username}`, {
            method: 'PUT',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            showToast('User Updated', `Account '${username}' updated successfully.`, 'success');
            closeEditUserModal();
            fetchUsersList();
            fetchActivityLogs();
            return;
        } else {
            const errData = await res.json();
            throw new Error(errData.detail || 'Failed to update user');
        }
    } catch (apiErr) {
        if (err) { err.textContent = apiErr.message || 'Failed to update user'; err.style.display = 'flex'; }
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-save"></i> Save Changes'; }
    }
};

// Toggle User Status directly from table pill
window.toggleUserStatus = async function(username, currentStatus) {
    const newStatus = currentStatus === 'active' ? 'disabled' : 'active';
    try {
        const res = await fetch(`/api/superuser/users/${username}`, {
            method: 'PUT',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({ status: newStatus })
        });
        if (res.ok) {
            showToast('Status Updated', `User '${username}' is now ${newStatus.toUpperCase()}.`, 'info');
            fetchUsersList();
            return;
        }
    } catch (e) {
        showToast('Error', 'Failed to update user status.', 'error');
    }
};

// Delete User Modal
window.openDeleteUserModal = function(username) {
    userToDeleteTarget = username;
    const targetEl = document.getElementById('delete-user-target');
    if (targetEl) targetEl.textContent = username;
    document.getElementById('modal-delete-user').style.display = 'flex';
};

window.closeDeleteUserModal = function() {
    userToDeleteTarget = null;
    document.getElementById('modal-delete-user').style.display = 'none';
};

window.confirmDeleteUser = async function() {
    if (!userToDeleteTarget) return;
    const username = userToDeleteTarget;
    const btn = document.getElementById('btn-confirm-delete-user');

    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Deleting...'; }

    try {
        const res = await fetch(`/api/superuser/users/${username}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });

        if (res.ok) {
            showToast('User Deleted', `User account '${username}' has been removed.`, 'warning');
            closeDeleteUserModal();
            fetchUsersList();
            fetchActivityLogs();
            return;
        } else {
            const errData = await res.json();
            showToast('Delete Failed', errData.detail || 'Could not delete user', 'error');
        }
    } catch (e) {
        showToast('Delete Failed', 'Server error while removing user', 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-trash-alt"></i> Delete Account'; }
    }
};


/* --------------------------------------------------------------------------
   Analytics & Chart.js Engine (Live Real-Time Server Data)
   -------------------------------------------------------------------------- */

window.fetchAnalyticsData = async function() {
    try {
        const [analyticsRes, uptimeRes] = await Promise.all([
            fetch('/api/superuser/analytics', { headers: { 'Authorization': `Bearer ${authToken}` } }),
            fetch('/api/superuser/system-uptime', { headers: { 'Authorization': `Bearer ${authToken}` } })
        ]);

        let analyticsData = null;

        if (analyticsRes.ok) {
            const aJson = await analyticsRes.json();
            analyticsData = aJson.analytics;
            
            const iotNodesEl = document.getElementById('strip-iot-nodes');
            if (iotNodesEl) iotNodesEl.textContent = `${aJson.iot_online_nodes || 0} / ${aJson.iot_nodes_count || 0} ONLINE`;
            
            const dbStatusEl = document.getElementById('strip-db-status');
            if (dbStatusEl) {
                dbStatusEl.textContent = aJson.db_healthy ? 'HEALTHY' : 'DEGRADED';
                dbStatusEl.style.color = aJson.db_healthy ? '#10b981' : '#f59e0b';
            }
        }

        if (uptimeRes.ok) {
            const uptimeData = await uptimeRes.json();
            if (uptimeData.boot_time) systemBootEpoch = uptimeData.boot_time;
            
            const wsClientsEl = document.getElementById('strip-ws-clients');
            if (wsClientsEl && uptimeData.subsystems?.websocket_hub) {
                wsClientsEl.textContent = `${uptimeData.subsystems.websocket_hub.clients} ACTIVE`;
            }
        }

        if (analyticsData) {
            renderCharts(analyticsData, allUsersList);
        }
    } catch (e) {
        console.error('Failed to fetch real-time analytics:', e);
    }
};

function renderCharts(data, users) {
    if (typeof Chart === 'undefined') {
        console.warn('Chart.js not loaded yet');
        return;
    }

    if (!data) return;

    const t = data.timeline || { labels: [], actions: [], logins: [], errors: [] };
    const topU = data.top_users || { labels: [], data: [] };
    const tele = data.system_telemetry || { cpu_percent: 0, memory_used_mb: 0, memory_total_mb: 0, memory_percent: 0 };

    // 1. Real-Time Hourly Timeline Chart (Smooth Line/Area)
    const ctxTimeline = document.getElementById('chart-activity-timeline');
    if (ctxTimeline) {
        if (chartActivityTimeline) chartActivityTimeline.destroy();
        chartActivityTimeline = new Chart(ctxTimeline, {
            type: 'line',
            data: {
                labels: t.labels,
                datasets: [
                    {
                        label: 'System Actions',
                        data: t.actions,
                        borderColor: '#8b5cf6',
                        backgroundColor: 'rgba(139, 92, 246, 0.12)',
                        borderWidth: 2,
                        tension: 0.35,
                        fill: true
                    },
                    {
                        label: 'User Logins',
                        data: t.logins,
                        borderColor: '#0284c7',
                        backgroundColor: 'rgba(2, 132, 199, 0.08)',
                        borderWidth: 2,
                        tension: 0.35,
                        fill: true
                    },
                    {
                        label: 'Errors / Warnings',
                        data: t.errors,
                        borderColor: '#dc2626',
                        backgroundColor: 'rgba(220, 38, 38, 0.1)',
                        borderWidth: 1.5,
                        tension: 0.2,
                        fill: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11, family: "'Open Sans', sans-serif" } } },
                    tooltip: { mode: 'index', intersect: false }
                },
                scales: {
                    x: { grid: { color: 'rgba(0,0,0,0.03)' }, ticks: { font: { size: 10 } } },
                    y: { grid: { color: 'rgba(0,0,0,0.05)' }, beginAtZero: true, ticks: { precision: 0, font: { size: 10 } } }
                }
            }
        });
    }

    // 2. Real System Resources Chart (Live OS CPU & RAM Metrics)
    const ctxRes = document.getElementById('chart-resources');
    if (ctxRes) {
        if (chartSystemResources) chartSystemResources.destroy();
        
        const resCpu = t.labels.map(() => tele.cpu_percent);
        const resMem = t.labels.map(() => tele.memory_used_mb);

        chartSystemResources = new Chart(ctxRes, {
            type: 'line',
            data: {
                labels: t.labels,
                datasets: [
                    {
                        label: 'CPU Utilization (%)',
                        data: resCpu,
                        borderColor: '#0ea5e9',
                        backgroundColor: 'rgba(14, 165, 233, 0.15)',
                        borderWidth: 2,
                        tension: 0.3,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Memory RSS (MB)',
                        data: resMem,
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } }
                },
                scales: {
                    x: { grid: { color: 'rgba(0,0,0,0.03)' }, ticks: { font: { size: 10 } } },
                    y: { type: 'linear', position: 'left', min: 0, max: 100, ticks: { callback: v => v + '%' } },
                    y1: { type: 'linear', position: 'right', grid: { drawOnChartArea: false }, ticks: { callback: v => v + ' MB' } }
                }
            }
        });
    }

    // 3. User Roles Doughnut Chart (From Live Registered Users)
    const ctxRoles = document.getElementById('chart-roles');
    if (ctxRoles) {
        if (chartUserRoles) chartUserRoles.destroy();
        
        const superCount = users.filter(u => u.role === 'superuser').length;
        const techCount = users.filter(u => u.role === 'technical').length;
        const staffCount = users.filter(u => u.role === 'staff').length;

        chartUserRoles = new Chart(ctxRoles, {
            type: 'doughnut',
            data: {
                labels: ['Super Users', 'Technical Admins', 'Library Staff'],
                datasets: [{
                    data: [superCount, techCount, staffCount],
                    backgroundColor: ['#8b5cf6', '#0284c7', '#10b981'],
                    hoverOffset: 6,
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } }
                }
            }
        });
    }

    // 4. Real Top Active Users Bar Chart
    const ctxTopUsers = document.getElementById('chart-top-users');
    if (ctxTopUsers) {
        if (chartTopUsers) chartTopUsers.destroy();
        chartTopUsers = new Chart(ctxTopUsers, {
            type: 'bar',
            data: {
                labels: topU.labels,
                datasets: [{
                    label: 'Operations & Transactions',
                    data: topU.data,
                    backgroundColor: ['#8b5cf6', '#0284c7', '#10b981', '#f59e0b', '#ec4899', '#3b82f6', '#14b8a6', '#6366f1'],
                    borderRadius: 4
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { grid: { color: 'rgba(0,0,0,0.04)' }, beginAtZero: true },
                    y: { grid: { display: false }, ticks: { font: { weight: '600', size: 11 } } }
                }
            }
        });
    }
}

/* --------------------------------------------------------------------------
   Activity Logging & Audit Stream (Live Records)
   -------------------------------------------------------------------------- */

window.fetchActivityLogs = async function() {
    try {
        const res = await fetch('/api/superuser/activity?limit=100', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (res.ok) {
            const data = await res.json();
            currentActivityLogs = data.activities || [];
            renderActivityTable(currentActivityLogs);
            return;
        }
    } catch (e) {
        console.error('Failed to fetch real activity logs:', e);
    }
};


function renderActivityTable(activities) {
    const tbody = document.getElementById('activity-tbody');
    if (!tbody) return;

    if (!activities || activities.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #888; padding: 2rem;"><i class="fas fa-history"></i> No activity logs matching current filter.</td></tr>';
        return;
    }

    tbody.innerHTML = activities.map(act => {
        let statusBadge = '<span class="status-badge online" style="font-size:0.65rem;padding:2px 6px;">SUCCESS</span>';
        if (act.status === 'FAILED' || act.status === 'ERROR') {
            statusBadge = '<span class="status-badge offline" style="font-size:0.65rem;padding:2px 6px;">FAILED</span>';
        } else if (act.status === 'WARN') {
            statusBadge = '<span style="font-size:0.65rem;padding:2px 6px;background:#fef3c7;color:#d97706;border-radius:3px;font-weight:700;">WARN</span>';
        }

        let catBadge = `<span style="font-size:0.68rem;font-weight:700;background:#f1f5f9;color:#475569;padding:2px 6px;border-radius:3px;">${(act.category || 'SYSTEM').toUpperCase()}</span>`;
        if (act.category === 'auth') catBadge = '<span style="font-size:0.68rem;font-weight:700;background:#ede9fe;color:#7c3aed;padding:2px 6px;border-radius:3px;">AUTH</span>';
        else if (act.category === 'user_mgmt') catBadge = '<span style="font-size:0.68rem;font-weight:700;background:#e0f2fe;color:#0284c7;padding:2px 6px;border-radius:3px;">USERS</span>';
        else if (act.category === 'security') catBadge = '<span style="font-size:0.68rem;font-weight:700;background:#fee2e2;color:#dc2626;padding:2px 6px;border-radius:3px;">SECURITY</span>';

        return `
            <tr>
                <td style="font-family:'JetBrains Mono', monospace; font-size: 0.74rem; color: #475569;">${act.timestamp}</td>
                <td>
                    <div style="font-weight: 700; color: #1e293b;"><i class="fas fa-user-circle" style="color: #8b5cf6; margin-right: 4px;"></i>${act.username}</div>
                </td>
                <td><span class="badge-role-tag ${act.role === 'superuser' ? 'super' : (act.role === 'technical' ? 'tech' : 'staff')}">${act.role.toUpperCase()}</span></td>
                <td style="font-family:'JetBrains Mono', monospace; font-size: 0.76rem; font-weight: 600; color: #0f172a;">${act.action}</td>
                <td>${catBadge}</td>
                <td style="font-size: 0.78rem; color: #334155;">${act.details}</td>
                <td style="font-family:'JetBrains Mono', monospace; font-size: 0.72rem; color: #64748b;">${act.ip_address}</td>
                <td>${statusBadge}</td>
            </tr>
        `;
    }).join('');
}

window.filterActivityCategory = function(cat) {
    activeActivityCategory = cat;
    document.querySelectorAll('.log-filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-cat') === cat);
    });
    filterActivityLogs();
};

window.filterActivityLogs = function() {
    const search = (document.getElementById('activity-search-input')?.value || '').toLowerCase().trim();

    const filtered = currentActivityLogs.filter(act => {
        const matchesCat = activeActivityCategory === 'all' || (act.category || '').toLowerCase() === activeActivityCategory;
        const matchesSearch = !search || [
            act.timestamp,
            act.username,
            act.role,
            act.action,
            act.category,
            act.details,
            act.ip_address
        ].some(val => (val || '').toLowerCase().includes(search));

        return matchesCat && matchesSearch;
    });

    renderActivityTable(filtered);
};

window.exportActivityLogsCSV = function() {
    if (!currentActivityLogs || currentActivityLogs.length === 0) {
        showToast('Export Empty', 'No activity records available to export.', 'warning');
        return;
    }

    const headers = ['Timestamp', 'Username', 'Role', 'Action', 'Category', 'Details', 'IP Address', 'Status'];
    const rows = currentActivityLogs.map(a => [
        `"${a.timestamp}"`,
        `"${a.username}"`,
        `"${a.role}"`,
        `"${a.action}"`,
        `"${a.category}"`,
        `"${(a.details || '').replace(/"/g, '""')}"`,
        `"${a.ip_address}"`,
        `"${a.status}"`
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `jpl_activity_logs_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast('Export Complete', 'Activity logs CSV downloaded.', 'success');
};

window.clearActivityLogsPrompt = async function() {
    if (!confirm('Are you sure you want to clear the entire platform activity log history? This action is permanent.')) {
        return;
    }

    try {
        const res = await fetch('/api/superuser/activity', {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (res.ok) {
            showToast('Logs Cleared', 'Activity history has been cleared.', 'info');
            fetchActivityLogs();
            return;
        }
    } catch (e) {}

    currentActivityLogs = [];
    renderActivityTable([]);
    showToast('Logs Cleared', 'Activity history reset.', 'info');
};



