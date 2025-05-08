document.addEventListener('DOMContentLoaded', function() {
    // Initialize chat interface if present
    initChatInterface();
    
    // Initialize schema explorer if present
    initSchemaExplorer();
    
    // Initialize data generation form if present
    initDataGenerationForm();
});

// Global object for Salesforce schema data
const sfSchema = {
    selectedObject: null,
    objectDetails: {},
    fields: {}
};

/**
 * Initialize the chat interface
 */
function initChatInterface() {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    
    if (!chatForm) return;
    
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const message = chatInput.value.trim();
        if (!message) return;
        
        // Add user message to chat
        addChatMessage('user', message);
        chatInput.value = '';
        
        // Show thinking indicator
        addChatMessage('assistant', '...', 'thinking');
        
        // Send message to server
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message })
        })
        .then(response => response.json())
        .then(data => {
            // Remove thinking indicator
            document.querySelector('.thinking')?.remove();
            
            // Add response to chat
            if (data.error) {
                addChatMessage('system', `Error: ${data.error}`, 'error');
            } else {
                addChatMessage('assistant', data.message);
            }
        })
        .catch(error => {
            // Remove thinking indicator
            document.querySelector('.thinking')?.remove();
            
            // Add error message
            addChatMessage('system', `Error: ${error.message}`, 'error');
        });
    });
}

/**
 * Add a message to the chat interface
 */
