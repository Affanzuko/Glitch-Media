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

  const API_BASE = 'http://127.0.0.1:5000/api';

  // Helper to format date
  const formatDate = (isoString) => {
    const d = new Date(isoString);
    return {
      date: d.toISOString().split('T')[0],
      time: d.toTimeString().split(' ')[0] + ' UTC' // Simplified for UI
    };
  };

  // 1. Load History
  const historyTbody = document.getElementById('history-tbody');
  if (historyTbody) {
    fetch(`${API_BASE}/history`)
      .then(res => res.json())
      .then(data => {
        historyTbody.innerHTML = '';
        if(data.length === 0) {
            historyTbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 2rem; color: var(--text-muted);">No records found.</td></tr>';
        }
        data.forEach(item => {
          const { date, time } = formatDate(item.created_at);
          const badgeClass = item.status === 'SUCCESS' ? 'badge-success' : 'badge-failed';
          const diagStyle = item.status === 'SUCCESS' ? 'color: var(--text-muted);' : 'color: var(--accent-red);';
          
          historyTbody.innerHTML += `
            <tr>
              <td>
                <div style="font-weight: 500;">${date}</div>
                <div class="text-muted" style="font-size: 0.75rem;">${time}</div>
              </td>
              <td style="font-weight: 500;">${item.payload_title}</td>
              <td class="text-muted">${item.target_platform}</td>
              <td><span class="badge ${badgeClass}">● ${item.status}</span></td>
              <td style="font-size: 0.8rem; ${diagStyle}">${item.diagnostics}</td>
              <td><span style="color: var(--text-muted); cursor: pointer;">&gt;</span></td>
            </tr>
          `;
        });
      })
      .catch(err => console.error("Failed to fetch history", err));
  }

  // 2. Load and Save Settings
  const btnSaveConfig = document.getElementById('btn-save-config');
  const inputOpenAI = document.getElementById('api-openai');
  const inputAnthropic = document.getElementById('api-anthropic');
  const input9Router = document.getElementById('api-9router');

  // Load on settings page
  if (btnSaveConfig) {
    fetch(`${API_BASE}/settings`)
      .then(res => res.json())
      .then(data => {
        if(data['OPENAI_API_KEY']) inputOpenAI.value = data['OPENAI_API_KEY'];
        if(data['ANTHROPIC_API_KEY']) inputAnthropic.value = data['ANTHROPIC_API_KEY'];
        if(data['NINEROUTER_API_KEY']) input9Router.value = data['NINEROUTER_API_KEY'];
      });

    btnSaveConfig.addEventListener('click', () => {
      const payload = {
        OPENAI_API_KEY: inputOpenAI.value,
        ANTHROPIC_API_KEY: inputAnthropic.value,
        NINEROUTER_API_KEY: input9Router.value
      };
      
      btnSaveConfig.innerText = 'SAVING...';
      fetch(`${API_BASE}/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(res => res.json())
      .then(() => {
        btnSaveConfig.innerText = 'SAVED ✓';
        setTimeout(() => btnSaveConfig.innerText = 'SAVE CONFIGURATION', 2000);
      });
    });
  }

  // Pipeline Logic
  const startContainer = document.getElementById('pipeline-start-container');
  const runningContainer = document.getElementById('pipeline-running-container');
  const hitlPanel = document.getElementById('hitl-validation-panel');
  const btnStart = document.getElementById('btn-start-pipeline');
  
  let pollingInterval = null;

  const updateStageUI = (stageId, status, name) => {
    const el = document.getElementById(stageId);
    if (!el) return;
    const icon = el.querySelector('.status-icon');
    const span = el.querySelector('span');
    
    icon.className = 'status-icon ' + status;
    
    if (status === 'done') {
      icon.innerHTML = '&#10003;';
      span.className = '';
      span.innerHTML = name;
    } else if (status === 'progress') {
      icon.innerHTML = name.charAt(0);
      span.className = 'text-cyan';
      span.innerHTML = `${name} <span style="display: inline-block; animation: blink 1s infinite;">●</span>`;
    } else {
      icon.innerHTML = '';
      span.className = 'text-muted';
      span.innerHTML = name;
    }
  };

  const pollPipelineStatus = () => {
    fetch(`${API_BASE}/pipeline/status`)
      .then(res => res.json())
      .then(data => {
        if (data.status !== 'idle') {
          if(startContainer) startContainer.style.display = 'none';
          if(runningContainer) runningContainer.style.display = 'block';
        } else {
          if(startContainer) startContainer.style.display = 'flex';
          if(runningContainer) runningContainer.style.display = 'none';
        }

        data.stages.forEach(stage => {
          updateStageUI(stage.id, stage.status, stage.name);
        });

        if (data.status === 'waiting_validation') {
          if(hitlPanel) hitlPanel.style.display = 'block';
          
          // Populate data from real AI
          const titleEl = document.getElementById('val-news-title');
          const capXEl = document.getElementById('val-caption-x');
          const capIGEl = document.getElementById('val-caption-ig');
          const imgEl = document.getElementById('val-image');
          const imgPlaceholder = document.getElementById('val-image-placeholder');

          if(titleEl) titleEl.innerText = "- " + data.data.news_title;
          if(capXEl) capXEl.value = data.data.caption_x;
          if(capIGEl) capIGEl.value = data.data.caption_ig;
          
          if(imgEl && data.data.image_url) {
            // Convert relative path to absolute using current API_BASE
            imgEl.src = data.data.image_url.startsWith('http') ? data.data.image_url : API_BASE.replace('/api', '') + data.data.image_url;
            imgEl.style.display = 'block';
            if(imgPlaceholder) imgPlaceholder.style.display = 'none';
          }
        } else {
          if(hitlPanel) hitlPanel.style.display = 'none';
        }

        if (data.status === 'error') {
           if (pollingInterval) {
               clearInterval(pollingInterval);
               pollingInterval = null;
               alert("Pipeline Error: " + data.error_message);
               if(startContainer) startContainer.style.display = 'flex';
               if(runningContainer) runningContainer.style.display = 'none';
           }
        }

        if (data.status === 'complete') {
           if (pollingInterval) {
               clearInterval(pollingInterval);
               pollingInterval = null;
               setTimeout(() => {
                 alert("Publishing sequence complete!");
                 // Refresh to idle state
                 fetch(`${API_BASE}/pipeline/reject`, {method: 'POST'}).then(() => window.location.reload());
               }, 1000);
           }
        }
      });
  };

  if (startContainer || runningContainer) {
    // Initial check
    pollPipelineStatus();
    pollingInterval = setInterval(pollPipelineStatus, 1000);
  }

  if (btnStart) {
    btnStart.addEventListener('click', () => {
      fetch(`${API_BASE}/pipeline/start`, { method: 'POST' })
        .then(() => pollPipelineStatus());
    });
  }

  const btnAccept = document.getElementById('btn-accept');
  if (btnAccept) {
    btnAccept.addEventListener('click', () => {
      // Create history record
      fetch(`${API_BASE}/history`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          payload_title: "Generated_Post_" + Math.floor(Math.random() * 1000),
          target_platform: "Platform X & Instagram",
          status: "SUCCESS",
          diagnostics: "Published via Dashboard."
        })
      }).then(() => {
        // Trigger publish sequence
        fetch(`${API_BASE}/pipeline/publish`, { method: 'POST' });
      });
    });
  }

  const btnReject = document.getElementById('btn-reject');
  if (btnReject) {
    btnReject.addEventListener('click', () => {
      fetch(`${API_BASE}/pipeline/reject`, { method: 'POST' })
        .then(() => {
          if(hitlPanel) hitlPanel.style.display = 'none';
          if(startContainer) startContainer.style.display = 'flex';
          if(runningContainer) runningContainer.style.display = 'none';
        });
    });
  }

  const btnRegen = document.getElementById('btn-regen');
  if (btnRegen) {
    btnRegen.addEventListener('click', () => {
      alert('Regenerating visual assets based on new caption...');
    });
  }
});
