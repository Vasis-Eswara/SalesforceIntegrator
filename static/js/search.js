// Simple, direct implementation of object search functionality
$(document).ready(function() {
    // Direct search with jQuery
    $("#object-search").on("keyup", function() {
        var value = $(this).val().toLowerCase();
        $("#object-list li").filter(function() {
            $(this).toggle($(this).text().toLowerCase().indexOf(value) > -1);
        });
        
        // Check if any items are visible
        var anyVisible = false;
        $("#object-list li").each(function() {
            if($(this).is(":visible")) {
                anyVisible = true;
                return false; // Break the loop
            }
        });
        
        // Show/hide no results message
        if(!anyVisible && value.length > 0) {
            if($("#no-results").length === 0) {
                $("#object-list").after('<div id="no-results" class="alert alert-warning mt-3">No objects matching "' + value + '" found</div>');
            } else {
                $("#no-results").html('No objects matching "' + value + '" found');
            }
        } else {
            $("#no-results").remove();
        }
    });
    
    // Clear search button
    $("#clear-search").click(function() {
        $("#object-search").val("");
        $("#object-search").trigger("keyup");
    });
});