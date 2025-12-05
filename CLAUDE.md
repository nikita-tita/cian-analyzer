# HOUSLER Project Rules

## Design Guidelines

### No Emojis
Do NOT use emojis in the UI, templates, or CSS. Use typography and CSS styling instead.

Examples:
- Lists: use `—` (em-dash) or CSS bullets, NOT checkmarks or emojis
- Icons: use CSS or inline SVG, NOT emoji icons
- Buttons: text only, no emoji decorations

### Product Features

**AI Calendar Assistant (@aibroker_bot)**
Current features:
- Voice input via Telegram
- Reminders for property showings
- Calendar slot search

NOT available (do not mention):
- Google Calendar sync (we don't have this integration)

## Code Style

### CSS
- Use existing design system variables (--color-primary, --color-text, etc.)
- Reuse existing classes (service-card, btn, btn-primary) before creating new ones
- Minimalist design, no decorative elements

### Templates
- Jinja2 templates in /templates
- Cache-busting via query params: landing.css?v=YYYYMMDD
