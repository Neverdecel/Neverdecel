/**
 * Terminal interaction handling for Ava chat
 * Includes: Command history, Tab completion, Scroll animations
 */

document.addEventListener('DOMContentLoaded', function() {
    const terminalInput = document.getElementById('terminal-input');
    const terminalBody = document.getElementById('terminal-body');
    const terminalForm = document.getElementById('terminal-form');
    const chatMessages = document.getElementById('chat-messages');

    if (!terminalInput || !terminalForm) return;

    // =========================================
    // Command History
    // =========================================
    const commandHistory = [];
    let historyIndex = -1;
    const MAX_HISTORY = 50;

    // =========================================
    // Tab Completion
    // =========================================
    const COMMANDS = ['help', 'projects', 'skills', 'contact', 'whoami', 'about', 'clear', 'sudo'];

    // =========================================
    // Character Limit
    // =========================================
    const MAX_LENGTH = 500;
    const WARNING_THRESHOLD = 50;

    // =========================================
    // Terminal Focus Management
    // =========================================

    // Focus input on terminal click
    document.querySelector('.terminal')?.addEventListener('click', function(e) {
        if (e.target.tagName !== 'A' && e.target.tagName !== 'INPUT') {
            terminalInput.focus();
        }
    });

    // Auto-focus on load (with delay for animations)
    setTimeout(() => terminalInput.focus(), 1000);

    // =========================================
    // Keyboard Event Handlers
    // =========================================

    terminalInput.addEventListener('keydown', function(e) {
        // Arrow Up - Previous command
        if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (commandHistory.length > 0 && historyIndex < commandHistory.length - 1) {
                historyIndex++;
                this.value = commandHistory[commandHistory.length - 1 - historyIndex] || '';
            }
        }

        // Arrow Down - Next command
        else if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (historyIndex > 0) {
                historyIndex--;
                this.value = commandHistory[commandHistory.length - 1 - historyIndex] || '';
            } else {
                historyIndex = -1;
                this.value = '';
            }
        }

        // Ctrl+L - Clear terminal
        else if (e.ctrlKey && e.key === 'l') {
            e.preventDefault();
            clearTerminal();
        }

        // Tab - Autocomplete
        else if (e.key === 'Tab') {
            e.preventDefault();
            handleTabCompletion();
        }
    });

    // =========================================
    // Character Counter
    // =========================================

    terminalInput.addEventListener('input', function() {
        const remaining = MAX_LENGTH - this.value.length;

        // Remove existing classes
        this.classList.remove('char-warning', 'char-danger');

        if (remaining < 0) {
            this.classList.add('char-danger');
        } else if (remaining < WARNING_THRESHOLD) {
            this.classList.add('char-warning');
        }
    });

    // =========================================
    // Tab Completion Handler
    // =========================================

    function handleTabCompletion() {
        const input = terminalInput.value.toLowerCase().trim();
        if (!input) return;

        const matches = COMMANDS.filter(cmd => cmd.startsWith(input));

        if (matches.length === 1) {
            // Single match - complete it
            terminalInput.value = matches[0];
        } else if (matches.length > 1) {
            // Multiple matches - show suggestions
            showSuggestions(matches);
        }
    }

    function showSuggestions(matches) {
        // Remove existing suggestions
        const existing = document.getElementById('tab-suggestions');
        if (existing) existing.remove();

        const div = document.createElement('div');
        div.id = 'tab-suggestions';
        div.className = 'text-text-muted text-xs mb-2';
        div.setAttribute('role', 'status');
        div.setAttribute('aria-live', 'polite');
        div.textContent = 'Suggestions: ' + matches.join(', ');
        chatMessages.appendChild(div);

        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (div.parentNode) div.remove();
        }, 3000);
    }

    // =========================================
    // Analytics Event Tracking
    // =========================================

    function trackEvent(eventName) {
        // Fire and forget - don't block UI
        const data = new FormData();
        data.append('event', eventName);
        data.append('path', window.location.pathname);
        navigator.sendBeacon('/admin/analytics/api/event', data);
    }

    // =========================================
    // Form Submission Handling
    // =========================================

    terminalForm.addEventListener('htmx:beforeRequest', function(e) {
        const message = terminalInput.value.trim();

        // Handle clear command client-side
        if (message.toLowerCase() === 'clear') {
            e.preventDefault();
            clearTerminal();
            terminalInput.value = '';
            return false;
        }

        // Store command in history
        if (message && message !== 'clear') {
            commandHistory.push(message);
            if (commandHistory.length > MAX_HISTORY) {
                commandHistory.shift();
            }
            historyIndex = -1;

            // Track Ava interaction
            trackEvent('ava_chat');
        }
    });

    // Clear input and scroll after HTMX request completes
    document.body.addEventListener('htmx:afterRequest', function(e) {
        if (e.detail.elt.id === 'terminal-form') {
            terminalInput.value = '';
            scrollToBottom();
        }
    });

    // Also scroll on swap for good measure
    document.body.addEventListener('htmx:afterSwap', function(e) {
        if (e.detail.target.id === 'chat-messages') {
            scrollToBottom();
        }
    });

    // =========================================
    // Utility Functions
    // =========================================

    /**
     * Clear the terminal chat messages
     */
    function clearTerminal() {
        if (chatMessages) {
            chatMessages.innerHTML = '';

            // Add cleared message
            const clearedMsg = document.createElement('div');
            clearedMsg.className = 'text-text-muted text-xs mb-4';
            clearedMsg.setAttribute('role', 'status');
            clearedMsg.textContent = '> Terminal cleared';
            chatMessages.appendChild(clearedMsg);
        }
    }

    /**
     * Scroll terminal body to bottom
     */
    function scrollToBottom() {
        if (terminalBody) {
            terminalBody.scrollTop = terminalBody.scrollHeight;
        }
    }

    // Expose functions globally for HTMX callbacks
    window.terminalClear = clearTerminal;
    window.terminalScrollToBottom = scrollToBottom;

    // =========================================
    // Scroll-Triggered Animations
    // =========================================

    initScrollAnimations();
});

/**
 * Initialize scroll-triggered animations using Intersection Observer
 */
function initScrollAnimations() {
    // Check for reduced motion preference
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        // Show elements without animation
        document.querySelectorAll('.project-card').forEach(el => {
            el.style.opacity = '1';
            el.style.transform = 'none';
        });
        return;
    }

    const observerOptions = {
        threshold: 0.2,
        rootMargin: '0px 0px -50px 0px'
    };

    const animateOnScroll = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-on-scroll', 'animate-in');
                animateOnScroll.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe project cards for scroll animation
    document.querySelectorAll('.project-card').forEach(el => {
        el.classList.add('animate-on-scroll');
        animateOnScroll.observe(el);
    });

    // Observe section headers
    document.querySelectorAll('#projects h2, #projects h3').forEach(el => {
        el.classList.add('animate-on-scroll');
        animateOnScroll.observe(el);
    });
}
