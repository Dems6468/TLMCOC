/* ============================================================
   Contest Tier List Builder
   Vanilla JS, no build step. Reads data/champions.json
   (produced by scripts/merge_portraits.py) and lets people
   build a tier list either one-champion-at-a-time (guided) or
   by dragging portraits into lanes (freeform).
   ============================================================ */

const STORAGE_KEY = 'contestTierState.v1';
const DATA_URL = 'data/champions_source.json';

const SWATCHES = ['#D8A945', '#3E8EDE', '#E24C4C', '#4CE28A', '#A24CE2', '#E89A3E', '#5FC7D6', '#D6608F'];

const CLASS_COLORS = {
  Cosmic: '#3E8EDE', Tech: '#E8C93E', Mutant: '#E89A3E',
  Skill: '#E24C4C', Science: '#4CE28A', Mystic: '#A24CE2',
};

let CHAMPIONS = [];          // full roster, loaded from JSON
let champById = {};

let state = {
  lanes: [],                 // [{id, name, color}]
  assignments: {},           // { champId: laneId }
  selectedClasses: null,     // null = all, else array of class names
  mode: null,                // 'guided' | 'freeform'
  guidedQueue: [],
  guidedHistory: [],         // [{champId, laneId}]
};

function uid(prefix) {
  return prefix + '_' + Math.random().toString(36).slice(2, 9);
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function loadState() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw) {
    try {
      Object.assign(state, JSON.parse(raw));
    } catch (e) { /* ignore corrupt state */ }
  }
}

function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.add('hidden'));
  document.getElementById(id).classList.remove('hidden');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ============================ Boot ============================ */

async function boot() {
  loadState();

  let json;
  if (window.CHAMPIONS_DATA) {
    // Inline data (data/champions.js), loaded via a plain <script> tag.
    // Works even opening index.html directly with no server at all.
    json = window.CHAMPIONS_DATA;
  } else {
    // Fallback for real deployments (GitHub Pages, any http:// server)
    // where data/champions.js might not have been regenerated yet.
    const res = await fetch(DATA_URL);
    json = await res.json();
  }
  CHAMPIONS = json.champions;
  champById = Object.fromEntries(CHAMPIONS.map(c => [c.id, c]));

  document.getElementById('topbarStats').textContent =
    `${CHAMPIONS.length} champions loaded`;

  renderLaneEditor();
  bindStep1();
  bindStep2();
  bindGuided();
  bindFreeform();
  bindBoard();

  // Resume mid-flow if there's saved progress with lanes already set.
  if (state.lanes.length > 0 && Object.keys(state.assignments).length > 0) {
    renderBoard();
    showScreen('screen-board');
  } else {
    showScreen('screen-lanes');
  }
}

/* ============================ Step 1: Lanes ============================ */

function renderLaneEditor() {
  const editor = document.getElementById('laneEditor');
  editor.innerHTML = '';
  state.lanes.forEach((lane, i) => {
    const row = document.createElement('div');
    row.className = 'lane-row';
    row.innerHTML = `
      <span class="lane-color-dot" style="background:${lane.color}"></span>
      <span class="lane-name">${escapeHtml(lane.name)}</span>
      <div class="lane-move-btns">
        <button class="icon-btn" data-act="up" ${i === 0 ? 'disabled' : ''} title="Move up">&uarr;</button>
        <button class="icon-btn" data-act="down" ${i === state.lanes.length - 1 ? 'disabled' : ''} title="Move down">&darr;</button>
        <button class="icon-btn danger" data-act="del" title="Delete lane">&times;</button>
      </div>`;
    row.querySelector('[data-act="up"]').onclick = () => moveLane(i, -1);
    row.querySelector('[data-act="down"]').onclick = () => moveLane(i, 1);
    row.querySelector('[data-act="del"]').onclick = () => deleteLane(lane.id);
    editor.appendChild(row);
  });
  document.getElementById('toStep2Btn').disabled = state.lanes.length === 0;
}

function moveLane(index, dir) {
  const target = index + dir;
  if (target < 0 || target >= state.lanes.length) return;
  [state.lanes[index], state.lanes[target]] = [state.lanes[target], state.lanes[index]];
  saveState();
  renderLaneEditor();
}

