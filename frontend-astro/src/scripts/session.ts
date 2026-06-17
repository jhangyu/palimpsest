/**
 * session.ts — Session bootstrap module
 *
 * Call initSession() once per page load (in admin-layout.astro's page script
 * or a dedicated bootstrap script).  It fetches the current user from the
 * server and caches it in memory for the lifetime of the page.
 *
 * Phase 5 will wire initSession() into the admin layout so every protected
 * page performs the auth check automatically.
 */

import { api, type AuthUser } from '@/scripts/api'

// Module-level cache — reset on each full page load
let _currentUser: AuthUser | null = null

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

/**
 * Fetch the current authenticated user from GET /auth/me.
 *
 * - On success: caches the user, calls renderCurrentUser() to update the DOM.
 * - On 401: api.ts redirects to /authentication/modern/login automatically.
 * - On other network errors: logs the error; the page continues to render
 *   without user data (safe — layout does not expose sensitive data by default).
 *
 * Returns the AuthUser on success, or null if the call failed for a
 * non-auth reason (e.g. network error during dev).
 */
export async function initSession(): Promise<AuthUser | null> {
  try {
    const user = await api.getMe()
    _currentUser = user
    renderCurrentUser(user)
    applyRoleGating(user)
    return user
  } catch (err) {
    // 401 is handled inside api.ts (redirect to login), so we only land here
    // for unexpected errors (network issues, 5xx, etc.)
    if (err instanceof Error && err.message !== 'Unauthorized') {
      console.error('[session] Failed to fetch current user:', err.message)
    }
    return null
  }
}

// ---------------------------------------------------------------------------
// Accessors
// ---------------------------------------------------------------------------

/** Return the cached AuthUser, or null if initSession() has not been called yet. */
export function getCurrentUser(): AuthUser | null {
  return _currentUser
}

/** Return true if the current user has the 'admin' role. */
export function isAdmin(): boolean {
  return _currentUser !== null && _currentUser.roles.includes('admin')
}

// ---------------------------------------------------------------------------
// DOM rendering
// ---------------------------------------------------------------------------

/**
 * Update topbar and profile offcanvas elements with the real user's data.
 *
 * Target elements (identified by data attributes so they survive template
 * refactors without changing selectors here):
 *
 *   - [data-session="user-name"]   — display name (full_name || username)
 *   - [data-session="user-email"]  — email address
 *   - [data-session="user-avatar"] — <img> src (avatar URL or initials fallback)
 *
 * These data attributes should be added to the relevant elements in
 * _topbar.astro during Phase 5.  If the elements are not found, this
 * function does nothing (safe during Batch 1 when templates are untouched).
 */
export function renderCurrentUser(user: AuthUser): void {
  const displayName = user.full_name || user.username

  // Update all name elements
  document.querySelectorAll<HTMLElement>('[data-session="user-name"]').forEach((el) => {
    el.textContent = displayName
  })

  // Update all email elements
  document.querySelectorAll<HTMLElement>('[data-session="user-email"]').forEach((el) => {
    el.textContent = user.email
  })

  // Update avatar images
  document.querySelectorAll<HTMLImageElement>('[data-session="user-avatar"]').forEach((img) => {
    img.alt = displayName
    if (user.avatar_source === 'upload' || user.avatar_source === 'gravatar') {
      img.src = api.getAvatarUrl() + '?t=' + Date.now()
    } else {
      // Generate initials avatar for 'none' source
      const initials = displayName
        .split(' ')
        .map(w => w[0])
        .join('')
        .toUpperCase()
        .slice(0, 2) || '?'
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120"><rect width="120" height="120" rx="60" fill="#6c757d"/><text x="60" y="60" text-anchor="middle" dominant-baseline="central" fill="white" font-size="40" font-family="system-ui,sans-serif">${initials}</text></svg>`
      img.src = 'data:image/svg+xml,' + encodeURIComponent(svg)
    }
  })

  // Wire logout buttons
  document.querySelectorAll<HTMLElement>('[data-session="logout-btn"]').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault()
      try {
        await api.logout()
      } catch {
        // Even if the API call fails, redirect to login
      }
      _currentUser = null
      window.location.href = '/authentication/modern/login'
    })
  })
}

// ---------------------------------------------------------------------------
// Role gating
// ---------------------------------------------------------------------------

/**
 * Show / hide nav elements based on the current user's roles.
 *
 * Elements marked with data-requires-role="admin" are hidden for non-admin
 * users.  This is a cosmetic gate only — the real security is server-side.
 *
 * Elements marked with data-nav-section="auth-demo" are always hidden for
 * authenticated users — the demo authentication pages are not part of the
 * product sidebar.
 *
 * The data attributes are added in _nav-tree.astro as part of Batch 1 prep.
 */
export function applyRoleGating(user: AuthUser): void {
  const adminRequired = document.querySelectorAll<HTMLElement>('[data-requires-role="admin"]')
  const hasAdmin = user.roles.includes('admin')

  adminRequired.forEach((el) => {
    if (!hasAdmin) {
      // Hide the element and mark as role-gated so CSS can also target it
      el.style.display = 'none'
      el.setAttribute('aria-hidden', 'true')
      el.dataset.roleGated = 'hidden'
    } else {
      el.style.removeProperty('display')
      el.removeAttribute('aria-hidden')
      el.dataset.roleGated = 'visible'
    }
  })

  // Always hide the auth demo section for authenticated users.
  // The demo auth pages are not part of the product experience.
  document.querySelectorAll<HTMLElement>('[data-nav-section="auth-demo"]').forEach((el) => {
    el.style.display = 'none'
    el.setAttribute('aria-hidden', 'true')
  })
}
