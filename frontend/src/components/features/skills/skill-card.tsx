import React from "react";
import { motion } from "framer-motion";
import { LucideZap, LucideTag, LucideToggleLeft, LucideToggleRight, LucideEdit, LucideTrash2 } from "lucide-react";

export interface SkillData {
  id: string;
  name: string;
  description: string;
  triggers: string[];
  tags: string[];
  version: string;
  author: string;
  priority: number;
  enabled: boolean;
  scope: "global" | "workspace" | "user";
  body: string;
}

interface SkillCardProps {
  skill: SkillData;
  onToggle: (id: string) => void;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
}

export function SkillCard({ skill, onToggle, onEdit, onDelete }: SkillCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`relative overflow-hidden rounded-2xl border p-5 transition-all ${
        skill.enabled
          ? "border-blue-500/30 bg-blue-500/5"
          : "border-white/10 bg-white/5"
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div
            className={`w-8 h-8 rounded-lg flex items-center justify-center ${
              skill.enabled ? "bg-blue-500/20" : "bg-white/10"
            }`}
          >
            <LucideZap
              className={`w-4 h-4 ${skill.enabled ? "text-blue-400" : "text-gray-500"}`}
            />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">{skill.name}</h3>
            <span className="text-xs text-gray-500">v{skill.version}</span>
          </div>
        </div>

        {/* Toggle */}
        <button
          onClick={() => onToggle(skill.id)}
          className="text-gray-400 hover:text-white transition-colors"
          aria-label={skill.enabled ? "Disable skill" : "Enable skill"}
        >
          {skill.enabled ? (
            <LucideToggleRight className="w-6 h-6 text-blue-400" />
          ) : (
            <LucideToggleLeft className="w-6 h-6" />
          )}
        </button>
      </div>

      {/* Description */}
      <p className="text-sm text-gray-400 mb-3 line-clamp-2">
        {skill.description}
      </p>

      {/* Triggers */}
      {skill.triggers.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {skill.triggers.map((trigger) => (
            <span
              key={trigger}
              className="px-2 py-0.5 text-xs bg-purple-500/20 text-purple-300 rounded-full border border-purple-500/30"
            >
              {trigger}
            </span>
          ))}
        </div>
      )}

      {/* Tags */}
      {skill.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {skill.tags.map((tag) => (
            <span
              key={tag}
              className="flex items-center gap-1 px-2 py-0.5 text-xs bg-white/10 text-gray-300 rounded-full"
            >
              <LucideTag className="w-2.5 h-2.5" />
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-white/10">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className="px-2 py-0.5 bg-white/10 rounded">{skill.scope}</span>
          {skill.author && <span>by {skill.author}</span>}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onEdit(skill.id)}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
            aria-label="Edit skill"
          >
            <LucideEdit className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onDelete(skill.id)}
            className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
            aria-label="Delete skill"
          >
            <LucideTrash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </motion.div>
  );
}
