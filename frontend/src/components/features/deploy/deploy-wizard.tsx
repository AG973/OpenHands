import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LucideCloud,
  LucideRocket,
  LucideCheck,
  LucideLoader2,
  LucideArrowRight,
  LucideArrowLeft,
  LucideGlobe,
  LucideServer,
  LucideDatabase,
  LucideShield,
  LucideZap,
  LucideSettings,
  LucideExternalLink,
} from "lucide-react";
import { AnimatedGradientText } from "#/components/ui/animated-gradient-text";

type DeployTarget =
  | "vercel"
  | "netlify"
  | "aws-s3"
  | "aws-ec2"
  | "aws-lambda"
  | "aws-ecs"
  | "gcp-cloudrun"
  | "gcp-appengine"
  | "azure-appservice"
  | "railway"
  | "flyio"
  | "digitalocean"
  | "cloudflare";

interface DeployTargetInfo {
  id: DeployTarget;
  name: string;
  icon: string;
  description: string;
  bestFor: string;
  difficulty: "easy" | "medium" | "advanced";
  estimatedTime: string;
}

const DEPLOY_TARGETS: DeployTargetInfo[] = [
  {
    id: "vercel",
    name: "Vercel",
    icon: "\u25B2",
    description: "Best for React, Next.js, and static sites",
    bestFor: "Frontend apps",
    difficulty: "easy",
    estimatedTime: "~2 min",
  },
  {
    id: "netlify",
    name: "Netlify",
    icon: "\uD83C\uDF10",
    description: "Static sites with serverless functions",
    bestFor: "Static sites & JAMstack",
    difficulty: "easy",
    estimatedTime: "~2 min",
  },
  {
    id: "railway",
    name: "Railway",
    icon: "\uD83D\uDE82",
    description: "Full-stack apps with databases included",
    bestFor: "Full-stack apps",
    difficulty: "easy",
    estimatedTime: "~3 min",
  },
  {
    id: "flyio",
    name: "Fly.io",
    icon: "\u2708\uFE0F",
    description: "Deploy globally with edge networking",
    bestFor: "Backend APIs & services",
    difficulty: "medium",
    estimatedTime: "~5 min",
  },
  {
    id: "aws-s3",
    name: "AWS S3 + CloudFront",
    icon: "\u2601\uFE0F",
    description: "Static hosting with CDN for maximum performance",
    bestFor: "High-traffic static sites",
    difficulty: "medium",
    estimatedTime: "~5 min",
  },
  {
    id: "aws-ec2",
    name: "AWS EC2",
    icon: "\u2601\uFE0F",
    description: "Full virtual machine for complete control",
    bestFor: "Custom server setup",
    difficulty: "advanced",
    estimatedTime: "~10 min",
  },
  {
    id: "aws-lambda",
    name: "AWS Lambda",
    icon: "\u2601\uFE0F",
    description: "Serverless functions — pay only for what you use",
    bestFor: "APIs & microservices",
    difficulty: "medium",
    estimatedTime: "~5 min",
  },
  {
    id: "aws-ecs",
    name: "AWS ECS (Containers)",
    icon: "\u2601\uFE0F",
    description: "Container orchestration for complex applications",
    bestFor: "Containerized apps",
    difficulty: "advanced",
    estimatedTime: "~15 min",
  },
  {
    id: "gcp-cloudrun",
    name: "Google Cloud Run",
    icon: "\uD83C\uDF10",
    description: "Serverless containers that scale to zero",
    bestFor: "Containerized APIs",
    difficulty: "medium",
    estimatedTime: "~5 min",
  },
  {
    id: "gcp-appengine",
    name: "Google App Engine",
    icon: "\uD83C\uDF10",
    description: "Fully managed platform for web applications",
    bestFor: "Web applications",
    difficulty: "medium",
    estimatedTime: "~5 min",
  },
  {
    id: "azure-appservice",
    name: "Azure App Service",
    icon: "\uD83D\uDFE6",
    description: "Fully managed web hosting on Microsoft Azure",
    bestFor: "Enterprise web apps",
    difficulty: "medium",
    estimatedTime: "~5 min",
  },
  {
    id: "digitalocean",
    name: "DigitalOcean App Platform",
    icon: "\uD83D\uDCA7",
    description: "Simple deployment for apps and databases",
    bestFor: "Small to medium apps",
    difficulty: "easy",
    estimatedTime: "~3 min",
  },
  {
    id: "cloudflare",
    name: "Cloudflare Pages & Workers",
    icon: "\uD83D\uDD36",
    description: "Edge-first deployment with global CDN",
    bestFor: "Edge computing & static sites",
    difficulty: "easy",
    estimatedTime: "~2 min",
  },
];

