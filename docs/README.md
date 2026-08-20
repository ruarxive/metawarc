# metawarc documentation

This directory contains the Docusaurus documentation site for metawarc.

## Development

### Prerequisites

- Node.js 18+ and npm

### Installation

```bash
cd docs
npm install
```

### Local development

Start the development server:

```bash
npm start
```

This starts a local development server and opens a browser window. Most changes
are reflected live without restarting the server.

### Build

Build the site for production:

```bash
npm run build
```

This generates static content into the `build` directory.

### Serve

Serve the built site locally:

```bash
npm run serve
```

## Project structure

```
docs/
├── docusaurus.config.js    # Docusaurus configuration
├── sidebars.js             # Sidebar navigation
├── package.json            # Node.js dependencies
├── babel.config.js         # Babel configuration
├── src/
│   ├── css/custom.css      # Custom styles
│   ├── pages/index.js      # Homepage (documentation contents)
│   └── components/         # React components
├── static/img/             # Logo and favicon
└── docs/                   # Documentation content
    ├── getting-started/    # Installation, quick start, cookbook
    ├── use-cases/          # End-to-end examples
    ├── commands/           # CLI reference
    ├── architecture/       # Workspace, query, security
    ├── integrations/       # REST API, replay, MCP
    ├── development/        # Contributing and release
    └── license.md
```

## Deployment

The documentation is deployed to GitHub Pages at
[datacoon.github.io/metawarc](https://datacoon.github.io/metawarc/) when changes
are pushed to `master` or `main`. The workflow lives in
`.github/workflows/deploy-docs.yml`.

### GitHub Pages setup

1. Open the repository settings on GitHub.
2. Navigate to **Pages**.
3. Under **Source**, select **GitHub Actions**.

See `GITHUB_PAGES_SETUP.md` for details.

## Documentation structure

- **Getting Started**: Installation, quick start, positioning, cookbook
- **Use Cases**: Indexing, export, analysis, replay, agents
- **CLI Reference**: Command-by-command documentation
- **Architecture**: Workspace schema, typed queries, threat model
- **Integrations**: REST API, website replay, MCP
- **Development**: Contributing, release checklist, community

## Contributing

When adding or updating documentation:

1. Edit the markdown files in `docs/docs/`.
2. Follow the existing frontmatter (`title`, `description`).
3. Test locally with `npm start`.
4. Confirm `npm run build` succeeds (broken links fail the build).
