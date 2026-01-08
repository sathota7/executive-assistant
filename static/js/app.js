// State for dismissed items and news queue
let dismissedEmails = JSON.parse(localStorage.getItem('dismissedEmails') || '[]');
let currentNewsTopic = 'general';
let newsQueue = [];
let displayedNewsCount = 10;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadLLMProviders();
    loadCalendar();
    loadEmails();
    loadNews('general');
    loadReddit();
    
    // Chat input handler
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');
    
    sendButton.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
});

// LLM Provider Management
async function loadLLMProviders() {
    try {
        const response = await fetch('/api/llm/providers');
        const data = await response.json();
        
        if (data.error) {
            console.error('Error loading providers:', data.error);
            return;
        }
        
        const select = document.getElementById('llm-provider-select');
        select.innerHTML = '';
        
        const providers = data.providers || {};
        const defaultProvider = data.default || '';
        
        // Sort providers: available first, then unavailable
        const sortedProviders = Object.entries(providers).sort((a, b) => {
            if (a[1].available && !b[1].available) return -1;
            if (!a[1].available && b[1].available) return 1;
            return 0;
        });
        
        for (const [providerId, providerInfo] of sortedProviders) {
            const option = document.createElement('option');
            option.value = providerId;
            option.textContent = providerInfo.name;
            
            if (!providerInfo.available) {
                option.disabled = true;
                option.style.color = '#999';
                option.style.fontStyle = 'italic';
            }
            
            if (providerId === defaultProvider) {
                option.selected = true;
            }
            
            select.appendChild(option);
        }
    } catch (error) {
        console.error('Error loading LLM providers:', error);
        const select = document.getElementById('llm-provider-select');
        select.innerHTML = '<option value="">Error loading providers</option>';
    }
}

