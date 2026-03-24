import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LucideCpu,
  LucideZap,
  LucideDollarSign,
  LucideGlobe,
  LucideSearch,
  LucideFilter,
  LucideExternalLink,
  LucideRocket,
  LucideServer,
  LucideCloud,
  LucideActivity,
  LucideX,
  LucideCheck,
  LucideLoader2,
  LucideClock,
  LucideHardDrive,
  LucideArrowUpDown,
} from "lucide-react";
import { AnimatedGradientText } from "#/components/ui/animated-gradient-text";

type GpuStatus = "available" | "limited" | "unavailable";
type BillingModel = "per-second" | "per-minute" | "per-hour" | "reserved";

interface GpuProvider {
  id: string;
  name: string;
  logo: string;
  description: string;
  website: string;
  gpuTypes: GpuType[];
  billingModel: BillingModel;
  minBilling: string;
  features: string[];
  regions: string[];
  category: "specialist" | "marketplace" | "serverless" | "hyperscaler";
}

interface GpuType {
  name: string;
  vram: string;
  pricePerHour: number;
  status: GpuStatus;
  performance: string;
}

const GPU_PROVIDERS: GpuProvider[] = [
  {
    id: "runpod",
    name: "RunPod",
    logo: "RP",
    description: "GPU cloud with FlashBoot fast cold starts, serverless endpoints, and per-second billing",
    website: "https://runpod.io",
    billingModel: "per-second",
    minBilling: "1 second",
    features: ["Serverless Endpoints", "FlashBoot (<200ms)", "Docker Support", "GitHub Deploy", "Persistent Storage"],
    regions: ["US", "EU", "Canada"],
    category: "specialist",
    gpuTypes: [
      { name: "NVIDIA H100 80GB", vram: "80GB", pricePerHour: 2.39, status: "available", performance: "3958 TFLOPS" },
      { name: "NVIDIA A100 80GB", vram: "80GB", pricePerHour: 1.09, status: "available", performance: "624 TFLOPS" },
      { name: "NVIDIA RTX 4090", vram: "24GB", pricePerHour: 0.44, status: "available", performance: "330 TFLOPS" },
      { name: "NVIDIA H200", vram: "141GB", pricePerHour: 3.29, status: "limited", performance: "3958 TFLOPS" },
    ],
  },
  {
    id: "lambda",
    name: "Lambda Labs",
    logo: "λ",
    description: "GPU cloud built for deep learning with pre-configured ML environments",
    website: "https://lambdalabs.com",
    billingModel: "per-hour",
    minBilling: "1 hour",
    features: ["Pre-configured ML Stack", "Jupyter Notebooks", "NFS Storage", "Multi-node Training"],
    regions: ["US West", "US East", "US South"],
    category: "specialist",
    gpuTypes: [
      { name: "NVIDIA H100 80GB", vram: "80GB", pricePerHour: 2.49, status: "limited", performance: "3958 TFLOPS" },
      { name: "NVIDIA A100 80GB", vram: "80GB", pricePerHour: 1.29, status: "available", performance: "624 TFLOPS" },
      { name: "NVIDIA H200", vram: "141GB", pricePerHour: 3.49, status: "unavailable", performance: "3958 TFLOPS" },
    ],
  },
  {
    id: "vastai",
    name: "Vast.ai",
    logo: "V",
    description: "GPU marketplace with lowest prices from community and data center providers",
    website: "https://vast.ai",
    billingModel: "per-minute",
    minBilling: "1 minute",
    features: ["Community GPUs", "Spot Pricing", "Docker Images", "SSH Access", "Jupiter Support"],
    regions: ["Global (30+ locations)"],
    category: "marketplace",
    gpuTypes: [
      { name: "NVIDIA H100 80GB", vram: "80GB", pricePerHour: 1.75, status: "available", performance: "3958 TFLOPS" },
      { name: "NVIDIA A100 80GB", vram: "80GB", pricePerHour: 0.85, status: "available", performance: "624 TFLOPS" },
      { name: "NVIDIA RTX 4090", vram: "24GB", pricePerHour: 0.28, status: "available", performance: "330 TFLOPS" },
      { name: "NVIDIA RTX 3090", vram: "24GB", pricePerHour: 0.16, status: "available", performance: "142 TFLOPS" },
    ],
  },
  {
    id: "coreweave",
    name: "CoreWeave",
    logo: "CW",
    description: "Enterprise GPU cloud with Kubernetes-native infrastructure and InfiniBand networking",
    website: "https://coreweave.com",
    billingModel: "per-minute",
    minBilling: "10 minutes",
    features: ["Kubernetes Native", "InfiniBand", "256+ Multi-node", "Block + NFS Storage", "Enterprise SLA"],
    regions: ["US East", "US Central", "US West", "EU"],
    category: "specialist",
    gpuTypes: [
      { name: "NVIDIA H100 80GB", vram: "80GB", pricePerHour: 2.23, status: "available", performance: "3958 TFLOPS" },
      { name: "NVIDIA A100 80GB", vram: "80GB", pricePerHour: 1.02, status: "available", performance: "624 TFLOPS" },
      { name: "NVIDIA H200", vram: "141GB", pricePerHour: 3.19, status: "limited", performance: "3958 TFLOPS" },
    ],
  },
  {
    id: "modal",
    name: "Modal",
    logo: "M",
    description: "Serverless GPU platform with Python-first SDK and per-second billing",
    website: "https://modal.com",
    billingModel: "per-second",
    minBilling: "1 second",
    features: ["Python SDK", "Zero Cold Starts", "Auto-scaling", "Web Endpoints", "Cron Jobs"],
    regions: ["US"],
    category: "serverless",
    gpuTypes: [
      { name: "NVIDIA H100 80GB", vram: "80GB", pricePerHour: 2.89, status: "available", performance: "3958 TFLOPS" },
      { name: "NVIDIA A100 80GB", vram: "80GB", pricePerHour: 1.38, status: "available", performance: "624 TFLOPS" },
      { name: "NVIDIA A10G", vram: "24GB", pricePerHour: 0.36, status: "available", performance: "125 TFLOPS" },
    ],
  },
  {
    id: "paperspace",
    name: "Paperspace",
    logo: "PS",
    description: "Cloud GPU platform with Gradient notebooks and managed ML workflows",
    website: "https://paperspace.com",
    billingModel: "per-hour",
    minBilling: "1 hour",
    features: ["Gradient Notebooks", "ML Pipelines", "Persistent Storage", "Team Collaboration"],
    regions: ["US East", "US West", "EU"],
    category: "specialist",
    gpuTypes: [
      { name: "NVIDIA A100 80GB", vram: "80GB", pricePerHour: 1.89, status: "available", performance: "624 TFLOPS" },
      { name: "NVIDIA RTX A6000", vram: "48GB", pricePerHour: 0.76, status: "available", performance: "155 TFLOPS" },
    ],
  },
  {
    id: "tensordock",
    name: "TensorDock",
    logo: "TD",
    description: "Affordable GPU cloud with wide selection and flexible configurations",
    website: "https://tensordock.com",
    billingModel: "per-hour",
    minBilling: "1 hour",
    features: ["Custom Configs", "SSH Access", "Docker Support", "API Access"],
    regions: ["US", "EU", "Asia"],
    category: "marketplace",
    gpuTypes: [
      { name: "NVIDIA A100 80GB", vram: "80GB", pricePerHour: 1.10, status: "available", performance: "624 TFLOPS" },
      { name: "NVIDIA RTX 4090", vram: "24GB", pricePerHour: 0.35, status: "available", performance: "330 TFLOPS" },
    ],
  },
];

