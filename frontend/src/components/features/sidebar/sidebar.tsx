import React from "react";
import { useLocation, useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { useGitUser } from "#/hooks/query/use-git-user";
import { UserActions } from "./user-actions";
import { OpenHandsLogoButton } from "#/components/shared/buttons/openhands-logo-button";
import { NewProjectButton } from "#/components/shared/buttons/new-project-button";
import { ConversationPanelButton } from "#/components/shared/buttons/conversation-panel-button";
import { SettingsModal } from "#/components/shared/modals/settings/settings-modal";
import { useSettings } from "#/hooks/query/use-settings";
import { ConversationPanel } from "../conversation-panel/conversation-panel";
import { ConversationPanelWrapper } from "../conversation-panel/conversation-panel-wrapper";
import { useConfig } from "#/hooks/query/use-config";
import { displayErrorToast } from "#/utils/custom-toast-handlers";
import { I18nKey } from "#/i18n/declaration";
import { cn } from "#/utils/utils";
import {
  Zap as LucideZap,
  Brain as LucideBrain,
  BarChart3 as LucideBarChart3,
  Puzzle as LucidePuzzle,
  Rocket as LucideRocket,
  Smartphone as LucideSmartphone,
  Server as LucideServer,
  Cpu as LucideCpu,
  Bug as LucideBug,
} from "lucide-react";

export function Sidebar() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const user = useGitUser();
  const { data: config } = useConfig();
  const {
    data: settings,
    error: settingsError,
    isError: settingsIsError,
    isFetching: isFetchingSettings,
  } = useSettings();

  const [settingsModalIsOpen, setSettingsModalIsOpen] = React.useState(false);

  const [conversationPanelIsOpen, setConversationPanelIsOpen] =
    React.useState(false);

  React.useEffect(() => {
    if (pathname === "/settings") {
      setSettingsModalIsOpen(false);
    } else if (
      !isFetchingSettings &&
      settingsIsError &&
      settingsError?.status !== 404
    ) {
      // We don't show toast errors for settings in the global error handler
      // because we have a special case for 404 errors
      displayErrorToast(
        "Something went wrong while fetching settings. Please reload the page.",
      );
    } else if (
      config?.app_mode === "oss" &&
      settingsError?.status === 404 &&
      !config?.feature_flags?.hide_llm_settings
    ) {
      setSettingsModalIsOpen(true);
    }
  }, [
    pathname,
    isFetchingSettings,
    settingsIsError,
    settingsError,
    config?.app_mode,
    config?.feature_flags?.hide_llm_settings,
  ]);

  return (
    <>
      <aside
        aria-label={t(I18nKey.SIDEBAR$NAVIGATION_LABEL)}
        className={cn(
          "h-[54px] p-3 md:p-0 md:h-[40px] md:h-auto flex flex-row md:flex-col gap-1 bg-base md:w-[75px] md:min-w-[75px] sm:pt-0 sm:px-2 md:pt-[14px] md:px-0",
          pathname === "/" && "md:pt-6.5 md:pb-3",
        )}
      >
        <nav className="flex flex-row md:flex-col items-center justify-between w-full h-auto md:w-auto md:h-full">
          <div className="flex flex-row md:flex-col items-center gap-[26px]">
            <div className="flex items-center justify-center">
              <OpenHandsLogoButton />
            </div>
            <div className="flex items-center justify-center">
              <NewProjectButton disabled={settings?.email_verified === false} />
            </div>
            <ConversationPanelButton
              isOpen={conversationPanelIsOpen}
              onClick={() =>
                settings?.email_verified === false
                  ? null
                  : setConversationPanelIsOpen((prev) => !prev)
              }
              disabled={settings?.email_verified === false}
            />
          </div>

          {/* Feature Navigation */}
          <div className="hidden md:flex flex-col items-center gap-2 overflow-y-auto custom-scrollbar py-1">
            {[
              { path: "/skills", icon: <LucideZap className="w-[18px] h-[18px]" />, label: "Skills" },
              { path: "/memory", icon: <LucideBrain className="w-[18px] h-[18px]" />, label: "Memory" },
              { path: "/evaluation", icon: <LucideBarChart3 className="w-[18px] h-[18px]" />, label: "Evaluation" },
              { path: "/integrations-hub", icon: <LucidePuzzle className="w-[18px] h-[18px]" />, label: "Integrations" },
              { path: "/deploy", icon: <LucideRocket className="w-[18px] h-[18px]" />, label: "Deploy" },
              { path: "/mobile-builder", icon: <LucideSmartphone className="w-[18px] h-[18px]" />, label: "Mobile" },
              { path: "/servers", icon: <LucideServer className="w-[18px] h-[18px]" />, label: "Servers" },
              { path: "/gpu-hub", icon: <LucideCpu className="w-[18px] h-[18px]" />, label: "GPU" },
              { path: "/mobile-testing", icon: <LucideBug className="w-[18px] h-[18px]" />, label: "Testing" },
            ].map((item) => (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                title={item.label}
                className={cn(
                  "w-10 h-10 flex items-center justify-center rounded-xl transition-colors",
                  pathname === item.path
                    ? "bg-white/15 text-white"
                    : "text-gray-500 hover:text-white hover:bg-white/5",
                )}
              >
                {item.icon}
              </button>
            ))}
          </div>

          <div className="flex flex-row md:flex-col md:items-center gap-[26px]">
            <UserActions
              user={
                user.data ? { avatar_url: user.data.avatar_url } : undefined
              }
              isLoading={user.isFetching}
            />
          </div>
        </nav>

        {conversationPanelIsOpen && (
          <ConversationPanelWrapper isOpen={conversationPanelIsOpen}>
            <ConversationPanel
              onClose={() => setConversationPanelIsOpen(false)}
            />
          </ConversationPanelWrapper>
        )}
      </aside>

      {settingsModalIsOpen && (
        <SettingsModal
          settings={settings}
          onClose={() => setSettingsModalIsOpen(false)}
        />
      )}
    </>
  );
}
