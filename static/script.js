document.addEventListener('DOMContentLoaded', () => {
  // --- Ingredient fields logic ---
  const ingredientsContainer = document.getElementById('ingredients-container');
  const addIngredientBtn     = document.getElementById('add-ingredient-btn');

  function updateIngredientNames() {
    if (!ingredientsContainer) return;
    const groups = ingredientsContainer.querySelectorAll('.ingredient-group');
    groups.forEach((group, index) => {
      const nameInput = group.querySelector('input[name^="ingredient_name_"]');
      const qtyInput  = group.querySelector('input[name^="ingredient_qty_"]');

      if (nameInput) {
        nameInput.name = `ingredient_name_${index}`;
        nameInput.id   = `ingredient_name_${index}`;
      }
      if (qtyInput) {
        qtyInput.name = `ingredient_qty_${index}`;
        qtyInput.id   = `ingredient_qty_${index}`;
      }

      const labels = group.querySelectorAll('label');
      if (labels[0]) labels[0].htmlFor = `ingredient_name_${index}`;
      if (labels[1]) labels[1].htmlFor = `ingredient_qty_${index}`;
    });
  }

  function addIngredient() {
    if (!ingredientsContainer) return;
    const newGroup = document.createElement('div');
    newGroup.className = 'ingredient-group';
    const newIndex = ingredientsContainer.querySelectorAll('.ingredient-group').length;

    newGroup.innerHTML = `
      <div class="form-group">
        <label for="ingredient_name_${newIndex}">Ingredient Name</label>
        <input type="text" id="ingredient_name_${newIndex}" name="ingredient_name_${newIndex}" placeholder="Ingredient Name">
      </div>
      <div class="form-group">
        <label for="ingredient_qty_${newIndex}">Quantity/Unit</label>
        <input type="text" id="ingredient_qty_${newIndex}" name="ingredient_qty_${newIndex}" placeholder="e.g., 1 cup">
      </div>
      <button type="button" class="remove-ingredient-btn">Remove ingredient</button>
    `;
    ingredientsContainer.appendChild(newGroup);

    // focus new name field
    const newInput = newGroup.querySelector(`#ingredient_name_${newIndex}`);
    if (newInput) newInput.focus();
  }

  function removeIngredient(event) {
    const removeBtn = event.target.closest('.remove-ingredient-btn');
    if (!removeBtn || !ingredientsContainer) return;
    const groups = ingredientsContainer.querySelectorAll('.ingredient-group');
    if (groups.length > 1) {
      removeBtn.closest('.ingredient-group').remove();
      updateIngredientNames();
    }
  }

  // Add / remove
  if (addIngredientBtn) addIngredientBtn.addEventListener('click', addIngredient);
  if (ingredientsContainer) ingredientsContainer.addEventListener('click', removeIngredient);

  // Enter on last qty field adds a new row
  if (ingredientsContainer) {
    ingredientsContainer.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      const groups = [...ingredientsContainer.querySelectorAll('.ingredient-group')];
      if (!groups.length) return;
      const last = groups[groups.length - 1];
      if (last.contains(e.target) && e.target.matches('input[id^="ingredient_qty_"]')) {
        e.preventDefault();
        addIngredient();
      }
    });
  }

  if (ingredientsContainer) updateIngredientNames();

  // --- Mobile Navigation Toggle ---
  const btn   = document.querySelector('.nav-toggle');
  const links = document.getElementById('site-links'); 

  if (btn && links) {
    btn.addEventListener('click', () => {
      const open = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', String(!open));
      links.classList.toggle('open', !open);
    });
  }

});
