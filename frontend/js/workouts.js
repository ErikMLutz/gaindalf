import { api } from './api.js';
import { debounce, formatDate, showSaved } from './utils.js';

// ---------------------------------------------------------------------------
// Module-level state
// ---------------------------------------------------------------------------

let currentWorkoutId = null;
let allLifts = [];        // [{id, name, muscle_group_ids}]
let allMuscleGroups = []; // [{id, name}]

// ---------------------------------------------------------------------------
// Reference data
// ---------------------------------------------------------------------------

async function loadReferenceData() {
  try {
    [allLifts, allMuscleGroups] = await Promise.all([
      api.getLifts(),
      api.getMuscleGroups(),
    ]);
  } catch (err) {
    console.error('Failed to load reference data:', err);
  }
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function showEmptyState() {
  const editor = document.getElementById('workout-editor');
  if (!editor) return;
  editor.innerHTML =
    '<p class="empty-state">No workouts yet. <button class="btn-primary" id="create-first-btn">Create your first workout</button></p>';
  document.getElementById('create-first-btn').addEventListener('click', async () => {
    try {
      const w = await api.createWorkout();
      loadWorkout(w.id);
    } catch (err) {
      console.error('Failed to create first workout:', err);
    }
  });
}

// ---------------------------------------------------------------------------
// Load + render workout
// ---------------------------------------------------------------------------

async function loadWorkout(workoutId) {
  currentWorkoutId = workoutId;
  let workout;
  try {
    workout = await api.getWorkout(workoutId);
  } catch (err) {
    console.error('Failed to load workout:', err);
    return;
  }
  renderWorkout(workout);
}

function renderWorkout(workout) {
  const editor = document.getElementById('workout-editor');
  if (!editor) return;

  // Clear previous content
  editor.innerHTML = '';

  // --- Header ---
  const header = document.createElement('div');
  header.className = 'workout-header';

  const dateSpan = document.createElement('span');
  dateSpan.className = 'workout-date';
  dateSpan.textContent = formatDate(workout.date);

  const subtitleInput = document.createElement('input');
  subtitleInput.className = 'workout-subtitle editable-field';
  subtitleInput.placeholder = 'Add a note\u2026 (e.g. Heavy leg day)';
  subtitleInput.value = workout.subtitle || '';

  const debouncedSubtitleSave = debounce(async () => {
    try {
      await api.updateWorkout(workout.id, { subtitle: subtitleInput.value });
      showSaved();
    } catch (err) {
      console.error('Failed to save subtitle:', err);
    }
  }, 500);

  subtitleInput.addEventListener('input', debouncedSubtitleSave);

  const deleteWorkoutBtn = document.createElement('button');
  deleteWorkoutBtn.className = 'btn-danger btn-small';
  deleteWorkoutBtn.title = 'Delete workout';
  deleteWorkoutBtn.textContent = '\u2715';
  deleteWorkoutBtn.addEventListener('click', async () => {
    if (!confirm('Delete this workout? This cannot be undone.')) return;
    try {
      await api.deleteWorkout(workout.id);
      currentWorkoutId = null;
      await initWorkoutsTab();
    } catch (err) {
      console.error('Failed to delete workout:', err);
      alert('Could not delete workout.');
    }
  });

  header.appendChild(dateSpan);
  header.appendChild(subtitleInput);
  header.appendChild(deleteWorkoutBtn);
  editor.appendChild(header);

  // --- Lift cards container ---
  const cardsContainer = document.createElement('div');
  cardsContainer.id = 'lift-cards-container';

  const lifts = workout.workout_lifts || [];
  lifts.forEach((wl) => {
    const card = buildLiftCard(wl);
    cardsContainer.appendChild(card);
  });

  editor.appendChild(cardsContainer);

  // --- Footer ---
  const footer = document.createElement('div');
  footer.className = 'workout-footer';

  const autoMagicBtn = document.createElement('button');
  autoMagicBtn.className = 'btn-primary';
  autoMagicBtn.id = 'auto-magic-btn';
  autoMagicBtn.textContent = '\u2726 Auto Magic Add';
  autoMagicBtn.addEventListener('click', handleAutoMagicAdd);

  // Manual lift-add row
  const addLiftWrap = document.createElement('div');
  addLiftWrap.className = 'add-lift-wrap';

  const addLiftDatalist = document.createElement('datalist');
  addLiftDatalist.id = 'workout-lifts-datalist';
  allLifts.forEach((lift) => {
    const opt = document.createElement('option');
    opt.value = lift.name;
    addLiftDatalist.appendChild(opt);
  });

  const addLiftInput = document.createElement('input');
  addLiftInput.className = 'add-lift-input';
  addLiftInput.type = 'text';
  addLiftInput.placeholder = 'Add a lift\u2026';
  addLiftInput.setAttribute('list', 'workout-lifts-datalist');
  addLiftInput.setAttribute('autocomplete', 'off');

  const addLiftConfirmBtn = document.createElement('button');
  addLiftConfirmBtn.className = 'btn-secondary';
  addLiftConfirmBtn.textContent = 'Add';

  const doAddLift = async () => {
    const name = addLiftInput.value.trim();
    const lift = allLifts.find((l) => l.name.toLowerCase() === name.toLowerCase());
    if (!lift) return;
    try {
      await api.addLiftToWorkout(currentWorkoutId, { liftId: lift.id, displayOrder: 0 });
      await loadWorkout(currentWorkoutId);
    } catch (err) {
      console.error('Failed to add lift:', err);
    }
  };

  addLiftConfirmBtn.addEventListener('click', doAddLift);
  addLiftInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); doAddLift(); }
  });

  addLiftWrap.appendChild(addLiftDatalist);
  addLiftWrap.appendChild(addLiftInput);
  addLiftWrap.appendChild(addLiftConfirmBtn);

  const newWorkoutBtn = document.createElement('button');
  newWorkoutBtn.className = 'btn-secondary';
  newWorkoutBtn.id = 'new-workout-btn';
  newWorkoutBtn.textContent = 'New Workout';
  newWorkoutBtn.addEventListener('click', async () => {
    try {
      const w = await api.createWorkout();
      loadWorkout(w.id);
    } catch (err) {
      console.error('Failed to create new workout:', err);
    }
  });

  footer.appendChild(autoMagicBtn);
  footer.appendChild(addLiftWrap);
  footer.appendChild(newWorkoutBtn);
  editor.appendChild(footer);
}

