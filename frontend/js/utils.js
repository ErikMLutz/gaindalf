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
 * Create a combobox: a text input with a filtered dropdown suggestion panel.
 * Returns { element, getValue, setValue, clear, setItems, getInputEl }.
 *
 * @param {{
 *   placeholder?: string,
 *   items?: Array<{value: string|number, label: string}>,
 *   onSelect?: (item: {value, label}) => void,
 *   onEnter?: () => void,
 *   inputClassName?: string,
 * }} opts
 */
export function createCombobox({ placeholder = '', items = [], onSelect, onEnter, inputClassName = '' } = {}) {
  let currentItems = [...items];
  let highlightedIndex = -1;
  let outsideListenerActive = false;

  const wrap = document.createElement('div');
  wrap.className = 'combobox-wrap';

  const input = document.createElement('input');
  input.type = 'text';
  input.className = inputClassName ? `combobox-input ${inputClassName}` : 'combobox-input';
  input.placeholder = placeholder;
  input.setAttribute('autocomplete', 'off');
  input.setAttribute('role', 'combobox');
  input.setAttribute('aria-expanded', 'false');
  input.setAttribute('aria-autocomplete', 'list');

  const panel = document.createElement('ul');
  panel.className = 'custom-select-panel';
  panel.setAttribute('role', 'listbox');
  panel.hidden = true;

  wrap.appendChild(input);
  wrap.appendChild(panel);

  function getFiltered() {
    const q = input.value.trim().toLowerCase();
    if (!q) return [];
    return currentItems.filter((item) => item.label.toLowerCase().includes(q));
  }

  function renderPanel(filtered) {
    panel.innerHTML = '';
    highlightedIndex = -1;
    if (filtered.length === 0) { closePanel(); return; }

    filtered.forEach((item, i) => {
      const li = document.createElement('li');
      li.className = 'custom-select-item';
      li.setAttribute('role', 'option');
      li.dataset.index = i;
      li.textContent = item.label;
      // mousedown keeps focus on input; click would blur first
      li.addEventListener('mousedown', (e) => { e.preventDefault(); select(item); });
      panel.appendChild(li);
    });

    panel.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    if (!outsideListenerActive) {
      outsideListenerActive = true;
      setTimeout(() => document.addEventListener('click', onOutsideClick), 0);
    }
  }

  function closePanel() {
    panel.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    if (outsideListenerActive) {
      document.removeEventListener('click', onOutsideClick);
      outsideListenerActive = false;
    }
  }

  function onOutsideClick(e) {
    if (!wrap.contains(e.target)) closePanel();
  }

  function highlight(index) {
    panel.querySelectorAll('.custom-select-item').forEach((li, i) => {
      li.classList.toggle('highlighted', i === index);
    });
    highlightedIndex = index;
  }

  function select(item) {
    input.value = item.label;
    closePanel();
    if (onSelect) onSelect(item);
  }

  input.addEventListener('input', () => renderPanel(getFiltered()));

  input.addEventListener('keydown', (e) => {
    const lis = [...panel.querySelectorAll('.custom-select-item')];
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!panel.hidden) highlight(Math.min(highlightedIndex + 1, lis.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (!panel.hidden) highlight(Math.max(highlightedIndex - 1, 0));
    } else if (e.key === 'Enter') {
      if (!panel.hidden && highlightedIndex >= 0 && lis[highlightedIndex]) {
        e.preventDefault();
        const filtered = getFiltered();
        if (filtered[highlightedIndex]) select(filtered[highlightedIndex]);
      } else if (onEnter) {
        onEnter();
      }
    } else if (e.key === 'Escape') {
      closePanel();
    }
  });

  input.addEventListener('focus', () => {
    const filtered = getFiltered();
    if (filtered.length > 0) renderPanel(filtered);
  });

  return {
    element: wrap,
    getValue: () => input.value,
    setValue: (label) => { input.value = label ?? ''; },
    clear: () => { input.value = ''; closePanel(); },
    setItems: (newItems) => { currentItems = [...newItems]; },
    getInputEl: () => input,
  };
}

/**
 * Create a Pines-style custom dropdown select component.
 * Returns { element, getValue, setValue, setItems }.
 *
 * @param {{ placeholder?: string, items?: Array<{value: string|number, label: string}>, ariaLabel?: string, onChange?: Function }} opts
 * @returns {{ element: HTMLElement, getValue: Function, setValue: Function, setItems: Function }}
 */
