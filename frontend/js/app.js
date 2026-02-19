import { initHome, refreshHome } from './home.js';
import { initLifts, refreshLifts } from './lifts.js';
import { initWorkouts, refreshWorkouts } from './workouts.js';
import { api } from './api.js';
import { showSaved } from './utils.js';

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------

// Each tab module may register a refresh callback via this map.
// Keys match the data-tab attribute values on .tab-btn elements.
const tabRefreshFns = {};

/**
 * Allow tab modules to register a function to call whenever their tab becomes
 * active. Called with no arguments.
 * @param {string} tabName
 * @param {Function} fn
 */
export function registerTabRefresh(tabName, fn) {
  tabRefreshFns[tabName] = fn;
}

function setupTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabPanels = document.querySelectorAll('.tab-panel');

  function activateTab(tab) {
    tabBtns.forEach((b) => b.classList.remove('active'));
    tabPanels.forEach((p) => p.classList.remove('active'));
    const btn = document.querySelector(`.tab-btn[data-tab="${tab}"]`);
    if (btn) btn.classList.add('active');
    const panel = document.getElementById(`tab-${tab}`);
    if (panel) panel.classList.add('active');
    if (typeof tabRefreshFns[tab] === 'function') {
      tabRefreshFns[tab]();
    }
  }

  tabBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      activateTab(tab);
      history.pushState({ tab }, '', `#${tab}`);
    });
  });

  // Back/forward navigation
  window.addEventListener('popstate', (e) => {
    activateTab(e.state?.tab ?? 'home');
  });

  // Restore from URL hash on initial load and seed the history state
  const validTabs = [...tabBtns].map((b) => b.dataset.tab);
  const hashTab = location.hash.slice(1);
  const startTab = validTabs.includes(hashTab) ? hashTab : 'home';
  const startUrl = startTab !== 'home' ? `#${startTab}` : location.pathname + location.search;
  history.replaceState({ tab: startTab }, '', startUrl);
  // Home is already active in HTML; only switch UI if a different tab is requested.
  // Refresh functions aren't registered yet so activateTab safely skips them here.
  if (startTab !== 'home') {
    activateTab(startTab);
  }
}

// ---------------------------------------------------------------------------
// Settings dialog
// ---------------------------------------------------------------------------

function setupSettings() {
  const dialog = document.getElementById('settings-dialog');
  const openBtn = document.getElementById('settings-btn');
  const closeBtn = document.getElementById('settings-close');

  if (!dialog || !openBtn || !closeBtn) return;

  // Open
  openBtn.addEventListener('click', () => {
    loadMuscleGroupsTable();
    loadMuscleGroupsIntoSelects();
    loadConflicts();
    dialog.showModal();
  });

  // Close via close button
  closeBtn.addEventListener('click', () => dialog.close());

  // Close on backdrop click (click outside the dialog inner content)
  dialog.addEventListener('click', (e) => {
    if (e.target === dialog) dialog.close();
  });

  // Add-conflict form
  const addBtn = document.getElementById('add-conflict-btn');
  if (addBtn) {
    addBtn.addEventListener('click', handleAddConflict);
  }
}

/**
 * Fetch muscle groups and render them as an editable table in the settings dialog.
 */
