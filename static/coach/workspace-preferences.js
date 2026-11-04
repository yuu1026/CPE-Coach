(() => {
  const form = document.getElementById('workspace-form');
  if (!form) return;
  const editor = document.querySelector('.CodeMirror')?.CodeMirror;
  const field = name => form.elements.namedItem(name);
  const status = document.getElementById('draft-status');
  const restore = document.getElementById('restore-draft');
  const draftKey = `cpe:draft:v1:${form.dataset.user}:${form.dataset.problem}`;
  const prefKey = `cpe:layout:v2:${form.dataset.user}`;
  let timer, saving = false, blocked = false, pending = null;
  function read(key) { try { return JSON.parse(localStorage.getItem(key)); } catch { return null; } }
  function snapshot() {
    return {code: editor ? editor.getValue() : field('code').value, question: field('question').value,
      hint_level: field('hint_level').value, run_custom: field('run_custom').checked,
      custom_input: field('custom_input').value, custom_expected: field('custom_expected').value,
      record: form.dataset.record, pending, time: Date.now()};
  }
  function save() {
    clearTimeout(timer); timer = null;
    if (saving || blocked) return;
    try { localStorage.setItem(draftKey, JSON.stringify(snapshot())); status.textContent = '草稿已保存於此瀏覽器'; }
    catch { status.textContent = '瀏覽器無法保存草稿，請自行備份'; }
  }
  function schedule() { if (!saving && !blocked) { status.textContent = '正在保存草稿…'; clearTimeout(timer); timer = setTimeout(save, 350); } }
  function apply(draft) {
    saving = true;
    if (editor) editor.setValue(String(draft.code || '')); else field('code').value = String(draft.code || '');
    for (const name of ['question', 'custom_input', 'custom_expected']) field(name).value = String(draft[name] || '');
    if (['1','2','3'].includes(draft.hint_level)) field('hint_level').value = draft.hint_level;
    field('run_custom').checked = draft.run_custom === true;
    field('code').dispatchEvent(new Event('input', {bubbles:true}));
    saving = false; blocked = false; restore.hidden = true; save();
    status.textContent = '已還原這題草稿（此瀏覽器）';
  }
  const draft = read(draftKey);
  if (draft && typeof draft.code === 'string') {
    const submitted = draft.pending && draft.pending.token === form.dataset.token;
    if (submitted && draft.pending.action === 'ask' && ['done','partial'].includes(form.dataset.status) && draft.question === draft.pending.question) draft.question = '';
    if (!form.dataset.errors && (draft.record === form.dataset.record || submitted)) apply(draft);
    else { blocked = true; restore.hidden = false; status.textContent = '另有保存草稿，可手動還原至目前對話'; }
  }
  restore.addEventListener('click', () => { const current = read(draftKey); if (current) apply(current); });
  // Keep older branches intact until the user explicitly chooses which draft to retain.
  const keepCurrent = document.createElement('button');
  keepCurrent.type = 'button'; keepCurrent.textContent = '保存目前內容'; keepCurrent.hidden = !blocked;
  keepCurrent.className = 'button-quiet'; restore.after(keepCurrent);
  keepCurrent.addEventListener('click', () => { blocked = false; restore.hidden = keepCurrent.hidden = true; save(); });
  restore.addEventListener('click', () => { keepCurrent.hidden = true; });
  document.getElementById('clear-draft').addEventListener('click', () => {
    clearTimeout(timer); timer = null;
    try { localStorage.removeItem(draftKey); blocked = false; restore.hidden = keepCurrent.hidden = true; status.textContent = '已清除保存草稿；編輯區內容保留'; }
    catch { status.textContent = '無法清除瀏覽器草稿'; }
  });
  form.addEventListener('input', schedule);
  form.addEventListener('change', schedule);
  form.addEventListener('draft-change', schedule);
  form.addEventListener('chat-cleared', () => { blocked = false; pending = null; restore.hidden = keepCurrent.hidden = true; save(); });
  form.addEventListener('test-completed', () => { blocked = false; pending = null; restore.hidden = keepCurrent.hidden = true; save(); });
  form.addEventListener('submit', event => {
    if (event.defaultPrevented) return;
    pending = {token: field('submission_id').value, action: field('action').value, question: field('question').value};
    if (blocked) {
      // A submitted branch becomes the user's current working draft.
      blocked = false;
    }
    save();
  });
  window.addEventListener('pagehide', () => { if (timer) save(); });

  const reading = document.getElementById('reading-size');
  const coding = document.getElementById('editor-size');
  let widths = [24, 48, 28];
  const collapsed = {problem:false, chat:false};
  const toggles = [...document.querySelectorAll('[data-toggle-pane]')];
  function layout() {
    form.style.gridTemplateColumns = `${collapsed.problem ? '0px 0px' : `minmax(220px,${widths[0]}fr) 10px`} minmax(330px,${widths[1]}fr) ${collapsed.chat ? '0px 0px' : `10px minmax(300px,${widths[2]}fr)`}`;
    form.classList.toggle('is-problem-collapsed', collapsed.problem);
    form.classList.toggle('is-chat-collapsed', collapsed.chat);
    toggles.forEach(button => {
      const name = button.dataset.togglePane;
      button.setAttribute('aria-expanded', String(!collapsed[name]));
      button.textContent = name === 'problem' ? (collapsed.problem ? '展開題目 ›' : '收合題目 ‹') : (collapsed.chat ? '展開助理 ‹' : '收合助理 ›');
    });
    document.documentElement.style.setProperty('--reading-size', reading.value + 'px');
    document.documentElement.style.setProperty('--editor-size', coding.value + 'px');
    document.querySelectorAll('[data-divider]').forEach((handle, index) => {
      handle.setAttribute('aria-valuemin', '15'); handle.setAttribute('aria-valuemax', '60');
      handle.setAttribute('aria-valuenow', String(Math.round(widths[index])));
    });
    if (editor) editor.refresh();
  }
  function saveLayout() { try { localStorage.setItem(prefKey, JSON.stringify({reading:reading.value, coding:coding.value, widths, collapsed})); } catch {} }
  const prefs = read(prefKey);
  if (prefs) {
    collapsed.problem = prefs.collapsed?.problem === true;
    collapsed.chat = prefs.collapsed?.chat === true;
    if ([...reading.options].some(option => option.value === prefs.reading)) reading.value = prefs.reading;
    if ([...coding.options].some(option => option.value === prefs.coding)) coding.value = prefs.coding;
    if (Array.isArray(prefs.widths) && prefs.widths.length === 3 && prefs.widths.every(n => Number.isFinite(n) && n >= 15 && n <= 60) && Math.abs(prefs.widths.reduce((a,b) => a+b,0)-100)<0.1) widths = prefs.widths;
  }
  [reading,coding].forEach(control => control.addEventListener('change', () => { layout(); saveLayout(); }));
  toggles.forEach(button => button.addEventListener('click', () => { const name = button.dataset.togglePane; collapsed[name] = !collapsed[name]; layout(); saveLayout(); }));
  document.getElementById('reset-layout').addEventListener('click', () => { reading.value = coding.value = '15'; widths = [24,48,28]; collapsed.problem = collapsed.chat = false; layout(); saveLayout(); });
  document.querySelectorAll('[data-divider]').forEach(handle => {
    const index = Number(handle.dataset.divider);
    let startX, initial;
    function adjust(delta) {
      const amount = Math.max(15 - initial[index], Math.min(initial[index+1] - 15, delta));
      const bounded = Math.max(initial[index+1]-60, Math.min(60-initial[index], amount));
      widths = [...initial]; widths[index] += bounded; widths[index+1] -= bounded; layout();
    }
    handle.addEventListener('pointerdown', event => { if (event.button !== 0) return; event.preventDefault(); startX = event.clientX; initial = [...widths]; handle.setPointerCapture(event.pointerId); });
    handle.addEventListener('pointermove', event => { if (handle.hasPointerCapture(event.pointerId)) adjust((event.clientX-startX) / (form.clientWidth-20) * 100); });
    handle.addEventListener('pointerup', event => { if (handle.hasPointerCapture(event.pointerId)) { handle.releasePointerCapture(event.pointerId); saveLayout(); } });
    handle.addEventListener('keydown', event => { if (['ArrowLeft','ArrowRight'].includes(event.key)) { event.preventDefault(); initial = [...widths]; adjust(event.key === 'ArrowLeft' ? -2 : 2); saveLayout(); } });
  });
  form.addEventListener('click', event => {
    const button = event.target.closest('[data-cases]');
    if (button) document.querySelectorAll('#test-area .test-case').forEach(item => { item.open = button.dataset.cases === 'expand'; });
  });
  layout();
})();
