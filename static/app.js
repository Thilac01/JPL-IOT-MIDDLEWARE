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
    document.getElementById('stat-events').textContent = `${eventsThisMin}/min`;
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
    initWebSocket();
    
    // Initial data synchronization
    syncAllData();

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

            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            tabPanes.forEach(pane => {
                pane.classList.remove('active');
                if (pane.id === targetTab) pane.classList.add('active');
            });

            breadcrumbPath.innerHTML = `<b>${targetTab.toUpperCase()}</b>`;
            
            if (targetTab === 'live-tables' && document.getElementById('table-selector').options.length <= 1) {
                fetchTableList();
            }
            if (targetTab === 'iot-maps') {
                fetchIotNodes();
                setTimeout(drawLines, 100);
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
    } else if (event.table === 'old_issues') {
        category = 'RETURN-IN';
        message = `Recovery: Asset ${event.data?.barcode || event.data?.issue_id} returned to shelf`;
        fetchReturns();
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
    const entry = document.createElement('div');
    entry.className = `log-line ${category}`;
    const time = new Date().toLocaleTimeString('en-US', { hour12: false });
    
    entry.innerHTML = `
        <span class="log-time">[${time}]</span>
        <span class="log-tag">${tag}</span>
        <span class="log-msg">${message}</span>
    `;

    stream.prepend(entry);
    if (stream.children.length > 50) stream.lastChild.remove();
}

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
        const overdue = data.overdue || 0;
        document.getElementById('stat-alerts').textContent = overdue;
        document.getElementById('stat-loans').textContent = data.active_loans || 0;
        
        // Update Alerts content
        const alertsContent = document.getElementById('alerts-content');
        if (overdue > 0) {
            alertsContent.innerHTML = `<div style="color: #dc3545; font-weight: bold;"><i class="fas fa-exclamation-triangle"></i> Warning: ${overdue} unacknowledged alerts require attention.</div>`;
        } else {
            alertsContent.innerHTML = `No unacknowledged alerts found.`;
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

