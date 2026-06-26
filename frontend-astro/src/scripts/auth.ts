/*
---
name: auth
description: "Auth page handlers: login, register, forgot-password, reset-password, and first-run setup form submission with inline error/success display"
type: script
target:
  layer: frontend
  domain: auth
spec_doc: null
test_file: tests/stage2/e2e/stage2/auth.spec.ts
functions:
  - name: showFormError
    line: 55
    purpose: "Display an error alert inside a form using .auth-form-error element"
  - name: showFormSuccess
    line: 71
    purpose: "Display a success alert inside a form using .auth-form-success element"
  - name: clearFormErrors
    line: 86
    purpose: "Hide and clear all error/success alert elements inside a form"
  - name: initLoginPage
    line: 124
    purpose: "Attach submit handler to login form; calls api.login and redirects to dashboard on success"
  - name: initRegisterPage
    line: 191
    purpose: "Attach submit handler to register form; calls api.register and redirects on success"
  - name: initForgotPasswordPage
    line: 248
    purpose: "Attach submit handler to forgot-password form; calls api.forgotPassword with generic success message"
  - name: initResetPasswordPage
    line: 303
    purpose: "Attach submit handler to reset-password form; reads token from URL query string"
  - name: initSetupPage
    line: 371
    purpose: "Attach submit handler to first-run setup form; POSTs to /auth/first-run-setup"
---
*/
/* global fetch */
/**
 * auth.ts — Auth page handlers (login / register / forgot / reset / setup)
 *
 * Phase 5 will wire these into the actual Astro pages.
 * This file provides the init functions and form helpers.
 */

import { api, type LoginRequest, type RegisterRequest, type ForgotPasswordRequest, type ResetPasswordRequest } from '@/scripts/api'

// ---------------------------------------------------------------------------
// Internal types
// ---------------------------------------------------------------------------

interface FirstRunSetupRequest {
  email: string
  username: string
  password: string
  full_name?: string
}

// ---------------------------------------------------------------------------
// Form error helpers
// ---------------------------------------------------------------------------

/**
 * Show an error alert inside the given form.
 * Inserts or updates a `.auth-form-error` element at the top of the form.
 */
export function showFormError(form: HTMLFormElement, message: string): void {
  let errorEl = form.querySelector<HTMLElement>('.auth-form-error')
  if (!errorEl) {
    errorEl = document.createElement('div')
    errorEl.className = 'alert alert-danger auth-form-error d-flex align-items-center gap-2 mb-3'
    errorEl.setAttribute('role', 'alert')
    form.prepend(errorEl)
  }
  errorEl.innerHTML = `<i class="ri-error-warning-line flex-shrink-0"></i><span>${escapeText(message)}</span>`
  errorEl.removeAttribute('hidden')
}

/**
 * Show a success alert inside the given form.
 * Inserts or updates a `.auth-form-success` element at the top of the form.
 */
export function showFormSuccess(form: HTMLFormElement, message: string): void {
  let successEl = form.querySelector<HTMLElement>('.auth-form-success')
  if (!successEl) {
    successEl = document.createElement('div')
    successEl.className = 'alert alert-success auth-form-success d-flex align-items-center gap-2 mb-3'
    successEl.setAttribute('role', 'alert')
    form.prepend(successEl)
  }
  successEl.innerHTML = `<i class="ri-checkbox-circle-line flex-shrink-0"></i><span>${escapeText(message)}</span>`
  successEl.removeAttribute('hidden')
}

/**
 * Clear all `.auth-form-error` and `.auth-form-success` elements inside the form.
 */
export function clearFormErrors(form: HTMLFormElement): void {
  form.querySelectorAll<HTMLElement>('.auth-form-error, .auth-form-success').forEach((el) => {
    el.setAttribute('hidden', '')
    el.textContent = ''
  })
}

/** Escape text for safe insertion into innerHTML. */
function escapeText(str: string): string {
  const div = document.createElement('div')
  div.textContent = str
  return div.innerHTML
}

/** Set a submit button into loading state and return a restore function. */
function setSubmitLoading(form: HTMLFormElement): () => void {
  const btn = form.querySelector<HTMLButtonElement>('button[type="submit"]')
  if (!btn) return () => {}
  const originalText = btn.innerHTML
  btn.disabled = true
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Loading...'
  return () => {
    btn.disabled = false
    btn.innerHTML = originalText
  }
}

// ---------------------------------------------------------------------------
// Login page
// ---------------------------------------------------------------------------

/**
 * Attach submit handler to the login form.
 * Calls api.login(), then redirects to /dashboard on success.
 *
 * Expects a <form id="login-form"> (or first <form> on the page)
 * with inputs named "email" and "password".
 */
