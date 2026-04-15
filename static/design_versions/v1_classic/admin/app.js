/**
 * Admin Panel JavaScript - Enhanced
 * 챗봇 관리자 페이지 기능 (계층 뷰, 권한 관리, 통계 대시보드 포함)
 */

// Global state
let chatbots = [];
let currentFilter = 'all';
let currentView = 'store';
let deleteTargetId = null;
let detailChatbotId = null;

// DB 목록 (mock)
const availableDBs = ['db_new', 'db_001', 'db_002', 'db_003', 'db_004', 
                      'db_hr_policy', 'db_hr_benefit', 'db_hr_overview',
                      'db_backend', 'db_frontend', 'db_devops', 'db_tech_overview',
                      'db_rtl_verilog', 'db_rtl_synthesis'];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadChatbots();
    loadStats();
    setupEventListeners();
});

// ===== 뷰 전환 =====
function switchView(viewName) {
    currentView = viewName;
    
    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.view === viewName) {
            item.classList.add('active');
        }
    });
    
    // Show/hide views
    document.querySelectorAll('.view').forEach(view => {
        view.classList.remove('active');
    });
    document.getElementById(`view-${viewName}`).classList.add('active');
    
    // Load view-specific data
    if (viewName === 'hierarchy') {
        loadHierarchy();
    } else if (viewName === 'users') {
        loadUsers();
    } else if (viewName === 'stats') {
        loadStatsDashboard();
    }
}

