import { api } from './api.js';
import { debounce, formatDate, showSaved } from './utils.js';

let liftChart = null;       // Chart.js instance, destroyed/recreated on each lift selection
let allLifts = [];           // [{id, name, muscle_group_ids}]
let muscleGroupMap = {};     // {id: name}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

async function loadLiftsData() {
  try {
    const [lifts, muscleGroups] = await Promise.all([
      api.getLifts(),
      api.getMuscleGroups(),
    ]);
    allLifts = Array.isArray(lifts) ? lifts : [];
    muscleGroupMap = {};
    if (Array.isArray(muscleGroups)) {
      muscleGroups.forEach((g) => {
        muscleGroupMap[g.id] = g.name;
      });
    }
  } catch (err) {
    console.error('Failed to load lifts data:', err);
    allLifts = [];
    muscleGroupMap = {};
  }
}

// ---------------------------------------------------------------------------
// Datalist population
// ---------------------------------------------------------------------------

function populateDatalist() {
  const datalist = document.getElementById('lifts-datalist');
  if (!datalist) return;
  datalist.innerHTML = '';
  allLifts.forEach((lift) => {
    const opt = document.createElement('option');
    opt.value = lift.name;
    opt.dataset.id = lift.id;
    datalist.appendChild(opt);
  });
}

// ---------------------------------------------------------------------------
// Lift history chart
// ---------------------------------------------------------------------------

async function renderLiftChart(liftId) {
  const canvas = document.getElementById('lift-chart');
  if (!canvas) return;

  // Destroy existing chart before recreating
  if (liftChart) {
    liftChart.destroy();
    liftChart = null;
  }

  let data = [];
  try {
    data = await api.getLiftHistory(liftId);
    if (!Array.isArray(data)) data = [];
  } catch (err) {
    console.error('Failed to load lift history:', err);
    data = [];
  }

  const labels = data.map((d) => d.date);
  const strengthValues = data.map((d) => d.strength_index ?? null);
  const enduranceValues = data.map((d) => d.endurance_index ?? null);
  const baselineValues = data.map(() => 1.0);

  const textColor = '#5c4a1e';
  const gridColor = 'rgba(196, 165, 90, 0.3)';

  liftChart = new window.Chart(canvas, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Strength Index',
          data: strengthValues,
          borderColor: '#8b6914',
          backgroundColor: 'rgba(139, 105, 20, 0.08)',
          pointRadius: 3,
          pointHoverRadius: 5,
          tension: 0.3,
          spanGaps: false,
          fill: false,
        },
        {
          label: 'Endurance Index',
          data: enduranceValues,
          borderColor: '#7a2020',
          backgroundColor: 'rgba(122, 32, 32, 0.08)',
          pointRadius: 3,
          pointHoverRadius: 5,
          tension: 0.3,
          spanGaps: false,
          fill: false,
        },
        {
          label: '_baseline',
          data: baselineValues,
          borderColor: 'rgba(139, 105, 20, 0.35)',
          borderDash: [6, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          pointHoverRadius: 0,
          tension: 0,
          spanGaps: true,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      animation: false,
      plugins: {
        legend: {
          labels: {
            color: textColor,
            font: { family: "'Lora', serif", size: 12 },
            filter: (item) => !item.text.startsWith('_'),
          },
        },
        tooltip: {
          callbacks: {
            title: (items) => {
              if (!items.length) return '';
              return formatDate(items[0].label);
            },
            label: (item) => {
              if (item.dataset.label.startsWith('_')) return null;
              const val = item.parsed.y;
              if (val === null || val === undefined) return null;
              return `${item.dataset.label}: ${val.toFixed(2)}`;
            },
          },
          backgroundColor: 'rgba(245, 236, 215, 0.95)',
          borderColor: 'rgba(196, 165, 90, 0.6)',
          borderWidth: 1,
          titleColor: textColor,
          bodyColor: textColor,
          titleFont: { family: "'Cinzel', serif", size: 11 },
          bodyFont: { family: "'Lora', serif", size: 12 },
        },
      },
      scales: {
        x: {
          type: 'time',
          time: {
            unit: 'week',
            displayFormats: { week: 'MMM d' },
          },
          ticks: { color: textColor, font: { family: "'Lora', serif", size: 11 } },
          grid: { color: gridColor },
        },
        y: {
          min: 0,
          ticks: { color: textColor, font: { family: "'Lora', serif", size: 11 } },
          grid: { color: gridColor },
        },
      },
    },
  });
}

