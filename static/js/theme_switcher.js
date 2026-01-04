/**
 * Theme Switcher - Handles dark/light theme toggling
 */

// Set theme and update localStorage
function setTheme(theme) {
    localStorage.setItem('theme', theme);

    if (theme === 'dark') {
        document.documentElement.classList.add('dark');
    } else if (theme === 'light') {
        document.documentElement.classList.remove('dark');
    } else if (theme === 'auto') {
        // Check system preference
        if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
    }
}

// Listen for system theme changes when in 'auto' mode
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    const currentTheme = localStorage.getItem('theme');
    if (currentTheme === 'auto') {
        if (e.matches) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
    }
});

// Initialize theme on page load
document.addEventListener('DOMContentLoaded', function() {
    const stored = localStorage.getItem('theme');
    if (stored) {
        setTheme(stored);
    }
});
