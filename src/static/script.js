(() => {
  const form = document.getElementById('card-form');
  const preview = document.getElementById('card-preview');
  const downloadLink = document.querySelector('.button.secondary');
  const iconFileInput = document.getElementById('icon-file');
  const iconDataInput = document.getElementById('icon-data');
  const iconDropzone = document.getElementById('icon-dropzone');
  const iconStatus = document.getElementById('icon-status');
  const previewHint = document.getElementById('preview-hint');
  const creatureField = document.getElementById('creature-field');
  const phasesField = document.getElementById('phases-field');
  const rpField = document.getElementById('rp-field');
  let timeoutId = null;
  let currentCardType = 'ability';

  const sanitizeFilename = (value) => {
    return `${(value || 'card').replace(/[^A-Za-z0-9А-Яа-яЁё._-]+/g, '_').replace(/^[._-]+|[._-]+$/g, '') || 'card'}.png`;
  };

  const updateFieldVisibility = (cardType) => {
    currentCardType = cardType;
    
    // Hide/show fields based on card type
    creatureField.style.display = cardType === 'ability' || cardType === 'air-unit' ? '' : 'none';
    phasesField.style.display = cardType === 'ability' ? '' : 'none';
    rpField.style.display = cardType === 'air-unit' ? '' : 'none';
  };

  const refreshPreview = () => {
    const formData = new FormData(form);
    const params = new URLSearchParams();

    params.set('title', formData.get('title')?.toString() ?? '');
    params.set('description', formData.get('description')?.toString() ?? '');
    params.set('icon', formData.get('icon')?.toString() ?? '');
    params.set('icon_data', iconDataInput.value || '');
    params.set('card_type', currentCardType);

    // Add creature if visible (ability or air-unit)
    if (currentCardType === 'ability' || currentCardType === 'air-unit') {
      params.set('creature', formData.get('creature')?.toString() ?? '');
    }

    // Add phases if visible (ability)
    if (currentCardType === 'ability') {
      for (const phase of ['phase1', 'phase2', 'phase3', 'phase4']) {
        params.set(phase, form.querySelector(`[name="${phase}"]`)?.checked ? '1' : '0');
      }
    }

    // Add RP value if visible (air-unit)
    if (currentCardType === 'air-unit') {
      params.set('rp_value', formData.get('rp_value')?.toString() ?? '5');
    }

    const url = `/cards/card.png?${params.toString()}`;
    const titleValue = (formData.get('title')?.toString() ?? '').trim();
    const filename = sanitizeFilename(titleValue);
    preview.src = url;
    downloadLink.href = url;
    downloadLink.setAttribute('download', filename);
    previewHint.textContent = `/cards/card.png (${currentCardType})`;
  };

  const scheduleRefresh = () => {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(refreshPreview, 120);
  };

  const updateIconStatus = (message) => {
    iconStatus.textContent = message;
  };

  const loadIconFile = (file) => {
    if (!file) {
      iconDataInput.value = '';
      updateIconStatus('Иконка не загружена, используется заглушка.');
      scheduleRefresh();
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      iconDataInput.value = String(reader.result || '');
      updateIconStatus(`Загружен файл: ${file.name}`);
      scheduleRefresh();
    };
    reader.onerror = () => {
      iconDataInput.value = '';
      updateIconStatus('Не удалось прочитать DDS файл.');
    };
    reader.readAsDataURL(file);
  };

  form.addEventListener('input', scheduleRefresh);
  form.addEventListener('change', scheduleRefresh);
  iconDropzone.addEventListener('click', () => iconFileInput.click());
  iconDropzone.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      iconFileInput.click();
    }
  });
  iconFileInput.addEventListener('change', () => {
    loadIconFile(iconFileInput.files?.[0] ?? null);
  });
  iconDropzone.addEventListener('dragover', (event) => {
    event.preventDefault();
    iconDropzone.classList.add('is-dragover');
  });
  iconDropzone.addEventListener('dragleave', () => {
    iconDropzone.classList.remove('is-dragover');
  });
  iconDropzone.addEventListener('drop', (event) => {
    event.preventDefault();
    iconDropzone.classList.remove('is-dragover');
    const file = event.dataTransfer?.files?.[0] ?? null;
    loadIconFile(file);
  });

  // Card type button event listeners
  const typeButtons = document.querySelectorAll('.type-button');
  typeButtons.forEach(button => {
    button.addEventListener('click', () => {
      const cardType = button.getAttribute('data-type');
      
      // Update active button
      typeButtons.forEach(btn => btn.classList.remove('active'));
      button.classList.add('active');
      
      // Update field visibility
      updateFieldVisibility(cardType);
      
      // Refresh preview
      scheduleRefresh();
    });
  });

  // Initialize from URL parameters if available
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.has('title')) form.querySelector('[name=\"title\"]').value = urlParams.get('title');
  if (urlParams.has('creature')) form.querySelector('[name=\"creature\"]').value = urlParams.get('creature');
  if (urlParams.has('icon')) form.querySelector('[name=\"icon\"]').value = urlParams.get('icon');
  if (urlParams.has('description')) form.querySelector('[name=\"description\"]').value = urlParams.get('description');
  if (urlParams.has('rp_value')) form.querySelector('[name=\"rp_value\"]').value = urlParams.get('rp_value');
  if (urlParams.has('card_type')) {
    const cardType = urlParams.get('card_type');
    const typeButton = document.querySelector(`.type-button[data-type=\"${cardType}\"]`);
    if (typeButton) {
      typeButtons.forEach(btn => btn.classList.remove('active'));
      typeButton.classList.add('active');
      updateFieldVisibility(cardType);
    }
  }

  for (let i = 1; i <= 4; i++) {
    const phaseName = `phase${i}`;
    if (urlParams.has(phaseName)) {
      const val = urlParams.get(phaseName);
      form.querySelector(`[name="${phaseName}"]`).checked = ['1', 'true', 'on', 'yes'].includes(val.toLowerCase());
    }
  }

  // Initialize preview on page load
  refreshPreview();
})();