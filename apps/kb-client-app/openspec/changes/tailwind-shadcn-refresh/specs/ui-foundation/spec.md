## ADDED Requirements

### Requirement: Tailwind CSS Integration
The system SHALL use Tailwind CSS for all utility styling, replacing the legacy SCSS theme configuration.

#### Scenario: Global styles applied
- **WHEN** the application loads
- **THEN** Tailwind utility classes are available and applied correctly without `smui-theme` compilation errors.

### Requirement: shadcn-svelte UI Components
The system SHALL provide a set of accessible UI components managed via `shadcn-svelte` instead of SMUI.

#### Scenario: Using a button component
- **WHEN** a developer imports a Button from `$lib/components/ui/button`
- **THEN** the button renders with Tailwind styles and Bits UI accessibility features.

### Requirement: Application Layout
The system SHALL provide a responsive layout featuring a top app bar, a collapsible sidebar drawer, and a main content area.

#### Scenario: Toggling the sidebar
- **WHEN** the user clicks the menu icon in the top bar
- **THEN** the sidebar drawer slides in or out, pushing or overlaying the main content appropriately.