export function createCustomSelect({ placeholder = 'Select\u2026', items = [], ariaLabel, onChange } = {}) {
  let currentValue = null;
  let currentItems = [...items];

  const wrap = document.createElement('div');
  wrap.className = 'custom-select';

  const trigger = document.createElement('button');
  trigger.type = 'button';
  trigger.className = 'custom-select-trigger';
  trigger.setAttribute('aria-haspopup', 'listbox');
  trigger.setAttribute('aria-expanded', 'false');
  if (ariaLabel) trigger.setAttribute('aria-label', ariaLabel);

  const triggerLabel = document.createElement('span');
  triggerLabel.className = 'custom-select-label custom-select-placeholder';
  triggerLabel.textContent = placeholder;

  const triggerArrow = document.createElement('span');
  triggerArrow.className = 'custom-select-arrow';
  triggerArrow.setAttribute('aria-hidden', 'true');
  triggerArrow.textContent = '\u25be'; // ▾

  trigger.appendChild(triggerLabel);
  trigger.appendChild(triggerArrow);

  const panel = document.createElement('ul');
  panel.className = 'custom-select-panel';
  panel.setAttribute('role', 'listbox');
  panel.hidden = true;

  wrap.appendChild(trigger);
  wrap.appendChild(panel);

  function buildPanel() {
    panel.innerHTML = '';
    currentItems.forEach((item) => {
      const li = document.createElement('li');
      li.className = 'custom-select-item';
      li.setAttribute('role', 'option');
      li.dataset.value = item.value;
      li.textContent = item.label;
      if (currentValue !== null && String(item.value) === String(currentValue)) {
        li.classList.add('selected');
        li.setAttribute('aria-selected', 'true');
      }
      li.addEventListener('click', () => {
        applySelection(item.value, item.label);
        close();
        if (onChange) onChange(item.value);
      });
      panel.appendChild(li);
    });
  }

  function open() {
    buildPanel();
    panel.hidden = false;
    trigger.setAttribute('aria-expanded', 'true');
    setTimeout(() => document.addEventListener('click', onOutsideClick), 0);
  }

  function close() {
    panel.hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
    document.removeEventListener('click', onOutsideClick);
  }

  function onOutsideClick(e) {
    if (!wrap.contains(e.target)) close();
  }

  function applySelection(value, label) {
    currentValue = value;
    triggerLabel.textContent = label;
    triggerLabel.classList.remove('custom-select-placeholder');
  }

  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    panel.hidden ? open() : close();
  });

  wrap.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') close();
  });

  return {
    element: wrap,
    getValue: () => currentValue,
    setValue: (val) => {
      if (val === null || val === undefined || val === '') {
        currentValue = null;
        triggerLabel.textContent = placeholder;
        triggerLabel.classList.add('custom-select-placeholder');
      } else {
        const item = currentItems.find((i) => String(i.value) === String(val));
        if (item) applySelection(item.value, item.label);
      }
      buildPanel();
    },
    setItems: (newItems) => {
      currentItems = [...newItems];
      // Clear selection if the selected item no longer exists
      if (currentValue !== null) {
        const still = currentItems.find((i) => String(i.value) === String(currentValue));
        if (!still) {
          currentValue = null;
          triggerLabel.textContent = placeholder;
          triggerLabel.classList.add('custom-select-placeholder');
        }
      }
      buildPanel();
    },
  };
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
  el.classList.remove('error');
  clearTimeout(el._hideTimer);
  el._hideTimer = setTimeout(() => {
    el.classList.remove('visible');
  }, 1800);
}

/**
 * Show a brief error toast in the corner.
 * @param {string} message
 */
export function showError(message) {
  const el = document.getElementById('saved-indicator');
  if (!el) return;
  el.textContent = message;
  el.classList.add('visible', 'error');
  clearTimeout(el._hideTimer);
  el._hideTimer = setTimeout(() => {
    el.classList.remove('visible', 'error');
  }, 4000);
}

/**
 * Show a custom confirmation dialog. Returns a Promise<boolean>.
 * Resolves true if confirmed, false if cancelled or dismissed.
 * @param {string} message
 * @returns {Promise<boolean>}
 */
export function showConfirm(message) {
  return new Promise((resolve) => {
    const dialog = document.getElementById('confirm-dialog');
    const msgEl = document.getElementById('confirm-dialog-message');
    const okBtn = document.getElementById('confirm-ok-btn');
    const cancelBtn = document.getElementById('confirm-cancel-btn');

    msgEl.textContent = message;

    function onOk() { finish(true); }
    function onCancel() { finish(false); }
    function onClose() { finish(false); }

    function finish(result) {
      okBtn.removeEventListener('click', onOk);
      cancelBtn.removeEventListener('click', onCancel);
      dialog.removeEventListener('close', onClose);
      if (dialog.open) dialog.close();
      resolve(result);
    }

    okBtn.addEventListener('click', onOk);
    cancelBtn.addEventListener('click', onCancel);
    dialog.addEventListener('close', onClose);

    dialog.showModal();
  });
}

/**
 * Show a custom prompt dialog with a text input. Returns Promise<string | null>.
 * Resolves with the entered string (may be empty), or null if cancelled/dismissed.
 * @param {string} label
 * @returns {Promise<string | null>}
 */
export function showPrompt(label) {
  return new Promise((resolve) => {
    const dialog = document.getElementById('prompt-dialog');
    const labelEl = document.getElementById('prompt-dialog-label');
    const input = document.getElementById('prompt-dialog-input');
    const okBtn = document.getElementById('prompt-ok-btn');
    const cancelBtn = document.getElementById('prompt-cancel-btn');

    labelEl.textContent = label;
    input.value = '';

    function onOk() { finish(input.value); }
    function onCancel() { finish(null); }
    function onKeydown(e) {
      if (e.key === 'Enter') { e.preventDefault(); onOk(); }
    }
    function onClose() { finish(null); }

    function finish(result) {
      okBtn.removeEventListener('click', onOk);
      cancelBtn.removeEventListener('click', onCancel);
      input.removeEventListener('keydown', onKeydown);
      dialog.removeEventListener('close', onClose);
      if (dialog.open) dialog.close();
      resolve(result);
    }

    okBtn.addEventListener('click', onOk);
    cancelBtn.addEventListener('click', onCancel);
    input.addEventListener('keydown', onKeydown);
    dialog.addEventListener('close', onClose);

    dialog.showModal();
    input.focus();
  });
}
