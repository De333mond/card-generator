// DOM Elements
const cardTypeSelect = document.getElementById('cardType');
const cardForm = document.getElementById('cardForm');
const cardPreview = document.getElementById('cardPreview');
const downloadBtn = document.getElementById('downloadBtn');

// Form fields
const titleInput = document.getElementById('title');
const creatureInput = document.getElementById('creature');
const descriptionInput = document.getElementById('description');
const iconInput = document.getElementById('icon');
const iconFileInput = document.getElementById('iconFile');

// Ability fields
const abilityFields = document.getElementById('abilityFields');
const phaseCheckboxes = document.querySelectorAll('input[name^="phase"]');

// Study fields
const studyFields = document.getElementById('studyFields');
const studyDescriptionInput = document.getElementById('studyDescription');

// Building fields
const buildingFields = document.getElementById('buildingFields');
const crystalInput = document.getElementById('crystal');
const cloudInput = document.getElementById('cloud');
const clockInput = document.getElementById('clock');
const buildingDescriptionInput = document.getElementById('buildingDescription');
const unlocksInput = document.getElementById('unlocks');
const requirementsInput = document.getElementById('requirements');

// Air unit fields
const airUnitFields = document.getElementById('airUnitFields');
const airCreatureInput = document.getElementById('airCreature');
const airDescriptionInput = document.getElementById('airDescription');
const rpValueInput = document.getElementById('rpValue');
const airPhaseCheckboxes = document.querySelectorAll('input[name^="airPhase"]');

// Unit fields
const unitFields = document.getElementById('unitFields');
const unitNameInput = document.getElementById('unitName');
const unitHealthInput = document.getElementById('unitHealth');
const unitShieldsInput = document.getElementById('unitShields');
const unitForwardInput = document.getElementById('unitForward');
const unitShieldInput = document.getElementById('unitShield');
const unitSwordInput = document.getElementById('unitSword');
const unitCrystalInput = document.getElementById('unitCrystal');
const unitCloudInput = document.getElementById('unitCloud');
const unitDescriptionInput = document.getElementById('unitDescription');
const unitPropertiesInput = document.getElementById('unitProperties');

// Icon data (base64)
let iconData = '';

// Update visibility of form fields based on card type
function updateFormFields() {
  const cardType = cardTypeSelect.value;

  abilityFields.style.display = cardType === 'ability' ? 'block' : 'none';
  studyFields.style.display = cardType === 'study' ? 'block' : 'none';
  buildingFields.style.display = cardType === 'building' ? 'block' : 'none';
  airUnitFields.style.display = cardType === 'air-unit' ? 'block' : 'none';
  unitFields.style.display = cardType === 'unit' ? 'block' : 'none';

  updatePreview();
}

// Build query string based on card type and form values
function buildQueryString() {
  const cardType = cardTypeSelect.value;
  const params = new URLSearchParams();

  params.append('card_type', cardType);
  params.append('title', titleInput.value || 'New Card');
  params.append('icon', iconInput.value || 'DDS');

  if (iconData) {
    params.append('icon_data', iconData);
  }

  switch (cardType) {
    case 'ability':
      params.append('creature', creatureInput.value || 'Существо');
      params.append('description', descriptionInput.value || '');
      addPhaseParams(params, phaseCheckboxes);
      break;

    case 'study':
      params.append('description', studyDescriptionInput.value || '');
      break;

    case 'building':
      params.append('crystal', crystalInput.value || '0');
      params.append('cloud', cloudInput.value || '0');
      params.append('clock', clockInput.value || '0');
      params.append('description', buildingDescriptionInput.value || '');
      params.append('unlocks', unlocksInput.value || '');
      params.append('requirements', requirementsInput.value || '');
      break;

    case 'air-unit':
      params.append('creature', airCreatureInput.value || 'Юнит');
      params.append('description', airDescriptionInput.value || '');
      params.append('rp_value', rpValueInput.value || '5');
      addPhaseParams(params, airPhaseCheckboxes);
      break;

    case 'unit':
      params.append('creature', unitNameInput.value || 'Юнит');
      params.append('health', unitHealthInput.value || '5');
      params.append('shields', unitShieldsInput.value || '10');
      params.append('forward', unitForwardInput.value || '0');
      params.append('shield', unitShieldInput.value || '0');
      params.append('sword', unitSwordInput.value || '0');
      params.append('crystal', unitCrystalInput.value || '0');
      params.append('cloud', unitCloudInput.value || '0');
      params.append('description', unitDescriptionInput.value || '');
      params.append('properties', unitPropertiesInput.value || '');
      break;
  }

  return params.toString();
}

// Add phase parameters
function addPhaseParams(params, checkboxes) {
  checkboxes.forEach((checkbox, index) => {
    if (checkbox.checked) {
      params.append(`phase${index + 1}`, '1');
    }
  });
}

// Update card preview
function updatePreview() {
  const queryString = buildQueryString();
  cardPreview.src = `/cards/card.png?${queryString}`;
}

// Handle file upload for icon
iconFileInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (file) {
    const reader = new FileReader();
    reader.onload = (event) => {
      iconData = event.target.result;
      updatePreview();
    };
    reader.readAsDataURL(file);
  }
});

// Add event listeners for form changes
cardTypeSelect.addEventListener('change', updateFormFields);
titleInput.addEventListener('input', updatePreview);
creatureInput.addEventListener('input', updatePreview);
descriptionInput.addEventListener('input', updatePreview);
iconInput.addEventListener('input', updatePreview);
studyDescriptionInput.addEventListener('input', updatePreview);
crystalInput.addEventListener('input', updatePreview);
cloudInput.addEventListener('input', updatePreview);
clockInput.addEventListener('input', updatePreview);
buildingDescriptionInput.addEventListener('input', updatePreview);
unlocksInput.addEventListener('input', updatePreview);
requirementsInput.addEventListener('input', updatePreview);
airCreatureInput.addEventListener('input', updatePreview);
airDescriptionInput.addEventListener('input', updatePreview);
rpValueInput.addEventListener('input', updatePreview);

unitNameInput.addEventListener('input', updatePreview);
unitHealthInput.addEventListener('input', updatePreview);
unitShieldsInput.addEventListener('input', updatePreview);
unitForwardInput.addEventListener('input', updatePreview);
unitShieldInput.addEventListener('input', updatePreview);
unitSwordInput.addEventListener('input', updatePreview);
unitCrystalInput.addEventListener('input', updatePreview);
unitCloudInput.addEventListener('input', updatePreview);
unitDescriptionInput.addEventListener('input', updatePreview);
unitPropertiesInput.addEventListener('input', updatePreview);

phaseCheckboxes.forEach(checkbox => {
  checkbox.addEventListener('change', updatePreview);
});

airPhaseCheckboxes.forEach(checkbox => {
  checkbox.addEventListener('change', updatePreview);
});

// Download button
downloadBtn.addEventListener('click', () => {
  const queryString = buildQueryString();
  const link = document.createElement('a');
  link.href = `/cards/card.png?${queryString}`;
  link.download = `${titleInput.value || 'card'}.png`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
});

// Initialize
updateFormFields();