// ---------------------------------------------------------------------------
// Lift card
// ---------------------------------------------------------------------------

function buildLiftCard(wl) {
  const card = document.createElement('div');
  card.className = 'lift-card';
  card.dataset.wlId = wl.id;

  // --- Card header ---
  const cardHeader = document.createElement('div');
  cardHeader.className = 'lift-card-header';

  const titleDiv = document.createElement('div');
  titleDiv.className = 'lift-card-title';

  const nameSpan = document.createElement('span');
  nameSpan.className = 'lift-card-name';
  nameSpan.textContent = wl.lift_name;

  titleDiv.appendChild(nameSpan);

  // Muscle group pills — look up from already-loaded reference data
  const liftData = allLifts.find((l) => l.id === wl.lift_id);
  const mgIds = liftData?.muscle_group_ids ?? [];
  if (mgIds.length > 0) {
    const mgMap = {};
    allMuscleGroups.forEach((g) => { mgMap[g.id] = g.name; });
    const pillsDiv = document.createElement('div');
    pillsDiv.className = 'lift-card-muscles';
    mgIds.forEach((gid) => {
      const gname = mgMap[gid];
      if (!gname) return;
      const pill = document.createElement('span');
      pill.className = 'muscle-pill';
      pill.textContent = gname;
      pillsDiv.appendChild(pill);
    });
    titleDiv.appendChild(pillsDiv);
  }

  const removeBtn = document.createElement('button');
  removeBtn.className = 'remove-lift-btn icon-btn';
  removeBtn.title = 'Remove lift';
  removeBtn.textContent = '\u2715';
  removeBtn.addEventListener('click', async () => {
    try {
      await api.removeWorkoutLift(currentWorkoutId, wl.id);
      card.remove();
    } catch (err) {
      console.error('Failed to remove lift:', err);
    }
  });

  cardHeader.appendChild(titleDiv);
  cardHeader.appendChild(removeBtn);
  card.appendChild(cardHeader);

  // --- Sets table ---
  const table = document.createElement('table');
  table.className = 'sets-table';

  const thead = document.createElement('thead');
  thead.innerHTML = '<tr><th>Set</th><th>Reps</th><th>Weight (kg)</th><th></th></tr>';
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  tbody.className = 'sets-tbody';

  const sets = wl.sets || [];
  sets.forEach((set) => {
    const row = buildSetRow(set);
    tbody.appendChild(row);
  });

  table.appendChild(tbody);
  card.appendChild(table);

  // --- Card footer ---
  const cardFooter = document.createElement('div');
  cardFooter.className = 'lift-card-footer';

  const addSetBtn = document.createElement('button');
  addSetBtn.className = 'btn-secondary add-set-btn';
  addSetBtn.textContent = '+ Set';
  addSetBtn.addEventListener('click', async () => {
    try {
      const newSet = await api.addSet(wl.id, {});
      const row = buildSetRow(newSet);
      tbody.appendChild(row);
    } catch (err) {
      console.error('Failed to add set:', err);
    }
  });

  cardFooter.appendChild(addSetBtn);
  card.appendChild(cardFooter);

  return card;
}

