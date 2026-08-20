/**
 * Creating a sidebar enables you to:
 - create an ordered group of docs
 - render a sidebar for each doc of that group
 - provide next/previous navigation
 */

// @ts-check

/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  docs: [
    {
      type: 'link',
      label: 'Contents',
      href: '/',
    },
    {
      type: 'category',
      label: 'Getting Started',
      items: [
        'getting-started/installation',
        'getting-started/quick-start',
        'getting-started/when-to-use',
        'getting-started/cookbook',
        'getting-started/basic-usage',
        'getting-started/performance',
        'getting-started/troubleshooting',
        'getting-started/best-practices',
      ],
    },
    {
      type: 'category',
      label: 'Use Cases',
      items: [
        'use-cases/indexing-collections',
        'use-cases/querying-and-export',
        'use-cases/metadata-and-analysis',
        'use-cases/website-replay',
        'use-cases/agents-and-mcp',
      ],
    },
    {
      type: 'category',
      label: 'CLI Reference',
      items: [
        'commands/index',
        {
          type: 'category',
          label: 'Index and ingest',
          items: [
            'commands/index-records',
            'commands/ingest',
            'commands/index-content',
          ],
        },
        {
          type: 'category',
          label: 'Inspect',
          items: [
            'commands/catalog',
            'commands/stats',
            'commands/list-files',
            'commands/doctor',
          ],
        },
        {
          type: 'category',
          label: 'Export',
          items: [
            'commands/dump',
            'commands/get',
            'commands/dump-metadata',
            'commands/export-cdxj',
          ],
        },
        {
          type: 'category',
          label: 'Analysis',
          items: ['commands/analyze'],
        },
        {
          type: 'category',
          label: 'Maintenance',
          items: ['commands/rebind', 'commands/cleanup'],
        },
        {
          type: 'category',
          label: 'Interfaces',
          items: ['commands/serve', 'commands/replay', 'commands/mcp'],
        },
      ],
    },
    {
      type: 'category',
      label: 'Architecture',
      items: [
        'architecture/workspace',
        'architecture/query',
        'architecture/security',
      ],
    },
    {
      type: 'category',
      label: 'Integrations',
      items: [
        'integrations/rest-api',
        'integrations/replay',
        'integrations/mcp',
      ],
    },
    {
      type: 'category',
      label: 'Development',
      items: [
        'development/contributing',
        'development/release-checklist',
        'development/community',
      ],
    },
    'license',
  ],
};

module.exports = sidebars;
