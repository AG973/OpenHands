import React, { useState } from "react";
import { motion } from "framer-motion";
import { LucideX, LucideSave, LucidePlus, LucideTrash2 } from "lucide-react";
import type { SkillData } from "./skill-card";

interface SkillEditorProps {
  skill?: SkillData;
  onSave: (skill: Omit<SkillData, "id"> & { id?: string }) => void;
  onClose: () => void;
}

const SKILL_TEMPLATES = [
  {
    name: "Debug Python Error",
    description: "Step-by-step Python debugging workflow",
    triggers: ["debug", "error", "traceback"],
    tags: ["python", "debugging"],
    body: `## Steps\n1. Read the error traceback carefully\n2. Identify the file and line number\n3. Check the relevant code\n4. Look for common causes (typo, wrong type, missing import)\n5. Apply fix and test`,
  },
  {
    name: "Build React App",
    description: "Create, test, and deploy a React project from scratch",
    triggers: ["build app", "create app", "new project"],
    tags: ["react", "frontend", "deploy"],
    body: `## Steps\n1. Create project with Vite: npm create vite@latest\n2. Install dependencies\n3. Build component structure\n4. Add routing and state management\n5. Write tests\n6. Build and deploy`,
  },
  {
    name: "Deploy to AWS",
    description: "Build, test, and deploy application to AWS",
    triggers: ["deploy", "aws", "production"],
    tags: ["aws", "deploy", "cloud"],
    body: `## Steps\n1. Ensure all tests pass\n2. Build production bundle\n3. Configure AWS credentials\n4. Choose deployment target (S3, EC2, ECS, Lambda)\n5. Deploy and verify\n6. Set up monitoring`,
  },
  {
    name: "Build Mobile App",
    description: "Create React Native app with Expo for iOS and Android",
    triggers: ["mobile", "ios", "android", "app"],
    tags: ["mobile", "react-native", "expo"],
    body: `## Steps\n1. Create Expo project: npx create-expo-app\n2. Design UI screens\n3. Add navigation (React Navigation)\n4. Implement features\n5. Test on Expo Go\n6. Build with EAS: eas build\n7. Submit to app stores`,
  },
  {
    name: "Fix Bug from Issue",
    description: "Read GitHub issue, reproduce bug, fix, and create PR",
    triggers: ["fix bug", "issue", "bug report"],
    tags: ["bugfix", "github"],
    body: `## Steps\n1. Read the issue description and reproduction steps\n2. Reproduce the bug locally\n3. Identify root cause\n4. Write a failing test\n5. Implement fix\n6. Verify test passes\n7. Create PR with description`,
  },
];

