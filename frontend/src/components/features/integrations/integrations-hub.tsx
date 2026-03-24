import React, { useState, useMemo } from "react";
import { AnimatePresence } from "framer-motion";
import {
  LucideSearch,
  LucideFilter,
  LucidePlug,
} from "lucide-react";
import { IntegrationCard } from "./integration-card";
import { ConnectionWizard } from "./connection-wizard";
import type { IntegrationData, IntegrationCategory } from "./integration-card";
import { AnimatedGradientText } from "#/components/ui/animated-gradient-text";

const ALL_INTEGRATIONS: IntegrationData[] = [
  // Developer tools
  {
    id: "github",
    name: "GitHub",
    description: "Connect repositories, create PRs, manage issues, and trigger Actions workflows",
    category: "developer",
    icon: "\uD83D\uDC19",
    connected: false,
    authMethod: "OAuth / Personal Access Token",
    configFields: [
      { key: "token", label: "Personal Access Token", type: "password", placeholder: "ghp_xxxxxxxxxxxx" },
    ],
  },
  {
    id: "gitlab",
    name: "GitLab",
    description: "Connect repositories, merge requests, CI/CD pipelines, and issue tracking",
    category: "developer",
    icon: "\uD83E\uDD8A",
    connected: false,
    authMethod: "OAuth / Personal Access Token",
    configFields: [
      { key: "url", label: "GitLab URL", type: "url", placeholder: "https://gitlab.com" },
      { key: "token", label: "Personal Access Token", type: "password", placeholder: "glpat-xxxxxxxxxxxx" },
    ],
  },
  {
    id: "bitbucket",
    name: "Bitbucket",
    description: "Connect repositories, pull requests, and Bitbucket Pipelines",
    category: "developer",
    icon: "\uD83E\uDEA3",
    connected: false,
    authMethod: "App Password",
    configFields: [
      { key: "username", label: "Username", type: "text", placeholder: "your-username" },
      { key: "password", label: "App Password", type: "password", placeholder: "xxxxxxxxxxxx" },
    ],
  },
  {
    id: "linear",
    name: "Linear",
    description: "Issue tracking, project management, and sprint planning integration",
    category: "developer",
    icon: "\uD83D\uDCCB",
    connected: false,
    authMethod: "API Key",
    configFields: [
      { key: "apiKey", label: "API Key", type: "password", placeholder: "lin_api_xxxxxxxxxxxx" },
    ],
  },
  {
    id: "jira",
    name: "Jira",
    description: "Issue tracking, Agile boards, and project management for development teams",
    category: "developer",
    icon: "\uD83D\uDCCA",
    connected: false,
    authMethod: "API Token",
    configFields: [
      { key: "url", label: "Jira URL", type: "url", placeholder: "https://your-domain.atlassian.net" },
      { key: "email", label: "Email", type: "text", placeholder: "your@email.com" },
      { key: "token", label: "API Token", type: "password", placeholder: "xxxxxxxxxxxx" },
    ],
  },
  {
    id: "notion",
    name: "Notion",
    description: "Documentation, knowledge base, and wiki integration for your projects",
    category: "developer",
    icon: "\uD83D\uDCD3",
    connected: false,
    authMethod: "OAuth / Integration Token",
    configFields: [
      { key: "token", label: "Integration Token", type: "password", placeholder: "secret_xxxxxxxxxxxx" },
    ],
  },

  // Communication
  {
    id: "discord",
    name: "Discord",
    description: "Send notifications, receive commands, and integrate bot functionality",
    category: "communication",
    icon: "\uD83D\uDCAC",
    connected: false,
    authMethod: "Bot Token / Webhook",
    configFields: [
      { key: "webhookUrl", label: "Webhook URL", type: "url", placeholder: "https://discord.com/api/webhooks/..." },
    ],
  },
  {
    id: "slack",
    name: "Slack",
    description: "Send notifications, receive commands, and integrate with Slack workflows",
    category: "communication",
    icon: "\uD83D\uDCE8",
    connected: false,
    authMethod: "OAuth / Webhook",
    configFields: [
      { key: "webhookUrl", label: "Webhook URL", type: "url", placeholder: "https://hooks.slack.com/services/..." },
    ],
  },

  // Cloud
  {
    id: "aws",
    name: "Amazon Web Services",
    description: "Deploy to EC2, S3, Lambda, ECS, CloudFormation — full AWS cloud access",
    category: "cloud",
    icon: "\u2601\uFE0F",
    connected: false,
    authMethod: "Access Key + Secret",
    configFields: [
      { key: "accessKeyId", label: "Access Key ID", type: "text", placeholder: "AKIAIOSFODNN7EXAMPLE" },
      { key: "secretAccessKey", label: "Secret Access Key", type: "password", placeholder: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" },
      { key: "region", label: "Default Region", type: "text", placeholder: "us-east-1" },
    ],
  },
  {
    id: "gcp",
    name: "Google Cloud Platform",
    description: "Deploy to GCE, GCS, Cloud Run, Cloud Functions — full GCP access",
    category: "cloud",
    icon: "\uD83C\uDF10",
    connected: false,
    authMethod: "Service Account JSON",
    configFields: [
      { key: "projectId", label: "Project ID", type: "text", placeholder: "my-project-123" },
      { key: "serviceAccountKey", label: "Service Account Key (JSON)", type: "password", placeholder: "Paste service account JSON..." },
    ],
  },
  {
    id: "azure",
    name: "Microsoft Azure",
    description: "Deploy to VMs, Blob Storage, App Service, Functions — full Azure access",
    category: "cloud",
    icon: "\uD83D\uDFE6",
    connected: false,
    authMethod: "Service Principal",
    configFields: [
      { key: "tenantId", label: "Tenant ID", type: "text", placeholder: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" },
      { key: "clientId", label: "Client ID", type: "text", placeholder: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" },
      { key: "clientSecret", label: "Client Secret", type: "password", placeholder: "xxxxxxxxxxxx" },
    ],
  },
  {
    id: "vercel",
    name: "Vercel",
    description: "One-click frontend deployment with preview URLs and automatic HTTPS",
    category: "cloud",
    icon: "\u25B2",
    connected: false,
    authMethod: "API Token",
    configFields: [
      { key: "token", label: "Vercel Token", type: "password", placeholder: "xxxxxxxxxxxx" },
    ],
  },
  {
    id: "netlify",
    name: "Netlify",
    description: "Deploy static sites and web applications with continuous deployment",
    category: "cloud",
    icon: "\uD83C\uDF10",
    connected: false,
    authMethod: "API Token",
    configFields: [
      { key: "token", label: "Netlify Token", type: "password", placeholder: "xxxxxxxxxxxx" },
    ],
  },
  {
    id: "railway",
    name: "Railway",
    description: "Deploy full-stack applications with databases and background workers",
    category: "cloud",
    icon: "\uD83D\uDE82",
    connected: false,
    authMethod: "API Token",
    configFields: [
      { key: "token", label: "Railway Token", type: "password", placeholder: "xxxxxxxxxxxx" },
    ],
  },
  {
    id: "flyio",
    name: "Fly.io",
    description: "Deploy backend applications globally with edge networking",
    category: "cloud",
    icon: "\u2708\uFE0F",
    connected: false,
    authMethod: "API Token",
    configFields: [
      { key: "token", label: "Fly.io Token", type: "password", placeholder: "xxxxxxxxxxxx" },
    ],
  },
  {
    id: "digitalocean",
    name: "DigitalOcean",
    description: "Deploy to Droplets, App Platform, and managed databases",
    category: "cloud",
    icon: "\uD83D\uDCA7",
    connected: false,
    authMethod: "API Token",
    configFields: [
      { key: "token", label: "DigitalOcean Token", type: "password", placeholder: "dop_v1_xxxxxxxxxxxx" },
    ],
  },
  {
    id: "cloudflare",
    name: "Cloudflare",
    description: "Deploy to Pages, Workers, R2 storage, and edge functions",
    category: "cloud",
    icon: "\uD83D\uDD36",
    connected: false,
    authMethod: "API Token",
    configFields: [
      { key: "token", label: "API Token", type: "password", placeholder: "xxxxxxxxxxxx" },
    ],
  },

  // Mobile
  {
    id: "expo",
    name: "Expo / EAS",
    description: "Build React Native apps and deploy to App Store and Play Store via EAS",
    category: "mobile",
    icon: "\uD83D\uDCF1",
    connected: false,
    authMethod: "Expo Token",
    configFields: [
      { key: "token", label: "Expo Access Token", type: "password", placeholder: "xxxxxxxxxxxx" },
    ],
  },
  {
    id: "appstore",
    name: "App Store Connect",
    description: "Submit iOS apps to the Apple App Store for review and distribution",
    category: "mobile",
    icon: "\uD83C\uDF4E",
    connected: false,
    authMethod: "API Key",
    configFields: [
      { key: "issuerId", label: "Issuer ID", type: "text", placeholder: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" },
      { key: "keyId", label: "Key ID", type: "text", placeholder: "XXXXXXXXXX" },
      { key: "privateKey", label: "Private Key (.p8)", type: "password", placeholder: "Paste private key content..." },
    ],
  },
  {
    id: "playstore",
    name: "Google Play Console",
    description: "Submit Android apps to Google Play Store for review and distribution",
    category: "mobile",
    icon: "\uD83E\uDD16",
    connected: false,
    authMethod: "Service Account",
    configFields: [
      { key: "serviceAccountKey", label: "Service Account Key (JSON)", type: "password", placeholder: "Paste service account JSON..." },
    ],
  },
];

const CATEGORY_CONFIG: Record<IntegrationCategory, { label: string; icon: string }> = {
  developer: { label: "Developer Tools", icon: "\uD83D\uDEE0\uFE0F" },
  cloud: { label: "Cloud & Deployment", icon: "\u2601\uFE0F" },
  mobile: { label: "Mobile App Stores", icon: "\uD83D\uDCF1" },
  communication: { label: "Communication", icon: "\uD83D\uDCAC" },
};

export function IntegrationsHub() {
  const [integrations, setIntegrations] = useState<IntegrationData[]>(ALL_INTEGRATIONS);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterCategory, setFilterCategory] = useState<IntegrationCategory | "all">("all");
  const [wizardIntegration, setWizardIntegration] = useState<IntegrationData | null>(null);

  const filteredIntegrations = useMemo(() => {
    return integrations.filter((int) => {
      const matchesSearch =
        !searchQuery ||
        int.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        int.description.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCategory = filterCategory === "all" || int.category === filterCategory;
      return matchesSearch && matchesCategory;
    });
  }, [integrations, searchQuery, filterCategory]);

  const groupedIntegrations = useMemo(() => {
    const groups: Record<IntegrationCategory, IntegrationData[]> = {
      developer: [],
      cloud: [],
      mobile: [],
      communication: [],
    };
    filteredIntegrations.forEach((int) => {
      groups[int.category].push(int);
    });
    return groups;
  }, [filteredIntegrations]);

  const handleConnect = (id: string) => {
    const integration = integrations.find((i) => i.id === id);
    if (integration) setWizardIntegration(integration);
  };

  const handleDisconnect = (id: string) => {
    setIntegrations(
      integrations.map((i) =>
        i.id === id ? { ...i, connected: false, lastSync: undefined } : i,
      ),
    );
  };

  const handleWizardComplete = (config: Record<string, string>) => {
    if (!wizardIntegration) return;
    setIntegrations(
      integrations.map((i) =>
        i.id === wizardIntegration.id
          ? { ...i, connected: true, lastSync: new Date().toISOString() }
          : i,
      ),
    );
    setWizardIntegration(null);
  };

  const connectedCount = integrations.filter((i) => i.connected).length;

  return (
    <div className="h-full overflow-y-auto custom-scrollbar-always p-6 lg:p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <AnimatedGradientText as="h1" className="text-2xl font-bold" gradient="from-purple-400 via-pink-400 to-red-400">
            Integrations Hub
          </AnimatedGradientText>
          <p className="text-sm text-gray-400 mt-1">
            {connectedCount} of {integrations.length} integrations connected
          </p>
        </div>
      </div>

      {/* Search & Filter */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="flex-1 relative">
          <LucideSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search integrations..."
            className="w-full pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 text-sm"
          />
        </div>
        <div className="flex bg-white/5 border border-white/10 rounded-xl overflow-hidden">
          <button
            onClick={() => setFilterCategory("all")}
            className={`px-4 py-2 text-sm ${filterCategory === "all" ? "bg-white/10 text-white" : "text-gray-400"}`}
          >
            All
          </button>
          {(Object.entries(CATEGORY_CONFIG) as [IntegrationCategory, { label: string; icon: string }][]).map(
            ([key, config]) => (
              <button
                key={key}
                onClick={() => setFilterCategory(key)}
                className={`px-3 py-2 text-sm ${filterCategory === key ? "bg-white/10 text-white" : "text-gray-400"}`}
              >
                {config.icon} {config.label}
              </button>
            ),
          )}
        </div>
      </div>

      {/* Integration Groups */}
      {(Object.entries(groupedIntegrations) as [IntegrationCategory, IntegrationData[]][])
        .filter(([_, items]) => items.length > 0)
        .map(([category, items]) => (
          <div key={category} className="mb-8">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-white mb-4">
              <span>{CATEGORY_CONFIG[category].icon}</span>
              {CATEGORY_CONFIG[category].label}
              <span className="text-sm font-normal text-gray-500">({items.length})</span>
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {items.map((integration) => (
                <IntegrationCard
                  key={integration.id}
                  integration={integration}
                  onConnect={handleConnect}
                  onDisconnect={handleDisconnect}
                  onConfigure={() => handleConnect(integration.id)}
                />
              ))}
            </div>
          </div>
        ))}

      {/* Empty state */}
      {filteredIntegrations.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-gray-500">
          <LucidePlug className="w-12 h-12 mb-3 opacity-50" />
          <p className="text-lg">No integrations found</p>
          <p className="text-sm mt-1">Try a different search</p>
        </div>
      )}

      {/* Connection Wizard */}
      <AnimatePresence>
        {wizardIntegration && (
          <ConnectionWizard
            integration={wizardIntegration}
            onConnect={handleWizardComplete}
            onClose={() => setWizardIntegration(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
