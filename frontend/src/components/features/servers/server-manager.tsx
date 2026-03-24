import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LucideServer,
  LucideMonitor,
  LucideCloud,
  LucidePlus,
  LucideTrash2,
  LucideRefreshCw,
  LucideTerminal,
  LucideWifi,
  LucideWifiOff,
  LucideShield,
  LucideHardDrive,
  LucideCpu,
  LucideActivity,
  LucideX,
  LucideCheck,
  LucideLoader2,
  LucideGlobe,
  LucideLock,
  LucideKey,
  LucideFolder,
} from "lucide-react";
import { AnimatedGradientText } from "#/components/ui/animated-gradient-text";

type ServerType = "local" | "cloud" | "gpu";
type ConnectionStatus = "connected" | "disconnected" | "connecting" | "error";
type AuthMethod = "password" | "ssh-key" | "token";

interface ServerConnection {
  id: string;
  name: string;
  type: ServerType;
  host: string;
  port: number;
  username: string;
  authMethod: AuthMethod;
  status: ConnectionStatus;
  os?: string;
  cpu?: string;
  ram?: string;
  storage?: string;
  gpu?: string;
  provider?: string;
  region?: string;
  lastConnected?: string;
}

const SAMPLE_SERVERS: ServerConnection[] = [
  {
    id: "1",
    name: "Local Dev Server",
    type: "local",
    host: "192.168.1.100",
    port: 22,
    username: "developer",
    authMethod: "ssh-key",
    status: "disconnected",
    os: "Ubuntu 22.04",
    cpu: "Intel i9-13900K",
    ram: "64GB DDR5",
    storage: "2TB NVMe",
  },
];

const STATUS_CONFIG: Record<ConnectionStatus, { color: string; icon: React.ReactNode; label: string }> = {
  connected: { color: "text-green-400", icon: <LucideWifi className="w-4 h-4" />, label: "Connected" },
  disconnected: { color: "text-gray-500", icon: <LucideWifiOff className="w-4 h-4" />, label: "Disconnected" },
  connecting: { color: "text-yellow-400", icon: <LucideLoader2 className="w-4 h-4 animate-spin" />, label: "Connecting..." },
  error: { color: "text-red-400", icon: <LucideWifiOff className="w-4 h-4" />, label: "Error" },
};

const TYPE_CONFIG: Record<ServerType, { icon: React.ReactNode; label: string; color: string }> = {
  local: { icon: <LucideMonitor className="w-5 h-5" />, label: "Local Server", color: "from-blue-500 to-cyan-500" },
  cloud: { icon: <LucideCloud className="w-5 h-5" />, label: "Cloud Server", color: "from-purple-500 to-pink-500" },
  gpu: { icon: <LucideCpu className="w-5 h-5" />, label: "GPU Server", color: "from-orange-500 to-red-500" },
};

