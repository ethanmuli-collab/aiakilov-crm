// Drag & drop pipeline with optimistic UI and server persistence.
(function () {
  const board = document.getElementById('kanban');
  if (!board) return;

  let dragged = null;

  board.querySelectorAll('.kanban-card').forEach(function (card) {
    card.setAttribute('draggable', 'true');
    card.addEventListener('dragstart', function (e) {
      dragged = card;
      card.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', card.dataset.leadId);
    });
    card.addEventListener('dragend', function () {
      card.classList.remove('dragging');
      dragged = null;
    });
  });

  board.querySelectorAll('.kanban-col').forEach(function (col) {
    col.addEventListener('dragover', function (e) {
      e.preventDefault();
      col.classList.add('drag-over');
    });
    col.addEventListener('dragleave', function () { col.classList.remove('drag-over'); });

    col.addEventListener('drop', function (e) {
      e.preventDefault();
      col.classList.remove('drag-over');
      if (!dragged) return;

      const leadId = dragged.dataset.leadId;
      const status = col.dataset.status;
      const from = dragged.closest('.kanban-col');
      if (from === col) return;

      col.querySelector('.kanban-items').appendChild(dragged); // optimistic
      updateCount(from); updateCount(col);

      fetch('/leads/' + leadId + '/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: status })
      }).then(function (r) {
        if (!r.ok) throw new Error('failed');
      }).catch(function () {
        from.querySelector('.kanban-items').appendChild(dragged); // rollback
        updateCount(from); updateCount(col);
        alert('עדכון הסטטוס נכשל. הכרטיס הוחזר למקומו.');
      });
    });
  });

  function updateCount(col) {
    const n = col.querySelectorAll('.kanban-card').length;
    col.querySelector('.kanban-count').textContent = n;
  }
})();
