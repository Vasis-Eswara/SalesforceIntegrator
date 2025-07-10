document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.getElementById("objectSearch");
    const objectItems = document.querySelectorAll(".object-item");
    const noResults = document.getElementById("noResults");

    if (!searchInput || !objectItems.length) {
        console.error("Search input or object items not found.");
        return;
    }

    searchInput.addEventListener("input", function () {
        const query = this.value.trim().toLowerCase();
        let visibleCount = 0;

        objectItems.forEach(item => {
            const label = (item.dataset.objectLabel || "").toLowerCase();
            const match = label.includes(query);

            item.classList.toggle("hidden", !match);
            if (match) visibleCount++;

            console.log("Searching for:", query, "| In label:", label, "| Match:", match);
        });

        noResults.style.display = visibleCount === 0 ? "block" : "none";
    });
});