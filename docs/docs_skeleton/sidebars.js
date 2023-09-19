/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 * @format
 */

/**
 * Creating a sidebar enables you to:
 - create an ordered group of docs
 - render a sidebar for each doc of that group
 - provide next/previous navigation

 The sidebars can be generated from the filesystem, or explicitly defined here.

 Create as many sidebars as you want.
 */

module.exports = {
  // By default, Docusaurus generates a sidebar from the docs folder structure
  docs: [
    {
      type: "category",
      label: "Get started",
      collapsed: false,
      collapsible: false,
      items: [{ type: "autogenerated", dirName: "get_started" }],
      link: {
        type: 'generated-index',
        description: 'Get started with LangChain',
      slug: "get_started",
      },
    },
    {
      type: "category",
      label: "Modules",
      collapsed: false,
      collapsible: false,
      items: [{ type: "autogenerated", dirName: "modules" } ],
      link: {
        type: 'doc',
        id: "modules/index"
      },
    },
    {
      type: "category",
      label: "LangChain Expression Language",
      collapsed: true,
      items: [{ type: "autogenerated", dirName: "expression_language" } ],
      link: {
        type: 'doc',
        id: "expression_language/index"
      },
    },
    {
      type: "category",
      label: "Guides",
      collapsed: true,
      items: [{ type: "autogenerated", dirName: "guides" }],
      link: {
        type: 'generated-index',
        description: 'Design guides for key parts of the development process',
        slug: "guides",
      },
    },
    {
      type: "category",
      label: "Additional resources",
      collapsed: true,
      items: [
        { type: "autogenerated", dirName: "additional_resources" },
        { type: "link", label: "Gallery", href: "https://github.com/kyrolabs/awesome-langchain" }
      ],
      link: {
        type: 'generated-index',
        slug: "additional_resources",
      },
    },
    'community'
  ],
  integrations: [
    {
      type: "category",
      label: "Providers",
      collapsible: false,
      items: [
        { type: "autogenerated", dirName: "integrations/platforms" },
        { type: "category", label: "More", collapsed: true, items: [{type:"autogenerated", dirName: "integrations/providers" }]},
      ],
      link: {
        type: 'generated-index',
        slug: "integrations/providers",
      },
    },
    {
      type: "category",
      label: "Components",
      collapsible: false,
      items: [
        { type: "category", label: "LLMs", collapsed: true, items: [{type:"autogenerated", dirName: "integrations/llms" }], link: {type: "generated-index", slug: "integrations/llms" }},
        { type: "category", label: "Chat models", collapsed: true, items: [{type:"autogenerated", dirName: "integrations/chat" }], link: {type: "generated-index", slug: "integrations/chat" }},
        { type: "category", label: "Document loaders", collapsed: true, items: [{type:"autogenerated", dirName: "integrations/document_loaders" }], link: {type: "generated-index", slug: "integrations/document_loaders" }},
        { type: "category", label: "Document transformers", collapsed: true, items: [{type: "autogenerated", dirName: "integrations/document_transformers" }], link: {type: "generated-index", slug: "integrations/document_transformers" }},
        { type: "category", label: "Text embedding models", collapsed: true, items: [{type: "autogenerated", dirName: "integrations/text_embedding" }], link: {type: "generated-index", slug: "integrations/text_embedding" }},
        { type: "category", label: "Vector stores", collapsed: true, items: [{type: "autogenerated", dirName: "integrations/vectorstores" }], link: {type: "generated-index", slug: "integrations/vectorstores" }},
        { type: "category", label: "Retrievers", collapsed: true, items: [{type: "autogenerated", dirName: "integrations/retrievers" }], link: {type: "generated-index", slug: "integrations/retrievers" }},
        { type: "category", label: "Tools", collapsed: true, items: [{type: "autogenerated", dirName: "integrations/tools" }], link: {type: "generated-index", slug: "integrations/tools" }},
        { type: "category", label: "Agents and toolkits", collapsed: true, items: [{type: "autogenerated", dirName: "integrations/toolkits" }], link: {type: "generated-index", slug: "integrations/toolkits" }},
        { type: "category", label: "Memory", collapsed: true, items: [{type: "autogenerated", dirName: "integrations/memory" }], link: {type: "generated-index", slug: "integrations/memory" }},
        { type: "category", label: "Callbacks", collapsed: true, items: [{type: "autogenerated", dirName: "integrations/callbacks" }], link: {type: "generated-index", slug: "integrations/callbacks" }},
        { type: "category", label: "Chat loaders", collapsed: true, items: [{type: "autogenerated", dirName: "integrations/chat_loaders" }], link: {type: "generated-index", slug: "integrations/chat_loaders" }},
      ],
      link: {
        type: 'generated-index',
      slug: "integrations/components",
      },
    },
  ],
  use_cases: [
    {type: "autogenerated", dirName: "use_cases" }
  ],
};
