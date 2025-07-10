document.addEventListener("DOMContentLoaded", function () {
  const searchInput = document.getElementById("objectSearch");
  const noResults = document.getElementById("noResults");
 
  if (searchInput && noResults) {
    searchInput.addEventListener("input", function () {
      const query = this.value.toLowerCase();
      let visibleCount = 0;
      
      // Get items dynamically to ensure we have the latest elements
      const items = document.querySelectorAll(".object-item");
   
      items.forEach(item => {
        const text = item.textContent.toLowerCase();
        const match = text.includes(query);
        item.style.display = match ? "block" : "none";
        if (match) visibleCount++;
      });
   
      noResults.style.display = visibleCount === 0 && query.trim() !== "" ? "block" : "none";
    });
  }
});