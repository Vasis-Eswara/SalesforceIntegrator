/**
 * Simple, reliable object search functionality
 */
document.addEventListener('DOMContentLoaded', function() {
    // Get search elements
    const searchInput = document.getElementById('object-search');
    const clearButton = document.getElementById('clear-search');
    const objectList = document.getElementById('object-list');
    
    if (!searchInput || !objectList) return;
    
    // Function to handle search filtering
    function performSearch() {
        const searchTerm = searchInput.value.toLowerCase().trim();
        const items = objectList.querySelectorAll('li');
        
        // Show/hide items based on search term
        let anyVisible = false;
        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            if (text.includes(searchTerm) || searchTerm === '') {
                item.style.display = '';
                anyVisible = true;
            } else {
                item.style.display = 'none';
            }
        });
        
        // Handle no results message
        let noResults = document.getElementById('no-results-message');
        if (!anyVisible && searchTerm !== '') {
            // No matches found
            if (!noResults) {
                noResults = document.createElement('div');
                noResults.id = 'no-results-message';
                noResults.className = 'alert alert-warning mt-3';
                noResults.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-2"></i> No objects matching "${searchTerm}" found`;
                objectList.parentNode.insertBefore(noResults, objectList.nextSibling);
            } else {
                noResults.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-2"></i> No objects matching "${searchTerm}" found`;
            }
        } else if (noResults) {
            // Remove no results message if there are results or empty search
            noResults.remove();
        }
    }
    
    // Attach event listeners
    searchInput.addEventListener('input', performSearch);
    
    // Clear search button
    if (clearButton) {
        clearButton.addEventListener('click', function() {
            searchInput.value = '';
            performSearch();
        });
    }
});