async function loadMuscleGroupsTable() {
  const wrap = document.getElementById('muscle-groups-table-wrap');
  if (!wrap) return;

  let groups;
  try {
    groups = await api.getMuscleGroups();
  } catch (err) {
    console.error('Failed to load muscle groups:', err);
    wrap.innerHTML = '<p class="empty-state">Could not load muscle groups.</p>';
    return;
  }

  wrap.innerHTML = `
    <div class="settings-add-row">
      <button class="btn-primary btn-small" id="add-muscle-group-btn">+ New</button>
    </div>
    <table class="settings-table">
      <tbody id="muscle-groups-tbody"></tbody>
    </table>
  `;

  const tbody = document.getElementById('muscle-groups-tbody');
  if (!groups || groups.length === 0) {
    const tr = document.createElement('tr');
    tr.innerHTML = '<td class="settings-table-empty">No muscle groups yet.</td>';
    tbody.appendChild(tr);
  } else {
    groups.forEach((g) => tbody.appendChild(buildMuscleGroupRow(g)));
  }

  document.getElementById('add-muscle-group-btn')?.addEventListener('click', async () => {
    const name = prompt('Muscle group name:');
    if (!name || !name.trim()) return;
    try {
      await api.createMuscleGroup(name.trim());
      await loadMuscleGroupsTable();
      await loadMuscleGroupsIntoSelects();
    } catch (err) {
      console.error('Failed to create muscle group:', err);
      alert('Could not create muscle group. Name may already exist.');
    }
  });
}

/**
 * Build a single table row for a muscle group with inline rename and delete.
 * @param {{ id: number, name: string }} group
 * @returns {HTMLTableRowElement}
 */
function buildMuscleGroupRow(group) {
  const tr = document.createElement('tr');
  tr.dataset.mgId = group.id;

  // Name cell with double-click-to-edit
  const nameTd = document.createElement('td');
  nameTd.className = 'lift-name-cell';

  const nameDisplay = document.createElement('span');
  nameDisplay.className = 'lift-name-display';
  nameDisplay.textContent = group.name;
  nameDisplay.title = 'Double-click to rename';

  const nameInput = document.createElement('input');
  nameInput.className = 'lift-name-input editable-field';
  nameInput.value = group.name;
  nameInput.style.display = 'none';

  nameDisplay.addEventListener('dblclick', (e) => {
    e.stopPropagation();
    nameDisplay.style.display = 'none';
    nameInput.style.display = '';
    nameInput.focus();
    nameInput.select();
  });

  nameInput.addEventListener('blur', () => {
    commitMuscleGroupRename(group.id, nameDisplay, nameInput);
  });

  nameInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      nameInput.blur();
    } else if (e.key === 'Escape') {
      nameInput.value = nameDisplay.textContent;
      nameInput.style.display = 'none';
      nameDisplay.style.display = '';
    }
  });

  nameTd.appendChild(nameDisplay);
  nameTd.appendChild(nameInput);

  // Delete cell
  const deleteTd = document.createElement('td');
  deleteTd.className = 'settings-table-action';
  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'btn-danger btn-small';
  deleteBtn.textContent = '\u2715';
  deleteBtn.setAttribute('aria-label', `Delete ${group.name}`);
  deleteBtn.addEventListener('click', async () => {
    if (!confirm(`Delete "${group.name}"?`)) return;
    try {
      await api.deleteMuscleGroup(group.id);
      tr.remove();
      await loadMuscleGroupsIntoSelects();
      await loadConflicts();
    } catch (err) {
      console.error('Failed to delete muscle group:', err);
      alert('Could not delete muscle group.');
    }
  });
  deleteTd.appendChild(deleteBtn);

  tr.appendChild(nameTd);
  tr.appendChild(deleteTd);
  return tr;
}

/**
 * Commit an inline rename for a muscle group.
 * @param {number} id
 * @param {HTMLElement} displayEl
 * @param {HTMLInputElement} inputEl
 */
async function commitMuscleGroupRename(id, displayEl, inputEl) {
  const newName = inputEl.value.trim();
  inputEl.style.display = 'none';
  displayEl.style.display = '';

  if (!newName || newName === displayEl.textContent) return;

  try {
    await api.renameMuscleGroup(id, newName);
    displayEl.textContent = newName;
    await loadMuscleGroupsIntoSelects();
    showSaved();
  } catch (err) {
    console.error('Failed to rename muscle group:', err);
    inputEl.value = displayEl.textContent;
    alert('Could not rename muscle group.');
  }
}

/**
 * Fetch muscle groups and populate both select dropdowns in the settings dialog.
 */
