import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LucideSmartphone,
  LucideApple,
  LucidePlay,
  LucideCheck,
  LucideLoader2,
  LucideArrowRight,
  LucideArrowLeft,
  LucidePalette,
  LucideLayout,
  LucideRocket,
  LucidePackage,
  LucideImage,
  LucideType,
} from "lucide-react";
import { AnimatedGradientText } from "#/components/ui/animated-gradient-text";

type AppPlatform = "both" | "ios" | "android";
type AppTemplate = "blank" | "tabs" | "drawer" | "ecommerce" | "social" | "productivity";

interface AppConfig {
  name: string;
  description: string;
  platform: AppPlatform;
  template: AppTemplate;
  primaryColor: string;
  icon: string;
  splashColor: string;
  bundleId: string;
  version: string;
}

const TEMPLATES: { id: AppTemplate; name: string; description: string; icon: React.ReactNode }[] = [
  { id: "blank", name: "Blank", description: "Start from scratch with a clean project", icon: <LucideLayout className="w-6 h-6" /> },
  { id: "tabs", name: "Tab Navigation", description: "Bottom tab bar with multiple screens", icon: <LucideLayout className="w-6 h-6" /> },
  { id: "drawer", name: "Side Drawer", description: "Side navigation with drawer menu", icon: <LucideLayout className="w-6 h-6" /> },
  { id: "ecommerce", name: "E-Commerce", description: "Product catalog, cart, and checkout", icon: <LucidePackage className="w-6 h-6" /> },
  { id: "social", name: "Social Feed", description: "Feed, profiles, messaging, and notifications", icon: <LucideSmartphone className="w-6 h-6" /> },
  { id: "productivity", name: "Productivity", description: "Tasks, notes, calendar, and reminders", icon: <LucideSmartphone className="w-6 h-6" /> },
];

const COLORS = [
  "#3B82F6", "#8B5CF6", "#06B6D4", "#10B981", "#F59E0B",
  "#EF4444", "#EC4899", "#6366F1", "#14B8A6", "#F97316",
];

type BuildStep = "config" | "template" | "design" | "review" | "building" | "complete";