// ---------------------------------------------------------------------------
// Lifts table
// ---------------------------------------------------------------------------

async function renderLiftsTable() {
  const wrap = document.getElementById('lifts-table-wrap');
  if (!wrap) return;

  wrap.innerHTML = `
    <div class="table-filter-row">
      <input class="input-search" id="lift-filter-input" placeholder="Filter lifts\u2026" type="text">
      <button class="btn-primary" id="add-lift-btn">+ New Lift</button>
    </div>
    <table class="lifts-table">
      <thead>
        <tr><th>Lift</th><th>Muscle Groups</th><th></th></tr>
      </thead>
      <tbody id="lifts-tbody"></tbody>
    </table>
  `;

  const tbody = document.getElementById('lifts-tbody');
  if (!tbody) return;

  if (allLifts.length === 0) {
    const tr = document.createElement('tr');
    tr.innerHTML = '<td colspan="3" class="empty-state">No lifts yet. Add exercises to a workout to begin.</td>';
    tbody.appendChild(tr);
  } else {
    allLifts.forEach((lift) => {
      const row = buildLiftRow(lift);
      tbody.appendChild(row);
    });
  }

  // Filter input
  const filterInput = document.getElementById('lift-filter-input');
  if (filterInput) {
    filterInput.addEventListener('input', debounce(() => {
      applyFilter(filterInput.value);
    }, 200));
  }

  // New lift button
  const addBtn = document.getElementById('add-lift-btn');
  if (addBtn) {
    addBtn.addEventListener('click', async () => {
      const name = prompt('Lift name:');
      if (!name || !name.trim()) return;
      try {
        await api.createLift(name.trim(), []);
        await loadLiftsData();
        populateDatalist();
        await renderLiftsTable();
      } catch (err) {
        console.error('Failed to create lift:', err);
        alert('Could not create lift.');
      }
    });
  }
}

/**
 * Build a single table row for one lift.
 * @param {{id: number, name: string, muscle_group_ids: number[]}} lift
 * @returns {HTMLTableRowElement}
 */
