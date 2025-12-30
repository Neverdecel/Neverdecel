/**
 * Terminal interaction handling for Ava chat
 */

document.addEventListener('DOMContentLoaded', function() {
    const terminalInput = document.getElementById('terminal-input');
    const terminalBody = document.getElementById('terminal-body');
    const terminalForm = document.getElementById('terminal-form');
    const chatMessages = document.getElementById('chat-messages');

    if (!terminalInput || !terminalForm) return;

    // Focus input on terminal click
    document.querySelector('.terminal')?.addEventListener('click', function(e) {
        if (e.target.tagName !== 'A' && e.target.tagName !== 'INPUT') {
            terminalInput.focus();
        }
    });

    // Auto-focus on load (with delay for animations)
    setTimeout(() => terminalInput.focus(), 1000);

    // Handle clear command client-side
    terminalForm.addEventListener('htmx:beforeRequest', function(e) {
        const message = terminalInput.value.trim().toLowerCase();

        if (message === 'clear') {
            e.preventDefault();
            clearTerminal();
            terminalInput.value = '';
            return false;
        }
    });

    // Scroll to bottom after HTMX swap
    document.body.addEventListener('htmx:afterSwap', function(e) {
        if (e.detail.target.id === 'chat-messages') {
            scrollToBottom();
        }
    });

    // Handle keyboard shortcuts
    terminalInput.addEventListener('keydown', function(e) {
        // Ctrl+L to clear
        if (e.ctrlKey && e.key === 'l') {
            e.preventDefault();
            clearTerminal();
        }
    });

    /**
     * Clear the terminal chat messages
     */
    function clearTerminal() {
        if (chatMessages) {
            chatMessages.innerHTML = '';

            // Add cleared message
            const clearedMsg = document.createElement('div');
            clearedMsg.className = 'text-text-muted text-xs mb-4';
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
});