export function initLoginPage(): void {
  const apiBase = (import.meta as any).env?.DEV ? 'http://localhost:8088' : ''

  fetch(`${apiBase}/auth/first-run-check`, { credentials: 'include' })
    .then(res => res.json())
    .then(data => {
      if (data.needs_setup) {
        const banner = document.getElementById('first-run-banner')
        if (banner) {
          banner.removeAttribute('hidden')
          banner.classList.add('d-flex')
        }
      }
    })
    .catch(() => {})

  const form = document.querySelector<HTMLFormElement>('#login-form, form')
  if (!form) return

  form.addEventListener('submit', async (e) => {
    e.preventDefault()
    clearFormErrors(form)

    const emailInput = form.querySelector<HTMLInputElement>('[name="email"]')
    const passwordInput = form.querySelector<HTMLInputElement>('[name="password"]')

    if (!emailInput || !passwordInput) {
      showFormError(form, 'Form inputs not found.')
      return
    }

    const data: LoginRequest = {
      email: emailInput.value.trim(),
      password: passwordInput.value
    }

    if (!data.email || !data.password) {
      showFormError(form, 'Please enter your email and password.')
      return
    }

    const restoreBtn = setSubmitLoading(form)
    try {
      await api.login(data)
      const pagesPrefix = (import.meta as any).env?.DEV ? '' : '/pages'
      window.location.href = `${pagesPrefix}/dashboard`
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed. Please try again.'
      showFormError(form, message)
    } finally {
      restoreBtn()
    }
  })
}

// ---------------------------------------------------------------------------
// Register page
// ---------------------------------------------------------------------------

/**
 * Attach submit handler to the register form.
 * Calls api.register(), then redirects to /dashboard on success.
 * If public registration is disabled the backend will return 403 with detail.
 *
 * Expects inputs named "email", "username", "password",
 * and optionally "full_name".
 */
export function initRegisterPage(): void {
  const form = document.querySelector<HTMLFormElement>('#register-form, form')
  if (!form) return

  form.addEventListener('submit', async (e) => {
    e.preventDefault()
    clearFormErrors(form)

    const emailInput = form.querySelector<HTMLInputElement>('[name="email"]')
    const usernameInput = form.querySelector<HTMLInputElement>('[name="username"]')
    const passwordInput = form.querySelector<HTMLInputElement>('[name="password"]')
    const fullNameInput = form.querySelector<HTMLInputElement>('[name="full_name"]')

    if (!emailInput || !usernameInput || !passwordInput) {
      showFormError(form, 'Form inputs not found.')
      return
    }

    const data: RegisterRequest = {
      email: emailInput.value.trim(),
      username: usernameInput.value.trim(),
      password: passwordInput.value
    }
    if (fullNameInput && fullNameInput.value.trim()) {
      data.full_name = fullNameInput.value.trim()
    }

    if (!data.email || !data.username || !data.password) {
      showFormError(form, 'Please fill in all required fields.')
      return
    }

    const restoreBtn = setSubmitLoading(form)
    try {
      await api.register(data)
      const pagesPrefix = (import.meta as any).env?.DEV ? '' : '/pages'
      window.location.href = `${pagesPrefix}/dashboard`
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Registration failed. Please try again.'
      showFormError(form, message)
    } finally {
      restoreBtn()
    }
  })
}

// ---------------------------------------------------------------------------
// Forgot password page
// ---------------------------------------------------------------------------

/**
 * Attach submit handler to the forgot password form.
 * Calls api.forgotPassword() and shows a generic success message
 * (the backend always returns 200 to avoid user enumeration).
 *
 * Expects an input named "email".
 */
export function initForgotPasswordPage(): void {
  const form = document.querySelector<HTMLFormElement>('#forgot-password-form, form')
  if (!form) return

  form.addEventListener('submit', async (e) => {
    e.preventDefault()
    clearFormErrors(form)

    const emailInput = form.querySelector<HTMLInputElement>('[name="email"]')
    if (!emailInput) {
      showFormError(form, 'Form inputs not found.')
      return
    }

    const data: ForgotPasswordRequest = {
      email: emailInput.value.trim()
    }

    if (!data.email) {
      showFormError(form, 'Please enter your email address.')
      return
    }

    const restoreBtn = setSubmitLoading(form)
    try {
      await api.forgotPassword(data)
      // Always show a generic message to avoid user enumeration
      showFormSuccess(
        form,
        'If an account with that email exists, a password reset link has been sent.'
      )
      form.reset()
    } catch (err) {
      // Only surface non-401 errors (401 is handled globally in api.ts)
      const message = err instanceof Error && err.message !== 'Unauthorized'
        ? err.message
        : 'Something went wrong. Please try again.'
      showFormError(form, message)
    } finally {
      restoreBtn()
    }
  })
}

// ---------------------------------------------------------------------------
// Reset password (new-password) page
// ---------------------------------------------------------------------------

