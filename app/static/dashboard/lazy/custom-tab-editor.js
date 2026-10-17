async function deleteCustomTab(tabId) {
  const tab = customTabs.find(t => t.id === tabId);
  const tabName = tab ? tab.name : 'this tab';
  
  if (!confirm(`Are you sure you want to delete "${tabName}"? All items in this tab will be permanently deleted. This action cannot be undone.`)) return;
  
  try {
    if (!hasStoredAuth()) {
      alert('You must be logged in to delete custom tabs');
      return;
    }
    
    const response = await fetch(`${API_BASE}/custom-tabs/${tabId}`, {
      method: 'DELETE',
      ...authFetchOptions()
    });
    
    if (response.ok) {
      await loadCustomTabs();
      loadCustomTabsList();
      
      const tabContent = document.getElementById(`custom-${tabId}-tab`);
      if (tabContent) {
        tabContent.remove();
      }
      
      if (currentTab === `custom-${tabId}`) {
        switchTab('movies');
      }
    } else {
      const errorData = await response.json().catch(() => ({ detail: 'Failed to delete custom tab' }));
      alert(errorData.detail || 'Failed to delete custom tab');
    }
  } catch (error) {
    console.error('Error deleting custom tab:', error);
    alert('Failed to delete custom tab. Please try again.');
  }
}

function resetCustomTabFormState() {
  const form = document.getElementById('newCustomTabForm');
  if (form) {
    delete form.dataset.editingTabId;
    form.reset();
  }
  const fieldsList = document.getElementById('customTabFieldsList');
  if (fieldsList) {
    fieldsList.innerHTML = '';
  }
  const formWrapper = document.getElementById('createCustomTabForm');
  if (formWrapper) {
    formWrapper.style.display = 'none';
  }
  customTabFieldCounter = 0;
  const submitBtn = form?.querySelector('button[type="submit"]');
  if (submitBtn) submitBtn.textContent = 'Create Tab';
}

async function openEditCustomTab(tabId) {
  try {
    if (!hasStoredAuth()) {
      alert('You must be logged in to edit custom tabs');
      return;
    }
    const response = await fetch(`${API_BASE}/custom-tabs/${tabId}`, authFetchOptions());
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Failed to load custom tab' }));
      alert(errorData.detail || 'Failed to load custom tab');
      return;
    }
    const tab = await response.json();
    const formWrapper = document.getElementById('createCustomTabForm');
    if (formWrapper) formWrapper.style.display = 'block';
    const form = document.getElementById('newCustomTabForm');
    if (form) form.dataset.editingTabId = tab.id;
    const nameInput = document.getElementById('customTabName');
    const sourceSelect = document.getElementById('customTabSourceType');
    const allowUploads = document.getElementById('customTabAllowUploads');
    if (nameInput) nameInput.value = tab.name || '';
    if (sourceSelect) sourceSelect.value = tab.source_type || 'none';
    if (allowUploads) allowUploads.checked = !!tab.allow_uploads;
    const fieldsList = document.getElementById('customTabFieldsList');
    if (fieldsList) fieldsList.innerHTML = '';
    customTabFieldCounter = 0;
    (tab.fields || []).forEach(field => addCustomTabField(field));
    const submitBtn = form?.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.textContent = 'Update Tab';
  } catch (error) {
    console.error('Error loading custom tab for edit:', error);
    alert('Failed to load custom tab. Please try again.');
  }
}