async function updateLLMProvider(providerId) {
    if (!providerId) return;
    
    try {
        const response = await fetch('/api/llm/provider', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ provider: providerId })
        });
        
        const data = await response.json();
        
        if (data.error) {
            alert('Error: ' + data.error);
            // Reload to restore previous selection
            loadLLMProviders();
            return;
        }
        
        if (data.success) {
            // Show brief notification and reload to apply changes
            const select = document.getElementById('llm-provider-select');
            const providerName = select.options[select.selectedIndex].textContent;
            
            // Show temporary notification
            const notification = document.createElement('div');
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #667eea;
                color: white;
                padding: 15px 20px;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                z-index: 10000;
                font-weight: 500;
            `;
            notification.textContent = `Switched to ${providerName}. Reloading...`;
            document.body.appendChild(notification);
            
            // Reload after short delay
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        }
    } catch (error) {
        console.error('Error updating LLM provider:', error);
        alert('Error updating provider: ' + error.message);
        loadLLMProviders(); // Restore on error
    }
}

// Chat functionality
async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Add user message to chat
    addChatMessage('user', message);
    input.value = '';
    
    // Show loading
    const loadingId = addChatMessage('assistant', 'Thinking...');
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message })
        });
        
        const data = await response.json();
        
        // Remove loading message
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.remove();
        
        // Add response
        addChatMessage('assistant', data.response || data.error || 'No response');
    } catch (error) {
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.remove();
        addChatMessage('assistant', 'Error: ' + error.message);
    }
}

function addChatMessage(role, text) {
    const messagesContainer = document.getElementById('chat-messages');
    const messageId = 'msg-' + Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.id = messageId;
    messageDiv.className = `message ${role}`;
    messageDiv.textContent = text;
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    return messageId;
}

// Calendar
async function loadCalendar() {
    const loading = document.getElementById('calendar-loading');
    const container = document.getElementById('calendar-events');
    
    try {
        const response = await fetch('/api/calendar/upcoming');
        const data = await response.json();
        
        loading.style.display = 'none';
        
        if (data.error) {
            container.innerHTML = `<p style="color: red;">Error: ${data.error}</p>`;
            return;
        }
        
        if (data.events.length === 0) {
            container.innerHTML = '<p>No upcoming events</p>';
            return;
        }
        
        // Render exactly up to 10 events, pad to 10 slots for 5x2 grid
        const eventsToShow = data.events.slice(0, 10);
        const emptySlots = 10 - eventsToShow.length;
        
        let html = eventsToShow.map(event => `
            <div class="tile calendar-tile ${event.is_priority ? 'priority' : ''}">
                <div class="tile-title">${escapeHtml(event.title)}</div>
                <div class="calendar-time">${event.start_display}</div>
                ${event.location ? `<div class="tile-content" style="-webkit-line-clamp: 2;">📍 ${escapeHtml(event.location)}</div>` : ''}
                ${event.htmlLink ? `<a href="${event.htmlLink}" target="_blank" class="tile-link">Open →</a>` : ''}
            </div>
        `).join('');
        
        // Add empty slots to maintain 5x2 grid layout
        for (let i = 0; i < emptySlots; i++) {
            html += '<div class="tile calendar-tile empty-slot"></div>';
        }
        
        container.innerHTML = html;
    } catch (error) {
        loading.style.display = 'none';
        container.innerHTML = `<p style="color: red;">Error loading calendar: ${error.message}</p>`;
    }
}

// Emails
async function loadEmails() {
    const loading = document.getElementById('email-loading');
    const container = document.getElementById('email-list');
    
    try {
        const response = await fetch('/api/emails/recent');
        const data = await response.json();
        
        loading.style.display = 'none';
        
        if (data.error) {
            container.innerHTML = `<p style="color: red;">Error: ${data.error}</p>`;
            return;
        }
        
        // Filter out dismissed emails and maintain sorting (response-required first)
        const filteredEmails = data.emails
            .filter(email => !dismissedEmails.includes(email.id))
            .sort((a, b) => {
                // Sort: response-required emails first
                if (a.requires_response && !b.requires_response) return -1;
                if (!a.requires_response && b.requires_response) return 1;
                return 0;
            });
        
        if (filteredEmails.length === 0) {
            container.innerHTML = '<p>No new emails</p>';
            return;
        }
        
        container.innerHTML = filteredEmails.map(email => `
            <div class="email-item ${email.requires_response ? 'response-required' : ''}" data-email-id="${email.id}">
                <button class="dismiss-btn" onclick="dismissEmail('${email.id}')" title="Dismiss">×</button>
                ${email.requires_response ? '<div class="response-badge">⚠️ Response Requested</div>' : ''}
                <div class="email-header">
                    <div class="email-from">${escapeHtml(email.from)}</div>
                    <div class="email-date">${email.date}</div>
                </div>
                <div class="email-subject">${escapeHtml(email.subject)}</div>
                <div class="email-snippet">${escapeHtml(email.snippet || 'No preview available')}</div>
                <a href="${email.gmail_link}" target="_blank" class="email-link">Open in Gmail →</a>
            </div>
        `).join('');
    } catch (error) {
        loading.style.display = 'none';
        container.innerHTML = `<p style="color: red;">Error loading emails: ${error.message}</p>`;
    }
}

function dismissEmail(emailId) {
    // Add to dismissed list
    if (!dismissedEmails.includes(emailId)) {
        dismissedEmails.push(emailId);
        localStorage.setItem('dismissedEmails', JSON.stringify(dismissedEmails));
    }
    
    // Remove from DOM with animation
    const emailItem = document.querySelector(`[data-email-id="${emailId}"]`);
    if (emailItem) {
        emailItem.style.transition = 'opacity 0.3s, transform 0.3s';
        emailItem.style.opacity = '0';
        emailItem.style.transform = 'translateX(-20px)';
        setTimeout(() => {
            emailItem.remove();
            // Check if no emails left
            const container = document.getElementById('email-list');
            if (container.children.length === 0) {
                container.innerHTML = '<p>No new emails</p>';
            }
        }, 300);
    }
}

function clearDismissedEmails() {
    dismissedEmails = [];
    localStorage.removeItem('dismissedEmails');
    loadEmails(); // Reload emails
}

// News
async function loadNews(topic) {
    const loading = document.getElementById('news-loading');
    const container = document.getElementById('news-articles');
    
    currentNewsTopic = topic;
    displayedNewsCount = 10;
    
    // Update active button
    document.querySelectorAll('.news-toggle').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.topic === topic) {
            btn.classList.add('active');
        }
    });
    
    loading.style.display = 'block';
    container.innerHTML = '';
    
    try {
        // Fetch more articles than needed for the queue
        const response = await fetch(`/api/news?topic=${topic}&limit=15`);
        const data = await response.json();
        
        loading.style.display = 'none';
        
        if (data.error) {
            container.innerHTML = `<p style="color: red;">Error: ${data.error}</p>`;
            return;
        }
        
        if (data.articles.length === 0) {
            container.innerHTML = '<p>No articles found</p>';
            return;
        }
        
        // Store all articles in queue
        newsQueue = data.articles;
        
        // Display first 5
        renderNewsArticles();
    } catch (error) {
        loading.style.display = 'none';
        container.innerHTML = `<p style="color: red;">Error loading news: ${error.message}</p>`;
    }
}

function renderNewsArticles() {
    const container = document.getElementById('news-articles');
    const articlesToShow = newsQueue.slice(0, displayedNewsCount);
    
    if (articlesToShow.length === 0) {
        container.innerHTML = '<p>No more articles available</p>';
        return;
    }
    
    container.innerHTML = articlesToShow.map((article, index) => `
        <div class="tile news-tile" data-news-index="${index}">
            <button class="dismiss-btn" onclick="dismissNews(${index})" title="Dismiss">×</button>
            <div class="tile-title">${escapeHtml(article.title)}</div>
            <div class="tile-content">${escapeHtml(article.description || 'No description')}</div>
            <div style="margin-top: 6px; color: #999; font-size: 0.75em;">Source: ${escapeHtml(article.source)}</div>
            ${article.url ? `<a href="${article.url}" target="_blank" class="tile-link">Read more →</a>` : ''}
        </div>
    `).join('');
    
    // Add empty slots to maintain 5x2 grid layout (10 articles)
    const emptySlots = 10 - articlesToShow.length;
    for (let i = 0; i < emptySlots; i++) {
        container.innerHTML += '<div class="tile empty-slot"></div>';
    }
}

function dismissNews(index) {
    // Remove from queue
    if (index >= 0 && index < newsQueue.length) {
        newsQueue.splice(index, 1);
        
        // Re-render with animation
        const newsItem = document.querySelector(`[data-news-index="${index}"]`);
        if (newsItem) {
            newsItem.style.transition = 'opacity 0.3s, transform 0.3s';
            newsItem.style.opacity = '0';
            newsItem.style.transform = 'scale(0.9)';
            setTimeout(() => {
                renderNewsArticles();
            }, 300);
        } else {
            renderNewsArticles();
        }
    }
}

// Reddit
async function loadReddit() {
    const loading = document.getElementById('reddit-loading');
    const container = document.getElementById('reddit-posts');
    
    try {
        const response = await fetch('/api/reddit?limit=5');
        const data = await response.json();
        
        loading.style.display = 'none';
        
        if (data.error) {
            container.innerHTML = `<p style="color: red;">Error: ${data.error}</p>`;
            return;
        }
        
        if (data.posts.length === 0) {
            container.innerHTML = '<p>No Reddit posts available</p>';
            return;
        }
        
        container.innerHTML = data.posts.map(post => `
            <div class="tile reddit-tile">
                <div class="tile-title">${escapeHtml(post.title)}</div>
                <div class="reddit-meta">
                    <span class="reddit-subreddit">r/${escapeHtml(post.subreddit)}</span>
                    <span>👍 ${post.score}</span>
                    <span>💬 ${post.num_comments}</span>
                </div>
                ${post.permalink ? `<a href="${post.permalink}" target="_blank" class="tile-link">View on Reddit →</a>` : ''}
            </div>
        `).join('');
    } catch (error) {
        loading.style.display = 'none';
        container.innerHTML = `<p style="color: red;">Error loading Reddit: ${error.message}</p>`;
    }
}

// Exclusions Modal
async function showExclusionsModal() {
    const modal = document.getElementById('exclusions-modal');
    const container = document.getElementById('exclusions-container');
    
    modal.style.display = 'block';
    
    try {
        const response = await fetch('/api/emails/exclusions');
        const data = await response.json();
        
        if (data.exclusions.length === 0) {
            container.innerHTML = '<p>No exclusions set</p>';
        } else {
            container.innerHTML = data.exclusions.map(domain => `
                <div class="exclusion-item">
                    <span>${escapeHtml(domain)}</span>
                    <button onclick="removeExclusion('${escapeHtml(domain)}')">Remove</button>
                </div>
            `).join('');
        }
    } catch (error) {
        container.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
    }
}

function closeExclusionsModal() {
    document.getElementById('exclusions-modal').style.display = 'none';
}

async function addExclusion() {
    const input = document.getElementById('new-exclusion');
    const domain = input.value.trim();
    
    if (!domain) return;
    
    try {
        const response = await fetch('/api/emails/exclusions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ domain: domain })
        });
        
        const data = await response.json();
        
        if (data.success) {
            input.value = '';
            showExclusionsModal(); // Reload list
        } else {
            alert(data.message || 'Failed to add exclusion');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function removeExclusion(domain) {
    try {
        const response = await fetch('/api/emails/exclusions', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ domain: domain })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showExclusionsModal(); // Reload list
        } else {
            alert(data.message || 'Failed to remove exclusion');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// Utility
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('exclusions-modal');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}