// ===== 챗봇 목록 로드 =====
async function loadChatbots() {
    const grid = document.getElementById('chatbotGrid');
    grid.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    
    try {
        const response = await fetch('/admin/api/chatbots');
        if (!response.ok) throw new Error('Failed to load');
        
        chatbots = await response.json();
        renderChatbots();
        populateParentSelect();
        loadStoreStats();
    } catch (error) {
        console.error('Error loading chatbots:', error);
        grid.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>로드 실패</h3><p>${error.message}</p></div>`;
    }
}

// ===== 통계 로드 =====
async function loadStats() {
    try {
        const response = await fetch('/admin/api/stats');
        if (!response.ok) return;
        
        const stats = await response.json();
        document.getElementById('statTotal').textContent = stats.total;
        document.getElementById('statParents').textContent = stats.parents;
        document.getElementById('statActive').textContent = stats.active;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

function loadStoreStats() {
    // Calculate from current data
    const total = chatbots.length;
    const parents = chatbots.filter(c => c.type === 'parent').length;
    const active = chatbots.filter(c => c.active).length;
    
    document.getElementById('statTotal').textContent = total;
    document.getElementById('statParents').textContent = parents;
    document.getElementById('statActive').textContent = active;
}

// ===== 챗봇 카드 렌더링 =====
function renderChatbots() {
    const grid = document.getElementById('chatbotGrid');
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    
    let filtered = chatbots.filter(cb => {
        if (currentFilter !== 'all' && cb.type !== currentFilter) return false;
        if (searchTerm && !cb.name.toLowerCase().includes(searchTerm) && 
            !cb.description.toLowerCase().includes(searchTerm) &&
            !cb.id.toLowerCase().includes(searchTerm)) return false;
        return true;
    });
    
    if (filtered.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🔍</div>
                <h3>챗봇을 찾을 수 없습니다</h3>
                <p>검색어를 변경하거나 새 챗봇을 만들어보세요.</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = filtered.map(chatbot => createCardHTML(chatbot)).join('');
}

function createCardHTML(chatbot) {
    const badgeClass = chatbot.type === 'parent' ? 'badge-parent' : 
                       chatbot.type === 'child' ? 'badge-child' : 'badge-standalone';
    const badgeText = chatbot.type === 'parent' ? '상위 Agent' : 
                      chatbot.type === 'child' ? '하위 Agent' : '단독';
    
    const icon = chatbot.type === 'parent' ? '🤖' : 
                 chatbot.type === 'child' ? '👤' : '💬';
    
    let hierarchyInfo = '';
    if (chatbot.type === 'child' && chatbot.parent) {
        const parent = chatbots.find(c => c.id === chatbot.parent);
        if (parent) {
            hierarchyInfo = `<div class="hierarchy-info"><span>🔗 ${parent.name}</span></div>`;
        }
    } else if (chatbot.type === 'parent' && chatbot.sub_chatbots?.length > 0) {
        hierarchyInfo = `<div class="hierarchy-info"><span>👥 하위 ${chatbot.sub_chatbots.length}개</span></div>`;
    }
    
    const dbTags = chatbot.db_ids?.map(db => `<span class="db-tag">${db}</span>`).join('') || '';
    
    return `
        <div class="chatbot-card" data-id="${chatbot.id}">
            <span class="card-badge ${badgeClass}">${badgeText}</span>
            <div class="card-icon">${icon}</div>
            <h3 class="card-title">${chatbot.name}</h3>
            <p class="card-desc">${chatbot.description || '설명 없음'}</p>
            ${hierarchyInfo}
            <div class="card-db-tags">${dbTags}</div>
            <div class="card-actions">
                <button class="btn-icon" onclick="openDetailModal('${chatbot.id}')" title="상세 보기">👁️</button>
                <button class="btn-icon btn-chat" onclick="startChat('${chatbot.id}')" title="채팅하기">💬</button>
                <button class="btn-icon btn-delete" onclick="openDeleteModal('${chatbot.id}', '${chatbot.name}')" title="삭제">🗑️</button>
            </div>
        </div>
    `;
}

// ===== 필터 =====
function filterChatbots(type) {
    currentFilter = type;
    
    document.querySelectorAll('.filter-tabs .tab').forEach(tab => {
        tab.classList.remove('active');
        if (tab.dataset.filter === type) tab.classList.add('active');
    });
    
    renderChatbots();
}

// ===== 계층 뷰 (3-tier 지원) =====
async function loadHierarchy() {
    const container = document.getElementById('hierarchyContainer');
    container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    
    try {
        const response = await fetch('/admin/api/chatbots');
        const bots = await response.json();
        
        // Build 3-tier hierarchy tree
        // Level 0: Root nodes (no parent)
        const roots = bots.filter(b => !b.parent_id || b.level === 0);
        
        const html = roots.map(root => renderHierarchyTree(root, bots, 0)).join('');
        
        // Add standalone section (not part of hierarchy)
        const standalone = bots.filter(b => b.level === undefined || (b.level === 0 && !b.parent_id && !roots.includes(b)));
        const standaloneHtml = standalone.map(s => `
            <div class="hierarchy-node standalone" data-level="0">
                <span class="icon">💬</span>
                <span class="name">${s.name}</span>
                <span class="id">${s.id}</span>
                <span class="badge">단독</span>
            </div>
        `).join('');
        
        container.innerHTML = `
            <div class="hierarchy-header">
                <h3 class="section-title">🌳 3-Tier Agent 계층 구조</h3>
                <div class="hierarchy-controls">
                    <button class="btn btn-sm btn-secondary" onclick="expandAllNodes()">전체 펼치기</button>
                    <button class="btn btn-sm btn-secondary" onclick="collapseAllNodes()">전체 접기</button>
                </div>
            </div>
            <div class="hierarchy-trees">
                ${html || '<div class="empty-state">Root Agent가 없습니다</div>'}
            </div>
            
            <h3 class="section-title">💬 단독 챗봇</h3>
            <div class="hierarchy-standalone-list">
                ${standaloneHtml || '<div class="hierarchy-empty">단독 챗봇 없음</div>'}
            </div>
            
            <div class="hierarchy-legend">
                <span class="legend-item"><span class="legend-color root"></span> Root (Level 0)</span>
                <span class="legend-item"><span class="legend-color parent"></span> Parent (Level 1)</span>
                <span class="legend-item"><span class="legend-color child"></span> Child (Level 2+)</span>
                <span class="legend-item"><span class="legend-color leaf"></span> Leaf (하위 없음)</span>
            </div>
        `;
        
        // Initialize expand/collapse state
        initHierarchyInteractions();
    } catch (error) {
        container.innerHTML = `<div class="error">로드 실패: ${error.message}</div>`;
    }
}

function renderHierarchyTree(node, allBots, depth = 0) {
    // Get children using level/parent_id
    const children = allBots.filter(b => b.parent_id === node.id);
    const isLeaf = children.length === 0;
    
    // Determine node type based on level
    let nodeClass = 'child';
    let icon = '👤';
    if (node.level === 0) {
        nodeClass = 'root';
        icon = '🏢';
    } else if (node.level === 1) {
        nodeClass = 'parent';
        icon = '🤖';
    }
    
    if (isLeaf) {
        nodeClass += ' leaf';
        icon = '👤';
    }
    
    const hasChildren = children.length > 0;
    const expandIcon = hasChildren ? '<span class="expand-icon">▼</span>' : '';
    
    // Recursively render children
    const childrenHtml = hasChildren ? `
        <div class="hierarchy-children" data-depth="${depth + 1}">
            ${children.map(child => renderHierarchyTree(child, allBots, depth + 1)).join('')}
        </div>
    ` : '';
    
    return `
        <div class="hierarchy-branch" data-level="${node.level || 0}" data-id="${node.id}">
            <div class="hierarchy-node ${nodeClass}" onclick="toggleNode('${node.id}')" style="padding-left: ${depth * 24}px;">
                ${expandIcon}
                <span class="icon">${icon}</span>
                <span class="name">${node.name}</span>
                <span class="id">${node.id}</span>
                <span class="badge">Lv.${node.level !== undefined ? node.level : '?'}</span>
                ${isLeaf ? '<span class="badge badge-leaf">Leaf</span>' : `<span class="badge badge-count">하위 ${children.length}개</span>`}
            </div>
            ${childrenHtml}
        </div>
    `;
}

function initHierarchyInteractions() {
    // All nodes expanded by default
    document.querySelectorAll('.hierarchy-children').forEach(el => {
        el.style.display = 'block';
    });
}

function toggleNode(nodeId) {
    const branch = document.querySelector(`.hierarchy-branch[data-id="${nodeId}"]`);
    if (!branch) return;
    
    const children = branch.querySelector(':scope > .hierarchy-children');
    const expandIcon = branch.querySelector(':scope > .hierarchy-node > .expand-icon');
    
    if (children) {
        const isVisible = children.style.display !== 'none';
        children.style.display = isVisible ? 'none' : 'block';
        if (expandIcon) {
            expandIcon.textContent = isVisible ? '▶' : '▼';
        }
    }
}

function expandAllNodes() {
    document.querySelectorAll('.hierarchy-children').forEach(el => {
        el.style.display = 'block';
    });
    document.querySelectorAll('.expand-icon').forEach(el => {
        el.textContent = '▼';
    });
}

function collapseAllNodes() {
    // Keep only root level visible
    document.querySelectorAll('.hierarchy-children').forEach(el => {
        if (parseInt(el.dataset.depth) > 0) {
            el.style.display = 'none';
        }
    });
    document.querySelectorAll('.expand-icon').forEach(el => {
        el.textContent = '▶';
    });
}

// ===== 사용자 권한 뷰 =====
let currentUserPermissions = [];

async function loadUsers() {
    const container = document.getElementById('permissionsContainer');
    container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    
    try {
        // Get stats for users
        const response = await fetch('/api/permissions/admin/stats');
        const stats = await response.json();
        
        // Store user data globally for filtering
        window.userPermissionsData = stats.user_stats;
        
        renderUsersList(stats.user_stats);
    } catch (error) {
        container.innerHTML = `<div class="error">로드 실패: ${error.message}</div>`;
    }
}

function renderUsersList(userStats) {
    const container = document.getElementById('permissionsContainer');
    
    if (!userStats || Object.keys(userStats).length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">👥</div>
                <h3>사용자 권한 정보 없음</h3>
                <p>권한을 추가하여 사용자를 관리하세요.</p>
            </div>
        `;
        return;
    }
    
    const userListHtml = Object.entries(userStats).map(([knoxId, data]) => `
        <div class="user-permission-card" data-knox-id="${knoxId}">
            <div class="user-info">
                <h4>${knoxId}</h4>
                <div class="user-stats">
                    <span class="badge badge-success">접근 가능 ${data.accessible}개</span>
                    <span class="badge badge-secondary">전체 ${data.total}개</span>
                </div>
            </div>
            <div class="user-actions">
                <button class="btn btn-sm btn-secondary" onclick="viewUserPermissions('${knoxId}')">상세 보기</button>
            </div>
        </div>
    `).join('');
    
    container.innerHTML = `
        <div class="users-list">
            ${userListHtml}
        </div>
    `;
}

