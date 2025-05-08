/**
 * Theme Toggle Functionality for Salesforce GPT Data Generator
 * Allows switching between dark and light modes
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get the theme toggle element
    const themeToggle = document.getElementById('themeToggle');
    
    // Check if there's a saved preference in localStorage
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    // Default to dark theme or user's saved preference
    const currentTheme = savedTheme || (prefersDark ? 'dark' : 'light');
    
    // Set the initial state based on saved preference or system preference
    if (currentTheme === 'light') {
        document.documentElement.setAttribute('data-bs-theme', 'light');
        if (themeToggle) themeToggle.checked = false;
    } else {
        document.documentElement.setAttribute('data-bs-theme', 'dark');
        if (themeToggle) themeToggle.checked = true;
    }
    
    // Add event listener to the toggle switch
    if (themeToggle) {
        themeToggle.addEventListener('change', function() {
            if (this.checked) {
                // Switch to dark theme
                document.documentElement.setAttribute('data-bs-theme', 'dark');
                localStorage.setItem('theme', 'dark');
            } else {
                // Switch to light theme
                document.documentElement.setAttribute('data-bs-theme', 'light');
                localStorage.setItem('theme', 'light');
            }
        });
    }
    
    // Add class to body for enhanced stylesheet targeting
    document.body.classList.add(`theme-${currentTheme}`);
});

// Enable collapsible sections
document.addEventListener('DOMContentLoaded', function() {
    // Find all collapsible section headers
    const collapsibleHeaders = document.querySelectorAll('.collapsible-header');
    
    collapsibleHeaders.forEach(header => {
        header.addEventListener('click', function() {
            // Toggle the active class on the header
            this.classList.toggle('active');
            
            // Get the content container
            const content = this.nextElementSibling;
            
            // Toggle visibility
            if (content.style.maxHeight) {
                content.style.maxHeight = null;
                // Change the icon if present
                const icon = this.querySelector('i.bi');
                if (icon) {
                    icon.classList.remove('bi-chevron-down');
                    icon.classList.add('bi-chevron-right');
                }
            } else {
                content.style.maxHeight = content.scrollHeight + 'px';
                // Change the icon if present
                const icon = this.querySelector('i.bi');
                if (icon) {
                    icon.classList.remove('bi-chevron-right');
                    icon.classList.add('bi-chevron-down');
                }
            }
        });
    });
});

// Add collapsible functionality to cards
document.addEventListener('DOMContentLoaded', function() {
    const cardHeaders = document.querySelectorAll('.card-header[data-bs-toggle="collapse"]');
    
    cardHeaders.forEach(header => {
        const targetId = header.getAttribute('data-bs-target');
        const collapseElement = document.querySelector(targetId);
        
        // Add click event listener
        header.addEventListener('click', function() {
            const isCollapsed = collapseElement.classList.contains('show');
            
            // Toggle collapse state
            if (isCollapsed) {
                collapseElement.classList.remove('show');
            } else {
                collapseElement.classList.add('show');
            }
            
            // Toggle icon
            const icon = header.querySelector('.collapse-icon');
            if (icon) {
                if (isCollapsed) {
                    icon.classList.remove('bi-chevron-down');
                    icon.classList.add('bi-chevron-right');
                } else {
                    icon.classList.remove('bi-chevron-right');
                    icon.classList.add('bi-chevron-down');
                }
            }
        });
    });
});