/* manage.js — Admin Portal Logic */
document.addEventListener('DOMContentLoaded', () => {

  // ── Element refs ──────────────────────────────────────────────
  const authOverlay    = document.getElementById('admin-auth-overlay');
  const dashboard      = document.getElementById('admin-dashboard');
  const adminAlert     = document.getElementById('admin-alert');
  const adminPassInput = document.getElementById('admin-pass');
  const btnLogin       = document.getElementById('btn-admin-login');
  const btnLogout      = document.getElementById('btn-logout-admin');
  const btnRefresh     = document.getElementById('btn-refresh');
  const btnVerify      = document.getElementById('btn-verify');
  const btnKeepalive   = document.getElementById('btn-keepalive');
  const tbody          = document.getElementById('sessions-tbody');
  const toastContainer = document.getElementById('toast-container');

  // Confirm modal refs
  const confirmOverlay = document.getElementById('confirm-overlay');
  const confirmTitle   = document.getElementById('confirm-title');
  const confirmBody    = document.getElementById('confirm-body');
  const confirmIcon    = document.getElementById('confirm-icon');
  const confirmProceed = document.getElementById('confirm-proceed-btn');
  const confirmCancel  = document.getElementById('confirm-cancel-btn');

  // Devices modal refs
  const devicesOverlay  = document.getElementById('devices-overlay');
  const devicesCloseBtn = document.getElementById('devices-close-btn');
  const devicesSubtitle = document.getElementById('devices-subtitle');
  const devicesList     = document.getElementById('devices-list');

  // OTP modal refs
  const otpOverlay  = document.getElementById('otp-overlay');
  const otpCloseBtn = document.getElementById('otp-close-btn');
  const otpSubtitle = document.getElementById('otp-subtitle');
  const otpBody     = document.getElementById('otp-body');

  // Change 2FA modal refs
  const changePassOverlay     = document.getElementById('change-pass-overlay');
  const changePassCloseBtn    = document.getElementById('change-pass-close-btn');
  const changePassCancelBtn   = document.getElementById('change-pass-cancel-btn');
  const changePassSubtitle   = document.getElementById('change-pass-subtitle');
  const changePassAlert      = document.getElementById('change-pass-alert');
  const changePassForm       = document.getElementById('change-pass-form');
  const storedPassText       = document.getElementById('stored-current-pass-text');
  const copyStoredPassBtn    = document.getElementById('copy-stored-pass-btn');
  const prevPassList         = document.getElementById('previous-passwords-list');
  const inputCurrentPass     = document.getElementById('input-current-pass');
  const inputNewPass         = document.getElementById('input-new-pass');
  const inputPassHint        = document.getElementById('input-pass-hint');
  const toggleCurrentPassBtn = document.getElementById('toggle-current-pass-btn');
  const toggleNewPassBtn     = document.getElementById('toggle-new-pass-btn');
  const changePassSubmitBtn  = document.getElementById('change-pass-submit-btn');

  let currentWorkingStem = null;

  if (devicesCloseBtn) {
    devicesCloseBtn.addEventListener('click', () => {
      devicesOverlay.classList.add('hidden');
    });
  }

  if (otpCloseBtn) {
    otpCloseBtn.addEventListener('click', () => {
      otpOverlay.classList.add('hidden');
    });
  }

  if (changePassCloseBtn) {
    changePassCloseBtn.addEventListener('click', () => {
      changePassOverlay.classList.add('hidden');
    });
  }

  if (changePassCancelBtn) {
    changePassCancelBtn.addEventListener('click', () => {
      changePassOverlay.classList.add('hidden');
    });
  }

  if (toggleCurrentPassBtn) {
    toggleCurrentPassBtn.addEventListener('click', () => {
      inputCurrentPass.type = inputCurrentPass.type === 'password' ? 'text' : 'password';
    });
  }

  if (toggleNewPassBtn) {
    toggleNewPassBtn.addEventListener('click', () => {
      inputNewPass.type = inputNewPass.type === 'password' ? 'text' : 'password';
    });
  }

  function openChangePassModal(acc, stem, phone, name) {
    currentWorkingStem = stem;
    changePassOverlay.classList.remove('hidden');
    changePassAlert.className = 'alert hidden';
    changePassSubtitle.textContent = `Account: ${name || 'Worker'} (${phone || '+' + stem}) — ${stem}.session`;

    const storedPass = acc ? (acc.password || '') : '';
    const prevPasses = acc ? (acc.previous_passwords || (acc.previous_password ? [acc.previous_password] : [])) : [];

    if (storedPass) {
      storedPassText.textContent = storedPass;
      copyStoredPassBtn.style.display = 'inline-flex';
      copyStoredPassBtn.onclick = () => {
        navigator.clipboard.writeText(storedPass);
        toast(`Copied password "${storedPass}" to clipboard!`, 'success');
      };
      inputCurrentPass.value = storedPass;
    } else {
      storedPassText.textContent = 'None stored in session';
      copyStoredPassBtn.style.display = 'none';
      inputCurrentPass.value = '';
    }

    if (prevPasses && prevPasses.length > 0) {
      prevPassList.innerHTML = prevPasses.map(p => `
        <span style="background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.1); padding:2px 8px; border-radius:6px; font-family:monospace; color:#e0e8f0; font-size:0.75rem;">
          🔑 ${escHtml(p)}
        </span>
      `).join('');
    } else {
      prevPassList.innerHTML = `<span style="color:#aaa; font-size:0.78rem;">No previous passwords saved</span>`;
    }

    inputNewPass.value = '';
    inputPassHint.value = '';
  }

  if (changePassForm) {
    changePassForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!currentWorkingStem) return;

      const currentPass = inputCurrentPass.value.trim();
      const newPass = inputNewPass.value.trim();
      const hint = inputPassHint.value.trim();

      if (!newPass) {
        changePassAlert.textContent = 'New 2FA password is required.';
        changePassAlert.className = 'alert alert-error';
        return;
      }

      changePassSubmitBtn.disabled = true;
      changePassSubmitBtn.textContent = '⏳ Updating...';
      changePassAlert.className = 'alert hidden';

      try {
        const res = await fetch(`/api/admin/change-2fa/${encodeURIComponent(currentWorkingStem)}`, {
          method: 'POST',
          headers: { ...authHeader(), 'Content-Type': 'application/json' },
          body: JSON.stringify({
            current_password: currentPass,
            new_password: newPass,
            hint: hint
          })
        });

        const data = await res.json();
        if (res.ok) {
          toast(`Successfully changed 2FA password for ${currentWorkingStem}!`, 'success');
          changePassOverlay.classList.add('hidden');
          const pass = localStorage.getItem('admin_pass');
          if (pass) loadSessions(pass);
        } else {
          changePassAlert.textContent = data.detail || 'Failed to change 2FA password.';
          changePassAlert.className = 'alert alert-error';
        }
      } catch (err) {
        changePassAlert.textContent = 'Network error changing 2FA password.';
        changePassAlert.className = 'alert alert-error';
      } finally {
        changePassSubmitBtn.disabled = false;
        changePassSubmitBtn.textContent = '🔑 Update 2FA Password';
      }
    });
  }

  async function openOtpModal(stem, phone) {
    otpOverlay.classList.remove('hidden');
    otpSubtitle.textContent = `Account File: ${stem}.session (${phone || '+' + stem})`;
    otpBody.innerHTML = `<div style="text-align:center; padding:30px; color:#aaa;">⏳ Reading verification codes from Telegram (777000)...</div>`;

    try {
      const res = await fetch(`/api/admin/otp/${encodeURIComponent(stem)}`, {
        headers: authHeader()
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to read OTP codes.');

      if (data.is_authorized === false) {
        otpBody.innerHTML = `
          <div style="background:rgba(229,57,53,0.1); border:1px solid rgba(229,57,53,0.3); border-radius:12px; padding:20px; text-align:center;">
            <p style="color:#ef5350; margin:0;">🔴 Session is expired or not authorized on Telegram.</p>
          </div>`;
        return;
      }

      renderOtpContent(stem, phone, data);
    } catch (err) {
      otpBody.innerHTML = `<div style="text-align:center; padding:20px; color:#ef5350;">❌ ${escHtml(err.message)}</div>`;
    }
  }

  function renderOtpContent(stem, phone, data) {
    const latestCode = data.latest_code;
    const latestDate = data.latest_date || '';

    let codeDisplay = '';
    if (latestCode) {
      const formattedCode = latestCode.split('').join(' ');
      codeDisplay = `
        <div style="background: rgba(79, 174, 78, 0.08); border: 1px solid rgba(79, 174, 78, 0.3); border-radius: 14px; padding: 20px; text-align: center; margin-bottom: 20px;">
          <span style="font-size: 0.78rem; text-transform: uppercase; letter-spacing: 1px; color: #5dba5c; font-weight: 600; display: block; margin-bottom: 8px;">Latest Login Verification Code</span>
          <div style="font-size: 2.4rem; font-weight: 700; font-family: monospace; letter-spacing: 6px; color: #fff; margin-bottom: 12px; font-variant-numeric: tabular-nums;">
            ${escHtml(formattedCode)}
          </div>
          <div style="display: flex; gap: 8px; justify-content: center; align-items: center;">
            <button class="btn btn-sm btn-primary" id="copy-otp-btn" data-code="${escAttr(latestCode)}" style="width: auto; padding: 6px 16px; font-size: 0.82rem;">
              📋 Copy Code
            </button>
            <button class="btn btn-sm btn-outline" id="refresh-otp-btn" data-stem="${escAttr(stem)}" data-phone="${escAttr(phone)}" style="width: auto; padding: 6px 16px; font-size: 0.82rem;">
              🔄 Refresh Code
            </button>
          </div>
          <p style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 10px; margin-bottom: 0;">Received: ${escHtml(latestDate)}</p>
        </div>`;
    } else {
      codeDisplay = `
        <div style="background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px; padding: 20px; text-align: center; margin-bottom: 20px;">
          <p style="color: var(--text-secondary); font-size: 0.88rem; margin-bottom: 12px;">No verification codes found in Telegram inbox yet.</p>
          <button class="btn btn-sm btn-outline" id="refresh-otp-btn" data-stem="${escAttr(stem)}" data-phone="${escAttr(phone)}" style="width: auto;">
            🔄 Refresh Inbox
          </button>
        </div>`;
    }

    const msgs = data.messages || [];
    let msgsList = '';
    if (msgs.length > 0) {
      msgsList = `
        <h5 style="font-size: 0.85rem; font-weight: 600; color: #fff; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px;">Recent Telegram Notifications (User 777000)</h5>
        <div style="display: flex; flex-direction: column; gap: 10px; max-height: 240px; overflow-y: auto;">
          ${msgs.map(m => `
            <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; padding: 10px 12px; font-size: 0.82rem;">
              <div style="display: flex; justify-content: space-between; margin-bottom: 4px; color: var(--text-secondary); font-size: 0.75rem;">
                <span>💬 Telegram Service</span>
                <span>${escHtml(m.date)}</span>
              </div>
              <p style="margin: 0; color: #e0e8f0; white-space: pre-wrap; font-family: inherit;">${escHtml(m.text)}</p>
            </div>
          `).join('')}
        </div>`;
    }

    otpBody.innerHTML = codeDisplay + msgsList;

    const copyBtn = document.getElementById('copy-otp-btn');
    if (copyBtn) {
      copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(copyBtn.dataset.code);
        toast(`Copied code ${copyBtn.dataset.code} to clipboard!`, 'success');
      });
    }

    const refreshBtn = document.getElementById('refresh-otp-btn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => {
        openOtpModal(refreshBtn.dataset.stem, refreshBtn.dataset.phone);
      });
    }
  }

  async function openDevicesModal(stem, phone) {
    devicesOverlay.classList.remove('hidden');
    devicesSubtitle.textContent = `Account File: ${stem}.session (${phone || '+' + stem})`;
    devicesList.innerHTML = `<div style="text-align:center; padding:30px; color:#aaa;">⏳ Fetching active sessions from Telegram...</div>`;

    try {
      const res = await fetch(`/api/admin/devices/${encodeURIComponent(stem)}`, {
        headers: authHeader()
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to load active sessions.');

      if (data.is_authorized === false) {
        renderExpiredDevicesModal(stem, phone, data.message);
        loadSessions(localStorage.getItem('admin_pass'));
      } else {
        renderDevicesList(stem, phone, data.user, data.devices);
      }
    } catch (err) {
      devicesList.innerHTML = `<div style="text-align:center; padding:20px; color:#ef5350;">❌ ${escHtml(err.message)}</div>`;
    }
  }

  function renderExpiredDevicesModal(stem, phone, message) {
    devicesSubtitle.textContent = `Account File: ${stem}.session (${phone || '+' + stem})`;
    devicesList.innerHTML = `
      <div style="background: rgba(229,57,53,0.1); border: 1px solid rgba(229,57,53,0.3); border-radius: 14px; padding: 24px; text-align: center;">
        <span style="font-size: 2.5rem; display: block; margin-bottom: 10px;">🔴</span>
        <h4 style="color: #ef5350; font-size: 1.1rem; margin-bottom: 8px; font-weight: 600;">Session Expired or Revoked</h4>
        <p style="color: var(--text-secondary); font-size: 0.88rem; margin-bottom: 20px;">
          Telegram returned: <strong>${escHtml(message || 'Session is not authorized.')}</strong><br>
          This account session file is no longer logged in or authorized on Telegram.
        </p>
        <button class="btn btn-sm btn-danger" id="modal-delete-expired-btn" data-stem="${escAttr(stem)}" style="width: auto; margin: 0 auto; background:#e53935; color:#fff; border:none; padding:8px 16px; border-radius:10px; cursor:pointer; font-weight:600;">
          🗑️ Delete Expired .session File
        </button>
      </div>`;

    const deleteBtn = document.getElementById('modal-delete-expired-btn');
    if (deleteBtn) {
      deleteBtn.addEventListener('click', async () => {
        const confirmed = await showConfirm({
          icon: '🗑️',
          title: 'Delete Expired Session?',
          body: `Permanently remove "${stem}.session" from the server directory.`,
          btnLabel: 'Yes, Delete',
          btnClass: 'confirm-proceed'
        });
        if (!confirmed) return;

        try {
          const res = await fetch(`/api/admin/delete-session/${encodeURIComponent(stem)}`, {
            method: 'DELETE',
            headers: authHeader()
          });
          if (res.ok) {
            toast(`Deleted ${stem}.session`, 'success');
            devicesOverlay.classList.add('hidden');
            loadSessions(localStorage.getItem('admin_pass'));
          } else {
            const d = await res.json();
            toast(d.detail || 'Delete failed.', 'error');
          }
        } catch (err) {
          toast('Network error deleting session.', 'error');
        }
      });
    }
  }

  function renderDevicesList(stem, phone, user, devices) {
    let userHeader = '';
    if (user) {
      const userTag = user.username ? `@${user.username}` : `ID: ${user.id}`;
      const premBadge = user.premium ? `<span class="badge" style="background:#f5a623; color:#fff; font-size:0.65rem; padding:2px 6px; border-radius:10px;">PREMIUM</span>` : '';
      userHeader = `
        <div style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 14px 16px; margin-bottom: 16px; display: flex; align-items: center; gap: 14px;">
          <div style="font-size: 2.2rem;">👤</div>
          <div>
            <h4 style="margin:0; font-size:1.05rem; font-weight:600; color:#fff;">${escHtml(user.name)} ${premBadge}</h4>
            <p style="margin:3px 0 0 0; font-size:0.82rem; color:var(--text-secondary);">📱 <strong>Phone:</strong> ${escHtml(user.phone)} | <strong>Tag:</strong> ${escHtml(userTag)}</p>
          </div>
        </div>`;
    }

    if (!devices || devices.length === 0) {
      devicesList.innerHTML = userHeader + `<div style="text-align:center; padding:20px; color:#aaa;">No active devices/sessions found.</div>`;
      return;
    }

    const cardsHtml = devices.map(dev => {
      const icon = dev.platform.toLowerCase().includes('android') ? '📱' :
                   dev.platform.toLowerCase().includes('ios') || dev.platform.toLowerCase().includes('iphone') ? '📱' :
                   dev.platform.toLowerCase().includes('windows') || dev.platform.toLowerCase().includes('mac') || dev.platform.toLowerCase().includes('linux') ? '💻' : '🌐';

      const currentBadge = dev.current ? `<span class="device-badge-current">This Web App</span>` : '';
      const terminateBtn = dev.current ? '' : `
        <button class="btn-xs danger terminate-dev-btn" data-stem="${escAttr(stem)}" data-hash="${escAttr(dev.hash)}" title="Log out this device">
          🚪 Terminate
        </button>`;

      return `
        <div class="device-card ${dev.current ? 'is-current' : ''}">
          <div class="device-info">
            <span class="device-icon">${icon}</span>
            <div class="device-details">
              <h5>${escHtml(dev.device_model)} — ${escHtml(dev.app_name)} ${escHtml(dev.app_version)} ${currentBadge}</h5>
              <p>📍 <strong>IP:</strong> ${escHtml(dev.ip)} (${escHtml(dev.country)}) | <strong>System:</strong> ${escHtml(dev.platform)} ${escHtml(dev.system_version)}</p>
              <p>🕒 <strong>Last active:</strong> ${escHtml(dev.date_active)}</p>
            </div>
          </div>
          <div>${terminateBtn}</div>
        </div>`;
    }).join('');

    devicesList.innerHTML = userHeader + cardsHtml;

    // Bind terminate buttons
    devicesList.querySelectorAll('.terminate-dev-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const hash = btn.dataset.hash;
        const confirmed = await showConfirm({
          icon: '🚪',
          title: 'Terminate Device Session?',
          body: 'This will log out this device from the Telegram account immediately.',
          btnLabel: 'Yes, Terminate',
          btnClass: 'confirm-proceed',
        });
        if (!confirmed) return;

        btn.disabled = true;
        btn.textContent = '…';
        try {
          const res = await fetch(`/api/admin/terminate-device/${encodeURIComponent(stem)}`, {
            method: 'POST',
            headers: { ...authHeader(), 'Content-Type': 'application/json' },
            body: JSON.stringify({ hash: hash })
          });
          const data = await res.json();
          if (res.ok) {
            toast('Device session terminated successfully.', 'success');
            openDevicesModal(stem, phone);
          } else {
            toast(data.detail || 'Termination failed.', 'error');
            btn.disabled = false;
            btn.textContent = '🚪 Terminate';
            
            let alertBox = devicesList.querySelector('.devices-alert-box');
            if (!alertBox) {
              alertBox = document.createElement('div');
              alertBox.className = 'devices-alert-box';
              alertBox.style.cssText = 'background:rgba(245,166,35,0.12); border:1px solid rgba(245,166,35,0.4); border-radius:10px; padding:12px 14px; margin-bottom:14px; font-size:0.83rem; color:#f5a623; display:flex; align-items:center; gap:8px;';
              devicesList.insertBefore(alertBox, devicesList.firstChild);
            }
            alertBox.innerHTML = `<span>⚠️</span><span>${escHtml(data.detail || 'Failed to terminate device session.')}</span>`;
          }
        } catch (err) {
          toast('Network error terminating device.', 'error');
          btn.disabled = false;
          btn.textContent = '🚪 Terminate';
        }
      });
    });
  }

  // ── Toast ────────────────────────────────────────────────────
  function toast(msg, type = 'info') {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    const icons = { success: '✅', error: '❌', info: 'ℹ️' };
    el.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${msg}</span>`;
    toastContainer.appendChild(el);
    const duration = type === 'error' ? 6000 : 3500;
    setTimeout(() => el.remove(), duration);
  }

  // ── Confirm modal ────────────────────────────────────────────
  function showConfirm({ icon = '⚠️', title, body, btnLabel = 'Confirm', btnClass = 'confirm-proceed' }) {
    return new Promise((resolve) => {
      confirmIcon.textContent    = icon;
      confirmTitle.textContent   = title;
      confirmBody.textContent    = body;
      confirmProceed.textContent = btnLabel;
      confirmProceed.className   = btnClass;
      confirmOverlay.classList.remove('hidden');

      const onProceed = () => { cleanup(); resolve(true); };
      const onCancel  = () => { cleanup(); resolve(false); };

      function cleanup() {
        confirmOverlay.classList.add('hidden');
        confirmProceed.removeEventListener('click', onProceed);
        confirmCancel.removeEventListener('click', onCancel);
      }

      confirmProceed.addEventListener('click', onProceed);
      confirmCancel.addEventListener('click', onCancel);
    });
  }

  // ── Alert (auth card) ─────────────────────────────────────────
  function showAlert(msg, isError = true) {
    adminAlert.textContent = msg;
    adminAlert.className = `alert ${isError ? 'alert-error' : 'alert-success'}`;
  }
  function hideAlert() { adminAlert.className = 'alert hidden'; }

  // ── Auth ──────────────────────────────────────────────────────
  const storedPass = localStorage.getItem('admin_pass');
  if (storedPass) verifyAndLoad(storedPass);

  btnLogin.addEventListener('click', () => {
    const pass = adminPassInput.value.trim();
    if (!pass) return showAlert('Please enter the admin password.');
    verifyAndLoad(pass);
  });

  adminPassInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') btnLogin.click();
  });

  btnLogout.addEventListener('click', () => {
    localStorage.removeItem('admin_pass');
    dashboard.classList.add('hidden');
    btnLogout.classList.add('hidden');
    authOverlay.classList.remove('hidden');
    adminPassInput.value = '';
    hideAlert();
  });

  btnRefresh.addEventListener('click', () => {
    const pass = localStorage.getItem('admin_pass');
    if (pass) loadSessions(pass);
  });

  if (btnVerify) {
    btnVerify.addEventListener('click', async () => {
      const pass = localStorage.getItem('admin_pass');
      if (!pass) return;
      btnVerify.disabled = true;
      btnVerify.textContent = '⏳ Checking…';
      tbody.innerHTML = `<tr><td colspan="6" class="table-empty"><span class="empty-icon">⏳</span>Verifying active sessions with Telegram...</td></tr>`;
      try {
        const res = await fetch('/api/admin/verify-sessions', {
          method: 'POST',
          headers: authHeader(pass)
        });
        const data = await res.json();
        if (res.ok) {
          toast('Session verification complete.', 'success');
          renderTable(data);
        } else {
          toast(data.detail || 'Verification failed.', 'error');
          loadSessions(pass);
        }
      } catch (err) {
        toast('Network error verifying sessions.', 'error');
        loadSessions(pass);
      } finally {
        btnVerify.disabled = false;
        btnVerify.textContent = '⚡ Sync & Check';
      }
    });
  }

  if (btnKeepalive) {
    btnKeepalive.addEventListener('click', async () => {
      const pass = localStorage.getItem('admin_pass');
      if (!pass) return;
      btnKeepalive.disabled = true;
      btnKeepalive.textContent = '⏳ Pinging…';
      try {
        const res = await fetch('/api/admin/keepalive', {
          method: 'POST',
          headers: authHeader(pass)
        });
        const data = await res.json();
        if (res.ok) {
          toast(`💓 Keep-alive ping sent to ${(data.accounts || []).length} session(s)!`, 'success');
          renderTable({ session_files: (data.accounts || []).map(a => a.session_file), accounts: data.accounts || [] });
        } else {
          toast(data.detail || 'Keep-alive failed.', 'error');
        }
      } catch (err) {
        toast('Network error during keep-alive ping.', 'error');
      } finally {
        btnKeepalive.disabled = false;
        btnKeepalive.textContent = '💓 Keep Alive';
      }
    });
  }

  async function verifyAndLoad(password) {
    btnLogin.disabled = true;
    btnLogin.textContent = 'Verifying…';
    hideAlert();
    try {
      const res  = await fetch('/api/admin/sessions', { headers: authHeader(password) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Incorrect password.');

      localStorage.setItem('admin_pass', password);
      authOverlay.classList.add('hidden');
      dashboard.classList.remove('hidden');
      btnLogout.classList.remove('hidden');
      renderTable(data);
    } catch (err) {
      localStorage.removeItem('admin_pass');
      showAlert(err.message);
    } finally {
      btnLogin.disabled    = false;
      btnLogin.textContent = 'UNLOCK PORTAL →';
    }
  }

  // ── Data loading ──────────────────────────────────────────────
  async function loadSessions(password) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty"><span class="empty-icon">⏳</span>Refreshing…</td></tr>`;
    try {
      const res  = await fetch('/api/admin/sessions', { headers: authHeader(password) });
      const data = await res.json();
      if (res.ok) renderTable(data);
      else toast(data.detail || 'Failed to load sessions.', 'error');
    } catch (err) {
      toast('Network error loading sessions.', 'error');
    }
  }

  // ── Render ────────────────────────────────────────────────────
  function renderTable(data) {
    const files    = data.session_files || [];
    const accounts = data.accounts      || [];

    // Update stats
    document.getElementById('stat-total').textContent   = files.length;
    document.getElementById('stat-active').textContent  = accounts.filter(a => a.status === 'active').length;
    document.getElementById('stat-limited').textContent = accounts.filter(a => a.status === 'limited').length;
    document.getElementById('stat-banned').textContent  = accounts.filter(a => a.status === 'banned').length;
    const statExpEl = document.getElementById('stat-expired');
    if (statExpEl) statExpEl.textContent = accounts.filter(a => a.status === 'expired').length;

    if (files.length === 0) {
      tbody.innerHTML = `
        <tr><td colspan="6" class="table-empty">
          <span class="empty-icon">📂</span>
          No .session files found on server.
        </td></tr>`;
      return;
    }

    tbody.innerHTML = files.map((stem, idx) => {
      const acc    = accounts.find(a => a.session_file === stem);
      const name   = acc ? escHtml(acc.display_name || acc.label) : 'Worker Account';
      const phone  = acc ? escHtml(acc.phone) : `+${stem}`;
      const status = acc ? acc.status : 'active';

      const statusBadge = {
        active:  '<span class="status-badge active">🟢 Active</span>',
        limited: '<span class="status-badge limited">🟡 Limited</span>',
        banned:  '<span class="status-badge banned">🔴 Banned</span>',
        expired: '<span class="status-badge expired">⚪ Expired</span>',
      }[status] || `<span class="status-badge">${status}</span>`;

      const savedPassDisplay = (acc && acc.password) ?
        `<span style="font-family:monospace; font-weight:600; background:rgba(0,0,0,0.3); padding:3px 8px; border-radius:6px; font-size:0.8rem; color:#fff;" title="Saved 2FA Password">🔑 ${escHtml(acc.password)}</span>` :
        `<span style="color:#aaa; font-size:0.78rem;">⚪ Not saved</span>`;

      return `
        <tr data-stem="${escAttr(stem)}">
          <td>${idx + 1}</td>
          <td>${name}</td>
          <td>${phone}</td>
          <td><code>${escHtml(stem)}.session</code></td>
          <td>${savedPassDisplay}</td>
          <td>${statusBadge}</td>
          <td>
            <div class="action-group">
              <button class="btn-xs success otp-btn" data-stem="${escAttr(stem)}" data-phone="${escAttr(phone)}" title="Read verification codes sent to Telegram inbox">
                🔑 OTP Code
              </button>
              <button class="btn-xs info devices-btn" data-stem="${escAttr(stem)}" data-phone="${escAttr(phone)}" title="View active devices/sessions">
                📱 Devices
              </button>
              <button class="btn-xs warning change-pass-btn" data-stem="${escAttr(stem)}" data-phone="${escAttr(phone)}" data-name="${escAttr(name)}" title="Change 2FA Password on Telegram">
                🔐 Change Pass
              </button>
              <select class="status-select status-change-select" data-stem="${escAttr(stem)}" title="Change status">
                <option value="active"  ${status === 'active'  ? 'selected' : ''}>🟢 Active</option>
                <option value="limited" ${status === 'limited' ? 'selected' : ''}>🟡 Limited</option>
                <option value="banned"  ${status === 'banned'  ? 'selected' : ''}>🔴 Banned</option>
                <option value="expired" ${status === 'expired' ? 'selected' : ''}>⚪ Expired</option>
              </select>
              <button class="btn-xs danger delete-btn" data-stem="${escAttr(stem)}" title="Delete session">
                🗑️ Delete
              </button>
            </div>
          </td>
        </tr>`;
    }).join('');

    // ── Bind OTP buttons ──
    tbody.querySelectorAll('.otp-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        openOtpModal(btn.dataset.stem, btn.dataset.phone);
      });
    });

    // ── Bind devices buttons ──
    tbody.querySelectorAll('.devices-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        openDevicesModal(btn.dataset.stem, btn.dataset.phone);
      });
    });

    // ── Bind change pass buttons ──
    tbody.querySelectorAll('.change-pass-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const stem = btn.dataset.stem;
        const phone = btn.dataset.phone;
        const name = btn.dataset.name;
        const acc = accounts.find(a => a.session_file === stem);
        openChangePassModal(acc, stem, phone, name);
      });
    });

    // ── Bind delete buttons ──
    tbody.querySelectorAll('.delete-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const stem = btn.dataset.stem;
        const confirmed = await showConfirm({
          icon:     '🗑️',
          title:    'Delete Session?',
          body:     `This will permanently delete "${stem}.session" from the server and unregister it. This cannot be undone.`,
          btnLabel: 'Yes, Delete',
          btnClass: 'confirm-proceed',
        });
        if (!confirmed) return;

        btn.disabled = true;
        btn.textContent = '…';
        try {
          const res = await fetch(`/api/admin/delete-session/${encodeURIComponent(stem)}`, {
            method:  'DELETE',
            headers: authHeader(),
          });
          const data = await res.json();
          if (res.ok) {
            toast(`Deleted ${stem}.session`, 'success');
            loadSessions(localStorage.getItem('admin_pass'));
          } else {
            toast(data.detail || 'Delete failed.', 'error');
            btn.disabled = false;
            btn.textContent = '🗑️ Delete';
          }
        } catch (err) {
          toast('Network error. Could not delete.', 'error');
          btn.disabled = false;
          btn.textContent = '🗑️ Delete';
        }
      });
    });

    // ── Bind status selects ──
    tbody.querySelectorAll('.status-change-select').forEach(sel => {
      sel.addEventListener('change', async () => {
        const stem      = sel.dataset.stem;
        const newStatus = sel.value;
        try {
          const res = await fetch(`/api/admin/set-status/${encodeURIComponent(stem)}`, {
            method:  'POST',
            headers: { ...authHeader(), 'Content-Type': 'application/json' },
            body:    JSON.stringify({ status: newStatus }),
          });
          if (res.ok) {
            toast(`Status updated to "${newStatus}" for ${stem}`, 'success');
            loadSessions(localStorage.getItem('admin_pass'));
          } else {
            const d = await res.json();
            toast(d.detail || 'Status update failed.', 'error');
          }
        } catch (err) {
          toast('Network error updating status.', 'error');
        }
      });
    });
  }

  // ── Helpers ───────────────────────────────────────────────────
  function authHeader(pass) {
    const p = pass || localStorage.getItem('admin_pass') || '';
    return { 'Authorization': `Bearer ${p}` };
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function escAttr(str) {
    return String(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
});

