document.addEventListener("DOMContentLoaded", function () {
  const searchInput = document.getElementById("objectSearch");
  const items = document.querySelectorAll(".object-item");
  const noResults = document.getElementById("noResults");
 
  searchInput.addEventListener("input", function () {
    const query = this.value.toLowerCase();
    let visibleCount = 0;
 
    items.forEach(item => {
      const text = item.textContent.toLowerCase();
      const match = text.includes(query);
      item.style.display = match ? "block" : "none";
      if (match) visibleCount++;
    });
 
    noResults.style.display = visibleCount === 0 ? "block" : "none";
  });
});