function addChatMessage(role, message, className = '') {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${role} ${className}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'chat-avatar';
    
    // Set avatar based on role
    switch(role) {
        case 'user':
            avatar.innerHTML = '<i class="bi bi-person-circle"></i>';
            break;
        case 'assistant':
            avatar.innerHTML = '<i class="bi bi-robot"></i>';
            break;
        case 'system':
            avatar.innerHTML = '<i class="bi bi-exclamation-triangle"></i>';
            break;
    }
    
    const content = document.createElement('div');
    content.className = 'chat-content';
    content.textContent = message;
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Initialize the schema explorer
 */
function initSchemaExplorer() {
    const objectList = document.getElementById('object-list');
    const objectDetails = document.getElementById('object-details');
    
    if (!objectList) return;
    
    // Add click event listeners to object list items
    const objectItems = objectList.querySelectorAll('li');
    objectItems.forEach(item => {
        item.addEventListener('click', function() {
            // Remove active class from all items
            objectItems.forEach(i => i.classList.remove('active'));
            
            // Add active class to clicked item
            this.classList.add('active');
            
            // Set selected object
            const objectName = this.getAttribute('data-object');
            sfSchema.selectedObject = objectName;
            
            // Show loading indicator
            objectDetails.innerHTML = '<div class="text-center my-5"><div class="spinner-border" role="status"></div><p class="mt-2">Loading object details...</p></div>';
            
            // Fetch object details
            fetch(`/schema/${objectName}`)
            .then(response => response.json())
            .then(data => {
                // Store object details
                sfSchema.objectDetails[objectName] = data;
                
                // Render object details
                renderObjectDetails(data);
            })
            .catch(error => {
                objectDetails.innerHTML = `<div class="alert alert-danger">Error loading object details: ${error.message}</div>`;
            });
        });
    });
}

/**
 * Filter the object list based on search term
 */
function filterObjectList(searchTerm) {
    console.log("Filtering object list with term:", searchTerm);
    const objectList = document.getElementById('object-list');
    if (!objectList) return;
    
    // Convert search term to lowercase for case-insensitive comparison
    searchTerm = searchTerm.toLowerCase();
    
    const items = objectList.querySelectorAll('li');
    let matchFound = false;
    
    // For empty search term, show all items
    if (searchTerm === '') {
        items.forEach(item => {
            item.style.display = 'flex';
        });
        
        // Remove any "no results" message
        const noResultsMessage = document.getElementById('no-search-results');
        if (noResultsMessage) {
            noResultsMessage.remove();
        }
        
        return;
    }
    
    // Process each item for non-empty search term
    items.forEach(item => {
        // Get all sources of text to search in
        const itemText = item.textContent.toLowerCase().trim();
        const objectName = (item.getAttribute('data-object') || '').toLowerCase();
        const objectLabel = (item.getAttribute('data-object-label') || '').toLowerCase();
        
        // Simple word match
        if (itemText.includes(searchTerm) || 
            objectName.includes(searchTerm) || 
            objectLabel.includes(searchTerm)) {
            item.style.display = 'flex';
            matchFound = true;
        } else {
            item.style.display = 'none';
        }
    });
    
    // Add visual feedback if no matches were found
    const noResultsMessage = document.getElementById('no-search-results');
    if (!noResultsMessage && !matchFound) {
        const message = document.createElement('div');
        message.id = 'no-search-results';
        message.className = 'alert alert-warning mt-3';
        message.textContent = `No objects matching "${searchTerm}" found`;
        message.style.color = '#fff';
        message.style.backgroundColor = 'rgba(255, 193, 7, 0.2)';
        message.style.borderColor = 'rgba(255, 193, 7, 0.3)';
        
        // Insert the message after the object list
        objectList.parentNode.insertBefore(message, objectList.nextSibling);
    } else if (noResultsMessage && matchFound) {
        noResultsMessage.remove();
    }
}

/**
 * Render object details in the UI
 */
function renderObjectDetails(objectData) {
    const objectDetails = document.getElementById('object-details');
    if (!objectDetails) return;
    
    // Create details HTML
    let html = `
        <div class="card mb-4">
            <div class="card-header">
                <h3>${objectData.label} (${objectData.name})</h3>
            </div>
            <div class="card-body">
                <h4>Fields</h4>
                <div class="table-responsive">
                    <table class="table table-striped">
                        <thead>
                            <tr>
                                <th>Label</th>
                                <th>API Name</th>
                                <th>Type</th>
                                <th>Required</th>
                                <th>Details</th>
                            </tr>
                        </thead>
                        <tbody>
    `;
    
    // Add fields to table
    objectData.fields.forEach(field => {
        html += `
            <tr>
                <td>${field.label}</td>
                <td>${field.name}</td>
                <td>${field.type}</td>
                <td>${field.required ? '<span class="badge bg-danger">Required</span>' : ''}</td>
                <td>
        `;
        
        // Add field-specific details
        if (field.type === 'picklist' || field.type === 'multipicklist') {
            html += `<button class="btn btn-sm btn-outline-info" data-bs-toggle="modal" data-bs-target="#fieldModal" data-field="${field.name}">View Options</button>`;
        } else if (field.type === 'reference') {
            html += `References: ${field.referenceTo.join(', ')}`;
        } else if (field.type === 'string' || field.type === 'textarea') {
            html += `Max Length: ${field.length}`;
        }
        
        html += `
                </td>
            </tr>
        `;
    });
    
    html += `
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="card-footer">
                <a href="/generate?object=${objectData.name}" class="btn btn-primary">Generate Test Data</a>
            </div>
        </div>
    `;
    
    // Add modal for field details
    html += `
        <div class="modal fade" id="fieldModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Field Details</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body" id="field-details-content">
                        Loading...
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Set HTML content
    objectDetails.innerHTML = html;
    
    // Add event listener for field detail modals
    const fieldModal = document.getElementById('fieldModal');
    if (fieldModal) {
        fieldModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const fieldName = button.getAttribute('data-field');
            const fieldData = objectData.fields.find(f => f.name === fieldName);
            
            const modalContent = document.getElementById('field-details-content');
            
            if (fieldData) {
                let content = `<h5>${fieldData.label} (${fieldData.name})</h5>`;
                
                if (fieldData.type === 'picklist' || fieldData.type === 'multipicklist') {
                    content += `<h6>Picklist Values:</h6><ul>`;
                    fieldData.picklistValues.forEach(value => {
                        content += `<li>${value}</li>`;
                    });
                    content += `</ul>`;
                }
                
                modalContent.innerHTML = content;
            } else {
                modalContent.innerHTML = `<div class="alert alert-danger">Field data not found</div>`;
            }
        });
    }
}

/**
 * Initialize the data generation form
 */
function initDataGenerationForm() {
    const generateForm = document.getElementById('generate-form');
    const recordCountInput = document.getElementById('record-count');
    const objectSelect = document.getElementById('object-select');
    
    if (!generateForm) return;
    
    // Set default record count
    if (recordCountInput && !recordCountInput.value) {
        recordCountInput.value = 5;
    }
    
    // Add form submission handler
    generateForm.addEventListener('submit', function(e) {
        // Validate form
        if (objectSelect && objectSelect.value === '') {
            e.preventDefault();
            alert('Please select an object');
            return;
        }
        
        if (recordCountInput) {
            const count = parseInt(recordCountInput.value);
            if (isNaN(count) || count < 1 || count > 100) {
                e.preventDefault();
                alert('Record count must be between 1 and 100');
                return;
            }
        }
        
        // Show loading indication
        const submitBtn = generateForm.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generating...';
        }
    });
}