const STATUS_BADGE: Record<GpuStatus, { color: string; label: string }> = {
  available: { color: "bg-green-500/20 text-green-400", label: "Available" },
  limited: { color: "bg-yellow-500/20 text-yellow-400", label: "Limited" },
  unavailable: { color: "bg-red-500/20 text-red-400", label: "Unavailable" },
};

const CATEGORY_LABELS: Record<string, string> = {
  specialist: "AI-Native Specialist",
  marketplace: "GPU Marketplace",
  serverless: "Serverless Platform",
  hyperscaler: "Hyperscaler",
};

type SortBy = "price" | "vram" | "name";

export function GpuHub() {
  const [search, setSearch] = useState("");
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [sortBy, setSortBy] = useState<SortBy>("price");
  const [showLaunchModal, setShowLaunchModal] = useState<{ provider: GpuProvider; gpu: GpuType } | null>(null);

  const filteredProviders = GPU_PROVIDERS.filter((p) => {
    const matchesSearch = p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.description.toLowerCase().includes(search.toLowerCase()) ||
      p.gpuTypes.some((g) => g.name.toLowerCase().includes(search.toLowerCase()));
    const matchesCategory = filterCategory === "all" || p.category === filterCategory;
    return matchesSearch && matchesCategory;
  });

  // Flatten all GPUs for comparison view
  const allGpus = filteredProviders.flatMap((p) =>
    p.gpuTypes.map((g) => ({ ...g, providerId: p.id, providerName: p.name })),
  );

  const sortedGpus = [...allGpus].sort((a, b) => {
    if (sortBy === "price") return a.pricePerHour - b.pricePerHour;
    if (sortBy === "vram") return parseInt(b.vram) - parseInt(a.vram);
    return a.name.localeCompare(b.name);
  });

  return (
    <div className="h-full overflow-y-auto custom-scrollbar-always p-6 lg:p-8">
      {/* Header */}
      <div className="mb-6">
        <AnimatedGradientText as="h1" className="text-2xl font-bold" gradient="from-orange-400 via-red-400 to-pink-400">
          Cloud GPU Hub
        </AnimatedGradientText>
        <p className="text-sm text-gray-400 mt-1">
          Rent GPU servers from top providers — compare prices, availability, and launch instances
        </p>
      </div>

      {/* Search & Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <div className="relative flex-1 min-w-[200px]">
          <LucideSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search providers or GPU types..."
            className="w-full pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 text-sm focus:outline-none focus:border-orange-500/50"
          />
        </div>
        <div className="flex gap-2">
          {["all", "specialist", "marketplace", "serverless"].map((cat) => (
            <button
              key={cat}
              onClick={() => setFilterCategory(cat)}
              className={`px-3 py-2 rounded-xl text-xs font-medium transition-colors ${
                filterCategory === cat
                  ? "bg-orange-500/20 text-orange-400 border border-orange-500/30"
                  : "bg-white/5 text-gray-400 border border-white/10 hover:border-white/20"
              }`}
            >
              {cat === "all" ? "All" : CATEGORY_LABELS[cat]}
            </button>
          ))}
        </div>
      </div>

      {/* Quick Price Comparison Table */}
      <div className="mb-8 p-5 bg-white/5 border border-white/10 rounded-2xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <LucideDollarSign className="w-4 h-4 text-green-400" /> GPU Price Comparison
          </h2>
          <div className="flex gap-2">
            {(["price", "vram", "name"] as SortBy[]).map((s) => (
              <button
                key={s}
                onClick={() => setSortBy(s)}
                className={`flex items-center gap-1 px-2 py-1 rounded-lg text-xs ${
                  sortBy === s ? "bg-white/10 text-white" : "text-gray-500 hover:text-gray-300"
                }`}
              >
                <LucideArrowUpDown className="w-3 h-3" />
                {s === "price" ? "Price" : s === "vram" ? "VRAM" : "Name"}
              </button>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b border-white/5">
                <th className="text-left py-2 pr-4">GPU</th>
                <th className="text-left py-2 pr-4">Provider</th>
                <th className="text-right py-2 pr-4">$/hour</th>
                <th className="text-right py-2 pr-4">VRAM</th>
                <th className="text-center py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {sortedGpus.slice(0, 12).map((gpu, i) => (
                <tr key={`${gpu.providerId}-${gpu.name}-${i}`} className="border-b border-white/5 hover:bg-white/5">
                  <td className="py-2 pr-4 text-white font-medium">{gpu.name}</td>
                  <td className="py-2 pr-4 text-gray-400">{gpu.providerName}</td>
                  <td className="py-2 pr-4 text-right text-green-400 font-mono">${gpu.pricePerHour.toFixed(2)}</td>
                  <td className="py-2 pr-4 text-right text-gray-300">{gpu.vram}</td>
                  <td className="py-2 text-center">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_BADGE[gpu.status].color}`}>
                      {STATUS_BADGE[gpu.status].label}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Provider Cards */}
      <h2 className="text-sm font-semibold text-white mb-4">Providers</h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
        {filteredProviders.map((provider) => (
          <motion.div
            key={provider.id}
            layout
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-5 bg-white/5 border border-white/10 rounded-2xl hover:border-white/20 transition-colors"
          >
            {/* Header */}
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center text-white text-sm font-bold">
                  {provider.logo}
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">{provider.name}</h3>
                  <span className="text-xs text-gray-500">{CATEGORY_LABELS[provider.category]}</span>
                </div>
              </div>
              <a
                href={provider.website}
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-500 hover:text-white"
              >
                <LucideExternalLink className="w-4 h-4" />
              </a>
            </div>

            <p className="text-xs text-gray-400 mb-3">{provider.description}</p>

            {/* Features */}
            <div className="flex flex-wrap gap-1.5 mb-3">
              {provider.features.slice(0, 4).map((f) => (
                <span key={f} className="px-2 py-0.5 bg-white/5 rounded-md text-xs text-gray-400">{f}</span>
              ))}
            </div>

            {/* GPU list */}
            <div className="space-y-2 mb-3">
              {provider.gpuTypes.slice(0, 3).map((gpu) => (
                <div key={gpu.name} className="flex items-center justify-between py-1.5 px-3 bg-white/5 rounded-lg">
                  <div className="flex items-center gap-2">
                    <LucideCpu className="w-3 h-3 text-orange-400" />
                    <span className="text-xs text-white">{gpu.name}</span>
                    <span className="text-xs text-gray-500">{gpu.vram}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-green-400 font-mono">${gpu.pricePerHour.toFixed(2)}/hr</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${STATUS_BADGE[gpu.status].color}`}>
                      {STATUS_BADGE[gpu.status].label}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Billing & Regions */}
            <div className="flex items-center justify-between text-xs text-gray-500">
              <div className="flex items-center gap-1">
                <LucideClock className="w-3 h-3" /> Min: {provider.minBilling}
              </div>
              <div className="flex items-center gap-1">
                <LucideGlobe className="w-3 h-3" /> {provider.regions.length > 1 ? `${provider.regions.length} regions` : provider.regions[0]}
              </div>
            </div>

            {/* Launch button */}
            <button
              onClick={() => {
                const availableGpu = provider.gpuTypes.find((g) => g.status === "available");
                if (availableGpu) setShowLaunchModal({ provider, gpu: availableGpu });
              }}
              className="w-full mt-3 flex items-center justify-center gap-2 px-4 py-2 bg-orange-500/20 text-orange-400 rounded-xl text-xs hover:bg-orange-500/30 transition-colors"
            >
              <LucideRocket className="w-3 h-3" /> Launch Instance
            </button>
          </motion.div>
        ))}
      </div>

      {/* Launch Modal */}
      <AnimatePresence>
        {showLaunchModal && (
          <LaunchModal
            provider={showLaunchModal.provider}
            gpu={showLaunchModal.gpu}
            onClose={() => setShowLaunchModal(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function LaunchModal({
  provider,
  gpu,
  onClose,
}: {
  provider: GpuProvider;
  gpu: GpuType;
  onClose: () => void;
}) {
  const [selectedGpu, setSelectedGpu] = useState(gpu.name);
  const [instanceName, setInstanceName] = useState("");
  const [dockerImage, setDockerImage] = useState("");
  const [launching, setLaunching] = useState(false);
  const [launched, setLaunched] = useState(false);

  const handleLaunch = () => {
    setLaunching(true);
    setTimeout(() => {
      setLaunching(false);
      setLaunched(true);
    }, 3000);
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95 }}
        animate={{ scale: 1 }}
        exit={{ scale: 0.95 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md bg-[#161b22] border border-white/10 rounded-2xl overflow-hidden"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <h2 className="text-lg font-semibold text-white">Launch on {provider.name}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <LucideX className="w-5 h-5" />
          </button>
        </div>

        {!launched ? (
          <div className="p-6 space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">GPU Type</label>
              <select
                value={selectedGpu}
                onChange={(e) => setSelectedGpu(e.target.value)}
                className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white text-sm focus:outline-none focus:border-orange-500/50 appearance-none"
              >
                {provider.gpuTypes.filter((g) => g.status !== "unavailable").map((g) => (
                  <option key={g.name} value={g.name}>{g.name} — {g.vram} — ${g.pricePerHour}/hr</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Instance Name</label>
              <input
                type="text"
                value={instanceName}
                onChange={(e) => setInstanceName(e.target.value)}
                placeholder="my-training-run"
                className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 text-sm font-mono focus:outline-none focus:border-orange-500/50"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Docker Image (optional)</label>
              <input
                type="text"
                value={dockerImage}
                onChange={(e) => setDockerImage(e.target.value)}
                placeholder="runpod/pytorch:2.1.0-py3.10-cuda12.1"
                className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 text-sm font-mono focus:outline-none focus:border-orange-500/50"
              />
            </div>

            <div className="p-3 bg-orange-500/10 border border-orange-500/20 rounded-xl">
              <p className="text-xs text-orange-300">
                You will need a {provider.name} API key configured in Integrations to launch instances. 
                The agent will handle provisioning via the provider&#39;s API.
              </p>
            </div>

            <div className="flex justify-end gap-3">
              <button onClick={onClose} className="px-4 py-2 text-gray-400 hover:text-white text-sm">Cancel</button>
              <button
                onClick={handleLaunch}
                disabled={launching}
                className="flex items-center gap-2 px-5 py-2 bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 text-white rounded-xl text-sm font-medium disabled:opacity-50"
              >
                {launching ? <LucideLoader2 className="w-4 h-4 animate-spin" /> : <LucideRocket className="w-4 h-4" />}
                {launching ? "Launching..." : "Launch"}
              </button>
            </div>
          </div>
        ) : (
          <div className="p-6 text-center">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 200, damping: 10 }}
              className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4"
            >
              <LucideCheck className="w-8 h-8 text-green-400" />
            </motion.div>
            <p className="text-lg font-semibold text-white mb-1">Instance Launched!</p>
            <p className="text-sm text-gray-400 mb-4">Your GPU instance on {provider.name} is starting up</p>
            <button
              onClick={onClose}
              className="px-5 py-2 bg-white/10 text-white rounded-xl text-sm hover:bg-white/15"
            >
              Close
            </button>
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}