/**
 * Attach submit handler to the reset password form.
 * Reads the reset token from the URL query string (?token=...).
 * Calls api.resetPassword() and redirects to login on success.
 *
 * Expects inputs named "password" and optionally "password_confirm".
 */
export function initResetPasswordPage(): void {
  const form = document.querySelector<HTMLFormElement>('#reset-password-form, form')
  if (!form) return

  // Parse token from URL
  const params = new URLSearchParams(window.location.search)
  const token = params.get('token')

  if (!token) {
    showFormError(form, 'Invalid or missing reset token. Please request a new password reset link.')
    const submitBtn = form.querySelector<HTMLButtonElement>('button[type="submit"]')
    if (submitBtn) submitBtn.disabled = true
    return
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault()
    clearFormErrors(form)

    const passwordInput = form.querySelector<HTMLInputElement>('[name="password"]')
    const confirmInput = form.querySelector<HTMLInputElement>('[name="password_confirm"]')

    if (!passwordInput) {
      showFormError(form, 'Form inputs not found.')
      return
    }

    const password = passwordInput.value
    if (!password) {
      showFormError(form, 'Please enter a new password.')
      return
    }

    if (confirmInput && confirmInput.value !== password) {
      showFormError(form, 'Passwords do not match.')
      return
    }

    const data: ResetPasswordRequest = { token, password }

    const restoreBtn = setSubmitLoading(form)
    try {
      await api.resetPassword(data)
      // Redirect to login with a success hint
      const pagesPrefix = (import.meta as any).env?.DEV ? '' : '/pages'
      window.location.href = `${pagesPrefix}/authentication/modern/login?reset=success`
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Password reset failed. Please try again.'
      showFormError(form, message)
    } finally {
      restoreBtn()
    }
  })
}

// ---------------------------------------------------------------------------
// First-run setup page
// ---------------------------------------------------------------------------

/**
 * Attach submit handler to the first-run setup form.
 * POSTs to /auth/first-run-setup to create the initial admin user.
 * On 403/409 (users already exist), shows a "setup already completed" message.
 * On success, redirects to login with a success query param.
 *
 * Expects inputs named "email", "username", "password", "confirm_password",
 * and optionally "full_name".
 */
export function initSetupPage(): void {
  const API_BASE = (import.meta as { env: { DEV: boolean } }).env.DEV ? 'http://localhost:8088' : ''

  const form = document.querySelector<HTMLFormElement>('#setup-form, form')
  const setupDoneAlert = document.getElementById('setup-done-alert')

  if (!form) return

  form.addEventListener('submit', async (e) => {
    e.preventDefault()
    clearFormErrors(form)

    const emailInput = form.querySelector<HTMLInputElement>('[name="email"]')
    const usernameInput = form.querySelector<HTMLInputElement>('[name="username"]')
    const passwordInput = form.querySelector<HTMLInputElement>('[name="password"]')
    const confirmInput = form.querySelector<HTMLInputElement>('[name="confirm_password"]')
    const fullNameInput = form.querySelector<HTMLInputElement>('[name="full_name"]')

    if (!emailInput || !usernameInput || !passwordInput) {
      showFormError(form, 'Form inputs not found.')
      return
    }

    const email = emailInput.value.trim()
    const username = usernameInput.value.trim()
    const password = passwordInput.value
    const full_name = fullNameInput?.value.trim() || undefined

    if (!email || !username || !password) {
      showFormError(form, 'Please fill in all required fields.')
      return
    }

    if (password.length < 8 || password.length > 20) {
      showFormError(form, 'Password must be between 8 and 20 characters.')
      return
    }

    if (confirmInput && confirmInput.value !== password) {
      showFormError(form, 'Passwords do not match.')
      return
    }

    const payload: FirstRunSetupRequest = { email, username, password }
    if (full_name) payload.full_name = full_name

    const restoreBtn = setSubmitLoading(form)
    try {
      const res = await fetch(`${API_BASE}/auth/first-run-setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      })

      if (res.status === 403 || res.status === 409) {
        // Users already exist — setup already done
        form.style.display = 'none'
        if (setupDoneAlert) {
          setupDoneAlert.removeAttribute('hidden')
          setupDoneAlert.classList.add('d-flex')
        }
        return
      }

      if (!res.ok) {
        let detail: string
        try {
          const body = await res.json()
          detail = body.detail || `HTTP ${res.status}`
        } catch {
          detail = `HTTP ${res.status}`
        }
        showFormError(form, detail)
        return
      }

      // Success — redirect to login with setup success hint
      const pagesPrefix = (import.meta as any).env?.DEV ? '' : '/pages'
      window.location.href = `${pagesPrefix}/authentication/modern/login?setup=success`
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Setup failed. Please try again.'
      showFormError(form, message)
    } finally {
      restoreBtn()
    }
  })
}
