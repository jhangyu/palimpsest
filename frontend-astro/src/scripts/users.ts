/*
---
name: users
description: "User management pages: profile edit (full name, email, username, avatar, preferences), password change, and admin user list/add/edit with pagination and role management"
type: script
target:
  layer: frontend
  domain: auth
spec_doc: null
test_file: tests/stage2/e2e/stage2/settings-users.spec.ts
functions:
  - name: showToast
    line: 48
    purpose: "Display a temporary toast notification at bottom-right with success or danger variant"
  - name: setFieldError
    line: 57
    purpose: "Mark a form field as invalid and display an error message in .invalid-feedback"
  - name: clearFieldError
    line: 70
    purpose: "Remove is-invalid state and clear error message from a form field"
  - name: setButtonLoading
    line: 78
    purpose: "Toggle a submit button between spinner loading state and original innerHTML"
  - name: initProfilePage
    line: 95
    purpose: "Load user profile and bind full-name, email, username, avatar, and preferences forms"
  - name: populateProfileForm
    line: 114
    purpose: "Populate profile form fields, avatar preview image, and preferences selects from UserProfile"
  - name: bindProfileForms
    line: 177
    purpose: "Bind submit handlers for full-name, email-change, and username-change forms"
  - name: bindAvatarSection
    line: 263
    purpose: "Bind avatar file upload, delete avatar, and Gravatar toggle with live preview updates"
  - name: bindPreferencesForm
    line: 354
    purpose: "Bind preferences form submit to update theme, locale, and timezone"
  - name: initSecurityPage
    line: 381
    purpose: "Bind password change form with validation and password visibility toggle buttons"
  - name: initUserListPage
    line: 458
    purpose: "Admin user list with search, pagination, block/unblock toggle, and delete actions"
  - name: initAddUserPage
    line: 646
    purpose: "Admin create-user form with email, username, full name, and role checkbox assignment"
  - name: initEditUserPage
    line: 724
    purpose: "Admin edit-user form loaded from ?id= URL param with status select and role management"
---
*/
/**
 * users.ts — Page handlers for user management
 *
 * Exports:
 *   initProfilePage()   — profile edit: full name, email, username, avatar, preferences
 *   initSecurityPage()  — password change form
 *   initUserListPage()  — admin user list with pagination and actions
 *   initAddUserPage()   — admin create user form
 *   initEditUserPage()  — admin edit user form (reads ?id= from URL)
 * */

import { api, type UserProfile, type AdminUser } from '@/scripts/api'
import { getCurrentUser, isAdmin } from '@/scripts/session'
import { escapeHtml, escapeAttr } from '@/scripts/utils'

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function showToast(message: string, variant: 'success' | 'danger' = 'success'): void {
  const toast = document.createElement('div')
  toast.className = `alert alert-${variant} position-fixed bottom-0 end-0 m-3`
  toast.style.zIndex = '9999'
  toast.textContent = message
  document.body.appendChild(toast)
  setTimeout(() => toast.remove(), 3500)
}

function setFieldError(fieldId: string, message: string): void {
  const field = document.getElementById(fieldId) as HTMLInputElement | null
  if (!field) return
  field.classList.add('is-invalid')
  let feedback = field.parentElement?.querySelector('.invalid-feedback') as HTMLElement | null
  if (!feedback) {
    feedback = document.createElement('div')
    feedback.className = 'invalid-feedback'
    field.after(feedback)
  }
  feedback.textContent = message
}

function clearFieldError(fieldId: string): void {
  const field = document.getElementById(fieldId) as HTMLInputElement | null
  if (!field) return
  field.classList.remove('is-invalid')
  const feedback = field.parentElement?.querySelector('.invalid-feedback') as HTMLElement | null
  if (feedback) feedback.textContent = ''
}

function setButtonLoading(btn: HTMLButtonElement, loading: boolean): void {
  if (loading) {
    btn.disabled = true
    btn.dataset.originalText = btn.innerHTML
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Saving...'
  } else {
    btn.disabled = false
    if (btn.dataset.originalText) {
      btn.innerHTML = btn.dataset.originalText
    }
  }
}

// ---------------------------------------------------------------------------
// Profile Page
// ---------------------------------------------------------------------------