export function ServerManager() {
  const [servers, setServers] = useState<ServerConnection[]>(SAMPLE_SERVERS);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showTerminal, setShowTerminal] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<ServerType | "all">("all");

  const filteredServers = filterType === "all" ? servers : servers.filter((s) => s.type === filterType);

  const handleConnect = (id: string) => {
    setServers((prev) =>
      prev.map((s) => (s.id === id ? { ...s, status: "connecting" as ConnectionStatus } : s)),
    );
    setTimeout(() => {
      setServers((prev) =>
        prev.map((s) =>
          s.id === id
            ? { ...s, status: "connected" as ConnectionStatus, lastConnected: new Date().toISOString() }
            : s,
        ),
      );
    }, 2000);
  };

  const handleDisconnect = (id: string) => {
    setServers((prev) =>
      prev.map((s) => (s.id === id ? { ...s, status: "disconnected" as ConnectionStatus } : s)),
    );
  };

  const handleDelete = (id: string) => {
    setServers((prev) => prev.filter((s) => s.id !== id));
  };

  return (
    <div className="h-full overflow-y-auto custom-scrollbar-always p-6 lg:p-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <AnimatedGradientText as="h1" className="text-2xl font-bold" gradient="from-blue-400 via-cyan-400 to-teal-400">
            Server Manager
          </AnimatedGradientText>
          <p className="text-sm text-gray-400 mt-1">
            Connect to local servers, cloud instances, and GPU machines for testing and deployment
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-blue-500 hover:bg-blue-600 text-white rounded-xl text-sm font-medium transition-colors"
        >
          <LucidePlus className="w-4 h-4" /> Add Server
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-6">
        {(["all", "local", "cloud", "gpu"] as const).map((type) => (
          <button
            key={type}
            onClick={() => setFilterType(type)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
              filterType === type
                ? "bg-white/10 text-white border border-white/20"
                : "text-gray-400 hover:text-white hover:bg-white/5"
            }`}
          >
            {type === "all" ? "All Servers" : TYPE_CONFIG[type].label + "s"}
          </button>
        ))}
      </div>

      {/* Server Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filteredServers.map((server) => {
          const typeConf = TYPE_CONFIG[server.type];
          const statusConf = STATUS_CONFIG[server.status];
          return (
            <motion.div
              key={server.id}
              layout
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="p-5 bg-white/5 border border-white/10 rounded-2xl hover:border-white/20 transition-colors"
            >
              {/* Top row */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${typeConf.color} flex items-center justify-center text-white`}>
                    {typeConf.icon}
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-white">{server.name}</h3>
                    <p className="text-xs text-gray-500 font-mono">{server.username}@{server.host}:{server.port}</p>
                  </div>
                </div>
                <div className={`flex items-center gap-1.5 ${statusConf.color}`}>
                  {statusConf.icon}
                  <span className="text-xs">{statusConf.label}</span>
                </div>
              </div>

              {/* Info grid */}
              <div className="grid grid-cols-2 gap-2 mb-4">
                {server.os && (
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <LucideMonitor className="w-3 h-3 shrink-0" /> {server.os}
                  </div>
                )}
                {server.cpu && (
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <LucideCpu className="w-3 h-3 shrink-0" /> {server.cpu}
                  </div>
                )}
                {server.ram && (
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <LucideActivity className="w-3 h-3 shrink-0" /> {server.ram}
                  </div>
                )}
                {server.storage && (
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <LucideHardDrive className="w-3 h-3 shrink-0" /> {server.storage}
                  </div>
                )}
                {server.gpu && (
                  <div className="flex items-center gap-2 text-xs text-gray-400 col-span-2">
                    <LucideCpu className="w-3 h-3 shrink-0" /> GPU: {server.gpu}
                  </div>
                )}
                {server.provider && (
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <LucideCloud className="w-3 h-3 shrink-0" /> {server.provider}
                  </div>
                )}
                {server.region && (
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <LucideGlobe className="w-3 h-3 shrink-0" /> {server.region}
                  </div>
                )}
              </div>

              {/* Auth badge */}
              <div className="flex items-center gap-2 mb-4">
                <div className="flex items-center gap-1 px-2 py-1 bg-white/5 rounded-lg text-xs text-gray-400">
                  {server.authMethod === "ssh-key" ? <LucideKey className="w-3 h-3" /> : <LucideLock className="w-3 h-3" />}
                  {server.authMethod === "ssh-key" ? "SSH Key" : server.authMethod === "password" ? "Password" : "API Token"}
                </div>
                {server.lastConnected && (
                  <span className="text-xs text-gray-500">
                    Last: {new Date(server.lastConnected).toLocaleDateString()}
                  </span>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2">
                {server.status === "connected" ? (
                  <>
                    <button
                      onClick={() => setShowTerminal(server.id)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-green-500/20 text-green-400 rounded-lg text-xs hover:bg-green-500/30"
                    >
                      <LucideTerminal className="w-3 h-3" /> Terminal
                    </button>
                    <button
                      onClick={() => handleDisconnect(server.id)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 text-gray-400 rounded-lg text-xs hover:bg-white/10"
                    >
                      <LucideWifiOff className="w-3 h-3" /> Disconnect
                    </button>
                  </>
                ) : server.status === "connecting" ? (
                  <button disabled className="flex items-center gap-1.5 px-3 py-1.5 bg-yellow-500/20 text-yellow-400 rounded-lg text-xs">
                    <LucideLoader2 className="w-3 h-3 animate-spin" /> Connecting...
                  </button>
                ) : (
                  <button
                    onClick={() => handleConnect(server.id)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500/20 text-blue-400 rounded-lg text-xs hover:bg-blue-500/30"
                  >
                    <LucideWifi className="w-3 h-3" /> Connect
                  </button>
                )}
                <button
                  onClick={() => handleDelete(server.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 text-gray-500 rounded-lg text-xs hover:bg-red-500/10 hover:text-red-400 ml-auto"
                >
                  <LucideTrash2 className="w-3 h-3" />
                </button>
              </div>
            </motion.div>
          );
        })}

        {/* Empty state */}
        {filteredServers.length === 0 && (
          <div className="col-span-full flex flex-col items-center justify-center py-16 text-center">
            <LucideServer className="w-12 h-12 text-gray-600 mb-4" />
            <p className="text-gray-400 text-sm">No servers configured</p>
            <p className="text-gray-500 text-xs mt-1">Click "Add Server" to connect to a local or cloud machine</p>
          </div>
        )}
      </div>

      {/* Terminal Overlay */}
      <AnimatePresence>
        {showTerminal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6"
          >
            <motion.div
              initial={{ scale: 0.95 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.95 }}
              className="w-full max-w-4xl h-[70vh] bg-[#0d1117] border border-white/10 rounded-2xl overflow-hidden flex flex-col"
            >
              <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
                <div className="flex items-center gap-2">
                  <LucideTerminal className="w-4 h-4 text-green-400" />
                  <span className="text-sm text-white font-medium">
                    Terminal — {servers.find((s) => s.id === showTerminal)?.name}
                  </span>
                </div>
                <button onClick={() => setShowTerminal(null)} className="text-gray-400 hover:text-white">
                  <LucideX className="w-4 h-4" />
                </button>
              </div>
              <div className="flex-1 p-4 font-mono text-sm text-green-400 overflow-auto">
                <p>$ Connected to {servers.find((s) => s.id === showTerminal)?.host}</p>
                <p>$ Welcome to {servers.find((s) => s.id === showTerminal)?.os || "Remote Server"}</p>
                <p className="mt-2">
                  <span className="text-gray-500">{servers.find((s) => s.id === showTerminal)?.username}@{servers.find((s) => s.id === showTerminal)?.host}</span>
                  <span className="text-white">:~$ </span>
                  <span className="animate-pulse">▊</span>
                </p>
                <p className="text-xs text-gray-600 mt-4">
                  (Terminal integration uses xterm.js + SSH2 via WebSocket — connect to real servers when backend is configured)
                </p>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Add Server Modal */}
      <AnimatePresence>
        {showAddModal && (
          <AddServerModal
            onClose={() => setShowAddModal(false)}
            onAdd={(server) => {
              setServers((prev) => [...prev, server]);
              setShowAddModal(false);
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function AddServerModal({
  onClose,
  onAdd,
}: {
  onClose: () => void;
  onAdd: (server: ServerConnection) => void;
}) {
  const [serverType, setServerType] = useState<ServerType>("local");
  const [name, setName] = useState("");
  const [host, setHost] = useState("");
  const [port, setPort] = useState("22");
  const [username, setUsername] = useState("");
  const [authMethod, setAuthMethod] = useState<AuthMethod>("ssh-key");
  const [provider, setProvider] = useState("");
  const [region, setRegion] = useState("");
  const [gpu, setGpu] = useState("");

  const CLOUD_PROVIDERS = [
    "RunPod", "Lambda Labs", "Vast.ai", "CoreWeave", "Modal",
    "AWS EC2", "GCP Compute", "Azure VM", "DigitalOcean", "Hetzner",
    "OVH", "Linode", "Vultr", "Paperspace",
  ];

  const GPU_TYPES = [
    "NVIDIA H100", "NVIDIA A100 80GB", "NVIDIA A100 40GB", "NVIDIA H200",
    "NVIDIA RTX 4090", "NVIDIA RTX A6000", "NVIDIA A40", "NVIDIA L40S",
    "NVIDIA RTX 3090", "NVIDIA T4", "AMD MI300X",
  ];

  const handleSubmit = () => {
    if (!name.trim() || !host.trim()) return;
    onAdd({
      id: Date.now().toString(),
      name,
      type: serverType,
      host,
      port: parseInt(port) || 22,
      username,
      authMethod,
      status: "disconnected",
      provider: provider || undefined,
      region: region || undefined,
      gpu: gpu || undefined,
    });
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
        className="w-full max-w-lg bg-[#161b22] border border-white/10 rounded-2xl overflow-hidden"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <h2 className="text-lg font-semibold text-white">Add Server</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <LucideX className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
          {/* Server Type */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">Server Type</label>
            <div className="grid grid-cols-3 gap-2">
              {(["local", "cloud", "gpu"] as ServerType[]).map((type) => (
                <button
                  key={type}
                  onClick={() => setServerType(type)}
                  className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border transition-all ${
                    serverType === type
                      ? "border-blue-500/50 bg-blue-500/10"
                      : "border-white/10 bg-white/5 hover:border-white/20"
                  }`}
                >
                  {TYPE_CONFIG[type].icon}
                  <span className="text-xs text-white">{TYPE_CONFIG[type].label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Name */}
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">Server Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Dev Server"
              className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 text-sm focus:outline-none focus:border-blue-500/50"
            />
          </div>

          {/* Host & Port */}
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="block text-sm text-gray-400 mb-1.5">Host / IP</label>
              <input
                type="text"
                value={host}
                onChange={(e) => setHost(e.target.value)}
                placeholder="192.168.1.100 or server.example.com"
                className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 text-sm font-mono focus:outline-none focus:border-blue-500/50"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Port</label>
              <input
                type="text"
                value={port}
                onChange={(e) => setPort(e.target.value)}
                className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white text-sm font-mono focus:outline-none focus:border-blue-500/50"
              />
            </div>
          </div>

          {/* Username */}
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="root"
              className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 text-sm font-mono focus:outline-none focus:border-blue-500/50"
            />
          </div>

          {/* Auth Method */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">Authentication</label>
            <div className="flex gap-2">
              {(
                [
                  { id: "ssh-key", label: "SSH Key", icon: <LucideKey className="w-3 h-3" /> },
                  { id: "password", label: "Password", icon: <LucideLock className="w-3 h-3" /> },
                  { id: "token", label: "API Token", icon: <LucideShield className="w-3 h-3" /> },
                ] as { id: AuthMethod; label: string; icon: React.ReactNode }[]
              ).map((auth) => (
                <button
                  key={auth.id}
                  onClick={() => setAuthMethod(auth.id)}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs border transition-all ${
                    authMethod === auth.id
                      ? "border-blue-500/50 bg-blue-500/10 text-blue-400"
                      : "border-white/10 bg-white/5 text-gray-400 hover:border-white/20"
                  }`}
                >
                  {auth.icon} {auth.label}
                </button>
              ))}
            </div>
          </div>

          {/* Cloud-specific fields */}
          {(serverType === "cloud" || serverType === "gpu") && (
            <>
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">Cloud Provider</label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white text-sm focus:outline-none focus:border-blue-500/50 appearance-none"
                >
                  <option value="">Select provider...</option>
                  {CLOUD_PROVIDERS.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">Region</label>
                <input
                  type="text"
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                  placeholder="us-east-1, eu-west-1, etc."
                  className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 text-sm focus:outline-none focus:border-blue-500/50"
                />
              </div>
            </>
          )}

          {/* GPU-specific fields */}
          {serverType === "gpu" && (
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">GPU Type</label>
              <select
                value={gpu}
                onChange={(e) => setGpu(e.target.value)}
                className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white text-sm focus:outline-none focus:border-blue-500/50 appearance-none"
              >
                <option value="">Select GPU...</option>
                {GPU_TYPES.map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-white/10">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-400 hover:text-white text-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!name.trim() || !host.trim()}
            className="flex items-center gap-2 px-5 py-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white rounded-xl text-sm font-medium"
          >
            <LucidePlus className="w-4 h-4" /> Add Server
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
