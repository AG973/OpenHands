import {
  type RouteConfig,
  layout,
  index,
  route,
} from "@react-router/dev/routes";

export default [
  route("login", "routes/login.tsx"),
  route("onboarding", "routes/onboarding-form.tsx"),
  layout("routes/root-layout.tsx", [
    index("routes/home.tsx"),
    route("accept-tos", "routes/accept-tos.tsx"),
    route("launch", "routes/launch.tsx"),
    route("settings", "routes/settings.tsx", [
      index("routes/llm-settings.tsx"),
      route("mcp", "routes/mcp-settings.tsx"),
      route("user", "routes/user-settings.tsx"),
      route("integrations", "routes/git-settings.tsx"),
      route("app", "routes/app-settings.tsx"),
      route("billing", "routes/billing.tsx"),
      route("secrets", "routes/secrets-settings.tsx"),
      route("api-keys", "routes/api-keys.tsx"),
      route("org-members", "routes/manage-organization-members.tsx"),
      route("org", "routes/manage-org.tsx"),
    ]),
    route("conversations/:conversationId", "routes/conversation.tsx"),
    route("microagent-management", "routes/microagent-management.tsx"),
    route("oauth/device/verify", "routes/device-verify.tsx"),
    route("skills", "routes/skills.tsx"),
    route("memory", "routes/memory.tsx"),
    route("evaluation", "routes/evaluation.tsx"),
    route("integrations-hub", "routes/integrations-hub.tsx"),
    route("deploy", "routes/deploy.tsx"),
    route("mobile-builder", "routes/mobile-builder.tsx"),
    route("servers", "routes/servers.tsx"),
    route("gpu-hub", "routes/gpu-hub.tsx"),
    route("mobile-testing", "routes/mobile-testing.tsx"),
    route("github-operations", "routes/github-ops.tsx"),
  ]),
  // Shared routes that don't require authentication
  route(
    "shared/conversations/:conversationId",
    "routes/shared-conversation.tsx",
  ),
] satisfies RouteConfig;
