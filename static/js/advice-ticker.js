/* ============================================
   HOUSLER ADVICE TICKER
   Unified component for all pages
   ============================================ */

(function() {
    'use strict';

    // Initialize ticker visibility handler
    function initAdviceTicker() {
        const ticker = document.getElementById('advice-ticker');
        if (!ticker) return;

        // Auto-hide ticker when scrolling near footer
        function handleTickerVisibility() {
            const scrollPosition = window.scrollY + window.innerHeight;
            const documentHeight = document.documentElement.scrollHeight;

            // Hide ticker when within 300px of bottom
            if (scrollPosition >= documentHeight - 300) {
                ticker.classList.add('hidden');
            } else {
                ticker.classList.remove('hidden');
            }
        }

        // Attach event listeners
        window.addEventListener('scroll', handleTickerVisibility);
        window.addEventListener('resize', handleTickerVisibility);

        // Initial check
        handleTickerVisibility();
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAdviceTicker);
    } else {
        initAdviceTicker();
    }
})();
