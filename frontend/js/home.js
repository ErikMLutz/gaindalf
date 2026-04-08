import { api } from './api.js';
import { formatDate } from './utils.js';

let progressChart = null; // Chart.js instance, destroyed/recreated on refresh
let workoutsPage = 0;     // current pagination page for workout history (0-indexed)
const WORKOUTS_PER_PAGE = 10;

async function renderProgressChart() {
  const canvas = document.getElementById('progress-chart');
  if (!canvas) return;

  // Destroy existing chart before recreating
  if (progressChart) {
    progressChart.destroy();
    progressChart = null;
  }

  let data = [];
  try {
    data = await api.getProgress();
  } catch (err) {
    console.error('Failed to load progress data:', err);
    // Leave data as empty array — chart will render with no points
  }

  const labels = data.map((d) => d.date);
  const strengthValues = data.map((d) => d.strength_index ?? null);
  const enduranceValues = data.map((d) => d.endurance_index ?? null);

  // Flat baseline across the full date range (or empty if no data)
  const baselineValues = data.map(() => 1.0);

  function yBounds(values) {
    const vals = values.filter((v) => v != null);
    if (!vals.length) return {};
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const range = hi - lo;
    const pad = range > 0 ? range * 0.25 : Math.abs(hi) * 0.1 || 0.1;
    return { min: lo - pad, max: hi + pad };
  }

  const textColor = '#5c4a1e';
  const gridColor = 'rgba(196, 165, 90, 0.3)';

  progressChart = new Chart(canvas, {
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
            // Hide the baseline dataset from the legend
            filter: (item) => !item.text.startsWith('_'),
          },
        },
        tooltip: {
          callbacks: {
            title: (items) => {
              if (!items.length) return '';
              const raw = items[0].label;
              return formatDate(raw);
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
          ...yBounds([...strengthValues, ...enduranceValues, ...baselineValues]),
          ticks: { color: textColor, font: { family: "'Lora', serif", size: 11 } },
          grid: { color: gridColor },
        },
      },
    },
  });
}

