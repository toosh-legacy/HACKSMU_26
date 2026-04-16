/**
 * Demo auth: localStorage accounts. Replace with a real API in production.
 */
const ACCOUNTS_KEY = 'tribal_accounts_demo';
const SESSION_KEY = 'tribal_session';

function readAccounts() {
  try {
    const raw = localStorage.getItem(ACCOUNTS_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeAccounts(list) {
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(list));
}

function setFormError(form, message) {
  let el = form.querySelector('.auth-form-error');
  if (!el) {
    el = document.createElement('p');
    el.className = 'auth-form-error';
    el.setAttribute('role', 'alert');
    form.prepend(el);
  }
  el.textContent = message || '';
  el.hidden = !message;
}

function initLogin() {
  const form = document.getElementById('login-form');
  if (!form) return;

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const email = String(form.email.value || '').trim().toLowerCase();
    const password = String(form.password.value || '');

    if (!email || !password) {
      setFormError(form, 'Enter your email and password.');
      return;
    }
    if (password.length < 8) {
      setFormError(form, 'Password must be at least 8 characters.');
      return;
    }

    const accounts = readAccounts();
    const user = accounts.find((a) => a.email === email);
    if (!user || user.password !== password) {
      setFormError(form, 'Invalid email or password.');
      return;
    }

    setFormError(form, '');
    sessionStorage.setItem(
      SESSION_KEY,
      JSON.stringify({ email: user.email, name: user.name || '' })
    );
    window.location.href = '/';
  });
}

function initSignup() {
  const form = document.getElementById('signup-form');
  if (!form) return;

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const name = String(form.name.value || '').trim();
    const email = String(form.email.value || '').trim().toLowerCase();
    const password = String(form.password.value || '');
    const confirm = String(form.confirm.value || '');

    if (!email) {
      setFormError(form, 'Enter a valid email address.');
      return;
    }
    if (password.length < 8) {
      setFormError(form, 'Password must be at least 8 characters.');
      return;
    }
    if (password !== confirm) {
      setFormError(form, 'Passwords do not match.');
      return;
    }

    const accounts = readAccounts();
    if (accounts.some((a) => a.email === email)) {
      setFormError(form, 'An account with this email already exists.');
      return;
    }

    accounts.push({ email, password, name });
    writeAccounts(accounts);
    setFormError(form, '');
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ email, name }));
    window.location.href = '/';
  });
}

const page = document.body?.dataset?.authPage;
if (page === 'login') initLogin();
else if (page === 'signup') initSignup();
