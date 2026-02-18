/**
 * Delays fn by ms milliseconds, restarting the timer on each call.
 * @param {Function} fn
 * @param {number} ms
 * @returns {Function}
 */
export function debounce(fn, ms = 400) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), ms);
  };
}

/**
 * Format an ISO date string to a human-readable form, e.g. "Jan 15, 2025".
 * Interprets the date as UTC so that "2025-01-15" never shifts to the prior day.
 * @param {string} isoStr  e.g. "2025-01-15" or full ISO-8601
 * @returns {string}
 */
export function formatDate(isoStr) {
  if (!isoStr) return '';
  // Parse date-only strings as UTC to avoid timezone-induced off-by-one
  const date = isoStr.length === 10
    ? new Date(`${isoStr}T00:00:00Z`)
    : new Date(isoStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

/**
 * Show a brief "Saved" toast in the corner, reusing the #saved-indicator element
 * that already exists in the HTML.
 */
export function showSaved() {
  const el = document.getElementById('saved-indicator');
  if (!el) return;
  el.textContent = 'Saved';
  el.classList.add('visible');
  clearTimeout(el._hideTimer);
  el._hideTimer = setTimeout(() => {
    el.classList.remove('visible');
  }, 1800);
}
