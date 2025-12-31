/**
 * Dropdown component behavior
 * - Click avatar to toggle dropdown
 * - Click outside to close
 * - Press Escape to close
 */

document.addEventListener('DOMContentLoaded', function() {
    const dropdowns = document.querySelectorAll('[data-dropdown]');

    dropdowns.forEach(dropdown => {
        const trigger = dropdown.querySelector('[data-dropdown-trigger]');
        const menu = dropdown.querySelector('[data-dropdown-menu]');

        if (!trigger || !menu) return;

        // Toggle dropdown on click
        trigger.addEventListener('click', function(e) {
            e.stopPropagation();
            menu.classList.toggle('hidden');
        });

        // Close on click outside
        document.addEventListener('click', function(e) {
            if (!dropdown.contains(e.target)) {
                menu.classList.add('hidden');
            }
        });

        // Close on Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                menu.classList.add('hidden');
            }
        });
    });
});