async function renderYearCalendar() {
  const container = document.getElementById('year-calendar');
  if (!container) return;

  let workouts = [];
  try {
    workouts = await api.getWorkouts();
  } catch (err) {
    console.error('Failed to load workouts for calendar:', err);
  }

  // Map date string -> workout id for click navigation
  const workoutByDate = new Map(workouts.map((w) => [w.date, w.id]));

  const year = new Date().getFullYear();
  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];
  const dayNames = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

  container.innerHTML = '';

  const grid = document.createElement('div');
  grid.className = 'cal-months-grid';

  for (let m = 0; m < 12; m++) {
    const monthEl = document.createElement('div');
    monthEl.className = 'cal-month';

    const titleEl = document.createElement('div');
    titleEl.className = 'cal-month-title';
    titleEl.textContent = monthNames[m];
    monthEl.appendChild(titleEl);

    const daysGrid = document.createElement('div');
    daysGrid.className = 'cal-days-grid';

    dayNames.forEach((d) => {
      const hdr = document.createElement('div');
      hdr.className = 'cal-dow-hdr';
      hdr.textContent = d;
      daysGrid.appendChild(hdr);
    });

    // Blank cells before the 1st
    const firstDow = new Date(year, m, 1).getDay();
    for (let i = 0; i < firstDow; i++) {
      const blank = document.createElement('div');
      blank.className = 'cal-day cal-day-blank';
      daysGrid.appendChild(blank);
    }

    const daysInMonth = new Date(year, m + 1, 0).getDate();
    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = `${year}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      const workoutId = workoutByDate.get(dateStr);

      const dayEl = document.createElement('div');
      dayEl.className = `cal-day${workoutId != null ? ' cal-day-workout' : ''}`;
      dayEl.title = workoutId != null ? `${monthNames[m]} ${d} — workout` : `${monthNames[m]} ${d}`;

      const circle = document.createElement('div');
      circle.className = 'cal-day-circle';
      dayEl.appendChild(circle);

      if (workoutId != null) {
        dayEl.addEventListener('click', () => {
          document.dispatchEvent(new CustomEvent('open-workout', { detail: { workoutId } }));
          document.querySelector('[data-tab="workouts"]').click();
        });
      }

      daysGrid.appendChild(dayEl);
    }

    monthEl.appendChild(daysGrid);
    grid.appendChild(monthEl);
  }

  container.appendChild(grid);
}

async function renderWorkoutHistory() {
  const container = document.getElementById('workout-history-list');
  if (!container) return;

  let workouts = [];
  try {
    workouts = await api.getWorkouts();
  } catch (err) {
    console.error('Failed to load workout history:', err);
    container.innerHTML = '<p class="empty-state">Could not load workout history.</p>';
    return;
  }

  if (!workouts || workouts.length === 0) {
    container.innerHTML = '<p class="empty-state">No workouts yet. Create your first one!</p>';
    return;
  }

  const totalPages = Math.max(1, Math.ceil(workouts.length / WORKOUTS_PER_PAGE));
  if (workoutsPage >= totalPages) workoutsPage = totalPages - 1;

  const pageItems = workouts.slice(workoutsPage * WORKOUTS_PER_PAGE, (workoutsPage + 1) * WORKOUTS_PER_PAGE);

  container.innerHTML = '';

  pageItems.forEach((workout) => {
    const item = document.createElement('div');
    item.className = 'history-item';
    item.dataset.workoutId = workout.id;

    // Date column
    const dateEl = document.createElement('span');
    dateEl.className = 'history-item-date';
    dateEl.textContent = formatDate(workout.date);

    // Body: subtitle + lifts
    const body = document.createElement('div');
    body.className = 'history-item-body';

    if (workout.subtitle) {
      const subtitleEl = document.createElement('div');
      subtitleEl.className = 'history-item-title';
      subtitleEl.textContent = workout.subtitle;
      body.appendChild(subtitleEl);
    }

    if (workout.lift_names && workout.lift_names.length > 0) {
      const metaEl = document.createElement('div');
      metaEl.className = 'history-item-meta';
      metaEl.textContent = workout.lift_names.join(' \u00b7 ');
      body.appendChild(metaEl);
    }

    // Chevron
    const chevron = document.createElement('span');
    chevron.className = 'history-item-chevron';
    chevron.setAttribute('aria-hidden', 'true');
    chevron.textContent = '\u203a'; // ›

    item.appendChild(dateEl);
    item.appendChild(body);
    item.appendChild(chevron);

    item.addEventListener('click', () => {
      document.dispatchEvent(
        new CustomEvent('open-workout', { detail: { workoutId: workout.id } })
      );
      document.querySelector('[data-tab="workouts"]').click();
    });

    container.appendChild(item);
  });

  if (totalPages > 1) {
    const pagination = document.createElement('div');
    pagination.className = 'pagination';

    const prevBtn = document.createElement('button');
    prevBtn.className = 'btn-secondary btn-small';
    prevBtn.textContent = '\u2190 Prev';
    prevBtn.disabled = workoutsPage === 0;
    prevBtn.addEventListener('click', () => {
      if (workoutsPage > 0) { workoutsPage--; renderWorkoutHistory(); }
    });

    const info = document.createElement('span');
    info.className = 'pagination-info';
    info.textContent = `${workoutsPage + 1} / ${totalPages}`;

    const nextBtn = document.createElement('button');
    nextBtn.className = 'btn-secondary btn-small';
    nextBtn.textContent = 'Next \u2192';
    nextBtn.disabled = workoutsPage >= totalPages - 1;
    nextBtn.addEventListener('click', () => {
      if (workoutsPage < totalPages - 1) { workoutsPage++; renderWorkoutHistory(); }
    });

    pagination.appendChild(prevBtn);
    pagination.appendChild(info);
    pagination.appendChild(nextBtn);
    container.appendChild(pagination);
  }
}

export async function initHome() {
  await renderProgressChart();
  await renderYearCalendar();
  await renderWorkoutHistory();

  document.getElementById('new-workout-home-btn')
    .addEventListener('click', async () => {
      let workout;
      try {
        workout = await api.createWorkout();
      } catch (err) {
        console.error('Failed to create workout:', err);
        return;
      }
      document.dispatchEvent(
        new CustomEvent('open-workout', { detail: { workoutId: workout.id } })
      );
      document.querySelector('[data-tab="workouts"]').click();
    });
}

// Called when the Home tab is re-activated (registered via registerTabRefresh in app.js)
export async function refreshHome() {
  await renderProgressChart();
  await renderYearCalendar();
  await renderWorkoutHistory();
}
