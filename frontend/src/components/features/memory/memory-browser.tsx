import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LucideSearch,
  LucideBrain,
  LucideZap,
  LucideBookOpen,
  LucideAlertTriangle,
  LucideFileText,
  LucideUser,
  LucideTrash2,
  LucidePlus,
  LucideX,
  LucideDatabase,
  LucideDownload,
  LucideUpload,
} from "lucide-react";
import { AnimatedGradientText } from "#/components/ui/animated-gradient-text";

type MemoryType =
  | "knowledge"
  | "skill"
  | "session_note"
  | "error_pattern"
  | "workspace_file"
  | "user_preference";

interface MemoryEntry {
  id: string;
  type: MemoryType;
  key: string;
  content: string;
  metadata: Record<string, string>;
  relevance_score: number;
  created_at: string;
  updated_at: string;
}

const TYPE_CONFIG: Record<
  MemoryType,
  { icon: React.ReactNode; label: string; color: string }
> = {
  knowledge: {
    icon: <LucideBookOpen className="w-4 h-4" />,
    label: "Knowledge",
    color: "blue",
  },
  skill: {
    icon: <LucideZap className="w-4 h-4" />,
    label: "Skill",
    color: "purple",
  },
  session_note: {
    icon: <LucideFileText className="w-4 h-4" />,
    label: "Session Note",
    color: "green",
  },
  error_pattern: {
    icon: <LucideAlertTriangle className="w-4 h-4" />,
    label: "Error Pattern",
    color: "red",
  },
  workspace_file: {
    icon: <LucideFileText className="w-4 h-4" />,
    label: "Workspace File",
    color: "yellow",
  },
  user_preference: {
    icon: <LucideUser className="w-4 h-4" />,
    label: "User Preference",
    color: "cyan",
  },
};

const COLOR_CLASSES: Record<string, { bg: string; text: string; border: string }> = {
  blue: { bg: "bg-blue-500/10", text: "text-blue-400", border: "border-blue-500/30" },
  purple: { bg: "bg-purple-500/10", text: "text-purple-400", border: "border-purple-500/30" },
  green: { bg: "bg-green-500/10", text: "text-green-400", border: "border-green-500/30" },
  red: { bg: "bg-red-500/10", text: "text-red-400", border: "border-red-500/30" },
  yellow: { bg: "bg-yellow-500/10", text: "text-yellow-400", border: "border-yellow-500/30" },
  cyan: { bg: "bg-cyan-500/10", text: "text-cyan-400", border: "border-cyan-500/30" },
};

// Sample data
const SAMPLE_MEMORIES: MemoryEntry[] = [
  {
    id: "1",
    type: "knowledge",
    key: "project_structure",
    content: "The project uses React 19 with Vite, TypeScript, and Tailwind CSS. State management via Zustand. Routing with React Router 7.",
    metadata: { source: "codebase_analysis" },
    relevance_score: 0.95,
    created_at: "2024-03-20T10:30:00Z",
    updated_at: "2024-03-20T10:30:00Z",
  },
  {
    id: "2",
    type: "error_pattern",
    key: "react_hydration_mismatch",
    content: "Hydration mismatch errors occur when server-rendered HTML doesn't match client React tree. Fix: ensure consistent rendering, check for browser-only APIs in SSR.",
    metadata: { frequency: "common", severity: "medium" },
    relevance_score: 0.88,
    created_at: "2024-03-19T14:20:00Z",
    updated_at: "2024-03-19T14:20:00Z",
  },
  {
    id: "3",
    type: "skill",
    key: "debugging_workflow",
    content: "1. Read error message 2. Check stack trace 3. Reproduce locally 4. Isolate cause 5. Fix and test 6. Write regression test",
    metadata: { trigger: "debug" },
    relevance_score: 0.92,
    created_at: "2024-03-18T09:00:00Z",
    updated_at: "2024-03-18T09:00:00Z",
  },
  {
    id: "4",
    type: "session_note",
    key: "session_2024_03_20",
    content: "User wants to build a task management app with React Native. Prefer Expo for cross-platform. Deploy to both App Store and Play Store.",
    metadata: { session_id: "abc123" },
    relevance_score: 0.75,
    created_at: "2024-03-20T16:45:00Z",
    updated_at: "2024-03-20T16:45:00Z",
  },
  {
    id: "5",
    type: "user_preference",
    key: "coding_style",
    content: "Prefer functional components, TypeScript strict mode, Tailwind for styling. No class components. Always add proper types, avoid 'any'.",
    metadata: {},
    relevance_score: 0.9,
    created_at: "2024-03-17T11:00:00Z",
    updated_at: "2024-03-20T11:00:00Z",
  },
];

