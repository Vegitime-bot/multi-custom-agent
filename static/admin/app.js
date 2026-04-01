/**
 * Admin Panel JavaScript
 * 챗봇 관리자 페이지 기능
 */

// Global state
let chatbots = [];
let currentFilter = 'all';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadChatbots();
    setupEventListeners();
});

// Load chatbots from API
async function loadChatbots() {
    const grid = document.getElementById('chatbotGrid');
    grid.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    
    try {
        const response = await fetch('/admin/api/chatbots');
        if (!response.ok) throw new Error('Failed to load');
        
        chatbots = await response.json();
        renderChatbots();
        populateParentSelect();
    } catch (error) {
        console.error('Error loading chatbots:', error);
        grid.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>로드 실패</h3><p>${error.message}</p></div>`;
    }
}

// Render chatbot cards
function renderChatbots() {
    const grid = document.getElementById('chatbotGrid');
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    
    // Filter chatbots
    let filtered = chatbots.filter(cb => {
        // Type filter
        if (currentFilter !== 'all' && cb.type !== currentFilter) {
            return false;
        }
        
        // Search filter
        if (searchTerm && !cb.name.toLowerCase().includes(searchTerm) && 
            !cb.description.toLowerCase().includes(searchTerm)) {
            return false;
        }
        
        return true;
    });
    
    if (filtered.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🔍</div>
                <h3>챗봘을 찾을 수 없습니다</h3>
                <p>검색어를 변경하거나 새 챗봘을 만들어보세요.</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = filtered.map(chatbot => createCardHTML(chatbot)).join('');
}

// Create card HTML
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
            hierarchyInfo = `
                <div class="hierarchy-info">
                    <span>🔗 상위:</span>
                    <span class="parent">${parent.name}</span>
                </div>
            `;
        }
    } else if (chatbot.type === 'parent' && chatbot.sub_chatbots?.length > 0) {
        hierarchyInfo = `
            <div class="hierarchy-info">
                <span>👥 하위 Agent: ${chatbot.sub_chatbots.length}개</span>
            </div>
        `;
    }
    
    return `
        <div class="chatbot-card" data-id="${chatbot.id}">
            <span class="card-badge ${badgeClass}">${badgeText}</span>
            <div class="card-header">
                <div class="card-icon">${icon}</div>
                <h3 class="card-title">${chatbot.name}</h3>
                <p class="card-desc">${chatbot.description}</p>
            </div>
            <div class="card-meta">
                <div class="meta-item">
                    <span class="meta-label">ID</span>
                    <span class="meta-value">${chatbot.id}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">DB</span>
                    <span class="meta-value">${chatbot.db_ids?.length || 0}개</span>
                </div>
                ${hierarchyInfo}
            </div>
            <div class="card-actions">
                <button class="btn-card btn-chat" onclick="startChat('${chatbot.id}')">
                    💬 채팅하기
                </button>
                <button class="btn-card btn-edit" onclick="editChatbot('${chatbot.id}')">
                    ✏️ 수정
                </button>
                <button class="btn-card btn-delete" onclick="confirmDelete('${chatbot.id}')">
                    🗑️
                </button>
            </div>
        </div>
    `;
}

// Populate parent select dropdown
function populateParentSelect() {
    const select = document.getElementById('parentAgent');
    const parents = chatbots.filter(c => c.type === 'parent');
    
    select.innerHTML = '<option value="">선택하세요</option>' + 
        parents.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
}

// Event listeners
function setupEventListeners() {
    // Search input
    document.getElementById('searchInput').addEventListener('input', renderChatbots);
    
    // Filter tabs
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            currentFilter = e.target.dataset.filter;
            renderChatbots();
        });
    });
    
    // Form submission
    document.getElementById('chatbotForm').addEventListener('submit', saveChatbot);
}

// Modal functions
function openCreateModal() {
    document.getElementById('modalTitle').textContent = '새 챗봘 만들기';
    document.getElementById('chatbotForm').reset();
    document.getElementById('chatbotModal').classList.add('active');
}

function closeModal() {
    document.getElementById('chatbotModal').classList.remove('active');
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

// Save chatbot
async function saveChatbot(e) {
    e.preventDefault();
    
    const chatbotData = {
        id: document.getElementById('chatbotId').value,
        name: document.getElementById('chatbotName').value,
        description: document.getElementById('chatbotDesc').value,
        type: document.getElementById('chatbotType').value,
        system_prompt: document.getElementById('systemPrompt').value,
        db_ids: [], // TODO: Get selected DBs
        active: true
    };
    
    if (chatbotData.type === 'child') {
        chatbotData.parent = document.getElementById('parentAgent').value;
    }
    
    try {
        const response = await fetch('/admin/api/chatbots', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(chatbotData)
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Failed to save');
        }
        
        closeModal();
        loadChatbots();
        showNotification('챗봘이 생성되었습니다!', 'success');
    } catch (error) {
        console.error('Error saving chatbot:', error);
        showNotification(`오류: ${error.message}`, 'error');
    }
}

// Edit chatbot
function editChatbot(id) {
    const chatbot = chatbots.find(c => c.id === id);
    if (!chatbot) return;
    
    document.getElementById('modalTitle').textContent = '챗봘 수정';
    document.getElementById('chatbotId').value = chatbot.id;
    document.getElementById('chatbotName').value = chatbot.name;
    document.getElementById('chatbotDesc').value = chatbot.description || '';
    document.getElementById('chatbotType').value = chatbot.type || 'standalone';
    
    onTypeChange();
    
    if (chatbot.parent) {
        document.getElementById('parentAgent').value = chatbot.parent;
    }
    
    document.getElementById('chatbotModal').classList.add('active');
}

// Delete chatbot
function confirmDelete(id) {
    const chatbot = chatbots.find(c => c.id === id);
    if (!chatbot) return;
    
    document.getElementById('deleteChatbotName').textContent = chatbot.name;
    document.getElementById('confirmDeleteBtn').onclick = () => deleteChatbot(id);
    document.getElementById('deleteModal').classList.add('active');
}

function closeDeleteModal() {
    document.getElementById('deleteModal').classList.remove('active');
}

async function deleteChatbot(id) {
    try {
        const response = await fetch(`/admin/api/chatbots/${id}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) throw new Error('Failed to delete');
        
        closeDeleteModal();
        loadChatbots();
        showNotification('챗봘이 삭제되었습니다!', 'success');
    } catch (error) {
        console.error('Error deleting chatbot:', error);
        showNotification(`오류: ${error.message}`, 'error');
    }
}

// Start chat - 채팅 페이지로 이동
function startChat(chatbotId) {
    window.open(`/?chatbot=${chatbotId}`, '_blank');
}

// Notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 24px;
        background: ${type === 'success' ? '#10b981' : '#6366f1'};
        color: white;
        border-radius: 12px;
        font-weight: 500;
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Close modal on backdrop click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('active');
    }
});