function buildLiftRow(lift) {
  const tr = document.createElement('tr');
  tr.dataset.liftId = lift.id;

  // --- Name cell ---
  const nameTd = document.createElement('td');
  nameTd.className = 'lift-name-cell';

  const nameDisplay = document.createElement('span');
  nameDisplay.className = 'lift-name-display';
  nameDisplay.textContent = lift.name;

  const nameInput = document.createElement('input');
  nameInput.className = 'lift-name-input editable-field';
  nameInput.value = lift.name;
  nameInput.style.display = 'none';

  nameTd.appendChild(nameDisplay);
  nameTd.appendChild(nameInput);

  // Click on display span → switch to edit mode
  nameDisplay.addEventListener('click', () => {
    nameDisplay.style.display = 'none';
    nameInput.style.display = '';
    nameInput.focus();
    nameInput.select();
  });

  // Commit edit on blur
  nameInput.addEventListener('blur', () => {
    commitNameEdit(lift.id, nameDisplay, nameInput);
  });

  // Keyboard shortcuts while editing
  nameInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      nameInput.blur(); // triggers blur → commitNameEdit
    } else if (e.key === 'Escape') {
      // Cancel: restore original value and hide input
      nameInput.value = nameDisplay.textContent;
      nameInput.style.display = 'none';
      nameDisplay.style.display = '';
    }
  });

  // --- Muscle groups cell ---
  const groupsTd = document.createElement('td');
  groupsTd.className = 'lift-groups-cell';

  const ids = Array.isArray(lift.muscle_group_ids) ? lift.muscle_group_ids : [];
  ids.forEach((gid) => {
    const name = muscleGroupMap[gid];
    if (!name) return;
    const pill = document.createElement('span');
    pill.className = 'muscle-pill';
    pill.textContent = name;
    groupsTd.appendChild(pill);
  });

  // --- Delete cell ---
  const deleteTd = document.createElement('td');
  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'btn-danger btn-small delete-lift-btn';
  deleteBtn.textContent = '\u2715'; // ✕
  deleteBtn.addEventListener('click', async () => {
    if (!confirm('Delete this lift?')) return;
    try {
      await api.deleteLift(lift.id);
      tr.remove();
      // Also remove from allLifts and refresh datalist
      allLifts = allLifts.filter((l) => l.id !== lift.id);
      populateDatalist();
    } catch (err) {
      console.error('Failed to delete lift:', err);
      alert('Could not delete lift.');
    }
  });
  deleteTd.appendChild(deleteBtn);

  tr.appendChild(nameTd);
  tr.appendChild(groupsTd);
  tr.appendChild(deleteTd);
  return tr;
}

/**
 * Commit an inline name edit for a lift.
 * @param {number} liftId
 * @param {HTMLElement} displayEl
 * @param {HTMLInputElement} inputEl
 */
async function commitNameEdit(liftId, displayEl, inputEl) {
  const newName = inputEl.value.trim();

  // Always hide the input and show the display, regardless of outcome
  inputEl.style.display = 'none';
  displayEl.style.display = '';

  if (!newName || newName === displayEl.textContent) return;

  try {
    await api.updateLift(liftId, { name: newName });
    displayEl.textContent = newName;
    // Keep allLifts in sync so datalist stays accurate
    const lift = allLifts.find((l) => l.id === liftId);
    if (lift) lift.name = newName;
    populateDatalist();
    showSaved();
  } catch (err) {
    console.error('Failed to update lift name:', err);
    // Restore the previous name in the input so a retry is possible
    inputEl.value = displayEl.textContent;
    alert('Could not save lift name.');
  }
}

// ---------------------------------------------------------------------------
// Filter
// ---------------------------------------------------------------------------

/**
 * Show/hide table rows based on a filter string (case-insensitive substring match).
 * @param {string} query
 */
function applyFilter(query) {
  const tbody = document.getElementById('lifts-tbody');
  if (!tbody) return;
  const q = query.toLowerCase();
  Array.from(tbody.querySelectorAll('tr[data-lift-id]')).forEach((row) => {
    const nameEl = row.querySelector('.lift-name-display');
    const name = nameEl ? nameEl.textContent.toLowerCase() : '';
    row.style.display = name.includes(q) ? '' : 'none';
  });
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function initLifts() {
  await loadLiftsData();
  populateDatalist();
  renderLiftsTable();

  // Lift selector change handler
  const selectInput = document.getElementById('lift-select-input');
  if (selectInput) {
    selectInput.addEventListener('change', () => {
      const name = selectInput.value.trim();
      const lift = allLifts.find((l) => l.name === name);
      if (lift) {
        renderLiftChart(lift.id);
      }
    });
  }
}

export async function refreshLifts() {
  await loadLiftsData();
  populateDatalist();
  await renderLiftsTable();

  // If a lift is currently selected in the search input, re-render its chart
  const selectInput = document.getElementById('lift-select-input');
  if (selectInput && selectInput.value.trim()) {
    const name = selectInput.value.trim();
    const lift = allLifts.find((l) => l.name === name);
    if (lift) {
      renderLiftChart(lift.id);
    }
  }
}
