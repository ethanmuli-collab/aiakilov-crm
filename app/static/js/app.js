// Small shared behaviours. No framework, no build step.
document.addEventListener('submit', function (e) {
  const btn = e.target.querySelector('button[type="submit"]');
  if (btn && !btn.dataset.noLoading) {
    btn.classList.add('is-loading');
    btn.disabled = true;
    setTimeout(function () { btn.disabled = false; btn.classList.remove('is-loading'); }, 4000);
  }
});

// Auto-submit filter forms when a select changes.
document.querySelectorAll('[data-auto-submit] select').forEach(function (el) {
  el.addEventListener('change', function () { el.closest('form').submit(); });
});
