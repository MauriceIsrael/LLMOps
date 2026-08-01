# template-app

Enterprise Architecture Governance Project

## Getting Started

This project uses ArcKit for enterprise architecture governance and vendor procurement.

### Available Commands

Once you start your AI assistant, you'll have access to these commands:

#### Project Planning
- `$arckit-plan` - Create project plan with timeline, phases, and gates

#### Core Workflow
- `$arckit-principles` - Create or update architecture principles
- `$arckit-stakeholders` - Analyze stakeholder drivers, goals, and outcomes
- `$arckit-risk` - Create comprehensive risk register (Orange Book)
- `$arckit-sobc` - Create Strategic Outline Business Case (Green Book 5-case)
- `$arckit-requirements` - Define comprehensive requirements
- `$arckit-data-model` - Create data model with ERD, GDPR compliance, data governance
- `$arckit-research` - Research technology, services, and products with build vs buy analysis
- `$arckit-wardley` - Create strategic Wardley Maps for build vs buy and procurement strategy

#### Vendor Procurement
- `$arckit-sow` - Generate Statement of Work (RFP)
- `$arckit-dos` - Digital Outcomes and Specialists (DOS) procurement (UK Digital Marketplace)
- `$arckit-gcloud-search` - Search G-Cloud services on UK Digital Marketplace
- `$arckit-gcloud-clarify` - Validate G-Cloud services and generate clarification questions
- `$arckit-evaluate` - Create vendor evaluation framework and score vendors

#### Design Review
- `$arckit-hld-review` - Review High-Level Design
- `$arckit-dld-review` - Review Detailed Design

#### Architecture Diagrams
- `$arckit-diagram` - Generate visual architecture diagrams using Mermaid

#### Sprint Planning
- `$arckit-backlog` - Generate prioritised product backlog with GDS user stories

#### Service Management
- `$arckit-servicenow` - Generate ServiceNow service design (CMDB, SLAs, incident/change management)

#### Traceability & Quality
- `$arckit-traceability` - Generate requirements traceability matrix
- `$arckit-analyze` - Comprehensive governance quality analysis

#### Template Customization
- `$arckit-customize` - Copy templates for customization (preserves across updates)

#### UK Government Compliance
- `$arckit-service-assessment` - GDS Service Standard assessment preparation
- `$arckit-tcop` - Technology Code of Practice assessment (all 13 points)
- `$arckit-ai-playbook` - AI Playbook compliance for responsible AI
- `$arckit-atrs` - Algorithmic Transparency Recording Standard (ATRS) record

#### Security Assessment
- `$arckit-secure` - UK Government Secure by Design (NCSC CAF, Cyber Essentials, UK GDPR)
- `$arckit-mod-secure` - MOD Secure by Design (JSP 440, IAMM, security clearances)
- `$arckit-jsp-936` - MOD JSP 936 AI assurance documentation

## Project Structure

```
template-app/
├── .arckit/
│   ├── scripts/
│   │   └── bash/
│   ├── templates/           # Default templates (refreshed by arckit init)
│   └── templates-custom/    # Your customizations (preserved across updates)
├── .agents/skills/          # Codex skills (auto-discovered)
├── projects/
│   ├── 000-global/
│   │   └── ARC-000-PRIN-v1.0.md (global principles)
│   └── 001-project-name/
│       ├── requirements.md
│       ├── sow.md
│       └── vendors/
```

## Template Customization

ArcKit templates can be customized without modifying the defaults:

1. Run `$arckit-customize <template-name>` to copy a template for editing
2. Your customizations are stored in `.arckit/templates-custom/`
3. Commands automatically use your custom templates when present
4. Running `arckit init` again preserves your customizations

Example:
```
$arckit-customize requirements   # Copy requirements template
$arckit-customize all            # Copy all templates
```

## Next Steps

1. Start your AI assistant (OpenAI Codex CLI)
2. Run `$arckit-principles` to establish architecture governance
3. Create your first project with `$arckit-requirements`

## Documentation

- [ArcKit Documentation](https://github.com/github/arc-kit)
- [Architecture Principles Guide](https://github.com/github/arc-kit/docs/principles.md)
- [Vendor Procurement Guide](https://github.com/github/arc-kit/docs/procurement.md)
