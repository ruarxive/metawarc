import React from 'react';
import Link from '@docusaurus/Link';
import styles from './DocsContents.module.css';

const sections = [
  {
    title: 'Getting Started',
    to: '/getting-started/installation',
    description: 'Install metawarc and index, query, or replay a WARC collection.',
    links: [
      {label: 'Installation', to: '/getting-started/installation'},
      {label: 'Quick start', to: '/getting-started/quick-start'},
      {label: 'When to use', to: '/getting-started/when-to-use'},
      {label: 'Cookbook', to: '/getting-started/cookbook'},
      {label: 'Basic usage', to: '/getting-started/basic-usage'},
      {label: 'Performance', to: '/getting-started/performance'},
      {label: 'Troubleshooting', to: '/getting-started/troubleshooting'},
      {label: 'Best practices', to: '/getting-started/best-practices'},
    ],
  },
  {
    title: 'Use Cases',
    to: '/use-cases/indexing-collections',
    description: 'End-to-end examples for indexing, export, analysis, replay, and agents.',
    links: [
      {label: 'Indexing collections', to: '/use-cases/indexing-collections'},
      {label: 'Querying and export', to: '/use-cases/querying-and-export'},
      {label: 'Metadata and analysis', to: '/use-cases/metadata-and-analysis'},
      {label: 'Website replay', to: '/use-cases/website-replay'},
      {label: 'Agents and MCP', to: '/use-cases/agents-and-mcp'},
    ],
  },
  {
    title: 'CLI Reference',
    to: '/commands/',
    description: 'Command-by-command reference for index, query, extract, analyze, and serve.',
    links: [
      {label: 'All commands', to: '/commands/'},
      {label: 'index', to: '/commands/index-records'},
      {label: 'ingest', to: '/commands/ingest'},
      {label: 'list-files / dump', to: '/commands/list-files'},
      {label: 'analyze', to: '/commands/analyze'},
      {label: 'serve / replay', to: '/commands/serve'},
      {label: 'mcp', to: '/commands/mcp'},
    ],
  },
  {
    title: 'Architecture',
    to: '/architecture/workspace',
    description: 'Workspace schema, typed queries, and the threat model for hostile archives.',
    links: [
      {label: 'Workspace and schema', to: '/architecture/workspace'},
      {label: 'Query model', to: '/architecture/query'},
      {label: 'Security', to: '/architecture/security'},
    ],
  },
  {
    title: 'Integrations',
    to: '/integrations/rest-api',
    description: 'Read-only REST API, local website replay, and MCP tools for agents.',
    links: [
      {label: 'REST API', to: '/integrations/rest-api'},
      {label: 'Website replay', to: '/integrations/replay'},
      {label: 'MCP server', to: '/integrations/mcp'},
    ],
  },
  {
    title: 'Development',
    to: '/development/contributing',
    description: 'Contributing, release checklist, community, and license.',
    links: [
      {label: 'Contributing', to: '/development/contributing'},
      {label: 'Release checklist', to: '/development/release-checklist'},
      {label: 'Community', to: '/development/community'},
      {label: 'License', to: '/license'},
    ],
  },
];

function Section({title, to, description, links}) {
  return (
    <article className={styles.card}>
      <h3 className={styles.cardTitle}>
        <Link to={to}>{title}</Link>
      </h3>
      <p className={styles.cardDescription}>{description}</p>
      <ul className={styles.linkList}>
        {links.map((item) => (
          <li key={item.label}>
            {item.href ? (
              <a href={item.href}>{item.label}</a>
            ) : (
              <Link to={item.to}>{item.label}</Link>
            )}
          </li>
        ))}
      </ul>
    </article>
  );
}

export default function DocsContents() {
  return (
    <section className={styles.contents}>
      <div className="container">
        <h2 className={styles.heading}>Documentation contents</h2>
        <p className={styles.intro}>
          Start with a section below, or use the sidebar from any page. The CLI
          entry point is <code>metawarc</code>. Source WARC files stay immutable;
          the DuckDB catalog and Parquet sidecars are the operational index.
        </p>
        <div className={styles.grid}>
          {sections.map((section) => (
            <Section key={section.title} {...section} />
          ))}
        </div>
      </div>
    </section>
  );
}