function deleteLane(laneId) {
  state.lanes = state.lanes.filter(l => l.id !== laneId);
  // unassign anyone who was in that lane
  for (const champId in state.assignments) {
    if (state.assignments[champId] === laneId) delete state.assignments[champId];
  }
  saveState();
  renderLaneEditor();
}

function addLane(name, color) {
  if (!name.trim()) return;
  state.lanes.push({ id: uid('lane'), name: name.trim(), color });
  saveState();
  renderLaneEditor();
}

function bindStep1() {
  const swatchPicker = document.getElementById('swatchPicker');
  let selectedColor = SWATCHES[0];
  SWATCHES.forEach((c, i) => {
    const sw = document.createElement('button');
    sw.type = 'button';
    sw.className = 'swatch' + (i === 0 ? ' selected' : '');
    sw.style.background = c;
    sw.onclick = () => {
      selectedColor = c;
      swatchPicker.querySelectorAll('.swatch').forEach(s => s.classList.remove('selected'));
      sw.classList.add('selected');
    };
    swatchPicker.appendChild(sw);
  });

  document.getElementById('laneAddForm').addEventListener('submit', (e) => {
    e.preventDefault();
    const input = document.getElementById('laneNameInput');
    addLane(input.value, selectedColor);
    input.value = '';
    input.focus();
  });

  document.getElementById('clearLanesBtn').onclick = () => {
    if (state.lanes.length && !confirm('Remove all lanes?')) return;
    state.lanes = [];
    saveState();
    renderLaneEditor();
  };

  document.querySelectorAll('[data-preset]').forEach(btn => {
    btn.onclick = () => {
      const presets = {
        tier: [['S', '#D8A945'], ['A', '#4CE28A'], ['B', '#3E8EDE'], ['C', '#E89A3E'], ['D', '#E24C4C']],
        use: [['Take', '#4CE28A'], ['Situational', '#E89A3E'], ['Bench', '#E24C4C']],
      };
      presets[btn.dataset.preset].forEach(([name, color]) => {
        if (!state.lanes.some(l => l.name === name)) addLane(name, color);
      });
    };
  });

  document.getElementById('toStep2Btn').onclick = () => {
    renderClassFilter();
    showScreen('screen-setup2');
  };
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

/* ============================ Step 2: roster + mode ============================ */

function renderClassFilter() {
  const wrap = document.getElementById('classFilter');
  wrap.innerHTML = '';
  const classes = [...new Set(CHAMPIONS.map(c => c.class))];

  const allChip = document.createElement('button');
  allChip.type = 'button';
  allChip.className = 'chip' + (state.selectedClasses === null ? ' active' : '');
  allChip.textContent = 'All classes';
  allChip.onclick = () => { state.selectedClasses = null; renderClassFilter(); updateStartBtn(); };
  wrap.appendChild(allChip);

  classes.forEach(cls => {
    const chip = document.createElement('button');
    chip.type = 'button';
    const active = state.selectedClasses !== null && state.selectedClasses.includes(cls);
    chip.className = 'chip' + (active ? ' active' : '');
    chip.textContent = cls;
    chip.onclick = () => {
      if (state.selectedClasses === null) state.selectedClasses = [];
      if (state.selectedClasses.includes(cls)) {
        state.selectedClasses = state.selectedClasses.filter(c => c !== cls);
        if (state.selectedClasses.length === 0) state.selectedClasses = null;
      } else {
        state.selectedClasses = [...state.selectedClasses, cls];
      }
      renderClassFilter();
      updateStartBtn();
    };
    wrap.appendChild(chip);
  });
}

function getFilteredPool() {
  return CHAMPIONS.filter(c =>
    (state.selectedClasses === null || state.selectedClasses.includes(c.class)) &&
    !(c.id in state.assignments)
  );
}

function updateStartBtn() {
  document.getElementById('startBtn').disabled = !state.mode;
}

function bindStep2() {
  document.querySelectorAll('.mode-card').forEach(card => {
    card.onclick = () => {
      state.mode = card.dataset.mode;
      document.querySelectorAll('.mode-card').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      updateStartBtn();
    };
  });

  document.getElementById('back1Btn').onclick = () => showScreen('screen-lanes');

  document.getElementById('startBtn').onclick = () => {
    saveState();
    const pool = getFilteredPool();
    if (pool.length === 0) {
      alert("Everyone in this selection is already sorted. Try a different class filter.");
      return;
    }
    if (state.mode === 'guided') {
      state.guidedQueue = shuffle(pool.map(c => c.id));
      state.guidedHistory = [];
      saveState();
      showGuidedCard();
      showScreen('screen-guided');
    } else {
      renderFreeform();
      showScreen('screen-freeform');
    }
  };
}

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/* ============================ Guided mode ============================ */

function bindGuided() {
  document.getElementById('guidedSkipBtn').onclick = () => {
    if (state.guidedQueue.length <= 1) { finishGuided(); return; }
    const current = state.guidedQueue.shift();
    state.guidedQueue.push(current);
    saveState();
    showGuidedCard();
  };

  document.getElementById('guidedBackBtn').onclick = () => {
    const last = state.guidedHistory.pop();
    if (!last) return;
    delete state.assignments[last.champId];
    state.guidedQueue.unshift(last.champId);
    saveState();
    showGuidedCard();
  };

  document.getElementById('guidedFinishEarlyBtn').onclick = () => {
    renderBoard();
    showScreen('screen-board');
  };
}

function showGuidedCard() {
  if (state.guidedQueue.length === 0) { finishGuided(); return; }
  const champId = state.guidedQueue[0];
  const champ = champById[champId];

  const total = state.guidedQueue.length + Object.keys(state.assignments).length;
  const done = Object.keys(state.assignments).length;
  document.getElementById('guidedProgressFill').style.width = `${(done / (done + state.guidedQueue.length)) * 100}%`;
  document.getElementById('guidedProgressLabel').textContent = `${done} sorted \u00b7 ${state.guidedQueue.length} to go`;

  document.getElementById('guidedPortrait').src = champ.image;
  document.getElementById('guidedPortrait').alt = champ.name;
  document.getElementById('guidedName').textContent = champ.name;
  const tag = document.getElementById('guidedClassTag');
  tag.textContent = champ.class;
  tag.style.background = CLASS_COLORS[champ.class] || '#888';

  // re-trigger the card-in animation
  const card = document.getElementById('guidedCard');
  card.style.animation = 'none';
  void card.offsetWidth;
  card.style.animation = '';

  const laneWrap = document.getElementById('guidedLaneButtons');
  laneWrap.innerHTML = '';
  state.lanes.forEach(lane => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'lane-btn';
    btn.textContent = lane.name;
    btn.style.background = lane.color;
    btn.onclick = () => assignGuided(champId, lane.id);
    laneWrap.appendChild(btn);
  });
}

