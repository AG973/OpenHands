import React from "react";
import { motion } from "framer-motion";
import { LucideCheck, LucideLink, LucideSettings, LucideUnlink } from "lucide-react";

export type IntegrationCategory = "developer" | "cloud" | "mobile" | "communication";

export interface IntegrationData {
  id: string;
  name: string;
  description: string;
  category: IntegrationCategory;
  icon: string; // emoji or icon identifier
  connected: boolean;
  lastSync?: string;
  authMethod: string;
  configFields: { key: string; label: string; type: "text" | "password" | "url"; placeholder: string }[];
}

interface IntegrationCardProps {
  integration: IntegrationData;
  onConnect: (id: string) => void;
  onDisconnect: (id: string) => void;
  onConfigure: (id: string) => void;
}

export function IntegrationCard({
  integration,
  onConnect,
  onDisconnect,
  onConfigure,
}: IntegrationCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`relative rounded-2xl border p-5 transition-all ${
        integration.connected
          ? "border-green-500/30 bg-green-500/5"
          : "border-white/10 bg-white/5 hover:border-white/20"
      }`}
    >
      {/* Status indicator */}
      {integration.connected && (
        <div className="absolute top-3 right-3 flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="text-xs text-green-400">Connected</span>
        </div>
      )}

      {/* Icon & Name */}
      <div className="flex items-center gap-3 mb-3">
        <div className="w-12 h-12 rounded-xl bg-white/10 flex items-center justify-center text-2xl">
          {integration.icon}
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">{integration.name}</h3>
          <span className="text-xs text-gray-500">{integration.authMethod}</span>
        </div>
      </div>

      {/* Description */}
      <p className="text-sm text-gray-400 mb-4 line-clamp-2">
        {integration.description}
      </p>

      {/* Last sync */}
      {integration.connected && integration.lastSync && (
        <p className="text-xs text-gray-500 mb-3">
          Last synced: {new Date(integration.lastSync).toLocaleString()}
        </p>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        {integration.connected ? (
          <>
            <button
              onClick={() => onConfigure(integration.id)}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-white/5 border border-white/10 rounded-xl text-sm text-gray-300 hover:bg-white/10 transition-colors"
            >
              <LucideSettings className="w-3.5 h-3.5" />
              Configure
            </button>
            <button
              onClick={() => onDisconnect(integration.id)}
              className="flex items-center justify-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 hover:bg-red-500/20 transition-colors"
            >
              <LucideUnlink className="w-3.5 h-3.5" />
            </button>
          </>
        ) : (
          <button
            onClick={() => onConnect(integration.id)}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-blue-500 hover:bg-blue-600 rounded-xl text-sm text-white font-medium transition-colors"
          >
            <LucideLink className="w-3.5 h-3.5" />
            Connect
          </button>
        )}
      </div>
    </motion.div>
  );
}