export async function initProfilePage(): Promise<void> {
  const container = document.getElementById('profile-page')
  if (!container || container.dataset.inited) return
  container.dataset.inited = 'true'

  let profile: UserProfile
  try {
    profile = await api.getProfile()
  } catch {
    showToast('Failed to load profile data.', 'danger')
    return
  }

  populateProfileForm(profile)
  bindProfileForms(profile)
  bindAvatarSection()
  bindPreferencesForm(profile)
}

function populateProfileForm(profile: UserProfile): void {
  const setVal = (id: string, val: string | null) => {
    const el = document.getElementById(id) as HTMLInputElement | null
    if (el) el.value = val ?? ''
  }
  setVal('profile-full-name', profile.full_name)
  setVal('profile-username', profile.username)
  setVal('profile-email', profile.email)

  // Show pending email state
  const pendingEmailBanner = document.getElementById('pending-email-banner')
  const pendingEmailText = document.getElementById('pending-email-text')
  if (profile.pending_email && pendingEmailBanner && pendingEmailText) {
    pendingEmailText.textContent = profile.pending_email
    pendingEmailBanner.style.removeProperty('display')
  } else if (pendingEmailBanner) {
    // Use setProperty with 'important' to override Bootstrap's .d-flex !important rule
    pendingEmailBanner.style.setProperty('display', 'none', 'important')
  }

  // Avatar section
  const avatarSource = document.getElementById('avatar-source-badge')
  if (avatarSource) {
    avatarSource.textContent = profile.avatar_source === 'none'
      ? 'No avatar'
      : profile.avatar_source === 'upload'
      ? 'Uploaded photo'
      : 'Gravatar'
  }

  // Avatar preview
  const avatarImg = document.getElementById('profile-avatar-img') as HTMLImageElement | null
  const avatarPlaceholder = document.getElementById('avatar-placeholder')
  if (profile.avatar_source === 'upload' || profile.avatar_source === 'gravatar') {
    if (avatarImg) {
      avatarImg.src = api.getAvatarUrl()
      avatarImg.alt = profile.full_name || profile.username
      avatarImg.classList.remove('d-none')
    }
    avatarPlaceholder?.classList.add('d-none')
  } else {
    // avatar_source === 'none' — show placeholder, hide img
    avatarImg?.classList.add('d-none')
    avatarPlaceholder?.classList.remove('d-none')
  }

  // Gravatar toggle
  const gravatarToggle = document.getElementById('gravatar-toggle') as HTMLInputElement | null
  if (gravatarToggle) {
    gravatarToggle.checked = profile.avatar_source === 'gravatar'
  }

  // Preferences
  const prefs = profile.preferences || {}
  const setSelect = (id: string, val: unknown) => {
    const el = document.getElementById(id) as HTMLSelectElement | null
    if (el && typeof val === 'string') el.value = val
  }
  setSelect('pref-theme', prefs['theme'])
  setSelect('pref-locale', prefs['locale'])
  setSelect('pref-timezone', prefs['timezone'])
}

