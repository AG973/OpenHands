import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LucideSearch,
  LucidePlus,
  LucideZap,
  LucideFilter,
  LucideLayoutGrid,
  LucideLayoutList,
} from "lucide-react";
import { SkillCard } from "./skill-card";
import { SkillEditor } from "./skill-editor";
import type { SkillData } from "./skill-card";
import { AnimatedGradientText } from "#/components/ui/animated-gradient-text";

// Sample skills for demonstration
const SAMPLE_SKILLS: SkillData[] = [
  {
    id: "1",
    name: "Debug Python Error",
    description: "Step-by-step Python debugging workflow — reads traceback, identifies root cause, applies fix",
    triggers: ["debug", "error", "traceback", "python"],
    tags: ["python", "debugging"],
    version: "1.0.0",
    author: "system",
    priority: 10,
    enabled: true,
    scope: "global",
    body: "## Steps\n1. Read the error traceback carefully\n2. Identify the file and line number\n3. Check the relevant code\n4. Apply fix and test",
  },
  {
    id: "2",
    name: "Build React App",
    description: "Create, test, and deploy a React project from scratch using Vite and TypeScript",
    triggers: ["build app", "create app", "new project", "react"],
    tags: ["react", "frontend", "deploy"],
    version: "1.0.0",
    author: "system",
    priority: 8,
    enabled: true,
    scope: "global",
    body: "## Steps\n1. Create project with Vite\n2. Install dependencies\n3. Build component structure\n4. Add routing\n5. Write tests\n6. Deploy",
  },
  {
    id: "3",
    name: "Deploy to AWS",
    description: "Build, test, and deploy application to AWS using appropriate service (S3, EC2, ECS, Lambda)",
    triggers: ["deploy", "aws", "production", "cloud"],
    tags: ["aws", "deploy", "cloud"],
    version: "1.0.0",
    author: "system",
    priority: 7,
    enabled: false,
    scope: "global",
    body: "## Steps\n1. Ensure all tests pass\n2. Build production bundle\n3. Configure AWS credentials\n4. Deploy\n5. Verify",
  },
  {
    id: "4",
    name: "Build Mobile App",
    description: "Create React Native app with Expo for iOS and Android deployment",
    triggers: ["mobile", "ios", "android", "app", "expo"],
    tags: ["mobile", "react-native", "expo"],
    version: "1.0.0",
    author: "system",
    priority: 6,
    enabled: false,
    scope: "global",
    body: "## Steps\n1. Create Expo project\n2. Design UI screens\n3. Add navigation\n4. Test on Expo Go\n5. Build with EAS\n6. Submit to stores",
  },
  {
    id: "5",
    name: "Code Review",
    description: "Review pull request for code quality, bugs, security issues, and suggest improvements",
    triggers: ["review", "pr", "pull request", "code review"],
    tags: ["review", "quality"],
    version: "1.0.0",
    author: "system",
    priority: 5,
    enabled: true,
    scope: "global",
    body: "## Steps\n1. Read PR description\n2. Check code changes\n3. Look for bugs\n4. Check security\n5. Suggest improvements\n6. Leave review",
  },
  {
    id: "6",
    name: "Write Tests",
    description: "Generate comprehensive unit and integration tests for the codebase",
    triggers: ["test", "tests", "testing", "coverage"],
    tags: ["testing", "quality"],
    version: "1.0.0",
    author: "system",
    priority: 5,
    enabled: true,
    scope: "global",
    body: "## Steps\n1. Identify untested code\n2. Write unit tests\n3. Write integration tests\n4. Run coverage report\n5. Fix gaps",
  },
];