export function SkillEditor({ skill, onSave, onClose }: SkillEditorProps) {
  const [name, setName] = useState(skill?.name || "");
  const [description, setDescription] = useState(skill?.description || "");
  const [triggers, setTriggers] = useState<string[]>(skill?.triggers || []);
  const [tags, setTags] = useState<string[]>(skill?.tags || []);
  const [body, setBody] = useState(skill?.body || "");
  const [scope, setScope] = useState<SkillData["scope"]>(skill?.scope || "global");
  const [priority, setPriority] = useState(skill?.priority || 0);
  const [newTrigger, setNewTrigger] = useState("");
  const [newTag, setNewTag] = useState("");

  const handleSave = () => {
    onSave({
      id: skill?.id,
      name,
      description,
      triggers,
      tags,
      version: skill?.version || "1.0.0",
      author: skill?.author || "user",
      priority,
      enabled: skill?.enabled ?? true,
      scope,
      body,
    });
  };

  const loadTemplate = (template: typeof SKILL_TEMPLATES[number]) => {
    setName(template.name);
    setDescription(template.description);
    setTriggers(template.triggers);
    setTags(template.tags);
    setBody(template.body);
  };

  const addTrigger = () => {
    if (newTrigger.trim() && !triggers.includes(newTrigger.trim())) {
      setTriggers([...triggers, newTrigger.trim()]);
      setNewTrigger("");
    }
  };

  const addTag = () => {
    if (newTag.trim() && !tags.includes(newTag.trim())) {
      setTags([...tags, newTag.trim()]);
      setNewTag("");
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="bg-[#0d1117] border border-white/10 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-white/10">
          <h2 className="text-lg font-semibold text-white">
            {skill ? "Edit Skill" : "Create New Skill"}
          </h2>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg"
            aria-label="Close editor"
          >
            <LucideX className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Templates (only for new skills) */}
          {!skill && (
            <div>
              <label className="block text-sm text-gray-400 mb-2">
                Start from template
              </label>
              <div className="flex flex-wrap gap-2">
                {SKILL_TEMPLATES.map((template) => (
                  <button
                    key={template.name}
                    onClick={() => loadTemplate(template)}
                    className="px-3 py-1.5 text-xs bg-white/5 border border-white/10 rounded-lg text-gray-300 hover:bg-white/10 hover:text-white transition-colors"
                  >
                    {template.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Name */}
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Debug Python Error"
              className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this skill do?"
              className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
            />
          </div>

          {/* Triggers */}
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">
              Triggers (words that activate this skill)
            </label>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {triggers.map((trigger) => (
                <span
                  key={trigger}
                  className="flex items-center gap-1 px-2 py-0.5 text-xs bg-purple-500/20 text-purple-300 rounded-full border border-purple-500/30"
                >
                  {trigger}
                  <button
                    onClick={() =>
                      setTriggers(triggers.filter((t) => t !== trigger))
                    }
                    className="hover:text-red-400"
                    aria-label={`Remove trigger ${trigger}`}
                  >
                    <LucideX className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={newTrigger}
                onChange={(e) => setNewTrigger(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addTrigger()}
                placeholder="Add trigger word..."
                className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50"
              />
              <button
                onClick={addTrigger}
                className="px-3 py-2 bg-purple-500/20 text-purple-300 rounded-lg hover:bg-purple-500/30 transition-colors"
              >
                <LucidePlus className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Tags */}
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">Tags</label>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {tags.map((tag) => (
                <span
                  key={tag}
                  className="flex items-center gap-1 px-2 py-0.5 text-xs bg-white/10 text-gray-300 rounded-full"
                >
                  {tag}
                  <button
                    onClick={() => setTags(tags.filter((t) => t !== tag))}
                    className="hover:text-red-400"
                    aria-label={`Remove tag ${tag}`}
                  >
                    <LucideX className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addTag()}
                placeholder="Add tag..."
                className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
              />
              <button
                onClick={addTag}
                className="px-3 py-2 bg-white/10 text-gray-300 rounded-lg hover:bg-white/20 transition-colors"
              >
                <LucidePlus className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Scope & Priority */}
          <div className="flex gap-4">
            <div className="flex-1">
              <label className="block text-sm text-gray-400 mb-1.5">
                Scope
              </label>
              <select
                value={scope}
                onChange={(e) => setScope(e.target.value as SkillData["scope"])}
                className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:border-blue-500/50"
              >
                <option value="global">Global</option>
                <option value="workspace">Workspace</option>
                <option value="user">User</option>
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-sm text-gray-400 mb-1.5">
                Priority (higher = more important)
              </label>
              <input
                type="number"
                value={priority}
                onChange={(e) => setPriority(parseInt(e.target.value, 10) || 0)}
                min={0}
                max={100}
                className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:border-blue-500/50"
              />
            </div>
          </div>

          {/* Body (Markdown) */}
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">
              Skill Instructions (Markdown)
            </label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Write the step-by-step instructions for this skill..."
              rows={10}
              className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 font-mono text-sm resize-y"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-white/10">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!name.trim()}
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl text-sm font-medium transition-colors"
          >
            <LucideSave className="w-4 h-4" />
            {skill ? "Save Changes" : "Create Skill"}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
