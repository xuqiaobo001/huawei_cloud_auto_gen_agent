/* Sidebar toggle logic */
(function() {
    const STORAGE_KEY = 'sidebar_collapsed';

    function initSidebar() {
        const sidebar = document.getElementById('sidebar');
        if (!sidebar) return;
        if (localStorage.getItem(STORAGE_KEY) === '1') {
            sidebar.classList.add('collapsed');
        }
    }

    window.toggleSidebar = function() {
        const sidebar = document.getElementById('sidebar');
        if (!sidebar) return;
        sidebar.classList.toggle('collapsed');
        localStorage.setItem(STORAGE_KEY, sidebar.classList.contains('collapsed') ? '1' : '0');
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSidebar);
    } else {
        initSidebar();
    }
})();
