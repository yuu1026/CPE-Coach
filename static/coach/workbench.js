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
  const originalCode = originalNode ? JSON.parse(originalNode.textContent) : null;
  const originalCustomNode = document.getElementById('original-custom-test');
  const originalCustom = originalCustomNode ? JSON.parse(originalCustomNode.textContent) : null;
  function normalizeCustom(custom) { return JSON.stringify(custom?.enabled ? {enabled:true, input:custom.input || '', expected:custom.expected || ''} : {enabled:false}); }
  const customSnapshot = normalizeCustom(originalCustom && typeof originalCustom === 'object' ? originalCustom : {enabled: document.getElementById('id_run_custom').checked, input: document.getElementById('id_custom_input').value, expected: document.getElementById('id_custom_expected').value});
  function updateEditor() {
    const count = Array.from(code()).length;
    const counter = document.getElementById('code-count');
    counter.textContent = `${count} / 12000 字元`;
    counter.classList.toggle('error', count > 12000);
    editorError.hidden = true;
    const custom = normalizeCustom({enabled: document.getElementById('id_run_custom').checked, input: document.getElementById('id_custom_input').value, expected: document.getElementById('id_custom_expected').value});
    document.getElementById('stale-result').hidden = originalCode === null || (code() === originalCode && custom === customSnapshot);
    document.getElementById('result-freshness').textContent = document.getElementById('stale-result').hidden ? '' : '已修改，請重新測試';
    form.dispatchEvent(new Event('draft-change'));
  }
  textarea.addEventListener('input', updateEditor);
  ['id_run_custom', 'id_custom_input', 'id_custom_expected'].forEach(id => document.getElementById(id).addEventListener('input', updateEditor));
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
  question.addEventListener('keydown', event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); form.requestSubmit(askButton); } });
  form.addEventListener('submit', event => {
    if (form.getAttribute('aria-busy') === 'true') { event.preventDefault(); return; }
    if (editor) editor.save();
    const action = event.submitter?.value || 'ask';
    if (Array.from(code()).length > 12000 || (action === 'test' && !code().trim())) {
      event.preventDefault(); showPane('code');
      editorError.textContent = Array.from(code()).length > 12000 ? '程式碼超過 12000 字元，請縮小範圍。' : '請先輸入程式碼；沒有想法時可直接送出訊息。';
      editorError.hidden = false;
      if (editor) editor.focus(); else textarea.focus();
      return;
    }
    form.querySelector('input[name="action"]').value = action;
    form.setAttribute('aria-busy', 'true');
    testButton.disabled = askButton.disabled = true;
    wait.textContent = action === 'test' ? '正在編譯與執行測資…' : '助理正在整理回覆…';
    wait.hidden = false;
    if (action === 'test') document.getElementById('result-freshness').textContent = '正在編譯與執行測資…';
    if (action === 'test') testButton.textContent = '測試中…'; else askButton.textContent = '回覆中…';
  });
  window.addEventListener('pageshow', () => { form.removeAttribute('aria-busy'); testButton.disabled = askButton.disabled = false; testButton.textContent = '▷ 執行測試'; askButton.textContent = '送出訊息 ↑'; wait.hidden = true; });
})();
