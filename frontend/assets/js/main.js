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

  const API_BASE = window.location.origin + '/api';

  // Helper to format date
  const formatDate = (isoString) => {
    const d = new Date(isoString);
    return {
      date: d.toISOString().split('T')[0],
      time: d.toTimeString().split(' ')[0] + ' UTC' // Simplified for UI
    };
  };

  let globalHistoryRecords = [];

  // 1. Load History
  const historyTbody = document.getElementById('history-tbody');
  if (historyTbody) {
    fetch(`${API_BASE}/history`)
      .then(res => res.json())
      .then(data => {
        globalHistoryRecords = data;
        historyTbody.innerHTML = '';
        if (data.length === 0) {
          historyTbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 2rem; color: var(--text-muted);">No records found.</td></tr>';
        }
        data.forEach(item => {
          const { date, time } = formatDate(item.created_at);
          const badgeClass = item.status === 'SUCCESS' ? 'badge-success' : (item.status === 'UNPUBLISHED' ? 'badge-unpublished' : 'badge-failed');
          const diagStyle = item.status === 'SUCCESS' ? 'color: var(--text-muted);' : 'color: var(--accent-red);';

          let actionHtml = `<td><span style="color: var(--text-muted); cursor: pointer;"></span></td>`;
          if (item.status === 'UNPUBLISHED') {
            actionHtml = `<td><button class="btn btn-primary" onclick="publishFromHistory(${item.id})" style="padding: 0.3rem 0.6rem; font-size: 0.8rem;">Publish</button></td>`;
          } else if (item.status === 'FAILED') {
            actionHtml = `<td><button class="btn btn-primary" onclick="publishFromHistory(${item.id})" style="padding: 0.3rem 0.6rem; font-size: 0.8rem;">Retry</button></td>`;
          }

          historyTbody.innerHTML += `
            <tr>
              <td style="white-space: normal;">
                <div style="font-weight: 500;">${date}</div>
                <div class="text-muted" style="font-size: 0.75rem;">${time}</div>
              </td>
              <td style="font-weight: 500;" title="${item.payload_title}">${item.payload_title}</td>
              <td class="text-muted">${item.target_platform}</td>
              <td><span class="badge ${badgeClass}">● ${item.status}</span></td>
              <td style="font-size: 0.8rem; ${diagStyle}" title="${item.diagnostics}">${item.diagnostics}</td>
              ${actionHtml}
            </tr>
          `;
        });
      })
      .catch(err => console.error("Failed to fetch history", err));
  }

  window.publishFromHistory = function (id) {
    const record = globalHistoryRecords.find(r => r.id === id);
    if (!record) return;

    const overlay = document.getElementById('history-popup-overlay');
    if (overlay) {
      document.getElementById('hist-news-title').innerText = "- " + (record.news_title || "");
      document.getElementById('hist-caption-x').value = record.caption_x || "";
      document.getElementById('hist-caption-ig').value = record.caption_ig || "";

      const imgEl = document.getElementById('hist-image');
      const placeholderEl = document.getElementById('hist-image-placeholder');
      if (record.image_url) {
        imgEl.src = record.image_url.startsWith('http') ? record.image_url : API_BASE.replace('/api', '') + record.image_url;
        imgEl.style.display = 'block';
        if (placeholderEl) placeholderEl.style.display = 'none';
      } else {
        imgEl.style.display = 'none';
        if (placeholderEl) placeholderEl.style.display = 'flex';
      }

      document.getElementById('btn-hist-publish').setAttribute('data-id', id);
      document.getElementById('btn-hist-regen').setAttribute('data-id', id);

      overlay.style.display = 'flex';
    }
  };

  const btnHistCancel = document.getElementById('btn-hist-cancel');
  if (btnHistCancel) {
    btnHistCancel.addEventListener('click', () => {
      document.getElementById('history-popup-overlay').style.display = 'none';
    });
  }

  const btnHistPublish = document.getElementById('btn-hist-publish');
  if (btnHistPublish) {
    btnHistPublish.addEventListener('click', () => {
      const id = btnHistPublish.getAttribute('data-id');
      if (!id) return;
      if (!confirm("Publish this agent now?")) return;

      btnHistPublish.disabled = true;
      btnHistPublish.textContent = "PUBLISHING...";

      const editedCaptionX = document.getElementById('hist-caption-x').value;
      const editedCaptionIG = document.getElementById('hist-caption-ig').value;

      fetch(`${API_BASE}/history/publish/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          caption_x: editedCaptionX,
          caption_ig: editedCaptionIG
        })
      })
        .then(res => res.json().then(data => ({ ok: res.ok, data })))
        .then(({ ok, data }) => {
          if (!ok && data.error === 'no_account_connected') {
            showNoAccountAlert(data.message);
            btnHistPublish.disabled = false;
            btnHistPublish.textContent = "PUBLISH";
            return;
          }
          if (!ok) {
            alert("Error: " + data.error);
            btnHistPublish.disabled = false;
            btnHistPublish.textContent = "PUBLISH";
            return;
          }
          alert("Publishing initiated!");
          window.location.reload();
        })
        .catch(err => {
          console.error("Publish error:", err);
          alert("Failed to publish from history.");
          btnHistPublish.disabled = false;
          btnHistPublish.textContent = "PUBLISH";
        });
    });
  }

  const btnHistRegen = document.getElementById('btn-hist-regen');
  if (btnHistRegen) {
    btnHistRegen.addEventListener('click', () => {
      const id = btnHistRegen.getAttribute('data-id');
      if (!id) return;

      const originalText = btnHistRegen.textContent;
      btnHistRegen.textContent = 'REGENERATING...';
      btnHistRegen.disabled = true;

      const editedCaptionIG = document.getElementById('hist-caption-ig').value;
      const editedCaptionX = document.getElementById('hist-caption-x').value;

      fetch(`${API_BASE}/history/regen-image/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          caption_x: editedCaptionX,
          caption_ig: editedCaptionIG
        })
      })
        .then(res => res.json())
        .then(data => {
          // To keep it simple, just reload to show the new image, or we can fetch the history again
          setTimeout(() => {
            alert("Regenerate requested. Please wait a moment and reload or check back.");
            window.location.reload();
          }, 2000);
        })
        .catch(err => {
          console.error("Regen error:", err);
          alert("Failed to regenerate image.");
          btnHistRegen.textContent = originalText;
          btnHistRegen.disabled = false;
        });
    });
  }

  // 2. Account Connection (Settings page)
  const cardX = document.getElementById('card-x');
  const cardIG = document.getElementById('card-ig');

  if (cardX || cardIG) {
    // Load account status on settings page
    loadAccountStatus();
  }

  function loadAccountStatus() {
    fetch(`${API_BASE}/oauth/status`)
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          console.error("OAuth status error:", data.error);
          return;
        }
        renderAccountCard('x', data.x || { connected: false });
        renderAccountCard('ig', data.ig || { connected: false });
      })
      .catch(err => {
        console.error("Failed to fetch OAuth status", err);
        renderAccountCard('x', { connected: false });
        renderAccountCard('ig', { connected: false });
      });
  }

  function renderAccountCard(platform, data) {
    const card = document.getElementById(`card-${platform}`);
    const statusEl = document.getElementById(`status-${platform}`);
    const infoEl = document.getElementById(`info-${platform}`);
    const emptyEl = document.getElementById(`empty-${platform}`);
    const btnConnect = document.getElementById(`btn-connect-${platform}`);
    const btnDisconnect = document.getElementById(`btn-disconnect-${platform}`);
    const usernameEl = document.getElementById(`username-${platform}`);
    const displaynameEl = document.getElementById(`displayname-${platform}`);
    const expiryEl = document.getElementById(`expiry-${platform}`);

    if (!card) return;

    if (data.connected) {
      // Connected state
      card.classList.add('connected');
      statusEl.className = 'account-status connected';
      statusEl.querySelector('.status-text').textContent = 'Connected';

      infoEl.style.display = 'flex';
      emptyEl.style.display = 'none';
      btnConnect.style.display = 'none';
      btnDisconnect.style.display = 'flex';

      usernameEl.textContent = `@${data.username || 'unknown'}`;
      displaynameEl.textContent = data.display_name || '';

      if (data.expires_at) {
        const expiryDate = new Date(data.expires_at * 1000);
        const now = new Date();
        const daysLeft = Math.ceil((expiryDate - now) / (1000 * 60 * 60 * 24));
        expiryEl.textContent = `Token expires in ${daysLeft} days`;
      } else {
        expiryEl.textContent = '';
      }
    } else {
      // Disconnected state
      card.classList.remove('connected');
      statusEl.className = 'account-status disconnected';
      statusEl.querySelector('.status-text').textContent = 'Not Connected';

      infoEl.style.display = 'none';
      emptyEl.style.display = 'block';
      btnConnect.style.display = 'flex';
      btnDisconnect.style.display = 'none';
    }
  }

  // Expose connect/disconnect to global scope for onclick handlers
  window.connectAccount = function (platform) {
    const btnConnect = document.getElementById(`btn-connect-${platform}`);
    const statusEl = document.getElementById(`status-${platform}`);
    const card = document.getElementById(`card-${platform}`);

    // Set loading state
    btnConnect.classList.add('loading');
    btnConnect.innerHTML = `CONNECTING...`;
    statusEl.className = 'account-status pending';
    statusEl.querySelector('.status-text').textContent = 'Waiting...';

    fetch(`${API_BASE}/oauth/login/${platform}`, { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          alert(`Error: ${data.error}`);
          btnConnect.classList.remove('loading');
          btnConnect.innerHTML = `CONNECT ${platform === 'x' ? 'X ACCOUNT' : 'INSTAGRAM'}`;
          renderAccountCard(platform, { connected: false });
          return;
        }

        // Open auth URL in a new tab
        if (data.auth_url) {
          window.open(data.auth_url, '_blank', 'width=600,height=700');
        }

        // Start polling for login completion
        let pollCount = 0;
        const maxPolls = 60; // 120 seconds (2s interval)
        const pollInterval = setInterval(() => {
          pollCount++;

          fetch(`${API_BASE}/oauth/login/${platform}/poll`)
            .then(res => res.json())
            .then(pollData => {
              if (pollData.status === 'success') {
                clearInterval(pollInterval);
                btnConnect.classList.remove('loading');
                loadAccountStatus(); // Refresh all cards
              } else if (pollData.status === 'error') {
                clearInterval(pollInterval);
                btnConnect.classList.remove('loading');
                btnConnect.innerHTML = `CONNECT ${platform === 'x' ? 'X ACCOUNT' : 'INSTAGRAM'}`;
                renderAccountCard(platform, { connected: false });
                alert(`Login failed: ${pollData.error}`);
              } else if (pollCount >= maxPolls) {
                clearInterval(pollInterval);
                btnConnect.classList.remove('loading');
                btnConnect.innerHTML = `CONNECT ${platform === 'x' ? 'X ACCOUNT' : 'INSTAGRAM'}`;
                renderAccountCard(platform, { connected: false });
                alert('Login timeout — please try again.');
              }
            })
            .catch(() => {
              // Network error during poll — keep trying
            });
        }, 2000);
      })
      .catch(err => {
        console.error(`Connect ${platform} error:`, err);
        btnConnect.classList.remove('loading');
        btnConnect.innerHTML = `CONNECT ${platform === 'x' ? 'X ACCOUNT' : 'INSTAGRAM'}`;
        alert('Failed to initiate login. Check server console.');
      });
  };

  window.disconnectAccount = function (platform) {
    if (!confirm(`Disconnect ${platform === 'x' ? 'X/Twitter' : 'Instagram'} account?`)) return;

    const btnDisconnect = document.getElementById(`btn-disconnect-${platform}`);
    btnDisconnect.textContent = 'DISCONNECTING...';
    btnDisconnect.style.opacity = '0.6';

    fetch(`${API_BASE}/oauth/logout/${platform}`, { method: 'POST' })
      .then(res => res.json())
      .then(() => {
        loadAccountStatus(); // Refresh all cards
      })
      .catch(err => {
        console.error(`Disconnect ${platform} error:`, err);
        alert('Failed to disconnect account.');
        btnDisconnect.textContent = 'DISCONNECT';
        btnDisconnect.style.opacity = '1';
      });
  };


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
      icon.innerHTML = '';
      span.className = 'text-cyan';
      span.innerHTML = name;
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
          if (startContainer) startContainer.style.display = 'none';
          if (runningContainer) runningContainer.style.display = 'block';
        } else {
          if (startContainer) startContainer.style.display = 'flex';
          if (runningContainer) runningContainer.style.display = 'none';
        }

        data.stages.forEach(stage => {
          updateStageUI(stage.id, stage.status, stage.name);
        });

        if (data.status === 'waiting_validation') {
          if (hitlPanel) hitlPanel.style.display = 'block';

          // Populate data from real AI
          const titleEl = document.getElementById('val-news-title');
          const capXEl = document.getElementById('val-caption-x');
          const capIGEl = document.getElementById('val-caption-ig');
          const imgEl = document.getElementById('val-image');
          const imgPlaceholder = document.getElementById('val-image-placeholder');

          if (titleEl) titleEl.innerText = "- " + data.data.news_title;
          if (capXEl) capXEl.value = data.data.caption_x;
          if (capIGEl) capIGEl.value = data.data.caption_ig;

          if (imgEl && data.data.image_url) {
            // Convert relative path to absolute using current API_BASE
            imgEl.src = data.data.image_url.startsWith('http') ? data.data.image_url : API_BASE.replace('/api', '') + data.data.image_url;
            imgEl.style.display = 'block';
            if (imgPlaceholder) imgPlaceholder.style.display = 'none';
          }
        } else {
          if (hitlPanel) hitlPanel.style.display = 'none';
        }

        if (data.status === 'error') {
          if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
            alert("Pipeline Error: " + data.error_message);
            if (startContainer) startContainer.style.display = 'flex';
            if (runningContainer) runningContainer.style.display = 'none';
          }
        }

        if (data.status === 'complete') {
          if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
            setTimeout(() => {
              alert("Publishing sequence complete!");
              // Refresh to idle state
              fetch(`${API_BASE}/pipeline/reject`, { method: 'POST' }).then(() => window.location.reload());
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
      // Cek dulu apakah publish bisa dilakukan (akun terkoneksi?)
      fetch(`${API_BASE}/pipeline/publish`, { method: 'POST' })
        .then(res => res.json().then(data => ({ ok: res.ok, data })))
        .then(({ ok, data }) => {
          if (!ok && data.error === 'no_account_connected') {
            // Tampilkan popup alert — akun belum terkoneksi
            showNoAccountAlert(data.message);
            return;
          }

          // Publish berhasil dimulai — buat history record
          fetch(`${API_BASE}/history`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              payload_title: "Generated_Post_" + Math.floor(Math.random() * 1000),
              target_platform: "Platform X & Instagram",
              status: "SUCCESS",
              diagnostics: "Published via Dashboard."
            })
          });
        })
        .catch(err => {
          console.error("Publish error:", err);
          alert("Gagal menghubungi server. Cek koneksi.");
        });
    });
  }

  // ── Popup Alert: Akun Belum Terkoneksi ──
  function showNoAccountAlert(message) {
    // Hapus overlay lama jika ada
    const existing = document.getElementById('no-account-overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'no-account-overlay';
    overlay.style.cssText = `
      position: fixed; top: 0; left: 0; width: 100%; height: 100%;
      background: rgba(0,0,0,0.6); display: flex; align-items: center;
      justify-content: center; z-index: 9999;
    `;

    overlay.innerHTML = `
      <div style="
        background: #1a1a2e; border: 1px solid var(--accent-purple); border-radius: 12px;
        padding: 32px; max-width: 440px; width: 90%; text-align: center;
      ">
        <div style="margin-bottom: 16px; display: flex; justify-content: center;">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="transparent" stroke="var(--accent-purple)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
        </div>
        <h3 style="color: #fff; margin: 0 0 12px 0; font-size: 1.2rem;">
          Akun Belum Terkoneksi
        </h3>
        <p style="color: #ccc; margin: 0 0 24px 0; font-size: 0.95rem; line-height: 1.5;">
          ${message}
        </p>
        <div style="display: flex; gap: 12px; justify-content: center;">
          <button onclick="window.location.href='settings.html'"
            style="
              background: linear-gradient(to right, var(--accent-purple), var(--accent-cyan)); color: #fff; border: none; padding: 10px 24px;
              border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.9rem;
            ">
            Buka Settings
          </button>
          <button onclick="document.getElementById('no-account-overlay').remove()"
            style="
              background: transparent; color: #ccc; border: 1px solid var(--accent-purple);
              padding: 10px 24px; border-radius: 6px; cursor: pointer; font-size: 0.9rem;
            ">
            Tutup
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    // Klik di luar popup untuk tutup
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.remove();
    });
  }

  const btnCancel = document.getElementById('btn-cancel');
  if (btnCancel) {
    btnCancel.addEventListener('click', () => {
      fetch(`${API_BASE}/pipeline/cancel`, { method: 'POST' })
        .then(() => {
          if (hitlPanel) hitlPanel.style.display = 'none';
          if (startContainer) startContainer.style.display = 'flex';
          if (runningContainer) runningContainer.style.display = 'none';
        });
    });
  }

  const btnRegen = document.getElementById('btn-regen');
  if (btnRegen) {
    btnRegen.addEventListener('click', () => {
      const originalText = btnRegen.textContent;
      btnRegen.textContent = 'REGENERATING...';
      btnRegen.disabled = true;

      fetch(`${API_BASE}/pipeline/regen-image`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
          // Polling will automatically pick up the new image URL when it's ready
          // We just need to reset the button after a short delay or let polling handle it
          setTimeout(() => {
            btnRegen.textContent = originalText;
            btnRegen.disabled = false;
          }, 3000); // Reset button after 3 seconds, image might take longer but polling will update UI
        })
        .catch(err => {
          console.error("Regen error:", err);
          alert("Failed to regenerate image.");
          btnRegen.textContent = originalText;
          btnRegen.disabled = false;
        });
    });
  }
});
