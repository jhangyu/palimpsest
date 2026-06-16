const iconMap: Record<string, string> = {
  // Navigation
  'home': 'ri-home-line',
  'dashboard': 'ri-dashboard-line',
  'menu': 'ri-menu-line',
  'arrow-left': 'ri-arrow-left-line',
  'arrow-right': 'ri-arrow-right-line',
  'arrow-up': 'ri-arrow-up-line',
  'arrow-down': 'ri-arrow-down-line',
  'chevron-left': 'ri-arrow-left-s-line',
  'chevron-right': 'ri-arrow-right-s-line',

  // Actions
  'edit': 'ri-edit-line',
  'delete': 'ri-delete-bin-line',
  'save': 'ri-save-line',
  'add': 'ri-add-line',
  'remove': 'ri-subtract-line',
  'close': 'ri-close-line',
  'search': 'ri-search-line',
  'refresh': 'ri-refresh-line',
  'copy': 'ri-file-copy-line',
  'download': 'ri-download-line',
  'upload': 'ri-upload-line',

  // Status
  'check': 'ri-check-line',
  'error': 'ri-error-warning-line',
  'warning': 'ri-alert-line',
  'info': 'ri-information-line',
  'success': 'ri-checkbox-circle-line',

  // Content
  'file': 'ri-file-line',
  'folder': 'ri-folder-line',
  'calendar': 'ri-calendar-line',
  'inbox': 'ri-inbox-line',
  'mail': 'ri-mail-line',
  'settings': 'ri-settings-line',
  'user': 'ri-user-line',
  'users': 'ri-group-line',
  'notification': 'ri-notification-line',
  'bell': 'ri-bell-line',

  // Media
  'image': 'ri-image-line',
  'video': 'ri-video-line',
  'music': 'ri-music-line',
  'camera': 'ri-camera-line',

  // Social
  'share': 'ri-share-line',
  'heart': 'ri-heart-line',
  'star': 'ri-star-line',
  'bookmark': 'ri-bookmark-line',

  // Charts
  'bar-chart': 'ri-bar-chart-line',
  'line-chart': 'ri-line-chart-line',
  'pie-chart': 'ri-pie-chart-line',

  // System
  'lock': 'ri-lock-line',
  'unlock': 'ri-lock-unlock-line',
  'key': 'ri-key-line',
  'shield': 'ri-shield-line',
  'server': 'ri-server-line',
  'database': 'ri-database-line',
  'cloud': 'ri-cloud-line'
}

export function mapIcon(name: string): string {
  return iconMap[name] || `ri-${name}-line`
}

export default iconMap
