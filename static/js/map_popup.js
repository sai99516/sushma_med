/*
 * MediFind map helpers.
 * escapeHtml() must wrap every server or user value that is put into
 * Leaflet popup HTML (bindPopup / setContent), because pharmacy name,
 * address and phone are typed by pharmacy owners (review finding N1).
 */
(function (root) {
  'use strict';

  var HTML_ESCAPES = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
    '`': '&#96;'
  };

  function escapeHtml(value) {
    if (value === null || value === undefined) {
      return '';
    }
    return String(value).replace(/[&<>"'`]/g, function (ch) {
      return HTML_ESCAPES[ch];
    });
  }

  root.escapeHtml = escapeHtml;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { escapeHtml: escapeHtml };
  }
})(typeof window !== 'undefined' ? window : this);