// ---------------------------------------------------------------------------
// Set row
// ---------------------------------------------------------------------------

function buildSetRow(set) {
  const tr = document.createElement('tr');
  tr.dataset.setId = set.id;

  // Set number cell
  const tdNum = document.createElement('td');
  tdNum.className = 'set-number';
  tdNum.textContent = set.set_number;

  // Reps cell
  const tdReps = document.createElement('td');
  const repsInput = document.createElement('input');
  repsInput.className = 'editable-number reps-input';
  repsInput.type = 'number';
  repsInput.min = '1';
  if (set.reps != null) repsInput.value = set.reps;
  repsInput.placeholder = '\u2014';
  tdReps.appendChild(repsInput);

  // Weight cell
  const tdWeight = document.createElement('td');
  const weightInput = document.createElement('input');
  weightInput.className = 'editable-number weight-input';
  weightInput.type = 'number';
  weightInput.min = '0';
  weightInput.step = '0.5';
  if (set.weight != null) weightInput.value = set.weight;
  weightInput.placeholder = '\u2014';
  tdWeight.appendChild(weightInput);

  // Delete cell
  const tdDelete = document.createElement('td');
  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'btn-danger btn-small delete-set-btn';
  deleteBtn.textContent = '\u2715';
  deleteBtn.addEventListener('click', async () => {
    try {
      await api.deleteSet(set.id);
      tr.remove();
    } catch (err) {
      console.error('Failed to delete set:', err);
    }
  });
  tdDelete.appendChild(deleteBtn);

  // Wire up auto-save for reps and weight
  const debouncedSave = debounce(async () => {
    const repsRaw = repsInput.value.trim();
    const weightRaw = weightInput.value.trim();
    const reps = repsRaw === '' ? null : parseInt(repsRaw, 10);
    const weight = weightRaw === '' ? null : parseFloat(weightRaw);
    try {
      await api.updateSet(set.id, { reps, weight });
      showSaved();
    } catch (err) {
      console.error('Failed to save set:', err);
    }
  }, 500);

  repsInput.addEventListener('input', debouncedSave);
  weightInput.addEventListener('input', debouncedSave);

  tr.appendChild(tdNum);
  tr.appendChild(tdReps);
  tr.appendChild(tdWeight);
  tr.appendChild(tdDelete);

  return tr;
}

// ---------------------------------------------------------------------------
// Auto Magic Add
// ---------------------------------------------------------------------------

async function handleAutoMagicAdd() {
  const btn = document.getElementById('auto-magic-btn');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '\u2726 Thinking\u2026';
  }

  try {
    // 1. Get suggestion
    const result = await api.suggestLift(currentWorkoutId);

    // 2. Add the lift to the workout
    const newWl = await api.addLiftToWorkout(currentWorkoutId, {
      liftId: result.lift_id,
      displayOrder: 0,
    });

    // 3. Add each previous set in order
    const previousSets = result.previous_sets || [];
    for (const s of previousSets) {
      await api.addSet(newWl.id, { reps: s.reps, weight: s.weight });
    }

    // 4. Re-render the full workout
    await loadWorkout(currentWorkoutId);
  } catch (err) {
    console.error('Auto magic add failed:', err);
    // Re-enable button so user can try again
    if (btn) {
      btn.disabled = false;
      btn.textContent = '\u2726 Auto Magic Add';
    }
  }
}

// ---------------------------------------------------------------------------
// Tab init + refresh
// ---------------------------------------------------------------------------

async function initWorkoutsTab() {
  await loadReferenceData();
  let workouts;
  try {
    workouts = await api.getWorkouts();
  } catch (err) {
    console.error('Failed to load workouts:', err);
    showEmptyState();
    return;
  }

  if (workouts.length > 0) {
    await loadWorkout(workouts[0].id); // list is already newest-first
  } else {
    showEmptyState();
  }
}

export function initWorkouts() {
  // Listen for navigation from home tab (open-workout event)
  document.addEventListener('open-workout', (e) => {
    loadWorkout(e.detail.workoutId);
  });

  // Load most recent workout on init (or show empty state)
  initWorkoutsTab();
}

export async function refreshWorkouts() {
  // Re-render current workout if one is loaded
  if (currentWorkoutId) {
    loadWorkout(currentWorkoutId);
  }
}