const DIFFICULTY_COLORS = {
  easy: { bg: "bg-green-500/10", text: "text-green-400", border: "border-green-500/30" },
  medium: { bg: "bg-yellow-500/10", text: "text-yellow-400", border: "border-yellow-500/30" },
  advanced: { bg: "bg-red-500/10", text: "text-red-400", border: "border-red-500/30" },
};

type WizardStep = "target" | "config" | "review" | "deploying" | "complete";

interface DeployConfig {
  projectName: string;
  buildCommand: string;
  outputDir: string;
  envVars: { key: string; value: string }[];
  region: string;
  autoDeploy: boolean;
  customDomain: string;
}

export function DeployWizard() {
  const [step, setStep] = useState<WizardStep>("target");
  const [selectedTarget, setSelectedTarget] = useState<DeployTarget | null>(null);
  const [config, setConfig] = useState<DeployConfig>({
    projectName: "",
    buildCommand: "npm run build",
    outputDir: "dist",
    envVars: [{ key: "", value: "" }],
    region: "us-east-1",
    autoDeploy: true,
    customDomain: "",
  });
  const [deployUrl, setDeployUrl] = useState("");
  const [filterDifficulty, setFilterDifficulty] = useState<"all" | "easy" | "medium" | "advanced">("all");

  const selectedTargetInfo = DEPLOY_TARGETS.find((t) => t.id === selectedTarget);

  const filteredTargets = DEPLOY_TARGETS.filter(
    (t) => filterDifficulty === "all" || t.difficulty === filterDifficulty,
  );

  const addEnvVar = () => {
    setConfig({ ...config, envVars: [...config.envVars, { key: "", value: "" }] });
  };

  const removeEnvVar = (index: number) => {
    setConfig({
      ...config,
      envVars: config.envVars.filter((_, i) => i !== index),
    });
  };

  const updateEnvVar = (index: number, field: "key" | "value", val: string) => {
    const newVars = [...config.envVars];
    newVars[index] = { ...newVars[index], [field]: val };
    setConfig({ ...config, envVars: newVars });
  };

  const handleDeploy = () => {
    setStep("deploying");
    setTimeout(() => {
      setDeployUrl(`https://${config.projectName || "my-app"}.${selectedTarget === "vercel" ? "vercel.app" : selectedTarget === "netlify" ? "netlify.app" : "example.com"}`);
      setStep("complete");
    }, 4000);
  };

  return (
    <div className="h-full overflow-y-auto custom-scrollbar-always p-6 lg:p-8">
      {/* Header */}
      <div className="mb-6">
        <AnimatedGradientText as="h1" className="text-2xl font-bold" gradient="from-orange-400 via-red-400 to-pink-400">
          Cloud Deployment
        </AnimatedGradientText>
        <p className="text-sm text-gray-400 mt-1">
          Deploy your project to the cloud in minutes — no terminal needed
        </p>
      </div>

      {/* Progress Steps */}
      <div className="flex items-center gap-2 mb-8 overflow-x-auto">
        {(
          [
            { key: "target", label: "Choose Target" },
            { key: "config", label: "Configure" },
            { key: "review", label: "Review" },
            { key: "deploying", label: "Deploy" },
            { key: "complete", label: "Done" },
          ] as { key: WizardStep; label: string }[]
        ).map((s, i) => {
          const steps: WizardStep[] = ["target", "config", "review", "deploying", "complete"];
          const currentIndex = steps.indexOf(step);
          const stepIndex = steps.indexOf(s.key);
          const isActive = s.key === step;
          const isDone = stepIndex < currentIndex;
          return (
            <React.Fragment key={s.key}>
              {i > 0 && (
                <div className={`h-px flex-1 min-w-[20px] ${isDone ? "bg-blue-500" : "bg-white/10"}`} />
              )}
              <div
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap ${
                  isActive
                    ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
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

      {/* Step Content */}
      <AnimatePresence mode="wait">
        {/* Step 1: Choose Target */}
        {step === "target" && (
          <motion.div
            key="target"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
          >
            {/* Difficulty filter */}
            <div className="flex items-center gap-2 mb-4">
              <LucideSettings className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-400">Complexity:</span>
              {(["all", "easy", "medium", "advanced"] as const).map((d) => (
                <button
                  key={d}
                  onClick={() => setFilterDifficulty(d)}
                  className={`px-3 py-1 text-xs rounded-full capitalize ${
                    filterDifficulty === d
                      ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                      : "bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10"
                  }`}
                >
                  {d === "all" ? "All" : d}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {filteredTargets.map((target) => {
                const diffColors = DIFFICULTY_COLORS[target.difficulty];
                return (
                  <button
                    key={target.id}
                    onClick={() => setSelectedTarget(target.id)}
                    className={`text-left p-5 rounded-2xl border transition-all ${
                      selectedTarget === target.id
                        ? "border-blue-500/50 bg-blue-500/10 ring-1 ring-blue-500/20"
                        : "border-white/10 bg-white/5 hover:border-white/20"
                    }`}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-2xl">{target.icon}</span>
                      <div>
                        <h3 className="text-sm font-semibold text-white">{target.name}</h3>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${diffColors.bg} ${diffColors.text} ${diffColors.border} border`}>
                          {target.difficulty} · {target.estimatedTime}
                        </span>
                      </div>
                    </div>
                    <p className="text-sm text-gray-400 mb-2">{target.description}</p>
                    <p className="text-xs text-gray-500">Best for: {target.bestFor}</p>
                  </button>
                );
              })}
            </div>

            <div className="flex justify-end mt-6">
              <button
                onClick={() => setStep("config")}
                disabled={!selectedTarget}
                className="flex items-center gap-2 px-5 py-2.5 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl text-sm font-medium transition-colors"
              >
                Next <LucideArrowRight className="w-4 h-4" />
              </button>
            </div>
          </motion.div>
        )}

        {/* Step 2: Configure */}
        {step === "config" && (
          <motion.div
            key="config"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="max-w-2xl space-y-5"
          >
            <div className="flex items-center gap-3 p-4 bg-white/5 border border-white/10 rounded-xl mb-6">
              <span className="text-2xl">{selectedTargetInfo?.icon}</span>
              <div>
                <p className="text-sm font-medium text-white">Deploying to {selectedTargetInfo?.name}</p>
                <p className="text-xs text-gray-400">{selectedTargetInfo?.description}</p>
              </div>
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Project Name</label>
              <input
                type="text"
                value={config.projectName}
                onChange={(e) => setConfig({ ...config, projectName: e.target.value })}
                placeholder="my-awesome-app"
                className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 text-sm"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">Build Command</label>
                <input
                  type="text"
                  value={config.buildCommand}
                  onChange={(e) => setConfig({ ...config, buildCommand: e.target.value })}
                  className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white text-sm font-mono focus:outline-none focus:border-blue-500/50"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">Output Directory</label>
                <input
                  type="text"
                  value={config.outputDir}
                  onChange={(e) => setConfig({ ...config, outputDir: e.target.value })}
                  className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white text-sm font-mono focus:outline-none focus:border-blue-500/50"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Custom Domain (optional)</label>
              <input
                type="text"
                value={config.customDomain}
                onChange={(e) => setConfig({ ...config, customDomain: e.target.value })}
                placeholder="app.example.com"
                className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 text-sm focus:outline-none focus:border-blue-500/50"
              />
            </div>

            {/* Environment Variables */}
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Environment Variables</label>
              <div className="space-y-2">
                {config.envVars.map((envVar, index) => (
                  <div key={index} className="flex gap-2">
                    <input
                      type="text"
                      value={envVar.key}
                      onChange={(e) => updateEnvVar(index, "key", e.target.value)}
                      placeholder="KEY"
                      className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm font-mono placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
                    />
                    <input
                      type="password"
                      value={envVar.value}
                      onChange={(e) => updateEnvVar(index, "value", e.target.value)}
                      placeholder="value"
                      className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm font-mono placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
                    />
                    {config.envVars.length > 1 && (
                      <button
                        onClick={() => removeEnvVar(index)}
                        className="px-2 text-gray-500 hover:text-red-400"
                      >
                        ×
                      </button>
                    )}
                  </div>
                ))}
                <button
                  onClick={addEnvVar}
                  className="text-xs text-blue-400 hover:text-blue-300"
                >
                  + Add variable
                </button>
              </div>
            </div>

            {/* Auto-deploy toggle */}
            <label className="flex items-center gap-3 p-3 bg-white/5 border border-white/10 rounded-xl cursor-pointer">
              <input
                type="checkbox"
                checked={config.autoDeploy}
                onChange={(e) => setConfig({ ...config, autoDeploy: e.target.checked })}
                className="w-4 h-4 rounded"
              />
              <div>
                <p className="text-sm text-white">Auto-deploy on push</p>
                <p className="text-xs text-gray-500">Automatically redeploy when you push changes</p>
              </div>
            </label>

            <div className="flex justify-between mt-6">
              <button
                onClick={() => setStep("target")}
                className="flex items-center gap-2 px-4 py-2 text-gray-400 hover:text-white transition-colors"
              >
                <LucideArrowLeft className="w-4 h-4" /> Back
              </button>
              <button
                onClick={() => setStep("review")}
                className="flex items-center gap-2 px-5 py-2.5 bg-blue-500 hover:bg-blue-600 text-white rounded-xl text-sm font-medium transition-colors"
              >
                Next <LucideArrowRight className="w-4 h-4" />
              </button>
            </div>
          </motion.div>
        )}

        {/* Step 3: Review */}
        {step === "review" && (
          <motion.div
            key="review"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="max-w-2xl"
          >
            <div className="p-6 bg-white/5 border border-white/10 rounded-2xl space-y-4">
              <h3 className="text-lg font-semibold text-white">Review Deployment</h3>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-gray-500">Target</p>
                  <p className="text-sm text-white flex items-center gap-2">
                    <span>{selectedTargetInfo?.icon}</span> {selectedTargetInfo?.name}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Project</p>
                  <p className="text-sm text-white">{config.projectName || "Unnamed"}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Build Command</p>
                  <p className="text-sm text-white font-mono">{config.buildCommand}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Output</p>
                  <p className="text-sm text-white font-mono">{config.outputDir}</p>
                </div>
              </div>

              {config.customDomain && (
                <div>
                  <p className="text-xs text-gray-500">Custom Domain</p>
                  <p className="text-sm text-white">{config.customDomain}</p>
                </div>
              )}

              {config.envVars.some((v) => v.key) && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">Environment Variables</p>
                  <div className="flex flex-wrap gap-1">
                    {config.envVars
                      .filter((v) => v.key)
                      .map((v) => (
                        <span key={v.key} className="px-2 py-0.5 text-xs bg-white/10 text-gray-300 rounded font-mono">
                          {v.key}
                        </span>
                      ))}
                  </div>
                </div>
              )}

              <div className="flex items-center gap-2 p-3 bg-green-500/10 border border-green-500/20 rounded-xl">
                <LucideShield className="w-4 h-4 text-green-400 shrink-0" />
                <p className="text-xs text-green-300">
                  All secrets will be encrypted and stored securely. They are never exposed in logs or source code.
                </p>
              </div>
            </div>

            <div className="flex justify-between mt-6">
              <button
                onClick={() => setStep("config")}
                className="flex items-center gap-2 px-4 py-2 text-gray-400 hover:text-white transition-colors"
              >
                <LucideArrowLeft className="w-4 h-4" /> Back
              </button>
              <button
                onClick={handleDeploy}
                className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white rounded-xl text-sm font-medium transition-all"
              >
                <LucideRocket className="w-4 h-4" /> Deploy Now
              </button>
            </div>
          </motion.div>
        )}

        {/* Step 4: Deploying */}
        {step === "deploying" && (
          <motion.div
            key="deploying"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="flex flex-col items-center justify-center py-16"
          >
            <div className="relative mb-8">
              <LucideCloud className="w-20 h-20 text-blue-400/30" />
              <motion.div
                animate={{ y: [-5, 5, -5] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="absolute inset-0 flex items-center justify-center"
              >
                <LucideRocket className="w-8 h-8 text-blue-400" />
              </motion.div>
            </div>
            <p className="text-xl font-semibold text-white mb-2">Deploying to {selectedTargetInfo?.name}...</p>
            <p className="text-sm text-gray-400 mb-6">This usually takes {selectedTargetInfo?.estimatedTime}</p>
            <div className="w-64 h-2 bg-white/10 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full"
                initial={{ width: "0%" }}
                animate={{ width: "100%" }}
                transition={{ duration: 3.5, ease: "easeInOut" }}
              />
            </div>
          </motion.div>
        )}

        {/* Step 5: Complete */}
        {step === "complete" && (
          <motion.div
            key="complete"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
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
            <p className="text-2xl font-bold text-white mb-2">Deployed!</p>
            <p className="text-sm text-gray-400 mb-6">
              Your project is live on {selectedTargetInfo?.name}
            </p>

            <div className="p-4 bg-white/5 border border-white/10 rounded-xl mb-6">
              <p className="text-xs text-gray-500 mb-1">Live URL</p>
              <a
                href={deployUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-blue-400 hover:text-blue-300"
              >
                <LucideGlobe className="w-4 h-4" />
                {deployUrl}
                <LucideExternalLink className="w-3 h-3" />
              </a>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => {
                  setStep("target");
                  setSelectedTarget(null);
                }}
                className="px-4 py-2 bg-white/5 border border-white/10 text-gray-300 rounded-xl text-sm hover:bg-white/10"
              >
                Deploy Another
              </button>
              <a
                href={deployUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-xl text-sm font-medium"
              >
                <LucideExternalLink className="w-4 h-4" /> Visit Site
              </a>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