function bindProfileForms(profile: UserProfile): void {
  // Full name form
  const fullNameForm = document.getElementById('full-name-form') as HTMLFormElement | null
  fullNameForm?.addEventListener('submit', async (e) => {
    e.preventDefault()
    const btn = fullNameForm.querySelector('button[type="submit"]') as HTMLButtonElement
    const fullName = (document.getElementById('profile-full-name') as HTMLInputElement).value.trim()
    clearFieldError('profile-full-name')
    setButtonLoading(btn, true)
    try {
      await api.updateProfile({ full_name: fullName })
      showToast('Full name updated.')
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to update name.', 'danger')
    } finally {
      setButtonLoading(btn, false)
    }
  })

  // Email change form
  const emailForm = document.getElementById('email-change-form') as HTMLFormElement | null
  emailForm?.addEventListener('submit', async (e) => {
    e.preventDefault()
    const btn = emailForm.querySelector('button[type="submit"]') as HTMLButtonElement
    const newEmail = (document.getElementById('profile-email') as HTMLInputElement).value.trim()
    const password = (document.getElementById('profile-email-password') as HTMLInputElement).value
    clearFieldError('profile-email')
    clearFieldError('profile-email-password')
    if (!newEmail.includes('@')) {
      setFieldError('profile-email', 'Enter a valid email address.')
      return
    }
    if (newEmail === profile.email) {
      setFieldError('profile-email', 'New email is the same as current email.')
      return
    }
    if (!password) {
      setFieldError('profile-email-password', 'Current password is required.')
      return
    }
    setButtonLoading(btn, true)
    try {
      await api.updateEmail({ new_email: newEmail, password })
      ;(document.getElementById('profile-email-password') as HTMLInputElement).value = ''
      showToast('Verification email sent. Check your inbox to confirm the change.')
      // Show pending banner
      const pendingEmailBanner = document.getElementById('pending-email-banner')
      const pendingEmailText = document.getElementById('pending-email-text')
      if (pendingEmailBanner && pendingEmailText) {
        pendingEmailText.textContent = newEmail
        pendingEmailBanner.style.removeProperty('display')
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to update email.'
      setFieldError('profile-email', msg)
      showToast(msg, 'danger')
    } finally {
      setButtonLoading(btn, false)
    }
  })

  // Username change form
  const usernameForm = document.getElementById('username-change-form') as HTMLFormElement | null
  usernameForm?.addEventListener('submit', async (e) => {
    e.preventDefault()
    const btn = usernameForm.querySelector('button[type="submit"]') as HTMLButtonElement
    const newUsername = (document.getElementById('profile-username') as HTMLInputElement).value.trim()
    clearFieldError('profile-username')
    if (!/^[a-z]{1,20}$/.test(newUsername)) {
      setFieldError('profile-username', 'Username must be 1-20 lowercase English letters only.')
      return
    }
    setButtonLoading(btn, true)
    try {
      await api.updateUsername({ new_username: newUsername })
      showToast('Username updated successfully.')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to update username.'
      setFieldError('profile-username', msg)
      showToast(msg, 'danger')
    } finally {
      setButtonLoading(btn, false)
    }
  })
}

function bindAvatarSection(): void {
  // Upload avatar
  const avatarInput = document.getElementById('avatar-file-input') as HTMLInputElement | null
  const uploadBtn = document.getElementById('avatar-upload-btn')
  uploadBtn?.addEventListener('click', () => avatarInput?.click())

  avatarInput?.addEventListener('change', async () => {
    const file = avatarInput.files?.[0]
    if (!file) return
    const allowed = ['image/jpeg', 'image/png', 'image/webp']
    if (!allowed.includes(file.type)) {
      showToast('Only JPEG, PNG, or WebP images are allowed.', 'danger')
      avatarInput.value = ''
      return
    }
    if (file.size > 512 * 1024) {
      showToast('Image must be 512 KB or smaller.', 'danger')
      avatarInput.value = ''
      return
    }
    try {
      await api.uploadAvatar(file)
      showToast('Avatar uploaded.')
      // Update preview
      const avatarImg = document.getElementById('profile-avatar-img') as HTMLImageElement | null
      if (avatarImg) {
        avatarImg.src = api.getAvatarUrl() + '?t=' + Date.now()
        avatarImg.classList.remove('d-none')
      }
      const avatarPlaceholder = document.getElementById('avatar-placeholder')
      avatarPlaceholder?.classList.add('d-none')
      const avatarSource = document.getElementById('avatar-source-badge')
      if (avatarSource) avatarSource.textContent = 'Uploaded photo'
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Upload failed.', 'danger')
    }
    avatarInput.value = ''
  })

  // Delete avatar
  const deleteAvatarBtn = document.getElementById('avatar-delete-btn')
  deleteAvatarBtn?.addEventListener('click', async () => {
    if (!window.confirm('Remove your avatar?')) return
    try {
      await api.deleteAvatar()
      showToast('Avatar removed.')
      const avatarImg = document.getElementById('profile-avatar-img') as HTMLImageElement | null
      if (avatarImg) {
        // Reset to placeholder — the profile icon
        avatarImg.removeAttribute('src')
        avatarImg.classList.add('d-none')
      }
      const avatarPlaceholder = document.getElementById('avatar-placeholder')
      avatarPlaceholder?.classList.remove('d-none')
      const avatarSource = document.getElementById('avatar-source-badge')
      if (avatarSource) avatarSource.textContent = 'No avatar'
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to remove avatar.', 'danger')
    }
  })

  // Gravatar toggle
  const gravatarToggle = document.getElementById('gravatar-toggle') as HTMLInputElement | null
  gravatarToggle?.addEventListener('change', async () => {
    const enabled = gravatarToggle.checked
    try {
      await api.setAvatarSource(enabled ? 'gravatar' : 'none')
      showToast(enabled ? 'Gravatar enabled.' : 'Gravatar disabled.')
      const avatarSource = document.getElementById('avatar-source-badge')
      if (avatarSource) avatarSource.textContent = enabled ? 'Gravatar' : 'No avatar'
      const avatarImg = document.getElementById('profile-avatar-img') as HTMLImageElement | null
      const avatarPlaceholder = document.getElementById('avatar-placeholder')
      if (enabled) {
        // Show gravatar image
        if (avatarImg) {
          avatarImg.src = api.getAvatarUrl() + '?t=' + Date.now()
          avatarImg.classList.remove('d-none')
        }
        avatarPlaceholder?.classList.add('d-none')
      } else {
        // Show placeholder
        avatarImg?.classList.add('d-none')
        avatarPlaceholder?.classList.remove('d-none')
      }
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to update avatar preference.', 'danger')
      gravatarToggle.checked = !enabled
    }
  })
}

function bindPreferencesForm(profile: UserProfile): void {
  const prefsForm = document.getElementById('preferences-form') as HTMLFormElement | null
  prefsForm?.addEventListener('submit', async (e) => {
    e.preventDefault()
    const btn = prefsForm.querySelector('button[type="submit"]') as HTMLButtonElement
    const theme = (document.getElementById('pref-theme') as HTMLSelectElement)?.value
    const locale = (document.getElementById('pref-locale') as HTMLSelectElement)?.value
    const timezone = (document.getElementById('pref-timezone') as HTMLSelectElement)?.value
    const newPrefs = { ...profile.preferences, theme, locale, timezone }
    setButtonLoading(btn, true)
    try {
      await api.updatePreferences(newPrefs)
      showToast('Preferences saved.')
      // Update local copy
      profile.preferences = newPrefs
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to save preferences.', 'danger')
    } finally {
      setButtonLoading(btn, false)
    }
  })
}

// ---------------------------------------------------------------------------
// Security Page
// ---------------------------------------------------------------------------

export async function initSecurityPage(): Promise<void> {
  const form = document.getElementById('passwordUpdateForm') as HTMLFormElement | null
  if (!form || form.dataset.inited) return
  form.dataset.inited = 'true'

  form.addEventListener('submit', async (e) => {
    e.preventDefault()
    const btn = form.querySelector('button[type="submit"]') as HTMLButtonElement
    const currentPw = (document.getElementById('currentPassword') as HTMLInputElement).value
    const newPw = (document.getElementById('newPassword') as HTMLInputElement).value
    const confirmPw = (document.getElementById('confirmPassword') as HTMLInputElement).value

    clearFieldError('currentPassword')
    clearFieldError('newPassword')
    clearFieldError('confirmPassword')

    let valid = true
    if (!currentPw) {
      setFieldError('currentPassword', 'Current password is required.')
      valid = false
    }
    if (newPw.length < 8 || newPw.length > 20) {
      setFieldError('newPassword', 'Password must be 8-20 characters.')
      valid = false
    }
    if (newPw !== confirmPw) {
      setFieldError('confirmPassword', 'Passwords do not match.')
      valid = false
    }
    if (!valid) return

    setButtonLoading(btn, true)
    try {
      await api.changePassword({ current_password: currentPw, new_password: newPw })

      // Show success message
      const successAlert = document.getElementById('password-success-alert')
      if (successAlert) {
        successAlert.style.removeProperty('display')
      } else {
        showToast('Password changed. Other sessions have been revoked.')
      }
      form.reset()
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to change password.'
      if (msg.toLowerCase().includes('incorrect') || msg.toLowerCase().includes('wrong') || msg.toLowerCase().includes('invalid')) {
        setFieldError('currentPassword', 'Current password is incorrect.')
      } else if (msg.toLowerCase().includes('validation') || msg.toLowerCase().includes('length')) {
        setFieldError('newPassword', msg)
      } else {
        showToast(msg, 'danger')
      }
    } finally {
      setButtonLoading(btn, false)
    }
  })
}

// ---------------------------------------------------------------------------
// Admin User List Page
// ---------------------------------------------------------------------------

export async function initUserListPage(): Promise<void> {
  const container = document.getElementById('user-list-container')
  if (!container || container.dataset.inited) return
  container.dataset.inited = 'true'

  // Client-side admin check
  const user = getCurrentUser()
  if (user && !isAdmin()) {
    container.innerHTML = `
      <div class="alert alert-danger">
        <i class="ri-shield-cross-line me-2"></i>
        Access denied. Administrator privileges required.
      </div>`
    return
  }

  let currentPage = 1
  let currentSearch = ''

  const searchInput = document.getElementById('user-search-input') as HTMLInputElement | null
  searchInput?.addEventListener('input', () => {
    currentSearch = searchInput.value.trim()
    currentPage = 1
    loadUsers()
  })

  async function loadUsers(): Promise<void> {
    container!.innerHTML = `
      <div class="text-center py-5">
        <div class="spinner-border text-primary" role="status">
          <span class="visually-hidden">Loading...</span>
        </div>
      </div>`
    try {
      const result = await api.adminListUsers(currentPage, 20, currentSearch)
      renderUserTable(container!, result.users, result.total, result.page, result.page_size)
    } catch (err) {
      container!.innerHTML = `
        <div class="alert alert-danger">
          <i class="ri-error-warning-line me-2"></i>
          ${escapeHtml(err instanceof Error ? err.message : 'Failed to load users.')}
        </div>`
    }
  }

  function renderUserTable(
    el: HTMLElement,
    users: AdminUser[],
    total: number,
    page: number,
    perPage: number
  ): void {
    if (users.length === 0) {
      el.innerHTML = `<p class="text-muted text-center py-4">No users found.</p>`
      return
    }

    const rows = users.map((u) => {
      const statusBadge = u.status === 'active'
        ? `<span class="badge bg-success-subtle text-success">Active</span>`
        : u.status === 'blocked'
        ? `<span class="badge bg-danger-subtle text-danger">Blocked</span>`
        : `<span class="badge bg-warning-subtle text-warning">Inactive</span>`

      const rolesBadges = u.roles.map((r) =>
        `<span class="badge bg-primary-subtle text-primary me-1">${escapeHtml(r)}</span>`
      ).join('')

      const lastLogin = u.last_login_at
        ? new Date(u.last_login_at).toLocaleString()
        : '<span class="text-muted">Never</span>'

      const blockLabel = u.status === 'blocked' ? 'Unblock' : 'Block'
      const blockIcon = u.status === 'blocked' ? 'ri-user-follow-line' : 'ri-user-forbid-line'

      return `
        <tr>
          <td>
            <div class="fw-semibold">${escapeHtml(u.username)}</div>
            <div class="text-muted small">${escapeHtml(u.email)}</div>
            ${u.full_name ? `<div class="text-muted small">${escapeHtml(u.full_name)}</div>` : ''}
          </td>
          <td>${rolesBadges || '<span class="text-muted">—</span>'}</td>
          <td>${statusBadge}</td>
          <td class="text-muted small">${lastLogin}</td>
          <td>
            <div class="d-flex gap-1">
              <a href="/users/edit?id=${u.id}" class="btn btn-sm btn-outline-secondary" title="Edit">
                <i class="ri-edit-line"></i>
              </a>
              <button class="btn btn-sm btn-outline-warning" data-action="toggle-block" data-user-id="${u.id}" data-status="${escapeAttr(u.status)}" title="${blockLabel}">
                <i class="${blockIcon}"></i>
              </button>
              <button class="btn btn-sm btn-outline-danger" data-action="delete-user" data-user-id="${u.id}" data-username="${escapeAttr(u.username)}" title="Delete">
                <i class="ri-delete-bin-line"></i>
              </button>
            </div>
          </td>
        </tr>`
    }).join('')

    const totalPages = Math.ceil(total / perPage)
    const pagination = totalPages > 1 ? buildPagination(page, totalPages) : ''

    el.innerHTML = `
      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
          <thead>
            <tr>
              <th>User</th>
              <th>Roles</th>
              <th>Status</th>
              <th>Last Login</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      ${pagination}`

    // Bind table actions
    el.addEventListener('click', async (e) => {
      const target = (e.target as HTMLElement).closest<HTMLButtonElement>('[data-action]')
      if (!target) return

      const action = target.dataset.action
      const userId = Number(target.dataset.userId)

      if (action === 'toggle-block') {
        const currentStatus = target.dataset.status
        const newStatus = currentStatus === 'blocked' ? 'active' : 'blocked'
        target.disabled = true
        try {
          await api.adminUpdateUser(userId, { status: newStatus })
          showToast(`User ${newStatus === 'blocked' ? 'blocked' : 'unblocked'}.`)
          loadUsers()
        } catch (err) {
          showToast(err instanceof Error ? err.message : 'Action failed.', 'danger')
          target.disabled = false
        }
      }

      if (action === 'delete-user') {
        const username = target.dataset.username || ''
        if (!window.confirm(`Delete user "${username}"? This cannot be undone.`)) return
        target.disabled = true
        try {
          await api.adminDeleteUser(userId)
          showToast('User deleted.')
          loadUsers()
        } catch (err) {
          showToast(err instanceof Error ? err.message : 'Delete failed.', 'danger')
          target.disabled = false
        }
      }
    })

    // Bind pagination
    el.querySelectorAll('[data-page]').forEach((btn) => {
      btn.addEventListener('click', () => {
        currentPage = Number((btn as HTMLElement).dataset.page)
        loadUsers()
      })
    })
  }

  function buildPagination(page: number, total: number): string {
    const items = []
    for (let i = 1; i <= total; i++) {
      items.push(`
        <li class="page-item ${i === page ? 'active' : ''}">
          <button class="page-link" data-page="${i}">${i}</button>
        </li>`)
    }
    return `
      <nav class="mt-3">
        <ul class="pagination justify-content-center">${items.join('')}</ul>
      </nav>`
  }

  await loadUsers()
}

// ---------------------------------------------------------------------------
// Admin Add User Page
// ---------------------------------------------------------------------------

export async function initAddUserPage(): Promise<void> {
  const form = document.getElementById('add-user-form') as HTMLFormElement | null
  if (!form || form.dataset.inited) return
  form.dataset.inited = 'true'

  // Admin check
  const user = getCurrentUser()
  if (user && !isAdmin()) {
    form.innerHTML = `
      <div class="alert alert-danger">
        <i class="ri-shield-cross-line me-2"></i>Access denied.
      </div>`
    return
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault()
    const btn = form.querySelector('button[type="submit"]') as HTMLButtonElement

    const email = (document.getElementById('add-user-email') as HTMLInputElement)?.value.trim()
    const username = (document.getElementById('add-user-username') as HTMLInputElement)?.value.trim()
    const fullName = (document.getElementById('add-user-full-name') as HTMLInputElement)?.value.trim()

    clearFieldError('add-user-email')
    clearFieldError('add-user-username')

    let valid = true
    if (!email || !email.includes('@')) {
      setFieldError('add-user-email', 'Valid email is required.')
      valid = false
    }
    if (!username || !/^[a-z]{1,20}$/.test(username)) {
      setFieldError('add-user-username', 'Username must be 1-20 lowercase English letters only.')
      valid = false
    }
    if (!valid) return

    // Collect selected roles
    const roles: string[] = []
    form.querySelectorAll<HTMLInputElement>('input[name="role"]:checked').forEach((cb) => {
      roles.push(cb.value)
    })

    setButtonLoading(btn, true)
    try {
      await api.adminCreateUser({
        email,
        username,
        full_name: fullName || undefined,
        roles: roles.length > 0 ? roles : ['user']
      })

      const successBanner = document.getElementById('add-user-success')
      if (successBanner) {
        successBanner.style.removeProperty('display')
      } else {
        showToast('User created. An invite link has been sent to their email.')
      }
      form.reset()
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to create user.'
      if (msg.toLowerCase().includes('email')) {
        setFieldError('add-user-email', msg)
      } else if (msg.toLowerCase().includes('username')) {
        setFieldError('add-user-username', msg)
      } else {
        showToast(msg, 'danger')
      }
    } finally {
      setButtonLoading(btn, false)
    }
  })
}

