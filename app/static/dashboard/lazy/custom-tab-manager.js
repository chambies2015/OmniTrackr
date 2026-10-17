function showCustomTabManager() {
  document.getElementById('customTabManagerModal').style.display = 'flex';
  loadCustomTabsList();
}

function closeCustomTabManager() {
  document.getElementById('customTabManagerModal').style.display = 'none';
  resetCustomTabFormState();
}

async function loadCustomTabsList() {
  try {
    if (!hasStoredAuth()) return;
    
    const listContainer = document.getElementById('customTabsList');
    if (listContainer) {
      listContainer.innerHTML = '<div class="custom-tab-list-status">Loading...</div>';
    }
    
    const response = await fetch(`${API_BASE}/custom-tabs/`, authFetchOptions());
    
    if (response.ok) {
      const tabs = await response.json();
      if (listContainer) {
        if (tabs.length === 0) {
          listContainer.innerHTML = '<div class="custom-tab-list-status custom-tab-list-status-muted">No custom tabs yet. Create your first one above!</div>';
        } else {
          listContainer.innerHTML = tabs.map(tab => {
            return `
              <div class="custom-tab-list-item">
                <div>
                  <strong>${escapeHtml(tab.name)}</strong>
                  <div class="custom-tab-list-meta">
                    Source: ${tab.source_type} | Fields: ${tab.fields?.length || 0}
                  </div>
                </div>
                <div>
                  <button class="action-btn" data-action="edit-custom-tab" data-tab-id="${tab.id}" title="Edit tab">Edit</button>
                  <button class="action-btn btn-danger" data-action="delete-custom-tab" data-tab-id="${tab.id}" title="Delete tab">Delete</button>
                </div>
              </div>
            `;
          }).join('');
        }
      }
    } else {
      if (listContainer) {
        listContainer.innerHTML = '<div class="custom-tab-list-status custom-tab-list-status-danger">Failed to load custom tabs</div>';
      }
    }
  } catch (error) {
    console.error('Error loading custom tabs list:', error);
    const listContainer = document.getElementById('customTabsList');
    if (listContainer) {
      listContainer.innerHTML = '<div class="custom-tab-list-status custom-tab-list-status-danger">Error loading custom tabs</div>';
    }
  }
}

function showCreateCustomTabForm() {
  document.getElementById('createCustomTabForm').style.display = 'block';
  document.getElementById('customTabFieldsList').innerHTML = '';
  customTabFieldCounter = 0;
  const form = document.getElementById('newCustomTabForm');
  if (form) {
    delete form.dataset.editingTabId;
  }
  const submitBtn = form?.querySelector('button[type="submit"]');
  if (submitBtn) submitBtn.textContent = 'Create Tab';
}

function cancelCreateCustomTab() {
  document.getElementById('createCustomTabForm').style.display = 'none';
  document.getElementById('newCustomTabForm').reset();
  resetCustomTabFormState();
}

function addCustomTabField(fieldData = null) {
  const container = document.getElementById('customTabFieldsList');
  if (!container) return;
  
  const existingFields = Array.from(container.children).length;
  if (existingFields >= 30) {
    alert('Maximum of 30 fields allowed per tab');
    return;
  }
  
  const fieldId = customTabFieldCounter++;
  
  const fieldDiv = document.createElement('div');
  fieldDiv.className = `custom-tab-field-${fieldId}`;
  fieldDiv.style.marginBottom = '10px';
  fieldDiv.style.padding = '12px';
  fieldDiv.style.border = '1px solid var(--border)';
  fieldDiv.style.borderRadius = '6px';
  fieldDiv.style.backgroundColor = 'var(--bg)';
  fieldDiv.innerHTML = `
    <div class="custom-tab-field-grid">
      <input type="text" placeholder="Field Key (e.g., year)" id="fieldKey${fieldId}" required maxlength="50" pattern="^[a-zA-Z_][a-zA-Z0-9_]*$" title="Must start with letter/underscore, alphanumeric only" class="custom-tab-field-input">
      <input type="text" placeholder="Field Label (e.g., Year)" id="fieldLabel${fieldId}" required maxlength="100" class="custom-tab-field-input">
      <select id="fieldType${fieldId}" required class="custom-tab-field-input">
        <option value="text">Text</option>
        <option value="number">Number</option>
        <option value="date">Date</option>
        <option value="boolean">Boolean</option>
        <option value="rating">Rating</option>
        <option value="review">Review</option>
        <option value="status">Status</option>
      </select>
      <label class="custom-tab-field-label">
        <input type="checkbox" id="fieldRequired${fieldId}">
        Required
      </label>
      <button type="button" class="action-btn btn-danger custom-tab-field-remove" data-action="remove-custom-tab-field" data-field-id="${fieldId}">Remove</button>
    </div>
  `;
  
  container.appendChild(fieldDiv);
  
  const keyInput = fieldDiv.querySelector(`#fieldKey${fieldId}`);
  const labelInput = fieldDiv.querySelector(`#fieldLabel${fieldId}`);
  const typeSelect = fieldDiv.querySelector(`#fieldType${fieldId}`);
  const requiredInput = fieldDiv.querySelector(`#fieldRequired${fieldId}`);
  if (fieldData) {
    if (keyInput) keyInput.value = fieldData.key || '';
    if (labelInput) labelInput.value = fieldData.label || '';
    if (typeSelect) typeSelect.value = fieldData.field_type || 'text';
    if (requiredInput) requiredInput.checked = !!fieldData.required;
  }
  if (keyInput) {
    keyInput.addEventListener('input', () => validateFieldKey(keyInput, container));
  }
}

function validateFieldKey(input, container) {
  const value = input.value.trim();
  if (!value) return;
  
  if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(value)) {
    input.setCustomValidity('Must start with letter/underscore, alphanumeric only');
  } else {
    const fieldDivs = Array.from(container.children);
    const duplicates = fieldDivs.filter(div => {
      const fieldId = div.className.match(/custom-tab-field-(\d+)/)?.[1];
      if (!fieldId) return false;
      const otherKeyInput = div.querySelector(`#fieldKey${fieldId}`);
      return otherKeyInput && otherKeyInput !== input && otherKeyInput.value.trim() === value;
    });
    
    if (duplicates.length > 0) {
      input.setCustomValidity('Field key must be unique');
    } else {
      input.setCustomValidity('');
    }
  }
}