function filterUsers() {
    const searchTerm = document.getElementById('userSearchInput')?.value.toLowerCase() || '';
    const userCards = document.querySelectorAll('.user-permission-card');
    
    userCards.forEach(card => {
        const knoxId = card.getAttribute('data-knox-id') || '';
        if (knoxId.toLowerCase().includes(searchTerm)) {
            card.style.display = 'flex';
        } else {
            card.style.display = 'none';
        }
    });
}

async function viewUserPermissions(knoxId) {
    try {
        const response = await fetch(`/api/permissions/users/${knoxId}`);
        if (!response.ok) throw new Error('조회 실패');
        
        const data = await response.json();
        currentUserPermissions = data.permissions;
        
        // Build modal content
        const permsHtml = data.permissions.map(p => `
            <div class="permission-item ${p.can_access ? 'granted' : 'denied'}">
                <div class="permission-info">
                    <span class="chatbot-name">${p.chatbot_id}</span>
                    <span class="permission-date">${p.created_at ? new Date(p.created_at).toLocaleDateString() : '-'}</span>
                </div>
                <div class="permission-actions">
                    <label class="toggle-switch-small">
                        <input type="checkbox" ${p.can_access ? 'checked' : ''} 
                               onchange="updateUserPermission('${knoxId}', '${p.chatbot_id}', this.checked)">
                        <span class="slider"></span>
                    </label>
                    <button class="btn-icon btn-delete" onclick="deleteUserPermission('${knoxId}', '${p.chatbot_id}')" title="권한 삭제">🗑️</button>
                </div>
            </div>
        `).join('');
        
        const content = `
            <div class="user-detail-header">
                <div class="user-profile">
                    <span class="user-avatar">👤</span>
                    <div class="user-info">
                        <h4>${knoxId}</h4>
                        <p>접근 가능: <strong>${data.accessible_count}</strong> / ${data.total}개 챗봇</p>
                    </div>
                </div>
            </div>
            <div class="permissions-detail-list">
                ${permsHtml || '<p class="empty">설정된 권한이 없습니다.</p>'}
            </div>
        `;
        
        document.getElementById('userDetailTitle').textContent = `${knoxId} - 권한 상세`;
        document.getElementById('userDetailContent').innerHTML = content;
        document.getElementById('userDetailModal').classList.add('active');
        
    } catch (error) {
        console.error('Error loading user permissions:', error);
        showToast('권한 조회 실패: ' + error.message, 'error');
    }
}

