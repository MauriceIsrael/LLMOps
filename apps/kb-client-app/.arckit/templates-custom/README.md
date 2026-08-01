# Custom Templates

This directory is for your customized ArcKit templates.

## How Template Customization Works

1. **Default templates** are in `.arckit/templates/` (refreshed by `arckit init`)
2. **Your customizations** go here in `.arckit/templates-custom/`
3. Commands automatically check here first, falling back to defaults

## Getting Started

Use the `/arckit.customize` command to copy templates for editing:

```
/arckit.customize requirements      # Copy requirements template
/arckit.customize all               # Copy all templates
/arckit.customize list              # See available templates
```

## Why This Pattern?

- Your customizations are preserved when running `arckit init` again
- Default templates can be updated without losing your changes
- Easy to see what you've customized vs defaults

## Common Customizations

- Add organization-specific document control fields
- Include mandatory compliance sections (ISO 27001, PCI-DSS)
- Add department-specific approval workflows
- Customize UK Government classification banners