function assignGuided(champId, laneId) {
  state.assignments[champId] = laneId;
  state.guidedHistory.push({ champId, laneId });
  state.guidedQueue.shift();
  saveState();
  showGuidedCard();
}

function finishGuided() {
  renderBoard();
  showScreen('screen-board');
}

/* ============================ Freeform mode ============================ */

function bindFreeform() {
  document.getElementById('freeformDoneBtn').onclick = () => {
    renderBoard();
    showScreen('screen-board');
  };
}

function makePortraitEl(champ, draggable = true) {
  const el = document.createElement('div');
  el.className = 'portrait';
  el.innerHTML = `<img src="${champ.image}" alt="${escapeHtml(champ.name)}" loading="lazy">`;
  el.title = `${champ.name} \u00b7 ${champ.class}`;
  if (draggable) {
    el.draggable = true;
    el.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', champ.id);
      el.classList.add('dragging');
    });
    el.addEventListener('dragend', () => el.classList.remove('dragging'));
  }
  return el;
}

function renderFreeform() {
  const pool = document.getElementById('freeformPool');
  pool.innerHTML = '';
  getFilteredPool().forEach(champ => pool.appendChild(makePortraitEl(champ)));

  const lanesWrap = document.getElementById('freeformLanes');
  lanesWrap.innerHTML = '';
  state.lanes.forEach(lane => {
    const laneEl = document.createElement('div');
    laneEl.className = 'freeform-lane';
    laneEl.innerHTML = `<span class="freeform-lane-label" style="background:${lane.color}">${escapeHtml(lane.name)}</span>
      <div class="freeform-lane-items"></div>`;
    const itemsEl = laneEl.querySelector('.freeform-lane-items');

    Object.entries(state.assignments)
      .filter(([, lId]) => lId === lane.id)
      .forEach(([champId]) => {
        if (champById[champId]) itemsEl.appendChild(makePortraitEl(champById[champId]));
      });

    laneEl.addEventListener('dragover', (e) => { e.preventDefault(); laneEl.classList.add('drag-over'); });
    laneEl.addEventListener('dragleave', () => laneEl.classList.remove('drag-over'));
    laneEl.addEventListener('drop', (e) => {
      e.preventDefault();
      laneEl.classList.remove('drag-over');
      const champId = e.dataTransfer.getData('text/plain');
      if (!champId) return;
      state.assignments[champId] = lane.id;
      saveState();
      renderFreeform();
    });

    lanesWrap.appendChild(laneEl);
  });
}

