(() => {
  const form = document.getElementById('workspace-form');
  if (!form) return;
  document.documentElement.classList.add('js-enabled');
  const textarea = document.getElementById('id_code');
  const question = document.getElementById('id_question');
  const testButton = document.getElementById('run-test');
  const askButton = document.getElementById('ask-assistant');
  const wait = form.querySelector('[data-wait]');
  const editorError = document.getElementById('editor-error');
  let editor;
  const tabs = [...document.querySelectorAll('[data-tab]')];
  function showPane(name, focus = false) {
    tabs.forEach(tab => { const selected = tab.dataset.tab === name; tab.setAttribute('aria-selected', String(selected)); tab.tabIndex = selected ? 0 : -1; });
    document.querySelectorAll('[data-pane]').forEach(pane => pane.classList.toggle('active-pane', pane.dataset.pane === name));
    if (editor) requestAnimationFrame(() => editor.refresh());
    if (focus) document.querySelector(`[data-tab="${name}"]`).focus();
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => showPane(tab.dataset.tab));
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next !== undefined) { event.preventDefault(); showPane(tabs[next].dataset.tab, true); }
    });
  });
  if (window.CodeMirror) {
    editor = CodeMirror.fromTextArea(textarea, {mode:'text/x-c++src', lineNumbers:true, indentUnit:4, tabSize:4, indentWithTabs:false, matchBrackets:true, autoCloseBrackets:true, lineWrapping:false, viewportMargin:15, extraKeys:{Tab: cm => cm.somethingSelected() ? cm.indentSelection('add') : cm.replaceSelection(' '.repeat(4), 'end'), 'Shift-Tab': cm => cm.indentSelection('subtract'), 'Ctrl-Enter': () => form.requestSubmit(testButton)}});
    editor.getInputField().setAttribute('aria-label', 'C++ 程式碼編輯器');
    editor.on('change', () => { editor.save(); updateEditor(); });
    editor.on('cursorActivity', () => { const cursor = editor.getCursor(); document.getElementById('editor-position').textContent = `第 ${cursor.line+1} 行，第 ${cursor.ch+1} 欄`; });
    new ResizeObserver(() => editor.refresh()).observe(document.querySelector('.editor-wrapper'));
  }
  function code() { return editor ? editor.getValue() : textarea.value; }
  const originalNode = document.getElementById('original-code');
  let originalCode = originalNode ? JSON.parse(originalNode.textContent) : null;
  const originalCustomNode = document.getElementById('original-custom-test');
  const originalCustom = originalCustomNode ? JSON.parse(originalCustomNode.textContent) : null;
  function normalizeCustom(custom) {
    const eol = text => (text || '').replace(/\r\n?/g,'\n');
    return JSON.stringify(custom?.enabled ? {enabled:true, input:eol(custom.input), expected:eol(custom.expected)} : {enabled:false});
  }
  let customSnapshot = normalizeCustom(originalCustom && typeof originalCustom === 'object' ? originalCustom : {enabled: document.getElementById('id_run_custom').checked, input: document.getElementById('id_custom_input').value, expected: document.getElementById('id_custom_expected').value});
  const revisionNode = document.getElementById('verified-revision');
  let revision = revisionNode ? JSON.parse(revisionNode.textContent) : null;
  const revisionCustomSnapshot = customSnapshot;
  const applyRevision = document.getElementById('apply-revision');
  const undoRevision = document.getElementById('undo-revision');
  const revisionStatus = document.getElementById('revision-status');
  // Native form submission and CodeMirror can differ only in CRLF/LF.
  const sameRevisionCode = (left, right) => left.replace(/\r\n?/g,'\n') === right.replace(/\r\n?/g,'\n');
  function setRevisionCode(value) {
    if (editor) editor.setValue(value); else { textarea.value = value; updateEditor(); }
  }
  if (applyRevision) applyRevision.addEventListener('click', () => {
    const currentCustom = normalizeCustom({enabled:document.getElementById('id_run_custom').checked,input:document.getElementById('id_custom_input').value,expected:document.getElementById('id_custom_expected').value});
    if (form.getAttribute('aria-busy') === 'true') return;
    if (!revision || !sameRevisionCode(code(),revision.base_code) || currentCustom !== revisionCustomSnapshot) {
      revisionStatus.textContent = '程式或測資已改變，請重新詢問以驗證目前版本；沒有覆寫你的編輯。'; return;
    }
    setRevisionCode(revision.candidate_code);
    revisionStatus.textContent = '已套用，套用前程式仍保留。請執行測試核對目前編輯器版本。';
  });
  if (undoRevision) undoRevision.addEventListener('click', () => {
    if (form.getAttribute('aria-busy') === 'true') return;
    if (!revision || !sameRevisionCode(code(),revision.candidate_code)) {
      revisionStatus.textContent = '套用後已有其他編輯，未覆寫；可使用編輯器復原功能。'; return;
    }
    setRevisionCode(revision.base_code); revisionStatus.textContent = '已還原套用前程式。';
  });
  function updateEditor() {
    const count = Array.from(code()).length;
    const counter = document.getElementById('code-count');
    counter.textContent = `${count} / 12000 字元`;
    counter.classList.toggle('error', count > 12000);
    editorError.hidden = true;
    const custom = normalizeCustom({enabled: document.getElementById('id_run_custom').checked, input: document.getElementById('id_custom_input').value, expected: document.getElementById('id_custom_expected').value});
    document.getElementById('stale-result').hidden = originalCode === null || (sameRevisionCode(code(),originalCode) && custom === customSnapshot);
    document.getElementById('result-freshness').textContent = document.getElementById('stale-result').hidden ? '' : '已修改，請重新測試';
    if (undoRevision) undoRevision.disabled = !revision || !sameRevisionCode(code(),revision.candidate_code);
    form.dispatchEvent(new Event('draft-change'));
  }
  textarea.addEventListener('input', updateEditor);
  form.addEventListener('input', event => { if (['id_run_custom','id_custom_input','id_custom_expected'].includes(event.target.id)) updateEditor(); });
  updateEditor();
  showPane(form.dataset.initialTab);
  if (window.markdownit) {
    const md = markdownit({html:false, breaks:true, linkify:false}).disable('image');
    md.renderer.rules.link_open = (tokens, index, options, env, renderer) => { tokens[index].attrSet('rel', 'noopener noreferrer'); return renderer.renderToken(tokens, index, options); };
    document.querySelectorAll('.markdown-message').forEach(message => {
      message.innerHTML = md.render(message.textContent); message.classList.add('is-rendered');
      const next = [...message.querySelectorAll('p, li')].reverse().find(item => /[？?]|請試|請先|試著/.test(item.textContent));
      if (next) { next.classList.add('next-step'); const label = document.createElement('strong'); label.textContent = '下一步'; label.className = 'next-step-label'; next.prepend(label); }
    });
  }
  const history = document.getElementById('chat-history');
  history.scrollTop = history.scrollHeight;
  document.querySelectorAll('[data-question]').forEach(chip => chip.addEventListener('click', () => { question.value = chip.dataset.question; question.dispatchEvent(new Event('input', {bubbles:true})); question.focus(); }));
  question.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) { event.preventDefault(); if (!event.repeat) form.requestSubmit(askButton); } });
  // Native submission has already captured the message at this point.
  // Clearing in the submit handler would accidentally send an empty question.
  form.addEventListener('formdata', event => {
    if (event.formData.get('action') === 'ask') {
      question.value = '';
      form.dispatchEvent(new Event('chat-sent'));
    }
  });
  const clearButton = document.getElementById('clear-chat');
  let following = false;
  function resetBusy() {
    form.removeAttribute('aria-busy'); testButton.disabled = askButton.disabled = clearButton.disabled = false;
    testButton.textContent = '▷ 執行測試'; askButton.textContent = '送出訊息 ↑'; wait.hidden = true;
  }
  const pendingKey = `cpe-pending-${form.dataset.user}-${form.dataset.problem}`;
  function rememberPending(value) {
    try { if (value) window.sessionStorage?.setItem(pendingKey, JSON.stringify(value)); else window.sessionStorage?.removeItem(pendingKey); } catch (_) {}
  }
  async function followReply(pending) {
    if (!/^\/submission\/\d+\/progress\/$/.test(pending.status_url)) throw new Error('回覆狀態網址不符。');
    const started = Date.now();
    while (Date.now()-started < 300000) {
      const response = await fetch(pending.status_url, {headers:{Accept:'application/json'}, signal:AbortSignal.timeout(10000)});
      if (!response.ok) throw new Error(response.status === 404 ? '這次對話已移除，未重新送出。' : '暫時無法讀取進度，請查看本次紀錄。');
      const state = await response.json();
      const seconds = Math.floor(state.elapsed_seconds || 0);
      wait.textContent = `${state.label} · ${seconds} 秒${state.phase === 'generation' && state.generated_chars ? ` · 已生成 ${state.generated_chars} 字` : ''}。完成檢查後顯示答案。`;
      if (state.status !== 'running') {
        if (!/^\/submission\/\d+\/$/.test(state.url)) throw new Error('回覆網址不符。');
        rememberPending(null);
        window.location.assign(state.url);
        return;
      }
      await new Promise(resolve => setTimeout(resolve, 700));
    }
    throw new Error('等待時間較長，請查看本次紀錄；沒有重複送出問題。');
  }
  function showReplyRecovery(error, pending) {
    wait.hidden = false;
    wait.textContent = error.message || '暫時無法取得回覆；原程式已保留。';
    if (pending && /^\/submission\/\d+\/$/.test(pending.url)) {
      const link = document.createElement('a'); link.href = pending.url; link.textContent = ' 查看本次紀錄'; wait.append(link);
    }
  }
  form.addEventListener('submit', async event => {
    if (form.getAttribute('aria-busy') === 'true') { event.preventDefault(); return; }
    if (editor) editor.save();
    const action = event.submitter?.value || 'ask';
    if (action === 'test' || form.dataset.askUrl) event.preventDefault();
    if (Array.from(code()).length > 12000 || (action === 'test' && !code().trim())) {
      event.preventDefault(); showPane('code');
      editorError.textContent = Array.from(code()).length > 12000 ? '程式碼超過 12000 字元，請縮小範圍。' : '請先輸入程式碼；沒有想法時可直接送出訊息。';
      editorError.hidden = false;
      if (editor) editor.focus(); else textarea.focus();
      return;
    }
    form.querySelector('input[name="action"]').value = action;
    form.setAttribute('aria-busy', 'true');
    const sentQuestion = question.value;
    const testData = action === 'test' ? new FormData(form) : null;
    if (testData) testData.delete('question');
    testButton.disabled = askButton.disabled = clearButton.disabled = true;
    wait.textContent = action === 'test' ? '正在編譯與執行測資…' : '正在送出問題；請勿重複送出。';
    wait.hidden = action === 'test';
    if (action === 'test') document.getElementById('result-freshness').textContent = '正在編譯與執行測資…';
    if (action === 'test') testButton.textContent = '測試中…'; else askButton.textContent = '回覆中…';
    if (action === 'test') {
      try {
        const response = await fetch(form.dataset.testUrl, {method:'POST', body:testData, headers:{Accept:'application/json'}});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || Object.values(result.errors || {}).flat().map(item => item.message).join('；') || '測試失敗，請稍後重試。');
        const currentCustom = {enabled:document.getElementById('id_run_custom').checked,input:document.getElementById('id_custom_input').value,expected:document.getElementById('id_custom_expected').value};
        document.getElementById('test-results').innerHTML = result.html;
        document.getElementById('id_run_custom').checked = currentCustom.enabled;
        document.getElementById('id_custom_input').value = currentCustom.input;
        document.getElementById('id_custom_expected').value = currentCustom.expected;
        originalCode = result.code; customSnapshot = normalizeCustom(result.custom_test);
        form.elements.namedItem('parent_submission').value = result.record;
        form.elements.namedItem('submission_id').value = result.next_token;
        form.dataset.record = String(result.record); form.dataset.token = result.token;
        form.action = form.dataset.practiceUrl;
        window.history.replaceState(null, '', result.url);
        updateEditor();
        form.dispatchEvent(new Event('test-completed'));
      } catch (error) {
        editorError.textContent = error.message || '測試連線失敗，請重試。'; editorError.hidden = false;
        document.getElementById('result-freshness').textContent = '本次測試未取得結果';
        form.elements.namedItem('submission_id').value = crypto.randomUUID();
      } finally { resetBusy(); }
    } else if (form.dataset.askUrl) {
      let pending, failed = false;
      try {
        const data = new FormData(form);
        // Capture before clearing; FormData's event may already clear it.
        data.set('question', sentQuestion);
        const response = await fetch(form.dataset.askUrl, {method:'POST', body:data, headers:{Accept:'application/json'}, signal:AbortSignal.timeout(15000)});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || Object.values(result.errors || {}).flat().map(item => item.message).join('；') || '問題未送出，請重試。');
        pending = result; rememberPending(pending);
        if (question.value === sentQuestion) question.value = '';
        form.dispatchEvent(new Event('chat-sent'));
        form.dispatchEvent(new Event('chat-accepted'));
        following = true;
        await followReply(pending);
      } catch (error) {
        failed = true;
        if (!pending && !question.value) { question.value = sentQuestion; question.dispatchEvent(new Event('input', {bubbles:true})); }
        resetBusy(); showReplyRecovery(error,pending);
      } finally {
        following = false; resetBusy();
        if (failed) { wait.hidden = false; if (pending) askButton.disabled = true; }
      }
    }
  });
  clearButton.addEventListener('click', async () => {
    if (form.getAttribute('aria-busy') === 'true' || !window.confirm('清除此題的所有聊天紀錄？程式碼、測試紀錄與完成標記會保留。')) return;
    form.setAttribute('aria-busy','true'); testButton.disabled = askButton.disabled = clearButton.disabled = true;
    try {
      const data = new FormData(); data.set('csrfmiddlewaretoken',form.elements.namedItem('csrfmiddlewaretoken').value);
      const response = await fetch(form.dataset.clearUrl,{method:'POST',body:data,headers:{Accept:'application/json'}});
      if (!response.ok) throw new Error('清除失敗，請重新整理後重試。');
      const result = await response.json();
      history.replaceChildren();
      revision = null;
      const revisionControls = document.getElementById('revision-controls'); if (revisionControls) revisionControls.hidden = true;
      const notice = document.createElement('p'); notice.className = 'muted'; notice.textContent = '聊天紀錄已清除，可以開始新的對話。'; history.append(notice);
      question.value = '';
      form.elements.namedItem('parent_submission').value = result.parent;
      form.elements.namedItem('submission_id').value = result.next_token;
      form.dataset.record = String(result.parent); form.dataset.token = '';
      form.action = form.dataset.practiceUrl;
      window.history.replaceState(null,'',result.url);
      const shortcuts = document.querySelector('.shortcut-drawer'); if (shortcuts) shortcuts.open = true;
      form.dispatchEvent(new Event('chat-cleared'));
    } catch (error) { window.alert(error.message); }
    finally { resetBusy(); }
  });
  window.addEventListener('pageshow', () => {
    if (!following) resetBusy();
    // Wait until browser scroll restoration and markdown layout finish.
    if (typeof requestAnimationFrame === 'function') requestAnimationFrame(() => { history.scrollTop = history.scrollHeight; });
  });
  try {
    const pending = JSON.parse(window.sessionStorage?.getItem(pendingKey) || 'null');
    if (pending) {
      form.setAttribute('aria-busy','true'); testButton.disabled = askButton.disabled = clearButton.disabled = true;
      wait.hidden = false; wait.textContent = '正在恢復本次回覆進度；沒有重新呼叫模型。';
      following = true;
      followReply(pending).catch(error => {
        following = false; resetBusy(); showReplyRecovery(error,pending); askButton.disabled = true;
      });
    }
  } catch (_) { rememberPending(null); }
})();