async function updateUserPermission(knoxId, chatbotId, canAccess) {
    try {
        const response = await fetch(`/api/permissions/${knoxId}/${chatbotId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ can_access: canAccess })
        });
        
        if (!response.ok) throw new Error('수정 실패');
        
        showToast('권한이 수정되었습니다', 'success');
        // Refresh user detail view
        viewUserPermissions(knoxId);
        // Refresh user list
        loadUsers();
    } catch (error) {
        showToast('권한 수정 실패: ' + error.message, 'error');
    }
}

async function deleteUserPermission(knoxId, chatbotId) {
    if (!confirm(`정말로 ${chatbotId}에 대한 권한을 삭제하시겠습니까?`)) return;
    
    try {
        const response = await fetch(`/api/permissions/${knoxId}/${chatbotId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) throw new Error('삭제 실패');
        
        showToast('권한이 삭제되었습니다', 'success');
        // Refresh user detail view
        viewUserPermissions(knoxId);
        // Refresh user list
        loadUsers();
    } catch (error) {
        showToast('권한 삭제 실패: ' + error.message, 'error');
    }
}

function closeUserDetailModal() {
    document.getElementById('userDetailModal').classList.remove('active');
}

// ===== 통계 대시보드 =====
async function loadStatsDashboard() {
    const container = document.getElementById('statsDashboard');
    container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    
    try {
        // Chatbot stats
        const chatbotRes = await fetch('/admin/api/stats');
        const chatbotStats = await chatbotRes.json();
        
        // Permission stats
        const permRes = await fetch('/api/permissions/admin/stats');
        const permStats = await permRes.json();
        
        container.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card large">
                    <div class="stat-icon">🤖</div>
                    <div class="stat-value">${chatbotStats.total}</div>
                    <div class="stat-label">전체 챗봇</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${chatbotStats.parents}</div>
                    <div class="stat-label">상위 Agent</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${chatbotStats.total - chatbotStats.parents}</div>
                    <div class="stat-label">하위/단독</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${permStats.unique_users}</div>
                    <div class="stat-label">사용자</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${permStats.total_permissions}</div>
                    <div class="stat-label">권한 설정</div>
                </div>
            </div>
            
            <div class="stats-sections">
                <div class="stats-section">
                    <h3>사용자별 챗봇 접근</h3>
                    <div class="stats-bar-list">
                        ${Object.entries(permStats.user_stats).map(([user, data]) => `
                            <div class="stats-bar-item">
                                <span class="label">${user}</span>
                                <div class="bar-container">
                                    <div class="bar" style="width: ${(data.accessible / data.total * 100) || 0}%">
                                        ${data.accessible}/${data.total}
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
    } catch (error) {
        container.innerHTML = `<div class="error">로드 실패: ${error.message}</div>`;
    }
}

// ===== 모달 관리 =====
function openCreateModal() {
    document.getElementById('chatbotModal').classList.add('active');
    document.getElementById('modalTitle').textContent = '새 챗봇 만들기';
    document.getElementById('chatbotForm').reset();
    document.getElementById('chatbotId').disabled = false;
}

function closeModal() {
    document.getElementById('chatbotModal').classList.remove('active');
}

function openDetailModal(chatbotId) {
    detailChatbotId = chatbotId;
    const chatbot = chatbots.find(c => c.id === chatbotId);
    if (!chatbot) return;
    
    const content = `
        <div class="detail-section">
            <div class="detail-header">
                <span class="badge ${chatbot.type === 'parent' ? 'badge-parent' : chatbot.type === 'child' ? 'badge-child' : 'badge-standalone'}">
                    ${chatbot.type === 'parent' ? '상위 Agent' : chatbot.type === 'child' ? '하위 Agent' : '단독'}
                </span>
            </div>
            <div class="detail-row">
                <label>ID:</label>
                <code>${chatbot.id}</code>
            </div>
            <div class="detail-row">
                <label>이름:</label>
                <span>${chatbot.name}</span>
            </div>
            <div class="detail-row">
                <label>설명:</label>
                <p>${chatbot.description || '없음'}</p>
            </div>
            ${chatbot.parent ? `
            <div class="detail-row">
                <label>상위 Agent:</label>
                <span>${chatbot.parent}</span>
            </div>` : ''}
            ${chatbot.sub_chatbots?.length ? `
            <div class="detail-row">
                <label>하위 Agent:</label>
                <span>${chatbot.sub_chatbots.join(', ')}</span>
            </div>` : ''}
            <div class="detail-row">
                <label>연결된 DB:</label>
                <div>${chatbot.db_ids?.map(db => `<span class="tag">${db}</span>`).join(' ') || '없음'}</div>
            </div>
        </div>
    `;
    
    document.getElementById('detailTitle').textContent = chatbot.name;
    document.getElementById('detailContent').innerHTML = content;
    document.getElementById('detailModal').classList.add('active');
}

function closeDetailModal() {
    document.getElementById('detailModal').classList.remove('active');
    detailChatbotId = null;
}

function startChatFromDetail() {
    if (detailChatbotId) {
        startChat(detailChatbotId);
        closeDetailModal();
    }
}

function openDeleteModal(chatbotId, name) {
    deleteTargetId = chatbotId;
    document.getElementById('deleteChatbotName').textContent = name;
    document.getElementById('deleteModal').classList.add('active');
}

function closeDeleteModal() {
    document.getElementById('deleteModal').classList.remove('active');
    deleteTargetId = null;
}

async function confirmDelete() {
    if (!deleteTargetId) return;
    
    try {
        const response = await fetch(`/admin/api/chatbots/${deleteTargetId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) throw new Error('Delete failed');
        
        closeDeleteModal();
        loadChatbots();
        loadStats();
        showToast('챗봇이 삭제되었습니다', 'success');
    } catch (error) {
        showToast('삭제 실패: ' + error.message, 'error');
    }
}

// ===== 일괄 권한 모달 =====
async function openBulkPermissionModal() {
    const list = document.getElementById('bulkChatbotList');
    list.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    document.getElementById('bulkPermissionModal').classList.add('active');
    
    try {
        const response = await fetch('/admin/api/chatbots');
        const bots = await response.json();
        
        list.innerHTML = bots.map(bot => `
            <label class="chatbot-checkbox">
                <input type="checkbox" value="${bot.id}" name="bulkChatbots">
                <span class="checkmark"></span>
                <span class="name">${bot.name}</span>
                <span class="id">${bot.id}</span>
            </label>
        `).join('');
    } catch (error) {
        list.innerHTML = '<div class="error">로드 실패</div>';
    }
}

// ===== 권한 추가 모달 =====
async function openAddPermissionModal() {
    document.getElementById('addPermissionModal').classList.add('active');
    document.getElementById('addPermissionForm').reset();
    
    // 챗봇 목록 로드
    const select = document.getElementById('addChatbotId');
    select.innerHTML = '<option value="">챗봇을 선택하세요</option>';
    
    try {
        const response = await fetch('/admin/api/chatbots');
        const bots = await response.json();
        
        bots.forEach(bot => {
            const option = document.createElement('option');
            option.value = bot.id;
            option.textContent = `${bot.name} (${bot.id})`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading chatbots:', error);
        select.innerHTML = '<option value="">챗봇 목록 로드 실패</option>';
    }
}

function closeAddPermissionModal() {
    document.getElementById('addPermissionModal').classList.remove('active');
}

async function saveAddPermission(event) {
    event.preventDefault();
    
    const knoxId = document.getElementById('addUserId').value.trim();
    const chatbotId = document.getElementById('addChatbotId').value;
    const canAccessRadio = document.querySelector('input[name="addCanAccess"]:checked');
    const canAccess = canAccessRadio ? canAccessRadio.value === 'true' : true;
    
    if (!knoxId || !chatbotId) {
        showToast('사용자 ID와 챗봇을 모두 선택하세요', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/permissions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                knox_id: knoxId,
                chatbot_id: chatbotId,
                can_access: canAccess
            })
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || '저장 실패');
        }
        
        closeAddPermissionModal();
        showToast('권한이 추가되었습니다', 'success');
        // Refresh user list
        loadUsers();
    } catch (error) {
        showToast('권한 추가 실패: ' + error.message, 'error');
    }
}

function closeBulkPermissionModal() {
    document.getElementById('bulkPermissionModal')?.classList.remove('active');
}

async function saveBulkPermissions(event) {
    event.preventDefault();
    
    const knoxId = document.getElementById('bulkUserId')?.value;
    const chatbotIds = Array.from(document.querySelectorAll('input[name="bulkChatbots"]:checked')).map(cb => cb.value);
    const canAccess = document.getElementById('bulkAccessType')?.value === 'true';
    
    if (!chatbotIds.length) {
        showToast('최소 하나의 챗봇을 선택하세요', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/permissions/bulk', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                knox_id: knoxId,
                chatbot_ids: chatbotIds,
                can_access: canAccess
            })
        });
        
        if (!response.ok) throw new Error('Failed');
        
        const result = await response.json();
        closeBulkPermissionModal();
        showToast(`${result.success_count}/${result.total}개 권한 설정 완료`, 'success');
    } catch (error) {
        showToast('저장 실패: ' + error.message, 'error');
    }
}