export function SkillsBrowser() {
  const [skills, setSkills] = useState<SkillData[]>(SAMPLE_SKILLS);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterTag, setFilterTag] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingSkill, setEditingSkill] = useState<SkillData | undefined>();

  const allTags = useMemo(() => {
    const tagSet = new Set<string>();
    skills.forEach((s) => s.tags.forEach((t) => tagSet.add(t)));
    return Array.from(tagSet).sort();
  }, [skills]);

  const filteredSkills = useMemo(() => {
    return skills.filter((skill) => {
      const matchesSearch =
        !searchQuery ||
        skill.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        skill.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        skill.triggers.some((t) =>
          t.toLowerCase().includes(searchQuery.toLowerCase()),
        );
      const matchesTag = !filterTag || skill.tags.includes(filterTag);
      return matchesSearch && matchesTag;
    });
  }, [skills, searchQuery, filterTag]);

  const handleToggle = (id: string) => {
    setSkills(
      skills.map((s) => (s.id === id ? { ...s, enabled: !s.enabled } : s)),
    );
  };

  const handleEdit = (id: string) => {
    const skill = skills.find((s) => s.id === id);
    if (skill) {
      setEditingSkill(skill);
      setEditorOpen(true);
    }
  };

  const handleDelete = (id: string) => {
    setSkills(skills.filter((s) => s.id !== id));
  };

  const handleSave = (skillData: Omit<SkillData, "id"> & { id?: string }) => {
    if (skillData.id) {
      setSkills(
        skills.map((s) =>
          s.id === skillData.id ? { ...s, ...skillData } : s,
        ),
      );
    } else {
      const newSkill: SkillData = {
        ...skillData,
        id: Date.now().toString(),
      };
      setSkills([...skills, newSkill]);
    }
    setEditorOpen(false);
    setEditingSkill(undefined);
  };

  const handleCreateNew = () => {
    setEditingSkill(undefined);
    setEditorOpen(true);
  };

  const enabledCount = skills.filter((s) => s.enabled).length;

  return (
    <div className="h-full overflow-y-auto custom-scrollbar-always p-6 lg:p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <AnimatedGradientText as="h1" className="text-2xl font-bold">
            Skills Manager
          </AnimatedGradientText>
          <p className="text-sm text-gray-400 mt-1">
            {skills.length} skills total, {enabledCount} active
          </p>
        </div>
        <button
          onClick={handleCreateNew}
          className="flex items-center gap-2 px-4 py-2.5 bg-blue-500 hover:bg-blue-600 text-white rounded-xl text-sm font-medium transition-colors"
        >
          <LucidePlus className="w-4 h-4" />
          New Skill
        </button>
      </div>

      {/* Search & Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="flex-1 relative">
          <LucideSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search skills by name, description, or trigger..."
            className="w-full pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 text-sm"
          />
        </div>
        <div className="flex gap-2">
          <div className="relative">
            <select
              value={filterTag || ""}
              onChange={(e) => setFilterTag(e.target.value || null)}
              className="appearance-none pl-9 pr-8 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-blue-500/50"
            >
              <option value="">All tags</option>
              {allTags.map((tag) => (
                <option key={tag} value={tag}>
                  {tag}
                </option>
              ))}
            </select>
            <LucideFilter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          </div>
          <div className="flex bg-white/5 border border-white/10 rounded-xl overflow-hidden">
            <button
              onClick={() => setViewMode("grid")}
              className={`p-2.5 ${viewMode === "grid" ? "bg-white/10 text-white" : "text-gray-400"}`}
              aria-label="Grid view"
            >
              <LucideLayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={`p-2.5 ${viewMode === "list" ? "bg-white/10 text-white" : "text-gray-400"}`}
              aria-label="List view"
            >
              <LucideLayoutList className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Skills Grid/List */}
      {filteredSkills.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-gray-500">
          <LucideZap className="w-12 h-12 mb-3 opacity-50" />
          <p className="text-lg">No skills found</p>
          <p className="text-sm mt-1">Try a different search or create a new skill</p>
        </div>
      ) : (
        <div
          className={
            viewMode === "grid"
              ? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
              : "flex flex-col gap-3"
          }
        >
          <AnimatePresence>
            {filteredSkills.map((skill) => (
              <SkillCard
                key={skill.id}
                skill={skill}
                onToggle={handleToggle}
                onEdit={handleEdit}
                onDelete={handleDelete}
              />
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* Skill Editor Modal */}
      <AnimatePresence>
        {editorOpen && (
          <SkillEditor
            skill={editingSkill}
            onSave={handleSave}
            onClose={() => {
              setEditorOpen(false);
              setEditingSkill(undefined);
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