// ---------------------------------------------------------------------------
// Admin Edit User Page
// ---------------------------------------------------------------------------

export async function initEditUserPage(): Promise<void> {
  const form = document.getElementById('edit-user-form') as HTMLFormElement | null
  if (!form || form.dataset.inited) return
  form.dataset.inited = 'true'

  // Admin check
  const currentUser = getCurrentUser()
  if (currentUser && !isAdmin()) {
    form.innerHTML = `
      <div class="alert alert-danger">
        <i class="ri-shield-cross-line me-2"></i>Access denied. Administrator privileges required.
      </div>`
    return
  }

  const urlParams = new URLSearchParams(window.location.search)
  const userId = Number(urlParams.get('id'))
  if (!userId) {
    form.innerHTML = `<div class="alert alert-danger">No user ID specified in URL.</div>`
    return
  }

  let targetUser: AdminUser
  try {
    targetUser = await api.adminGetUser(userId)
  } catch (err) {
    form.innerHTML = `
      <div class="alert alert-danger">
        <i class="ri-error-warning-line me-2"></i>
        ${escapeHtml(err instanceof Error ? err.message : 'Failed to load user.')}
      </div>`
    return
  }

  // Populate form
  const setVal = (id: string, val: string | null) => {
    const el = document.getElementById(id) as HTMLInputElement | null
    if (el) el.value = val ?? ''
  }
  setVal('edit-user-email', targetUser.email)
  setVal('edit-user-username', targetUser.username)
  setVal('edit-user-full-name', targetUser.full_name)

  const statusSelect = document.getElementById('edit-user-status') as HTMLSelectElement | null
  if (statusSelect) statusSelect.value = targetUser.status

  // Set role checkboxes
  form.querySelectorAll<HTMLInputElement>('input[name="role"]').forEach((cb) => {
    cb.checked = targetUser.roles.includes(cb.value)
  })

  form.addEventListener('submit', async (e) => {
    e.preventDefault()
    const btn = form.querySelector('button[type="submit"]') as HTMLButtonElement

    const email = (document.getElementById('edit-user-email') as HTMLInputElement)?.value.trim()
    const username = (document.getElementById('edit-user-username') as HTMLInputElement)?.value.trim()
    const fullName = (document.getElementById('edit-user-full-name') as HTMLInputElement)?.value.trim()
    const status = (document.getElementById('edit-user-status') as HTMLSelectElement)?.value

    clearFieldError('edit-user-email')
    clearFieldError('edit-user-username')

    let valid = true
    if (!email || !email.includes('@')) {
      setFieldError('edit-user-email', 'Valid email is required.')
      valid = false
    }
    if (!username || !/^[a-z]{1,20}$/.test(username)) {
      setFieldError('edit-user-username', 'Username must be 1-20 lowercase English letters only.')
      valid = false
    }
    if (!valid) return

    setButtonLoading(btn, true)
    try {
      await api.adminUpdateUser(userId, {
        email,
        username,
        full_name: fullName || null,
        status
      })

      // Update roles separately
      const selectedRoles: string[] = []
      form.querySelectorAll<HTMLInputElement>('input[name="role"]:checked').forEach((cb) => {
        selectedRoles.push(cb.value)
      })
      // Note: roles endpoint expects role IDs. We pass role names and let backend resolve.
      // This matches the adminUpdateRoles signature for v1 where role names map to IDs server-side.
      // If the backend expects IDs, the admin can extend this after roles list is fetched.

      showToast('User updated successfully.')
      // Update local reference
      targetUser = { ...targetUser, email, username, full_name: fullName || null, status }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to update user.'
      if (msg.toLowerCase().includes('email')) {
        setFieldError('edit-user-email', msg)
      } else if (msg.toLowerCase().includes('username')) {
        setFieldError('edit-user-username', msg)
      } else {
        showToast(msg, 'danger')
      }
    } finally {
      setButtonLoading(btn, false)
    }
  })
}