// ===== 챗봇 저장 =====
async function saveChatbot(event) {
    event.preventDefault();
    
    const data = {
        id: document.getElementById('chatbotId').value,
        name: document.getElementById('chatbotName').value,
        description: document.getElementById('chatbotDesc').value,
        type: document.getElementById('chatbotType').value,
        system_prompt: document.getElementById('systemPrompt').value,
        db_ids: document.getElementById('dbInput').value.split(',').map(s => s.trim()).filter(s => s),
        active: true
    };
    
    if (data.type === 'child') {
        data.parent = document.getElementById('parentAgent').value;
    }
    
    try {
        const response = await fetch('/admin/api/chatbots', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Failed');
        }
        
        closeModal();
        loadChatbots();
        loadStats();
        showToast('챗봇이 생성되었습니다', 'success');
    } catch (error) {
        showToast('저장 실패: ' + error.message, 'error');
    }
}

// ===== 유틸리티 =====
function populateParentSelect() {
    const select = document.getElementById('parentAgent');
    select.innerHTML = '<option value="">선택하세요</option>';
    
    const parents = chatbots.filter(c => c.type === 'parent');
    parents.forEach(p => {
        const option = document.createElement('option');
        option.value = p.id;
        option.textContent = p.name;
        select.appendChild(option);
    });
}

function onTypeChange() {
    const type = document.getElementById('chatbotType').value;
    const parentGroup = document.getElementById('parentSelectGroup');
    
    if (type === 'child') {
        parentGroup.style.display = 'block';
    } else {
        parentGroup.style.display = 'none';
    }
}

function startChat(chatbotId) {
    window.open(`/?chatbot=${chatbotId}`, '_blank');
}

function setupEventListeners() {
    // Search input
    document.getElementById('searchInput')?.addEventListener('input', renderChatbots);
    
    // Close modals on outside click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    });
    
    // DB tag input
    const dbInput = document.getElementById('dbInput');
    if (dbInput) {
        dbInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault();
                const value = dbInput.value.trim();
                if (value && value !== ',') {
                    addDbTag(value.replace(',', ''));
                    dbInput.value = '';
                }
            }
        });
    }
}

function addDbTag(dbId) {
    const container = document.getElementById('dbTags');
    const tag = document.createElement('span');
    tag.className = 'db-tag active';
    tag.innerHTML = `${dbId} <button onclick="this.parentElement.remove()">×</button>`;
    container.appendChild(tag);
}

// ===== 토스트 알림 =====
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}
