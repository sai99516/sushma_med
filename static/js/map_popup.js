/*
 * MediFind map helpers (review finding N1).
 *
 * Pharmacy name, address and phone are typed by pharmacy owners, so they
 * must never be put into popup HTML as strings. buildPopup() creates DOM
 * nodes and sets every value with textContent; Leaflet accepts a DOM node
 * in bindPopup() / setContent().
 *
 * escapeHtml() is kept for any code that still needs an escaped string.
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

  /*
   * rows: array of objects { text, tag, style, href, bold }
   *   text  - plain text (set via textContent, never parsed as HTML)
   *   tag   - element name, default 'div'
   *   style - inline CSS string (static, written by us)
   *   href  - optional link target; only tel:, / and https: are allowed
   *   label - optional bold prefix rendered before text
   * Rows with empty text are skipped.
   */
  function safeHref(href) {
    var h = String(href || '');
    if (/^(tel:|\/|https:\/\/)/i.test(h)) {
      return h;
    }
    return '#';
  }

  function buildPopup(rows, wrapperStyle) {
    var doc = root.document;
    var wrapper = doc.createElement('div');
    wrapper.setAttribute('style', wrapperStyle || "min-width: 190px; font-family: 'Plus Jakarta Sans', sans-serif;");
    (rows || []).forEach(function (row) {
      if (!row || row.text === null || row.text === undefined || row.text === '') {
        return;
      }
      var el = doc.createElement(row.href ? 'a' : (row.tag || 'div'));
      if (row.href) {
        el.setAttribute('href', safeHref(row.href));
      }
      if (row.style) {
        el.setAttribute('style', row.style);
      }
      if (row.label) {
        var strong = doc.createElement('strong');
        strong.textContent = row.label;
        el.appendChild(strong);
        el.appendChild(doc.createTextNode(': '));
      }
      el.appendChild(doc.createTextNode(String(row.text)));
      if (row.href) {
        var line = doc.createElement('div');
        line.appendChild(el);
        wrapper.appendChild(line);
      } else {
        wrapper.appendChild(el);
      }
    });
    return wrapper;
  }

  /*
   * Reads data-* attributes from a "Pin on Map" button so pharmacy values
   * never pass through an inline onclick string.
   */
  function popupDataFromButton(btn) {
    var d = btn.dataset || {};
    return {
      lat: parseFloat(d.lat),
      lng: parseFloat(d.lng),
      name: d.name || '',
      address: d.address || '',
      phone: d.phone || '',
      medicine: d.medicine || '',
      distance: d.distance || ''
    };
  }

  root.escapeHtml = escapeHtml;
  root.buildPopup = buildPopup;
  root.popupDataFromButton = popupDataFromButton;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { escapeHtml: escapeHtml, buildPopup: buildPopup };
  }
})(typeof window !== 'undefined' ? window : this);