async function loadMuscleGroupsIntoSelects() {
  const selectA = document.getElementById('conflict-group-a');
  const selectB = document.getElementById('conflict-group-b');
  if (!selectA || !selectB) return;

  let groups;
  try {
    groups = await api.getMuscleGroups();
  } catch (err) {
    console.error('Failed to load muscle groups:', err);
    return;
  }

  function buildOptions(select) {
    // Keep the placeholder option
    const placeholder = select.options[0];
    select.innerHTML = '';
    select.appendChild(placeholder);
    groups.forEach((g) => {
      const opt = document.createElement('option');
      opt.value = g.id;
      opt.textContent = g.name;
      select.appendChild(opt);
    });
  }

  buildOptions(selectA);
  buildOptions(selectB);
}

/**
 * Fetch the conflict list and render it into #conflicts-list.
 * Each conflict is rendered as a pill with a delete button.
 */
async function loadConflicts() {
  const container = document.getElementById('conflicts-list');
  if (!container) return;

  let conflicts;
  try {
    conflicts = await api.getConflicts();
  } catch (err) {
    console.error('Failed to load conflicts:', err);
    container.innerHTML = '<p class="empty-state">Could not load conflicts.</p>';
    return;
  }

  if (!conflicts || conflicts.length === 0) {
    container.innerHTML = '<p class="empty-state">No conflicts defined.</p>';
    return;
  }

  container.innerHTML = '';
  conflicts.forEach((conflict) => {
    const pill = buildConflictPill(conflict);
    container.appendChild(pill);
  });
}

/**
 * Build a single conflict pill element.
 * @param {{ id: number, muscle_group_a: { name: string }, muscle_group_b: { name: string } }} conflict
 * @returns {HTMLElement}
 */
function buildConflictPill(conflict) {
  const pill = document.createElement('div');
  pill.className = 'conflict-pill';
  pill.dataset.conflictId = conflict.id;

  const label = document.createElement('span');
  const nameA = conflict.muscle_group_a?.name ?? conflict.muscle_group_a_name ?? `Group ${conflict.muscle_group_a_id}`;
  const nameB = conflict.muscle_group_b?.name ?? conflict.muscle_group_b_name ?? `Group ${conflict.muscle_group_b_id}`;
  label.textContent = `${nameA} \u2194 ${nameB}`;

  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'conflict-delete-btn';
  deleteBtn.setAttribute('aria-label', `Remove conflict between ${nameA} and ${nameB}`);
  deleteBtn.textContent = '\u00d7';
  deleteBtn.addEventListener('click', () => handleDeleteConflict(conflict.id));

  pill.appendChild(label);
  pill.appendChild(deleteBtn);
  return pill;
}

/**
 * Handle the "Add" button click in the conflict form.
 */
async function handleAddConflict() {
  const selectA = document.getElementById('conflict-group-a');
  const selectB = document.getElementById('conflict-group-b');

  const idA = Number(selectA?.value);
  const idB = Number(selectB?.value);

  if (!idA || !idB) {
    alert('Please select both muscle groups.');
    return;
  }
  if (idA === idB) {
    alert('Please select two different muscle groups.');
    return;
  }

  try {
    await api.addConflict(idA, idB);
  } catch (err) {
    console.error('Failed to add conflict:', err);
    alert('Could not add conflict. It may already exist.');
    return;
  }

  // Reset selects and reload the list
  selectA.value = '';
  selectB.value = '';
  await loadConflicts();
}

/**
 * Handle the delete button on a conflict pill.
 * @param {number} id
 */
async function handleDeleteConflict(id) {
  try {
    await api.deleteConflict(id);
  } catch (err) {
    console.error('Failed to delete conflict:', err);
    alert('Could not remove conflict.');
    return;
  }
  await loadConflicts();
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  setupTabs();
  setupSettings();
  initHome();
  registerTabRefresh('home', refreshHome);
  initLifts();
  registerTabRefresh('lifts', refreshLifts);
  initWorkouts();
  registerTabRefresh('workouts', refreshWorkouts);
});
