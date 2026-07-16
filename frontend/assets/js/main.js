document.addEventListener('DOMContentLoaded', () => {
  // Setup password visibility toggles
  const eyeIcons = document.querySelectorAll('.input-with-icon .icon');
  
  eyeIcons.forEach(icon => {
    icon.addEventListener('click', (e) => {
      const input = e.target.previousElementSibling;
      if (input.type === 'password') {
        input.type = 'text';
        e.target.innerHTML = '&#128064;'; // Open eye approx
        e.target.style.opacity = '1';
      } else {
        input.type = 'password';
        e.target.innerHTML = '&#128065;'; // Closed eye
        e.target.style.opacity = '0.5';
      }
    });
  });

  // Example interactive elements
  const btnAccept = document.getElementById('btn-accept');
  if (btnAccept) {
    btnAccept.addEventListener('click', () => {
      alert('Payload Accepted & Publishing Sequence Initiated...');
    });
  }

  const btnReject = document.getElementById('btn-reject');
  if (btnReject) {
    btnReject.addEventListener('click', () => {
      alert('Payload Rejected. Restarting Generation Cycle...');
    });
  }

  const btnRegen = document.getElementById('btn-regen');
  if (btnRegen) {
    btnRegen.addEventListener('click', () => {
      alert('Regenerating visual assets based on new caption...');
    });
  }
});
