(() => {
  document.querySelectorAll('[data-picker]').forEach(form => {
    const search = form.querySelector('[data-search]');
    const filter = form.querySelector('[data-filter]');
    const track = form.querySelector('[data-track-filter]');
    const select = form.querySelector('[data-topics]');
    const options = [...select.options].filter(option => option.value);
    function update() {
      const query = search.value.trim().toLowerCase();
      const visible = options.filter(option => (!track?.value || option.dataset.track === track.value) && option.textContent.toLowerCase().includes(query) &&
        (filter.value === 'all' || (option.dataset.done === 'yes') === (filter.value === 'done')));
      const previous = select.value;
      select.replaceChildren(select.options[0], ...visible);
      select.value = visible.some(option => option.value === previous) ? previous : '';
      form.querySelector('[data-matches]').textContent = `${visible.length} 題`;
      form.querySelector('button').disabled = !visible.length;
    }
    search.addEventListener('input', update);
    filter.addEventListener('change', update);
    track?.addEventListener('change', update);
    search.addEventListener('keydown', event => { if (event.key === 'Enter') event.preventDefault(); });
    update();
  });
})();
