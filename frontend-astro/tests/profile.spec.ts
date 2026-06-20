/**
 * Frontend profile / security Playwright tests — Phase 6/8 stubs.
 *
 * Covers: email pending verification state, username unique/reserved-name
 * errors, password change session behavior, avatar upload/delete, and
 * Gravatar opt-in UI.
 *
 * All tests are marked as skipped until A4 frontend wiring lands in Phase 6.
 * Run: npx playwright test tests/profile.spec.ts
 */
import { test } from '@playwright/test'

// ---------------------------------------------------------------------------
// Email change — pending verification state
// ---------------------------------------------------------------------------

test.skip('email change shows pending verification banner', async () => {
  /**
   * After submitting a new email on the profile page, the UI should display
   * a "pending verification" notice showing the new email address.
   * The existing email must remain displayed as the active address.
   */
})

test.skip('pending email is cleared once verification link is used', async () => {
  /**
   * After clicking the email verification link (simulated via API or
   * dev outbox), the pending verification banner disappears and the
   * profile shows the new email as the active address.
   *
   * Phase 8: may require intercepting the dev outbox or calling the
   * verify-email endpoint directly.
   */
})

// ---------------------------------------------------------------------------
// Username validation UI
// ---------------------------------------------------------------------------

test.skip('username field rejects uppercase characters', async () => {
  /**
   * Typing an uppercase letter in the username field (or submitting a
   * username with uppercase chars) should show a validation error message.
   */
})

test.skip('username field rejects digits and special chars', async () => {
  /**
   * A username containing digits (e.g. "user123") or special characters
   * should be rejected by the UI or API with a clear error message.
   */
})

test.skip('username field rejects reserved names', async () => {
  /**
   * Submitting a reserved name (e.g. "admin", "api", "rss") should show
   * a "reserved username" error message.
   */
})

test.skip('duplicate username shows conflict error', async () => {
  /**
   * Submitting a username that is already taken by another user should
   * show a "username already taken" error message.
   */
})

// ---------------------------------------------------------------------------
// Password change — session behavior
// ---------------------------------------------------------------------------

test.skip('password change with wrong current password shows error', async () => {
  /**
   * On the Security page, submitting the password form with an incorrect
   * current_password should display an error without changing the password.
   */
})

test.skip('password change success shows session revocation notice', async () => {
  /**
   * After a successful password change, the UI should inform the user that
   * other active sessions have been revoked.
   */
})

// ---------------------------------------------------------------------------
// Avatar upload
// ---------------------------------------------------------------------------

test.skip('avatar upload accepts jpeg file', async () => {
  /**
   * Uploading a valid JPEG file via the avatar section should succeed
   * and display a preview of the uploaded image.
   */
})

test.skip('avatar upload rejects svg file', async () => {
  /**
   * Attempting to upload an SVG file should show a "file type not allowed"
   * error message; the avatar must not be updated.
   */
})

test.skip('avatar upload rejects oversized file', async () => {
  /**
   * Attempting to upload a file exceeding the maximum allowed size should
   * show a "file too large" error message.
   */
})

test.skip('avatar delete restores default state', async () => {
  /**
   * After deleting an existing avatar, the UI should revert to the default
   * placeholder (no avatar / initials fallback).
   */
})

// ---------------------------------------------------------------------------
// Gravatar opt-in
// ---------------------------------------------------------------------------

test.skip('gravatar is off by default', async () => {
  /**
   * The Gravatar option in the profile avatar section should be unchecked
   * or disabled by default for a new user.
   */
})

test.skip('gravatar optin enables gravatar avatar source', async () => {
  /**
   * Enabling the Gravatar opt-in toggle and saving should switch the
   * avatar_source to 'gravatar'; the profile must not expose the email hash
   * in the API response or DOM.
   */
})