/* ============================ Results board ============================ */

function bindBoard() {
  document.getElementById('addMoreBtn').onclick = () => {
    renderClassFilter();
    state.mode = null;
    document.getElementById('startBtn').disabled = true;
    document.querySelectorAll('.mode-card').forEach(c => c.classList.remove('selected'));
    showScreen('screen-setup2');
  };

  document.getElementById('exportBtn').onclick = exportResults;

  document.getElementById('resetAllBtn').onclick = () => {
    if (!confirm('This clears all lanes and sorting. Continue?')) return;
    state = { lanes: [], assignments: {}, selectedClasses: null, mode: null, guidedQueue: [], guidedHistory: [] };
    saveState();
    renderLaneEditor();
    showScreen('screen-lanes');
  };
}

function renderBoard() {
  const board = document.getElementById('board');
  board.innerHTML = '';

  state.lanes.forEach(lane => {
    const row = document.createElement('div');
    row.className = 'tier-row';
    row.innerHTML = `<span class="tier-label" style="background:${lane.color}">${escapeHtml(lane.name)}</span>
      <div class="tier-items"></div>`;
    const itemsEl = row.querySelector('.tier-items');

    Object.entries(state.assignments)
      .filter(([, lId]) => lId === lane.id)
      .forEach(([champId]) => {
        if (champById[champId]) itemsEl.appendChild(makePortraitEl(champById[champId]));
      });

    row.addEventListener('dragover', (e) => { e.preventDefault(); row.classList.add('drag-over'); });
    row.addEventListener('dragleave', () => row.classList.remove('drag-over'));
    row.addEventListener('drop', (e) => {
      e.preventDefault();
      row.classList.remove('drag-over');
      const champId = e.dataTransfer.getData('text/plain');
      if (!champId) return;
      state.assignments[champId] = lane.id;
      saveState();
      renderBoard();
    });

    board.appendChild(row);
  });

  // unsorted tray: anyone in the full roster not yet assigned
  const trayItems = document.getElementById('unsortedTrayItems');
  trayItems.innerHTML = '';
  const unsorted = CHAMPIONS.filter(c =>
  !(c.id in state.assignments) &&
  (state.selectedClasses === null || state.selectedClasses.includes(c.class))
);
  unsorted.forEach(champ => trayItems.appendChild(makePortraitEl(champ)));

  const tray = document.getElementById('unsortedTray');
  tray.addEventListener('dragover', (e) => { e.preventDefault(); });
  tray.addEventListener('drop', (e) => {
    e.preventDefault();
    const champId = e.dataTransfer.getData('text/plain');
    if (!champId) return;
    delete state.assignments[champId];
    saveState();
    renderBoard();
  });

  document.getElementById('addMoreBtn').style.display = unsorted.length ? '' : 'none';
}

function exportResults() {
  const out = { lanes: state.lanes.map(l => ({ name: l.name, color: l.color, champions: [] })) };
  const laneIndex = Object.fromEntries(state.lanes.map((l, i) => [l.id, i]));
  for (const [champId, laneId] of Object.entries(state.assignments)) {
    const champ = champById[champId];
    if (champ && laneId in laneIndex) {
      out.lanes[laneIndex[laneId]].champions.push({ name: champ.name, class: champ.class });
    }
  }
  const blob = new Blob([JSON.stringify(out, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'tier-list-results.json';
  a.click();
}

boot();