export function MobileBuilder() {
  const [step, setStep] = useState<BuildStep>("config");
  const [config, setConfig] = useState<AppConfig>({
    name: "",
    description: "",
    platform: "both",
    template: "blank",
    primaryColor: "#3B82F6",
    icon: "",
    splashColor: "#0d1117",
    bundleId: "",
    version: "1.0.0",
  });

  const steps: { key: BuildStep; label: string }[] = [
    { key: "config", label: "App Info" },
    { key: "template", label: "Template" },
    { key: "design", label: "Design" },
    { key: "review", label: "Review" },
    { key: "building", label: "Build" },
    { key: "complete", label: "Done" },
  ];

  const currentStepIndex = steps.findIndex((s) => s.key === step);

  const handleBuild = () => {
    setStep("building");
    setTimeout(() => {
      setStep("complete");
    }, 5000);
  };

  return (
    <div className="h-full overflow-y-auto custom-scrollbar-always p-6 lg:p-8">
      {/* Header */}
      <div className="mb-6">
        <AnimatedGradientText as="h1" className="text-2xl font-bold" gradient="from-pink-400 via-purple-400 to-indigo-400">
          Mobile App Builder
        </AnimatedGradientText>
        <p className="text-sm text-gray-400 mt-1">
          Build iOS and Android apps — no coding experience needed
        </p>
      </div>

      {/* Progress Steps */}
      <div className="flex items-center gap-2 mb-8 overflow-x-auto">
        {steps.map((s, i) => {
          const stepIndex = steps.findIndex((st) => st.key === s.key);
          const isActive = s.key === step;
          const isDone = stepIndex < currentStepIndex;
          return (
            <React.Fragment key={s.key}>
              {i > 0 && (
                <div className={`h-px flex-1 min-w-[20px] ${isDone ? "bg-purple-500" : "bg-white/10"}`} />
              )}
              <div
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap ${
                  isActive
                    ? "bg-purple-500/20 text-purple-400 border border-purple-500/30"
                    : isDone
                      ? "bg-green-500/20 text-green-400 border border-green-500/30"
                      : "bg-white/5 text-gray-500 border border-white/10"
                }`}
              >
                {isDone ? <LucideCheck className="w-3 h-3" /> : null}
                {s.label}
              </div>
            </React.Fragment>
          );
        })}
      </div>

      <AnimatePresence mode="wait">
        {/* Step 1: App Info */}
        {step === "config" && (
          <motion.div
            key="config"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="max-w-2xl space-y-5"
          >
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">App Name</label>
              <input
                type="text"
                value={config.name}
                onChange={(e) => setConfig({ ...config, name: e.target.value })}
                placeholder="My Awesome App"
                className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50 text-sm"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Description</label>
              <textarea
                value={config.description}
                onChange={(e) => setConfig({ ...config, description: e.target.value })}
                placeholder="Describe what your app does..."
                rows={3}
                className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50 text-sm resize-y"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Platform</label>
              <div className="grid grid-cols-3 gap-3">
                {(
                  [
                    { id: "both", label: "iOS & Android", icons: [<LucideApple key="a" className="w-5 h-5" />, <LucidePlay key="p" className="w-5 h-5" />] },
                    { id: "ios", label: "iOS Only", icons: [<LucideApple key="a" className="w-5 h-5" />] },
                    { id: "android", label: "Android Only", icons: [<LucidePlay key="p" className="w-5 h-5" />] },
                  ] as { id: AppPlatform; label: string; icons: React.ReactNode[] }[]
                ).map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setConfig({ ...config, platform: p.id })}
                    className={`flex flex-col items-center gap-2 p-4 rounded-xl border transition-all ${
                      config.platform === p.id
                        ? "border-purple-500/50 bg-purple-500/10"
                        : "border-white/10 bg-white/5 hover:border-white/20"
                    }`}
                  >
                    <div className="flex gap-1">{p.icons}</div>
                    <span className="text-sm text-white">{p.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">Bundle ID</label>
                <input
                  type="text"
                  value={config.bundleId}
                  onChange={(e) => setConfig({ ...config, bundleId: e.target.value })}
                  placeholder="com.example.myapp"
                  className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50 text-sm font-mono"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">Version</label>
                <input
                  type="text"
                  value={config.version}
                  onChange={(e) => setConfig({ ...config, version: e.target.value })}
                  className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white text-sm font-mono focus:outline-none focus:border-purple-500/50"
                />
              </div>
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => setStep("template")}
                disabled={!config.name.trim()}
                className="flex items-center gap-2 px-5 py-2.5 bg-purple-500 hover:bg-purple-600 disabled:opacity-50 text-white rounded-xl text-sm font-medium transition-colors"
              >
                Next <LucideArrowRight className="w-4 h-4" />
              </button>
            </div>
          </motion.div>
        )}

        {/* Step 2: Template */}
        {step === "template" && (
          <motion.div
            key="template"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
          >
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mb-6">
              {TEMPLATES.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setConfig({ ...config, template: t.id })}
                  className={`text-left p-5 rounded-2xl border transition-all ${
                    config.template === t.id
                      ? "border-purple-500/50 bg-purple-500/10 ring-1 ring-purple-500/20"
                      : "border-white/10 bg-white/5 hover:border-white/20"
                  }`}
                >
                  <div className="flex items-center gap-3 mb-2">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                      config.template === t.id ? "bg-purple-500/20 text-purple-400" : "bg-white/10 text-gray-400"
                    }`}>
                      {t.icon}
                    </div>
                    <h3 className="text-sm font-semibold text-white">{t.name}</h3>
                  </div>
                  <p className="text-sm text-gray-400">{t.description}</p>
                </button>
              ))}
            </div>

            <div className="flex justify-between">
              <button onClick={() => setStep("config")} className="flex items-center gap-2 px-4 py-2 text-gray-400 hover:text-white">
                <LucideArrowLeft className="w-4 h-4" /> Back
              </button>
              <button
                onClick={() => setStep("design")}
                className="flex items-center gap-2 px-5 py-2.5 bg-purple-500 hover:bg-purple-600 text-white rounded-xl text-sm font-medium"
              >
                Next <LucideArrowRight className="w-4 h-4" />
              </button>
            </div>
          </motion.div>
        )}

        {/* Step 3: Design */}
        {step === "design" && (
          <motion.div
            key="design"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="max-w-2xl space-y-6"
          >
            {/* Primary Color */}
            <div>
              <label className="flex items-center gap-2 text-sm text-gray-400 mb-3">
                <LucidePalette className="w-4 h-4" /> Primary Color
              </label>
              <div className="flex flex-wrap gap-3">
                {COLORS.map((color) => (
                  <button
                    key={color}
                    onClick={() => setConfig({ ...config, primaryColor: color })}
                    className={`w-10 h-10 rounded-xl transition-transform ${
                      config.primaryColor === color ? "ring-2 ring-white ring-offset-2 ring-offset-[#0d1117] scale-110" : ""
                    }`}
                    style={{ backgroundColor: color }}
                    aria-label={`Select color ${color}`}
                  />
                ))}
              </div>
            </div>

            {/* App Icon */}
            <div>
              <label className="flex items-center gap-2 text-sm text-gray-400 mb-2">
                <LucideImage className="w-4 h-4" /> App Icon (emoji or upload later)
              </label>
              <input
                type="text"
                value={config.icon}
                onChange={(e) => setConfig({ ...config, icon: e.target.value })}
                placeholder="Paste an emoji here, e.g. \uD83D\uDE80"
                className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white text-2xl placeholder-gray-500 focus:outline-none focus:border-purple-500/50"
              />
            </div>

            {/* Preview */}
            <div>
              <label className="flex items-center gap-2 text-sm text-gray-400 mb-3">
                <LucideSmartphone className="w-4 h-4" /> Preview
              </label>
              <div className="flex justify-center">
                <div className="w-[200px] h-[400px] rounded-[32px] border-4 border-white/20 bg-[#0d1117] overflow-hidden relative">
                  {/* Status bar */}
                  <div className="h-8 flex items-center justify-center">
                    <div className="w-16 h-4 bg-black rounded-full" />
                  </div>
                  {/* Content */}
                  <div className="flex flex-col items-center justify-center h-[calc(100%-80px)] px-4">
                    <div className="text-4xl mb-2">{config.icon || "\uD83D\uDCF1"}</div>
                    <p className="text-sm font-semibold text-white text-center">{config.name || "My App"}</p>
                    <p className="text-xs text-gray-500 text-center mt-1">{config.description || "Your app description"}</p>
                  </div>
                  {/* Bottom bar */}
                  <div className="absolute bottom-0 left-0 right-0 h-12 flex items-center justify-center" style={{ backgroundColor: config.primaryColor + "20" }}>
                    <div className="flex gap-6">
                      <div className="w-6 h-1 rounded-full" style={{ backgroundColor: config.primaryColor }} />
                      <div className="w-6 h-1 rounded-full bg-white/20" />
                      <div className="w-6 h-1 rounded-full bg-white/20" />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-between">
              <button onClick={() => setStep("template")} className="flex items-center gap-2 px-4 py-2 text-gray-400 hover:text-white">
                <LucideArrowLeft className="w-4 h-4" /> Back
              </button>
              <button
                onClick={() => setStep("review")}
                className="flex items-center gap-2 px-5 py-2.5 bg-purple-500 hover:bg-purple-600 text-white rounded-xl text-sm font-medium"
              >
                Next <LucideArrowRight className="w-4 h-4" />
              </button>
            </div>
          </motion.div>
        )}

        {/* Step 4: Review */}
        {step === "review" && (
          <motion.div
            key="review"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="max-w-2xl"
          >
            <div className="p-6 bg-white/5 border border-white/10 rounded-2xl space-y-4">
              <h3 className="text-lg font-semibold text-white">Review Your App</h3>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-gray-500">App Name</p>
                  <p className="text-sm text-white">{config.name}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Platform</p>
                  <p className="text-sm text-white capitalize">
                    {config.platform === "both" ? "iOS & Android" : config.platform}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Template</p>
                  <p className="text-sm text-white capitalize">{config.template}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Bundle ID</p>
                  <p className="text-sm text-white font-mono">{config.bundleId || "auto-generated"}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Version</p>
                  <p className="text-sm text-white">{config.version}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Primary Color</p>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded" style={{ backgroundColor: config.primaryColor }} />
                    <span className="text-sm text-white font-mono">{config.primaryColor}</span>
                  </div>
                </div>
              </div>

              {config.description && (
                <div>
                  <p className="text-xs text-gray-500">Description</p>
                  <p className="text-sm text-gray-300">{config.description}</p>
                </div>
              )}

              <div className="flex items-center gap-2 p-3 bg-purple-500/10 border border-purple-500/20 rounded-xl">
                <LucideSmartphone className="w-4 h-4 text-purple-400 shrink-0" />
                <p className="text-xs text-purple-300">
                  The AI agent will create a React Native + Expo project, build it with EAS, and prepare it for app store submission.
                </p>
              </div>
            </div>

            <div className="flex justify-between mt-6">
              <button onClick={() => setStep("design")} className="flex items-center gap-2 px-4 py-2 text-gray-400 hover:text-white">
                <LucideArrowLeft className="w-4 h-4" /> Back
              </button>
              <button
                onClick={handleBuild}
                className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white rounded-xl text-sm font-medium"
              >
                <LucideRocket className="w-4 h-4" /> Build App
              </button>
            </div>
          </motion.div>
        )}

        {/* Step 5: Building */}
        {step === "building" && (
          <motion.div
            key="building"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex flex-col items-center justify-center py-16"
          >
            <div className="relative mb-8">
              <LucideSmartphone className="w-20 h-20 text-purple-400/30" />
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                className="absolute inset-0 flex items-center justify-center"
              >
                <LucideLoader2 className="w-8 h-8 text-purple-400" />
              </motion.div>
            </div>
            <p className="text-xl font-semibold text-white mb-2">Building your app...</p>
            <p className="text-sm text-gray-400 mb-4">Creating React Native project with Expo</p>

            {/* Build steps */}
            <div className="w-80 space-y-3">
              {[
                "Creating Expo project...",
                "Installing dependencies...",
                "Configuring navigation...",
                "Building UI components...",
                "Running EAS Build...",
              ].map((label, i) => (
                <motion.div
                  key={label}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.8 }}
                  className="flex items-center gap-3"
                >
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: i * 0.8 + 0.5 }}
                  >
                    <LucideCheck className="w-4 h-4 text-green-400" />
                  </motion.div>
                  <span className="text-sm text-gray-300">{label}</span>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}

        {/* Step 6: Complete */}
        {step === "complete" && (
          <motion.div
            key="complete"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex flex-col items-center justify-center py-16"
          >
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 200, damping: 10 }}
              className="w-20 h-20 rounded-full bg-green-500/20 flex items-center justify-center mb-6"
            >
              <LucideCheck className="w-10 h-10 text-green-400" />
            </motion.div>
            <p className="text-2xl font-bold text-white mb-2">App Built!</p>
            <p className="text-sm text-gray-400 mb-6">
              {config.name} is ready for testing and deployment
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-md w-full mb-6">
              {(config.platform === "both" || config.platform === "ios") && (
                <div className="p-4 bg-white/5 border border-white/10 rounded-xl text-center">
                  <LucideApple className="w-8 h-8 text-white mx-auto mb-2" />
                  <p className="text-sm font-medium text-white">iOS Build</p>
                  <p className="text-xs text-green-400 mt-1">Ready for TestFlight</p>
                </div>
              )}
              {(config.platform === "both" || config.platform === "android") && (
                <div className="p-4 bg-white/5 border border-white/10 rounded-xl text-center">
                  <LucidePlay className="w-8 h-8 text-green-400 mx-auto mb-2" />
                  <p className="text-sm font-medium text-white">Android Build</p>
                  <p className="text-xs text-green-400 mt-1">Ready for Play Store</p>
                </div>
              )}
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => {
                  setStep("config");
                  setConfig({
                    name: "",
                    description: "",
                    platform: "both",
                    template: "blank",
                    primaryColor: "#3B82F6",
                    icon: "",
                    splashColor: "#0d1117",
                    bundleId: "",
                    version: "1.0.0",
                  });
                }}
                className="px-4 py-2 bg-white/5 border border-white/10 text-gray-300 rounded-xl text-sm hover:bg-white/10"
              >
                Build Another App
              </button>
              <button className="flex items-center gap-2 px-4 py-2 bg-purple-500 hover:bg-purple-600 text-white rounded-xl text-sm font-medium">
                <LucideRocket className="w-4 h-4" /> Submit to App Store
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
