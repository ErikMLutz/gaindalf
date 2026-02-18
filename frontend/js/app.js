import { initHome, refreshHome } from './home.js';
import { initLifts, refreshLifts } from './lifts.js';
import { initWorkouts, refreshWorkouts } from './workouts.js';
import { api } from './api.js';

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

  tabBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;

      // Deactivate all
      tabBtns.forEach((b) => b.classList.remove('active'));
      tabPanels.forEach((p) => p.classList.remove('active'));

      // Activate the selected tab
      btn.classList.add('active');
      const panel = document.getElementById(`tab-${tab}`);
      if (panel) panel.classList.add('active');

      // Call the tab's refresh function if one has been registered
      if (typeof tabRefreshFns[tab] === 'function') {
        tabRefreshFns[tab]();
      }
    });
  });
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
