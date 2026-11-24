import re

with open('templates/index.html', encoding='utf-8') as f:
    html = f.read()

ids = set(re.findall(r"id=['\"]([^'\"]+)['\"]", html))

top_level = [
    'planner-form', 'status', 'results', 'results-inner', 'submit-btn',
    'start_location', 'btn-detect-location', 'geo-status-hint',
    'start_date', 'end_date', 'travelers', 'currency', 'currency-symbol',
    'navbar', 'hamburger', 'mobile-menu',
    'chatbot-drawer', 'floating-chat-trigger', 'close-chat-btn', 'open-chat-nav-btn',
    'mobile-chat-btn', 'chat-form', 'chat-input', 'chat-messages', 'chat-provider-badge',
    'saved-trips-modal', 'close-saved-modal', 'saved-trips-list', 'nav-saved-trips-btn',
    'mobile-saved-trips-btn', 'footer-saved-link', 'share-modal', 'close-share-modal',
    'share-url-input', 'btn-copy-share-url', 'copy-status'
]

missing = [i for i in top_level if i not in ids]
print('Missing top-level elements:', missing)
assert not missing, f'Top level elements missing: {missing}'
print('ALL 36 top-level DOM references exist in index.html with ZERO missing elements!')