function MemoryEntryCard({
  entry,
  onDelete,
}: {
  entry: MemoryEntry;
  onDelete: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const config = TYPE_CONFIG[entry.type];
  const colors = COLOR_CLASSES[config.color];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className={`border ${colors.border} rounded-xl overflow-hidden`}
    >
      <div
        className="flex items-start gap-3 p-4 cursor-pointer hover:bg-white/5 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className={`w-8 h-8 rounded-lg ${colors.bg} flex items-center justify-center shrink-0`}>
          <span className={colors.text}>{config.icon}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs px-2 py-0.5 ${colors.bg} ${colors.text} rounded-full`}>
              {config.label}
            </span>
            <span className="text-xs text-gray-500">{entry.key}</span>
          </div>
          <p className={`text-sm text-gray-300 ${expanded ? "" : "line-clamp-2"}`}>
            {entry.content}
          </p>
          {expanded && Object.keys(entry.metadata).length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {Object.entries(entry.metadata).map(([k, v]) => (
                <span key={k} className="text-xs px-2 py-0.5 bg-white/5 text-gray-400 rounded">
                  {k}: {v}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs text-gray-500">
            {new Date(entry.updated_at).toLocaleDateString()}
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(entry.id);
            }}
            className="p-1 text-gray-500 hover:text-red-400 transition-colors"
            aria-label="Delete memory"
          >
            <LucideTrash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </motion.div>
  );
}

function AddMemoryModal({
  onSave,
  onClose,
}: {
  onSave: (entry: Omit<MemoryEntry, "id" | "created_at" | "updated_at" | "relevance_score">) => void;
  onClose: () => void;
}) {
  const [type, setType] = useState<MemoryType>("knowledge");
  const [key, setKey] = useState("");
  const [content, setContent] = useState("");

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        initial={{ scale: 0.95 }}
        animate={{ scale: 1 }}
        className="bg-[#0d1117] border border-white/10 rounded-2xl w-full max-w-lg"
      >
        <div className="flex items-center justify-between p-5 border-b border-white/10">
          <h3 className="text-lg font-semibold text-white">Add Memory</h3>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-white" aria-label="Close">
            <LucideX className="w-5 h-5" />
          </button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Type</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as MemoryType)}
              className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-xl text-white text-sm"
            >
              {Object.entries(TYPE_CONFIG).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Key</label>
            <input
              type="text"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="e.g., project_structure"
              className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-xl text-white text-sm placeholder-gray-500"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Content</label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Write the knowledge or information..."
              rows={5}
              className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-xl text-white text-sm placeholder-gray-500 resize-y"
            />
          </div>
        </div>
        <div className="flex justify-end gap-3 p-5 border-t border-white/10">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-400 hover:text-white">
            Cancel
          </button>
          <button
            onClick={() => {
              onSave({ type, key, content, metadata: {} });
              onClose();
            }}
            disabled={!key.trim() || !content.trim()}
            className="px-4 py-2 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white text-sm rounded-xl"
          >
            Save
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

export function MemoryBrowser() {
  const [memories, setMemories] = useState<MemoryEntry[]>(SAMPLE_MEMORIES);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<MemoryType | "all">("all");
  const [addModalOpen, setAddModalOpen] = useState(false);

  const filteredMemories = useMemo(() => {
    return memories.filter((m) => {
      const matchesSearch =
        !searchQuery ||
        m.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
        m.key.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesType = filterType === "all" || m.type === filterType;
      return matchesSearch && matchesType;
    });
  }, [memories, searchQuery, filterType]);

  const stats = useMemo(() => {
    const byType: Record<string, number> = {};
    memories.forEach((m) => {
      byType[m.type] = (byType[m.type] || 0) + 1;
    });
    return byType;
  }, [memories]);

  const handleDelete = (id: string) => {
    setMemories(memories.filter((m) => m.id !== id));
  };

  const handleAdd = (
    entry: Omit<MemoryEntry, "id" | "created_at" | "updated_at" | "relevance_score">,
  ) => {
    const now = new Date().toISOString();
    setMemories([
      {
        ...entry,
        id: Date.now().toString(),
        relevance_score: 1.0,
        created_at: now,
        updated_at: now,
      },
      ...memories,
    ]);
  };

  return (
    <div className="h-full overflow-y-auto custom-scrollbar-always p-6 lg:p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <AnimatedGradientText as="h1" className="text-2xl font-bold" gradient="from-cyan-400 via-blue-400 to-purple-400">
            Memory Browser
          </AnimatedGradientText>
          <p className="text-sm text-gray-400 mt-1">{memories.length} entries stored</p>
        </div>
        <div className="flex gap-2">
          <button className="flex items-center gap-2 px-3 py-2 bg-white/5 border border-white/10 text-gray-300 rounded-xl text-sm hover:bg-white/10 transition-colors">
            <LucideDownload className="w-4 h-4" /> Export
          </button>
          <button className="flex items-center gap-2 px-3 py-2 bg-white/5 border border-white/10 text-gray-300 rounded-xl text-sm hover:bg-white/10 transition-colors">
            <LucideUpload className="w-4 h-4" /> Import
          </button>
          <button
            onClick={() => setAddModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-xl text-sm font-medium transition-colors"
          >
            <LucidePlus className="w-4 h-4" /> Add Memory
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        {Object.entries(TYPE_CONFIG).map(([type, config]) => {
          const colors = COLOR_CLASSES[config.color];
          return (
            <button
              key={type}
              onClick={() =>
                setFilterType(
                  filterType === type ? "all" : (type as MemoryType),
                )
              }
              className={`p-3 rounded-xl border transition-all ${
                filterType === type
                  ? `${colors.border} ${colors.bg}`
                  : "border-white/10 bg-white/5 hover:bg-white/8"
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={colors.text}>{config.icon}</span>
                <span className={`text-lg font-bold ${colors.text}`}>
                  {stats[type] || 0}
                </span>
              </div>
              <p className="text-xs text-gray-400">{config.label}</p>
            </button>
          );
        })}
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <LucideSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search memories by content or key..."
          className="w-full pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 text-sm"
        />
      </div>

      {/* Memory list */}
      {filteredMemories.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-gray-500">
          <LucideDatabase className="w-12 h-12 mb-3 opacity-50" />
          <p className="text-lg">No memories found</p>
          <p className="text-sm mt-1">
            {searchQuery ? "Try a different search" : "Add your first memory entry"}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          <AnimatePresence>
            {filteredMemories.map((entry) => (
              <MemoryEntryCard key={entry.id} entry={entry} onDelete={handleDelete} />
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* Add Modal */}
      <AnimatePresence>
        {addModalOpen && (
          <AddMemoryModal onSave={handleAdd} onClose={() => setAddModalOpen(false)} />
        )}
      </AnimatePresence>
    </div>
  );
}
