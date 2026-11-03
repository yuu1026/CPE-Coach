(() => {
  const form = document.getElementById('workspace-form');
  const notes = document.getElementById('thinking-notes');
  if (!form || !notes) return;
  const key = `cpe:notes:v1:${form.dataset.user}:${form.dataset.problem}`;
  const status = document.getElementById('notes-status');
  try { notes.value = localStorage.getItem(key) || ''; }
  catch { status.textContent = '瀏覽器無法讀取筆記；內容不會送給模型。'; }
  notes.addEventListener('input', () => {
    try { localStorage.setItem(key, notes.value); status.textContent = '筆記已保存於此瀏覽器，不會送給模型。'; }
    catch { status.textContent = '瀏覽器無法保存筆記，請自行備份。'; }
  });
})();
