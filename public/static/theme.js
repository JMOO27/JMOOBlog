// Apply the theme before styles load, avoiding a flash of the wrong background.
(() => {
    const root = document.documentElement;
    const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
    const storageKey = 'jmoo-theme';
    let preference = null;

    try {
        const saved = localStorage.getItem(storageKey);
        if (saved === 'light' || saved === 'dark') preference = saved;
    } catch {
        // The toggle also works when browser storage is unavailable.
    }

    function applyTheme(theme) {
        root.dataset.theme = theme;
        document.querySelectorAll('[data-theme-choice]').forEach(button => {
            button.setAttribute('aria-pressed', String(button.dataset.themeChoice === theme));
        });
        document.querySelectorAll('[data-theme-toggle]').forEach(button => {
            const label = `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`;
            button.setAttribute('aria-label', label);
            button.title = label;
        });
    }

    function chooseTheme(theme) {
        preference = theme;
        applyTheme(theme);
        try {
            localStorage.setItem(storageKey, preference);
        } catch {
            // Keep the selected theme for this page even without storage.
        }
    }

    applyTheme(preference || (systemTheme.matches ? 'dark' : 'light'));

    document.addEventListener('DOMContentLoaded', () => {
        applyTheme(root.dataset.theme);
        document.querySelectorAll('[data-theme-choice]').forEach(button => {
            button.addEventListener('click', () => {
                chooseTheme(button.dataset.themeChoice);
            });
        });
        document.querySelectorAll('[data-theme-toggle]').forEach(button => {
            button.addEventListener('click', () => {
                chooseTheme(root.dataset.theme === 'dark' ? 'light' : 'dark');
            });
        });
    });

    systemTheme.addEventListener('change', event => {
        if (!preference) applyTheme(event.matches ? 'dark' : 'light');
    });
})();
