## ADDED Requirements

### Requirement: Theme State Management
The system SHALL manage light and dark mode preferences using a Svelte 5 `$state` module.

#### Scenario: Toggling theme
- **WHEN** the user clicks the theme toggle button
- **THEN** the global theme state updates, persisting the choice, and toggling the `dark` class on the document root.

### Requirement: Localization State Management
The system SHALL manage the active locale using Svelte 5 idioms to interface with `svelte-i18n`.

#### Scenario: Changing language
- **WHEN** the user selects a new language from the top bar
- **THEN** the locale state updates, translating the visible application text immediately.
