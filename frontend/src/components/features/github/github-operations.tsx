import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  GitBranch,
  GitPullRequest,
  GitCommit,
  GitMerge,
  FolderGit2,
  Search,
  Plus,
  RefreshCw,
  Upload,
  Download,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  Eye,
  FileCode,
  Folder,
  ChevronRight,
  ChevronDown,
  ExternalLink,
  Star,
  GitFork,
  Shield,
  Terminal,
  AlertCircle,
  Loader2,
  Copy,
  ArrowUpRight,
  Settings,
  Trash2,
  MessageSquare,
  Tag,
  Globe,
  BookOpen,
  Network,
  Layers,
  Code2,
  Braces,
  Microscope,
  Workflow,
  ArrowDownToLine,
  BarChart3,
  Puzzle,
  Zap,
  Bot,
} from "lucide-react";

// ─── Types ───

interface Repository {
  id: string;
  name: string;
  fullName: string;
  description: string;
  language: string;
  stars: number;
  forks: number;
  isPrivate: boolean;
  defaultBranch: string;
  updatedAt: string;
  openIssues: number;
  topics: string[];
  size?: string;
  license?: string;
}

interface PullRequest {
  id: number;
  title: string;
  number: number;
  state: "open" | "closed" | "merged";
  author: string;
  createdAt: string;
  updatedAt: string;
  baseBranch: string;
  headBranch: string;
  additions: number;
  deletions: number;
  comments: number;
  reviewStatus: "approved" | "changes_requested" | "pending" | "none";
  labels: string[];
  draft: boolean;
  checksStatus: "passing" | "failing" | "pending" | "none";
}

interface BranchInfo {
  name: string;
  isDefault: boolean;
  isProtected: boolean;
  lastCommit: string;
  lastCommitDate: string;
  behind: number;
  ahead: number;
}

interface CommitInfo {
  sha: string;
  message: string;
  author: string;
  date: string;
  additions: number;
  deletions: number;
  filesChanged: number;
}

interface TestRun {
  id: string;
  name: string;
  status: "passing" | "failing" | "running" | "pending";
  duration: string;
  startedAt: string;
  totalTests: number;
  passed: number;
  failed: number;
  skipped: number;
}

interface FileTreeItem {
  name: string;
  type: "file" | "directory";
  path: string;
  size?: string;
  language?: string;
  children?: FileTreeItem[];
}

interface AnalysisResult {
  id: string;
  type: string;
  title: string;
  description: string;
  status: "complete" | "running" | "pending";
  findings: number;
  severity?: "info" | "warning" | "critical";
}

type ActiveTab = "explore" | "my-repos" | "prs" | "branches" | "commits" | "tests" | "files" | "analyze" | "actions";

// ─── Language Colors ───

const LANGUAGE_COLORS: Record<string, string> = {
  TypeScript: "#3178c6",
  JavaScript: "#f1e05a",
  Python: "#3572A5",
  Rust: "#dea584",
  Go: "#00ADD8",
  Java: "#b07219",
  Ruby: "#701516",
  "C++": "#f34b7d",
  Swift: "#F05138",
  Kotlin: "#A97BFF",
  C: "#555555",
  "C#": "#178600",
  PHP: "#4F5D95",
  Dart: "#00B4AB",
  Shell: "#89e051",
  HTML: "#e34c26",
  CSS: "#563d7c",
  Vue: "#41b883",
  Svelte: "#ff3e00",
};

// ─── Sample Data ───

const TRENDING_REPOS: Repository[] = [
  {
    id: "t1", name: "repomix", fullName: "yamadashy/repomix",
    description: "Pack your entire repository into a single, AI-friendly file. Feed your codebase to LLMs like Claude, ChatGPT, DeepSeek.",
    language: "TypeScript", stars: 22505, forks: 1044, isPrivate: false, defaultBranch: "main",
    updatedAt: "2 hours ago", openIssues: 150, topics: ["ai", "llm", "developer-tools", "typescript"],
    size: "4.2 MB", license: "MIT",
  },
  {
    id: "t2", name: "gitingest", fullName: "coderamp-labs/gitingest",
    description: "Turn any Git repository into a prompt-friendly text digest for LLMs. Replace hub with ingest in any GitHub URL.",
    language: "Python", stars: 14190, forks: 1045, isPrivate: false, defaultBranch: "main",
    updatedAt: "1 day ago", openIssues: 19, topics: ["ai", "code", "developer-tool", "ingestion"],
    size: "1.8 MB", license: "MIT",
  },
  {
    id: "t3", name: "GitNexus", fullName: "abhigyanpatwari/GitNexus",
    description: "Client-side knowledge graph creator. Drop a GitHub repo and get an interactive knowledge graph with Graph RAG Agent.",
    language: "TypeScript", stars: 18900, forks: 2200, isPrivate: false, defaultBranch: "main",
    updatedAt: "3 days ago", openIssues: 15, topics: ["knowledge-graph", "code-exploration", "rag"],
    size: "8.5 MB", license: "MIT",
  },
  {
    id: "t4", name: "GitVizz", fullName: "adithya-s-k/GitVizz",
    description: "AI-powered repository analysis with interactive documentation, dependency graphs, and intelligent code conversations.",
    language: "TypeScript", stars: 242, forks: 32, isPrivate: false, defaultBranch: "main",
    updatedAt: "1 month ago", openIssues: 6, topics: ["code-visualization", "dependency-graph", "ai"],
    size: "12 MB", license: "MIT",
  },
  {
    id: "t5", name: "sourcegraph", fullName: "sourcegraph/sourcegraph",
    description: "Code AI platform with universal Code Search across all repos, branches, and code hosts.",
    language: "Go", stars: 9800, forks: 1200, isPrivate: false, defaultBranch: "main",
    updatedAt: "6 hours ago", openIssues: 800, topics: ["code-search", "code-intelligence", "ai"],
    size: "450 MB", license: "Apache-2.0",
  },
  {
    id: "t6", name: "codecharta", fullName: "MaibornWolff/codecharta",
    description: "Visualization tool that transforms software architecture and code metrics into interactive 3D maps.",
    language: "TypeScript", stars: 426, forks: 48, isPrivate: false, defaultBranch: "main",
    updatedAt: "1 week ago", openIssues: 150, topics: ["3d-map", "code-visualization", "metrics"],
    size: "35 MB", license: "BSD-3-Clause",
  },
];

const MY_REPOS: Repository[] = [
  {
    id: "1", name: "my-web-app", fullName: "user/my-web-app",
    description: "Full-stack web application with React and Node.js",
    language: "TypeScript", stars: 42, forks: 8, isPrivate: false, defaultBranch: "main",
    updatedAt: "2 hours ago", openIssues: 5, topics: ["react", "nodejs", "typescript"],
  },
  {
    id: "2", name: "mobile-app", fullName: "user/mobile-app",
    description: "Cross-platform mobile app built with React Native",
    language: "TypeScript", stars: 15, forks: 3, isPrivate: true, defaultBranch: "main",
    updatedAt: "1 day ago", openIssues: 2, topics: ["react-native", "expo", "mobile"],
  },
  {
    id: "3", name: "api-server", fullName: "user/api-server",
    description: "REST API server with FastAPI and PostgreSQL",
    language: "Python", stars: 28, forks: 6, isPrivate: false, defaultBranch: "main",
    updatedAt: "3 days ago", openIssues: 8, topics: ["python", "fastapi", "postgresql"],
  },
];

const SAMPLE_PRS: PullRequest[] = [
  { id: 1, title: "feat: Add user authentication with OAuth2", number: 45, state: "open", author: "developer1", createdAt: "2 hours ago", updatedAt: "30 min ago", baseBranch: "main", headBranch: "feature/oauth2-auth", additions: 342, deletions: 18, comments: 3, reviewStatus: "pending", labels: ["feature", "auth"], draft: false, checksStatus: "passing" },
  { id: 2, title: "fix: Resolve database connection pool exhaustion", number: 44, state: "open", author: "developer2", createdAt: "1 day ago", updatedAt: "4 hours ago", baseBranch: "main", headBranch: "fix/db-pool-exhaustion", additions: 28, deletions: 12, comments: 7, reviewStatus: "approved", labels: ["bug", "critical"], draft: false, checksStatus: "passing" },
  { id: 3, title: "refactor: Migrate to new API client", number: 43, state: "merged", author: "developer1", createdAt: "3 days ago", updatedAt: "1 day ago", baseBranch: "main", headBranch: "refactor/api-client-v2", additions: 567, deletions: 890, comments: 12, reviewStatus: "approved", labels: ["refactor"], draft: false, checksStatus: "passing" },
  { id: 4, title: "WIP: Dark mode support", number: 42, state: "open", author: "developer3", createdAt: "5 days ago", updatedAt: "2 days ago", baseBranch: "main", headBranch: "feature/dark-mode", additions: 156, deletions: 34, comments: 2, reviewStatus: "none", labels: ["feature", "ui"], draft: true, checksStatus: "failing" },
];

const SAMPLE_BRANCHES: BranchInfo[] = [
  { name: "main", isDefault: true, isProtected: true, lastCommit: "Update README", lastCommitDate: "2 hours ago", behind: 0, ahead: 0 },
  { name: "develop", isDefault: false, isProtected: true, lastCommit: "Merge feature/auth", lastCommitDate: "1 day ago", behind: 2, ahead: 5 },
  { name: "feature/oauth2-auth", isDefault: false, isProtected: false, lastCommit: "Add token refresh logic", lastCommitDate: "30 min ago", behind: 0, ahead: 8 },
  { name: "fix/db-pool-exhaustion", isDefault: false, isProtected: false, lastCommit: "Increase pool timeout", lastCommitDate: "4 hours ago", behind: 1, ahead: 2 },
  { name: "feature/dark-mode", isDefault: false, isProtected: false, lastCommit: "Add theme toggle", lastCommitDate: "2 days ago", behind: 5, ahead: 4 },
];

const SAMPLE_COMMITS: CommitInfo[] = [
  { sha: "a1b2c3d", message: "feat: Add user authentication with OAuth2 support", author: "developer1", date: "30 min ago", additions: 120, deletions: 5, filesChanged: 8 },
  { sha: "e4f5g6h", message: "fix: Resolve memory leak in WebSocket handler", author: "developer2", date: "2 hours ago", additions: 12, deletions: 8, filesChanged: 2 },
  { sha: "i7j8k9l", message: "docs: Update API documentation for v2 endpoints", author: "developer1", date: "4 hours ago", additions: 245, deletions: 89, filesChanged: 12 },
  { sha: "m1n2o3p", message: "chore: Update dependencies to latest versions", author: "bot", date: "6 hours ago", additions: 450, deletions: 420, filesChanged: 3 },
  { sha: "q4r5s6t", message: "test: Add integration tests for payment flow", author: "developer3", date: "1 day ago", additions: 180, deletions: 0, filesChanged: 5 },
];

const SAMPLE_TESTS: TestRun[] = [
  { id: "1", name: "Unit Tests", status: "passing", duration: "45s", startedAt: "10 min ago", totalTests: 156, passed: 156, failed: 0, skipped: 2 },
  { id: "2", name: "Integration Tests", status: "passing", duration: "2m 30s", startedAt: "10 min ago", totalTests: 42, passed: 42, failed: 0, skipped: 0 },
  { id: "3", name: "E2E Tests", status: "failing", duration: "5m 12s", startedAt: "10 min ago", totalTests: 28, passed: 25, failed: 3, skipped: 0 },
  { id: "4", name: "Lint & Type Check", status: "passing", duration: "18s", startedAt: "10 min ago", totalTests: 0, passed: 0, failed: 0, skipped: 0 },
  { id: "5", name: "Security Scan", status: "running", duration: "\u2014", startedAt: "5 min ago", totalTests: 0, passed: 0, failed: 0, skipped: 0 },
];

const SAMPLE_FILES: FileTreeItem[] = [
  { name: "src", type: "directory", path: "src", children: [
    { name: "components", type: "directory", path: "src/components", children: [
      { name: "App.tsx", type: "file", path: "src/components/App.tsx", size: "2.4 KB", language: "TypeScript" },
      { name: "Header.tsx", type: "file", path: "src/components/Header.tsx", size: "1.8 KB", language: "TypeScript" },
    ]},
    { name: "hooks", type: "directory", path: "src/hooks", children: [
      { name: "useAuth.ts", type: "file", path: "src/hooks/useAuth.ts", size: "890 B", language: "TypeScript" },
    ]},
    { name: "index.tsx", type: "file", path: "src/index.tsx", size: "450 B", language: "TypeScript" },
  ]},
  { name: "tests", type: "directory", path: "tests", children: [
    { name: "App.test.tsx", type: "file", path: "tests/App.test.tsx", size: "1.5 KB", language: "TypeScript" },
  ]},
  { name: "package.json", type: "file", path: "package.json", size: "1.2 KB", language: "JSON" },
  { name: "README.md", type: "file", path: "README.md", size: "4.5 KB", language: "Markdown" },
];

const SAMPLE_ANALYSIS: AnalysisResult[] = [
  { id: "a1", type: "architecture", title: "Architecture Overview", description: "Mapped 42 modules, 156 exports, 89 internal dependencies. Monolithic structure with 3 circular deps.", status: "complete", findings: 3, severity: "warning" },
  { id: "a2", type: "dependencies", title: "Dependency Graph", description: "Analyzed 128 npm packages. 4 outdated critical deps, 2 known vulnerabilities, 12 unused imports.", status: "complete", findings: 18, severity: "warning" },
  { id: "a3", type: "patterns", title: "Design Patterns", description: "Detected: Singleton (3), Factory (5), Observer (8), Strategy (2). Anti-patterns: God Object (1), Spaghetti (2).", status: "complete", findings: 21, severity: "info" },
  { id: "a4", type: "security", title: "Security Analysis", description: "Found 2 hardcoded secrets, 1 SQL injection risk, 3 XSS vectors, 5 missing input validations.", status: "complete", findings: 11, severity: "critical" },
  { id: "a5", type: "quality", title: "Code Quality Metrics", description: "Avg complexity: 12.4 (target <10). Test coverage: 67%. Duplication: 8.2%. Tech debt: ~45 hours.", status: "complete", findings: 8, severity: "warning" },
  { id: "a6", type: "api-map", title: "API Endpoint Map", description: "Discovered 34 REST endpoints, 8 WebSocket channels, 3 GraphQL queries. Full route-to-handler mapping.", status: "complete", findings: 45, severity: "info" },
];

// ─── Sub-components ───

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
    passing: { bg: "bg-green-500/20", text: "text-green-400", icon: <CheckCircle2 className="w-3 h-3" /> },
    failing: { bg: "bg-red-500/20", text: "text-red-400", icon: <XCircle className="w-3 h-3" /> },
    running: { bg: "bg-blue-500/20", text: "text-blue-400", icon: <Loader2 className="w-3 h-3 animate-spin" /> },
    pending: { bg: "bg-yellow-500/20", text: "text-yellow-400", icon: <Clock className="w-3 h-3" /> },
    open: { bg: "bg-green-500/20", text: "text-green-400", icon: <GitPullRequest className="w-3 h-3" /> },
    closed: { bg: "bg-red-500/20", text: "text-red-400", icon: <XCircle className="w-3 h-3" /> },
    merged: { bg: "bg-purple-500/20", text: "text-purple-400", icon: <GitMerge className="w-3 h-3" /> },
    approved: { bg: "bg-green-500/20", text: "text-green-400", icon: <CheckCircle2 className="w-3 h-3" /> },
    changes_requested: { bg: "bg-orange-500/20", text: "text-orange-400", icon: <AlertCircle className="w-3 h-3" /> },
    complete: { bg: "bg-green-500/20", text: "text-green-400", icon: <CheckCircle2 className="w-3 h-3" /> },
    none: { bg: "bg-gray-500/20", text: "text-gray-400", icon: <Clock className="w-3 h-3" /> },
  };
  const c = config[status] || config.none;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${c.bg} ${c.text}`}>
      {c.icon}
      {status.replace("_", " ")}
    </span>
  );
}

function FileTree({ items, depth = 0 }: { items: FileTreeItem[]; depth?: number }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  return (
    <div>
      {items.map((item) => (
        <div key={item.path}>
          <button
            onClick={() => {
              if (item.type === "directory") {
                setExpanded((prev) => ({ ...prev, [item.path]: !prev[item.path] }));
              }
            }}
            className={`w-full flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-white/5 rounded-lg transition-colors ${
              item.type === "file" ? "text-gray-300 cursor-pointer" : "text-white"
            }`}
            style={{ paddingLeft: `${depth * 20 + 12}px` }}
          >
            {item.type === "directory" ? (
              expanded[item.path] ? <ChevronDown className="w-3.5 h-3.5 text-gray-500" /> : <ChevronRight className="w-3.5 h-3.5 text-gray-500" />
            ) : (
              <span className="w-3.5" />
            )}
            {item.type === "directory" ? (
              <Folder className="w-4 h-4 text-blue-400" />
            ) : (
              <FileCode className="w-4 h-4 text-gray-400" />
            )}
            <span className="flex-1 text-left truncate">{item.name}</span>
            {item.language && <span className="text-[10px] text-gray-600 px-1.5 py-0.5 rounded bg-white/5">{item.language}</span>}
            {item.size && <span className="text-xs text-gray-500">{item.size}</span>}
          </button>
          {item.type === "directory" && expanded[item.path] && item.children && (
            <FileTree items={item.children} depth={depth + 1} />
          )}
        </div>
      ))}
    </div>
  );
}

function RepoCard({ repo, onSelect, isSelected, onAnalyze, onIngest }: {
  repo: Repository;
  onSelect: (repo: Repository) => void;
  isSelected: boolean;
  onAnalyze?: (repo: Repository) => void;
  onIngest?: (repo: Repository) => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`p-4 rounded-xl border transition-all cursor-pointer ${
        isSelected ? "bg-blue-500/10 border-blue-500/30" : "bg-white/5 border-white/10 hover:border-white/20"
      }`}
      onClick={() => onSelect(repo)}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <FolderGit2 className="w-5 h-5 text-blue-400" />
          <h3 className="font-semibold text-white text-sm">{repo.fullName}</h3>
          {repo.isPrivate && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-yellow-500/20 text-yellow-400">
              <Shield className="w-2.5 h-2.5" /> Private
            </span>
          )}
        </div>
        <button className="p-1 text-gray-500 hover:text-white transition-colors" title="Open on GitHub">
          <ExternalLink className="w-4 h-4" />
        </button>
      </div>
      <p className="text-sm text-gray-400 mb-3 line-clamp-2">{repo.description}</p>
      <div className="flex items-center gap-4 text-xs text-gray-500">
        {repo.language && (
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: LANGUAGE_COLORS[repo.language] || "#666" }} />
            {repo.language}
          </span>
        )}
        <span className="flex items-center gap-1"><Star className="w-3 h-3" /> {repo.stars.toLocaleString()}</span>
        <span className="flex items-center gap-1"><GitFork className="w-3 h-3" /> {repo.forks.toLocaleString()}</span>
        {repo.license && <span className="text-gray-600">{repo.license}</span>}
        <span className="ml-auto">{repo.updatedAt}</span>
      </div>
      {repo.topics.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {repo.topics.slice(0, 5).map((topic) => (
            <span key={topic} className="px-2 py-0.5 rounded-full text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20">
              {topic}
            </span>
          ))}
          {repo.topics.length > 5 && <span className="text-[10px] text-gray-500">+{repo.topics.length - 5} more</span>}
        </div>
      )}
      {isSelected && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-white/10"
        >
          <button className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600/20 text-blue-400 rounded-lg text-xs hover:bg-blue-600/30 transition-colors" onClick={(e) => { e.stopPropagation(); }}>
            <Download className="w-3 h-3" /> Clone
          </button>
          <button className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600/20 text-green-400 rounded-lg text-xs hover:bg-green-600/30 transition-colors" onClick={(e) => { e.stopPropagation(); }}>
            <Eye className="w-3 h-3" /> Browse Code
          </button>
          {onAnalyze && (
            <button className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600/20 text-purple-400 rounded-lg text-xs hover:bg-purple-600/30 transition-colors" onClick={(e) => { e.stopPropagation(); onAnalyze(repo); }}>
              <Microscope className="w-3 h-3" /> Reverse Engineer
            </button>
          )}
          {onIngest && (
            <button className="flex items-center gap-1.5 px-3 py-1.5 bg-orange-600/20 text-orange-400 rounded-lg text-xs hover:bg-orange-600/30 transition-colors" onClick={(e) => { e.stopPropagation(); onIngest(repo); }}>
              <Bot className="w-3 h-3" /> Ingest for AI
            </button>
          )}
          <button className="flex items-center gap-1.5 px-3 py-1.5 bg-cyan-600/20 text-cyan-400 rounded-lg text-xs hover:bg-cyan-600/30 transition-colors" onClick={(e) => { e.stopPropagation(); }}>
            <GitFork className="w-3 h-3" /> Fork
          </button>
        </motion.div>
      )}
    </motion.div>
  );
}

// ─── Main Component ───

export function GitHubOperations() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("explore");
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [publicSearchQuery, setPublicSearchQuery] = useState("");
  const [showCreatePR, setShowCreatePR] = useState(false);
  const [showCreateBranch, setShowCreateBranch] = useState(false);
  const [prFilter, setPrFilter] = useState<"all" | "open" | "closed" | "merged">("all");
  const [isLoading, setIsLoading] = useState(false);
  const [analysisRepo, setAnalysisRepo] = useState<Repository | null>(null);
  const [showIngestModal, setShowIngestModal] = useState(false);
  const [ingestRepo, setIngestRepo] = useState<Repository | null>(null);
  const [searchFilter, setSearchFilter] = useState<"all" | "repos" | "code" | "issues" | "users">("all");

  const [newPR, setNewPR] = useState({ title: "", description: "", baseBranch: "main", headBranch: "", isDraft: false });
  const [newBranch, setNewBranch] = useState({ name: "", fromBranch: "main" });

  const tabs: { id: ActiveTab; label: string; icon: React.ReactNode }[] = [
    { id: "explore", label: "Explore & Search", icon: <Globe className="w-4 h-4" /> },
    { id: "my-repos", label: "My Repos", icon: <FolderGit2 className="w-4 h-4" /> },
    { id: "prs", label: "Pull Requests", icon: <GitPullRequest className="w-4 h-4" /> },
    { id: "branches", label: "Branches", icon: <GitBranch className="w-4 h-4" /> },
    { id: "commits", label: "Commits", icon: <GitCommit className="w-4 h-4" /> },
    { id: "tests", label: "CI / Tests", icon: <Play className="w-4 h-4" /> },
    { id: "files", label: "Files", icon: <FileCode className="w-4 h-4" /> },
    { id: "analyze", label: "Analyze & RE", icon: <Microscope className="w-4 h-4" /> },
    { id: "actions", label: "Quick Actions", icon: <Zap className="w-4 h-4" /> },
  ];

  const filteredPRs = useMemo(() => {
    return SAMPLE_PRS.filter((pr) => {
      if (prFilter !== "all" && pr.state !== prFilter) return false;
      if (searchQuery && !pr.title.toLowerCase().includes(searchQuery.toLowerCase())) return false;
      return true;
    });
  }, [prFilter, searchQuery]);

  const simulateAction = (_action: string) => {
    setIsLoading(true);
    setTimeout(() => setIsLoading(false), 1500);
  };

  // ─── Tab: Explore & Search ───
  const renderExplore = () => (
    <div className="space-y-6">
      <div className="p-5 bg-gradient-to-r from-blue-500/10 via-purple-500/10 to-pink-500/10 border border-white/10 rounded-2xl">
        <h2 className="text-lg font-semibold text-white mb-1">Search All of GitHub</h2>
        <p className="text-sm text-gray-400 mb-4">Find any public repository, read code, analyze architecture, and reverse engineer</p>
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input type="text" value={publicSearchQuery} onChange={(e) => setPublicSearchQuery(e.target.value)}
              placeholder="Search repositories, code, users, issues..."
              className="w-full pl-10 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 text-sm" />
          </div>
          <button onClick={() => simulateAction("search")} className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-medium transition-colors">
            Search
          </button>
        </div>
        <div className="flex gap-2 mt-3">
          {(["all", "repos", "code", "issues", "users"] as const).map((f) => (
            <button key={f} onClick={() => setSearchFilter(f)}
              className={`px-3 py-1 rounded-lg text-xs capitalize transition-colors ${searchFilter === f ? "bg-white/10 text-white" : "text-gray-500 hover:text-white hover:bg-white/5"}`}>
              {f === "all" ? "All" : f}
            </button>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Quick Access Tools</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { icon: <Bot className="w-5 h-5" />, title: "Repo \u2192 AI Text", desc: "Ingest repo for LLM context (Repomix / Gitingest)", color: "from-orange-500/20 to-red-500/20", borderColor: "border-orange-500/20" },
            { icon: <Network className="w-5 h-5" />, title: "Knowledge Graph", desc: "Build interactive code knowledge graph (GitNexus)", color: "from-purple-500/20 to-blue-500/20", borderColor: "border-purple-500/20" },
            { icon: <Layers className="w-5 h-5" />, title: "Dependency Graph", desc: "Visualize dependencies and connections (GitVizz)", color: "from-cyan-500/20 to-teal-500/20", borderColor: "border-cyan-500/20" },
            { icon: <Microscope className="w-5 h-5" />, title: "Reverse Engineer", desc: "Analyze architecture, patterns, security", color: "from-pink-500/20 to-rose-500/20", borderColor: "border-pink-500/20" },
          ].map((tool) => (
            <button key={tool.title} onClick={() => simulateAction(tool.title)}
              className={`p-4 bg-gradient-to-br ${tool.color} border ${tool.borderColor} rounded-xl text-left hover:scale-[1.02] transition-transform`}>
              <div className="text-white mb-2">{tool.icon}</div>
              <h4 className="text-sm font-medium text-white">{tool.title}</h4>
              <p className="text-[11px] text-gray-400 mt-0.5">{tool.desc}</p>
            </button>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Featured Open-Source Tools</h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {TRENDING_REPOS.map((repo) => (
            <RepoCard key={repo.id} repo={repo} onSelect={setSelectedRepo} isSelected={selectedRepo?.id === repo.id}
              onAnalyze={(r) => { setAnalysisRepo(r); setActiveTab("analyze"); }}
              onIngest={(r) => { setIngestRepo(r); setShowIngestModal(true); }}
            />
          ))}
        </div>
      </div>
    </div>
  );

  // ─── Tab: My Repos ───
  const renderMyRepos = () => (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search your repositories..."
            className="w-full pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 text-sm" />
        </div>
        <button onClick={() => simulateAction("clone")} className="flex items-center gap-2 px-4 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-xl text-sm font-medium transition-colors">
          <Download className="w-4 h-4" /> Clone Repo
        </button>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {MY_REPOS.filter((r) => !searchQuery || r.name.toLowerCase().includes(searchQuery.toLowerCase())).map((repo) => (
          <RepoCard key={repo.id} repo={repo} onSelect={setSelectedRepo} isSelected={selectedRepo?.id === repo.id}
            onAnalyze={(r) => { setAnalysisRepo(r); setActiveTab("analyze"); }}
            onIngest={(r) => { setIngestRepo(r); setShowIngestModal(true); }}
          />
        ))}
      </div>
    </div>
  );

  // ─── Tab: Pull Requests ───
  const renderPRs = () => (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search pull requests..."
            className="w-full pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 text-sm" />
        </div>
        <div className="flex bg-white/5 border border-white/10 rounded-xl overflow-hidden">
          {(["all", "open", "closed", "merged"] as const).map((f) => (
            <button key={f} onClick={() => setPrFilter(f)}
              className={`px-3 py-2 text-sm capitalize ${prFilter === f ? "bg-white/10 text-white" : "text-gray-400 hover:text-white"}`}>
              {f}
            </button>
          ))}
        </div>
        <button onClick={() => setShowCreatePR(true)} className="flex items-center gap-2 px-4 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-xl text-sm font-medium transition-colors">
          <Plus className="w-4 h-4" /> New PR
        </button>
      </div>
      <div className="space-y-2">
        {filteredPRs.map((pr) => (
          <motion.div key={pr.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="p-4 bg-white/5 border border-white/10 rounded-xl hover:border-white/20 transition-all">
            <div className="flex items-start gap-3">
              <div className="mt-1">
                {pr.state === "merged" ? <GitMerge className="w-5 h-5 text-purple-400" /> : pr.state === "closed" ? <XCircle className="w-5 h-5 text-red-400" /> : <GitPullRequest className="w-5 h-5 text-green-400" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-medium text-white truncate">{pr.draft && <span className="text-gray-500 mr-1">[Draft]</span>}{pr.title}</h3>
                  <span className="text-xs text-gray-500 shrink-0">#{pr.number}</span>
                </div>
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <StatusBadge status={pr.state} />
                  {pr.reviewStatus !== "none" && <StatusBadge status={pr.reviewStatus} />}
                  {pr.labels.map((label) => (
                    <span key={label} className="px-2 py-0.5 rounded-full text-[10px] bg-blue-500/10 text-blue-300 border border-blue-500/20">{label}</span>
                  ))}
                </div>
                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span>{pr.author}</span>
                  <span>{pr.baseBranch} <ArrowUpRight className="inline w-3 h-3" /> {pr.headBranch}</span>
                  <span className="text-green-400">+{pr.additions}</span>
                  <span className="text-red-400">-{pr.deletions}</span>
                  <span className="flex items-center gap-1"><MessageSquare className="w-3 h-3" /> {pr.comments}</span>
                  <span className="ml-auto">{pr.updatedAt}</span>
                </div>
              </div>
              <div className="flex gap-1 shrink-0">
                <button className="p-1.5 text-gray-500 hover:text-white hover:bg-white/5 rounded-lg transition-colors" title="View"><Eye className="w-4 h-4" /></button>
                {pr.state === "open" && (
                  <button onClick={() => simulateAction("merge")} className="p-1.5 text-gray-500 hover:text-green-400 hover:bg-green-500/10 rounded-lg transition-colors" title="Merge"><GitMerge className="w-4 h-4" /></button>
                )}
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );

  // ─── Tab: Branches ───
  const renderBranches = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-400">{SAMPLE_BRANCHES.length} branches</p>
        <button onClick={() => setShowCreateBranch(true)} className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-xl text-sm font-medium transition-colors">
          <Plus className="w-4 h-4" /> New Branch
        </button>
      </div>
      <div className="space-y-2">
        {SAMPLE_BRANCHES.map((branch) => (
          <div key={branch.name} className="flex items-center justify-between p-4 bg-white/5 border border-white/10 rounded-xl hover:border-white/20 transition-all">
            <div className="flex items-center gap-3">
              <GitBranch className="w-5 h-5 text-blue-400" />
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-white">{branch.name}</span>
                  {branch.isDefault && <span className="px-2 py-0.5 rounded text-[10px] bg-blue-500/20 text-blue-400">default</span>}
                  {branch.isProtected && <span className="px-2 py-0.5 rounded text-[10px] bg-yellow-500/20 text-yellow-400"><Shield className="inline w-2.5 h-2.5 mr-0.5" />protected</span>}
                </div>
                <p className="text-xs text-gray-500 mt-0.5">{branch.lastCommit} &mdash; {branch.lastCommitDate}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {(branch.behind > 0 || branch.ahead > 0) && !branch.isDefault && (
                <div className="flex items-center gap-2 text-xs">
                  {branch.behind > 0 && <span className="text-red-400">{branch.behind} behind</span>}
                  {branch.ahead > 0 && <span className="text-green-400">{branch.ahead} ahead</span>}
                </div>
              )}
              <div className="flex gap-1">
                <button className="p-1.5 text-gray-500 hover:text-white hover:bg-white/5 rounded-lg transition-colors" title="Checkout"><Download className="w-4 h-4" /></button>
                {!branch.isProtected && !branch.isDefault && (
                  <button className="p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors" title="Delete"><Trash2 className="w-4 h-4" /></button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  // ─── Tab: Commits ───
  const renderCommits = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-400">Recent commits on <span className="text-white font-medium">main</span></p>
        <button onClick={() => simulateAction("push")} className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-medium transition-colors">
          <Upload className="w-4 h-4" /> Push Commits
        </button>
      </div>
      <div className="space-y-1">
        {SAMPLE_COMMITS.map((commit) => (
          <div key={commit.sha} className="flex items-center gap-3 p-3 bg-white/5 border border-white/10 rounded-xl hover:border-white/20 transition-all">
            <GitCommit className="w-4 h-4 text-blue-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-white truncate">{commit.message}</p>
              <div className="flex items-center gap-3 text-xs text-gray-500 mt-0.5">
                <span>{commit.author}</span>
                <span>{commit.date}</span>
                <span className="text-green-400">+{commit.additions}</span>
                <span className="text-red-400">-{commit.deletions}</span>
                <span>{commit.filesChanged} files</span>
              </div>
            </div>
            <button onClick={() => navigator.clipboard.writeText(commit.sha)}
              className="flex items-center gap-1 px-2 py-1 bg-white/5 rounded-lg text-xs text-gray-400 hover:text-white font-mono transition-colors shrink-0">
              <Copy className="w-3 h-3" /> {commit.sha}
            </button>
          </div>
        ))}
      </div>
    </div>
  );

  // ─── Tab: Tests ───
  const renderTests = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Total Tests", value: SAMPLE_TESTS.reduce((s, t) => s + t.totalTests, 0).toString(), color: "text-white" },
          { label: "Passing", value: SAMPLE_TESTS.reduce((s, t) => s + t.passed, 0).toString(), color: "text-green-400" },
          { label: "Failing", value: SAMPLE_TESTS.reduce((s, t) => s + t.failed, 0).toString(), color: "text-red-400" },
          { label: "Skipped", value: SAMPLE_TESTS.reduce((s, t) => s + t.skipped, 0).toString(), color: "text-yellow-400" },
        ].map((stat) => (
          <div key={stat.label} className="p-3 bg-white/5 border border-white/10 rounded-xl text-center">
            <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
            <p className="text-xs text-gray-500 mt-0.5">{stat.label}</p>
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-400">CI Pipeline</p>
        <button onClick={() => simulateAction("test")} className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-medium transition-colors">
          <Play className="w-4 h-4" /> Run All Tests
        </button>
      </div>
      <div className="space-y-2">
        {SAMPLE_TESTS.map((test) => (
          <div key={test.id} className="flex items-center justify-between p-4 bg-white/5 border border-white/10 rounded-xl hover:border-white/20 transition-all">
            <div className="flex items-center gap-3">
              <StatusBadge status={test.status} />
              <div>
                <p className="text-sm font-medium text-white">{test.name}</p>
                <p className="text-xs text-gray-500">{test.totalTests > 0 ? `${test.passed} passed, ${test.failed} failed${test.skipped > 0 ? `, ${test.skipped} skipped` : ""}` : test.status === "running" ? "Running..." : test.status === "pending" ? "Waiting..." : "Check passed"}</p>
              </div>
            </div>
            <div className="flex items-center gap-4 text-xs text-gray-500">
              <span>{test.duration}</span>
              <button className="p-1.5 text-gray-500 hover:text-white hover:bg-white/5 rounded-lg transition-colors" title="View logs"><Terminal className="w-4 h-4" /></button>
              <button onClick={() => simulateAction("rerun")} className="p-1.5 text-gray-500 hover:text-blue-400 hover:bg-blue-500/10 rounded-lg transition-colors" title="Re-run"><RefreshCw className="w-4 h-4" /></button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  // ─── Tab: Files ───
  const renderFiles = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <FolderGit2 className="w-4 h-4" />
          <span>{selectedRepo?.fullName || "user/my-web-app"}</span>
          <ChevronRight className="w-3 h-3" />
          <span className="text-white">main</span>
        </div>
        <div className="flex gap-2">
          <button className="flex items-center gap-2 px-3 py-1.5 bg-white/5 border border-white/10 text-gray-300 rounded-lg text-xs hover:bg-white/10 transition-colors"><Upload className="w-3.5 h-3.5" /> Upload</button>
          <button className="flex items-center gap-2 px-3 py-1.5 bg-white/5 border border-white/10 text-gray-300 rounded-lg text-xs hover:bg-white/10 transition-colors"><Plus className="w-3.5 h-3.5" /> New File</button>
        </div>
      </div>
      <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden p-2">
        <FileTree items={SAMPLE_FILES} />
      </div>
    </div>
  );

  // ─── Tab: Analyze & Reverse Engineer ───
  const renderAnalyze = () => (
    <div className="space-y-6">
      <div className="p-5 bg-gradient-to-r from-purple-500/10 via-pink-500/10 to-red-500/10 border border-white/10 rounded-2xl">
        <h2 className="text-lg font-semibold text-white mb-1">Reverse Engineering & Code Analysis</h2>
        <p className="text-sm text-gray-400 mb-4">Analyze any repository &mdash; understand architecture, map dependencies, find patterns, detect security issues. Powered by Repomix, GitVizz, GitNexus, and Sourcetrail patterns.</p>
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input type="text" placeholder="Enter GitHub repo URL to analyze (e.g., facebook/react)..."
              className="w-full pl-10 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50 text-sm" />
          </div>
          <button onClick={() => simulateAction("analyze")} className="px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-xl text-sm font-medium transition-colors">Analyze</button>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Analysis Capabilities</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {[
            { icon: <Layers className="w-5 h-5" />, title: "Architecture Mapping", desc: "Map modules, exports, dependencies, and circular references", tools: "AST analysis + Sourcetrail patterns" },
            { icon: <Network className="w-5 h-5" />, title: "Dependency Graphs", desc: "Interactive force-directed graphs showing how code connects", tools: "GitVizz + D3.js visualization" },
            { icon: <BookOpen className="w-5 h-5" />, title: "Knowledge Graph", desc: "Build navigable knowledge graph from codebase structure", tools: "GitNexus + Graph RAG" },
            { icon: <Code2 className="w-5 h-5" />, title: "Pattern Detection", desc: "Detect design patterns, anti-patterns, and code smells", tools: "AST analysis + heuristics" },
            { icon: <Shield className="w-5 h-5" />, title: "Security Scanning", desc: "Find hardcoded secrets, injection risks, XSS vectors", tools: "Static analysis + pattern matching" },
            { icon: <BarChart3 className="w-5 h-5" />, title: "Quality Metrics", desc: "Complexity, coverage, duplication, tech debt estimation", tools: "CodeCharta patterns + metrics" },
            { icon: <Workflow className="w-5 h-5" />, title: "API Endpoint Mapping", desc: "Discover REST, GraphQL, WebSocket endpoints and routes", tools: "Route analysis + handler mapping" },
            { icon: <Bot className="w-5 h-5" />, title: "AI-Powered Ingest", desc: "Convert entire repo to LLM-friendly text for deep analysis", tools: "Repomix (22K stars) + Gitingest (14K stars)" },
            { icon: <Braces className="w-5 h-5" />, title: "Code Understanding", desc: "Read, understand, and explain any file or function", tools: "GitHub Contents API + AI context" },
          ].map((cap) => (
            <div key={cap.title} className="p-4 bg-white/5 border border-white/10 rounded-xl hover:border-white/20 transition-all">
              <div className="flex items-center gap-2 mb-2">
                <div className="text-purple-400">{cap.icon}</div>
                <h4 className="font-medium text-white text-sm">{cap.title}</h4>
              </div>
              <p className="text-xs text-gray-400 mb-2">{cap.desc}</p>
              <p className="text-[10px] text-purple-400/60 flex items-center gap-1"><Puzzle className="w-3 h-3" /> {cap.tools}</p>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Analysis Results {analysisRepo ? `\u2014 ${analysisRepo.fullName}` : ""}</h3>
        <div className="space-y-2">
          {SAMPLE_ANALYSIS.map((result) => (
            <div key={result.id} className="flex items-center justify-between p-4 bg-white/5 border border-white/10 rounded-xl hover:border-white/20 transition-all">
              <div className="flex items-center gap-3">
                <StatusBadge status={result.status} />
                <div>
                  <p className="text-sm font-medium text-white">{result.title}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{result.description}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className={`text-xs font-medium ${result.severity === "critical" ? "text-red-400" : result.severity === "warning" ? "text-yellow-400" : "text-blue-400"}`}>
                  {result.findings} findings
                </span>
                <button className="p-1.5 text-gray-500 hover:text-white hover:bg-white/5 rounded-lg transition-colors" title="View details"><Eye className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="p-4 bg-white/5 border border-white/10 rounded-xl">
        <h3 className="text-sm font-semibold text-white mb-3">How Reverse Engineering Works</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {[
            { step: "1", title: "Clone & Ingest", desc: "Repository is cloned and converted to AI-readable format using Repomix / Gitingest" },
            { step: "2", title: "AST Analysis", desc: "Abstract Syntax Tree parsing identifies modules, functions, classes, and their relationships" },
            { step: "3", title: "Graph Building", desc: "Dependency graph and knowledge graph are constructed showing how code connects" },
            { step: "4", title: "AI Analysis", desc: "AI agent analyzes architecture, patterns, security issues, and generates comprehensive report" },
          ].map((s) => (
            <div key={s.step} className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center text-sm font-bold shrink-0">{s.step}</div>
              <div>
                <h4 className="text-sm font-medium text-white">{s.title}</h4>
                <p className="text-xs text-gray-500 mt-0.5">{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  // ─── Tab: Quick Actions ───
  const renderActions = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-white">Quick Actions</h3>
      <p className="text-sm text-gray-400">Common GitHub operations. The AI agent executes these on your behalf.</p>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {[
          { icon: <Download className="w-5 h-5" />, title: "Clone Repository", desc: "Clone any public or private repo into workspace", bg: "bg-blue-500/10", text: "text-blue-400" },
          { icon: <Upload className="w-5 h-5" />, title: "Push Changes", desc: "Commit and push all changes to remote", bg: "bg-green-500/10", text: "text-green-400" },
          { icon: <ArrowDownToLine className="w-5 h-5" />, title: "Pull Latest", desc: "Pull latest changes from remote branch", bg: "bg-cyan-500/10", text: "text-cyan-400" },
          { icon: <GitPullRequest className="w-5 h-5" />, title: "Create Pull Request", desc: "Create a new PR with your changes", bg: "bg-purple-500/10", text: "text-purple-400" },
          { icon: <GitMerge className="w-5 h-5" />, title: "Merge PR", desc: "Review and merge an open pull request", bg: "bg-violet-500/10", text: "text-violet-400" },
          { icon: <GitBranch className="w-5 h-5" />, title: "Create Branch", desc: "Create a new branch from current state", bg: "bg-orange-500/10", text: "text-orange-400" },
          { icon: <Play className="w-5 h-5" />, title: "Run Tests", desc: "Run test suite and show results", bg: "bg-yellow-500/10", text: "text-yellow-400" },
          { icon: <Terminal className="w-5 h-5" />, title: "Run Build", desc: "Build the project and check for errors", bg: "bg-red-500/10", text: "text-red-400" },
          { icon: <Tag className="w-5 h-5" />, title: "Create Release", desc: "Tag and publish a new release version", bg: "bg-pink-500/10", text: "text-pink-400" },
          { icon: <Eye className="w-5 h-5" />, title: "View Diff", desc: "See all uncommitted changes", bg: "bg-gray-500/10", text: "text-gray-400" },
          { icon: <RefreshCw className="w-5 h-5" />, title: "Sync Fork", desc: "Sync your fork with upstream repository", bg: "bg-teal-500/10", text: "text-teal-400" },
          { icon: <Globe className="w-5 h-5" />, title: "Search Public Repos", desc: "Search all of GitHub for open-source tools", bg: "bg-indigo-500/10", text: "text-indigo-400" },
          { icon: <Microscope className="w-5 h-5" />, title: "Reverse Engineer Repo", desc: "Deep-analyze any repo architecture and patterns", bg: "bg-rose-500/10", text: "text-rose-400" },
          { icon: <Bot className="w-5 h-5" />, title: "Ingest for AI", desc: "Convert repo to LLM-friendly text format", bg: "bg-amber-500/10", text: "text-amber-400" },
          { icon: <Settings className="w-5 h-5" />, title: "Configure Repo", desc: "Set up branch protection, secrets, webhooks", bg: "bg-slate-500/10", text: "text-slate-400" },
        ].map((action) => (
          <button key={action.title} onClick={() => simulateAction(action.title)}
            className="flex items-center gap-3 p-4 bg-white/5 border border-white/10 rounded-xl text-left hover:border-white/20 hover:bg-white/[0.07] transition-all group">
            <div className={`p-2.5 rounded-xl ${action.bg} ${action.text}`}>{action.icon}</div>
            <div>
              <h4 className="font-medium text-white text-sm">{action.title}</h4>
              <p className="text-xs text-gray-500 mt-0.5">{action.desc}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="h-full overflow-y-auto custom-scrollbar-always p-6 lg:p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-cyan-400 to-green-400">GitHub Operations</h1>
          <p className="text-sm text-gray-400 mt-1">Search, browse, clone, analyze, reverse engineer, create PRs, push, pull, test &mdash; full GitHub access</p>
        </div>
        <button onClick={() => simulateAction("refresh")} disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 text-gray-300 rounded-xl text-sm hover:bg-white/10 transition-colors disabled:opacity-50">
          <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      {/* Connection status */}
      <div className="flex items-center gap-3 mb-6 p-3 bg-green-500/10 border border-green-500/20 rounded-xl">
        <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
        <span className="text-sm text-green-400">Connected to GitHub</span>
        <span className="text-xs text-gray-500">&mdash; Full access: search, read, write, create PRs, manage repos</span>
        <span className="text-xs text-gray-500 ml-auto">via @octokit/rest (11.8M weekly downloads)</span>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-white/5 border border-white/10 rounded-xl p-1 overflow-x-auto">
        {tabs.map((tab) => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${activeTab === tab.id ? "bg-white/10 text-white" : "text-gray-400 hover:text-white hover:bg-white/5"}`}>
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <AnimatePresence mode="wait">
        <motion.div key={activeTab} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.2 }}>
          {activeTab === "explore" && renderExplore()}
          {activeTab === "my-repos" && renderMyRepos()}
          {activeTab === "prs" && renderPRs()}
          {activeTab === "branches" && renderBranches()}
          {activeTab === "commits" && renderCommits()}
          {activeTab === "tests" && renderTests()}
          {activeTab === "files" && renderFiles()}
          {activeTab === "analyze" && renderAnalyze()}
          {activeTab === "actions" && renderActions()}
        </motion.div>
      </AnimatePresence>

      {/* Loading overlay */}
      <AnimatePresence>
        {isLoading && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-gray-900 border border-white/10 rounded-2xl p-6 flex flex-col items-center gap-3">
              <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
              <p className="text-sm text-gray-300">Processing...</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Create PR Modal */}
      <AnimatePresence>
        {showCreatePR && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => setShowCreatePR(false)}>
            <motion.div initial={{ scale: 0.95 }} animate={{ scale: 1 }} exit={{ scale: 0.95 }}
              className="bg-gray-900 border border-white/10 rounded-2xl p-6 w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
              <h2 className="text-lg font-bold text-white mb-4">Create Pull Request</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Title</label>
                  <input type="text" value={newPR.title} onChange={(e) => setNewPR({ ...newPR, title: e.target.value })}
                    placeholder="feat: Add new feature..."
                    className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Description</label>
                  <textarea value={newPR.description} onChange={(e) => setNewPR({ ...newPR, description: e.target.value })}
                    placeholder="Describe your changes..." rows={4}
                    className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 text-sm resize-none" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Base Branch</label>
                    <select value={newPR.baseBranch} onChange={(e) => setNewPR({ ...newPR, baseBranch: e.target.value })}
                      className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:border-blue-500/50 text-sm">
                      {SAMPLE_BRANCHES.map((b) => <option key={b.name} value={b.name}>{b.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Head Branch</label>
                    <select value={newPR.headBranch} onChange={(e) => setNewPR({ ...newPR, headBranch: e.target.value })}
                      className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:border-blue-500/50 text-sm">
                      <option value="">Select branch...</option>
                      {SAMPLE_BRANCHES.filter((b) => b.name !== newPR.baseBranch).map((b) => <option key={b.name} value={b.name}>{b.name}</option>)}
                    </select>
                  </div>
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                  <input type="checkbox" checked={newPR.isDraft} onChange={(e) => setNewPR({ ...newPR, isDraft: e.target.checked })} className="rounded" />
                  Create as draft
                </label>
              </div>
              <div className="flex gap-3 mt-6">
                <button onClick={() => setShowCreatePR(false)} className="flex-1 px-4 py-2.5 bg-white/5 border border-white/10 text-gray-300 rounded-xl text-sm hover:bg-white/10 transition-colors">Cancel</button>
                <button onClick={() => { simulateAction("create-pr"); setShowCreatePR(false); }} disabled={!newPR.title || !newPR.headBranch}
                  className="flex-1 px-4 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-xl text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                  Create Pull Request
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Create Branch Modal */}
      <AnimatePresence>
        {showCreateBranch && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => setShowCreateBranch(false)}>
            <motion.div initial={{ scale: 0.95 }} animate={{ scale: 1 }} exit={{ scale: 0.95 }}
              className="bg-gray-900 border border-white/10 rounded-2xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
              <h2 className="text-lg font-bold text-white mb-4">Create New Branch</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Branch Name</label>
                  <input type="text" value={newBranch.name} onChange={(e) => setNewBranch({ ...newBranch, name: e.target.value })}
                    placeholder="feature/my-new-feature"
                    className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 text-sm" />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">From Branch</label>
                  <select value={newBranch.fromBranch} onChange={(e) => setNewBranch({ ...newBranch, fromBranch: e.target.value })}
                    className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:border-blue-500/50 text-sm">
                    {SAMPLE_BRANCHES.map((b) => <option key={b.name} value={b.name}>{b.name}</option>)}
                  </select>
                </div>
              </div>
              <div className="flex gap-3 mt-6">
                <button onClick={() => setShowCreateBranch(false)} className="flex-1 px-4 py-2.5 bg-white/5 border border-white/10 text-gray-300 rounded-xl text-sm hover:bg-white/10 transition-colors">Cancel</button>
                <button onClick={() => { simulateAction("create-branch"); setShowCreateBranch(false); }} disabled={!newBranch.name}
                  className="flex-1 px-4 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-xl text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                  Create Branch
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Ingest for AI Modal */}
      <AnimatePresence>
        {showIngestModal && ingestRepo && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => setShowIngestModal(false)}>
            <motion.div initial={{ scale: 0.95 }} animate={{ scale: 1 }} exit={{ scale: 0.95 }}
              className="bg-gray-900 border border-white/10 rounded-2xl p-6 w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
              <h2 className="text-lg font-bold text-white mb-2">Ingest Repository for AI</h2>
              <p className="text-sm text-gray-400 mb-4">Convert <span className="text-white font-medium">{ingestRepo.fullName}</span> into LLM-friendly text format</p>
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-white">Choose Tool:</h3>
                {[
                  { name: "Repomix", stars: "22.5K", desc: "Pack repo into a single AI-friendly file. Best for deep analysis with Claude/ChatGPT.", badge: "Recommended" },
                  { name: "Gitingest", stars: "14.2K", desc: "Prompt-friendly digest with directory structure, file contents, and statistics.", badge: "" },
                  { name: "GitNexus", stars: "18.9K", desc: "Build interactive knowledge graph with Graph RAG Agent for code exploration.", badge: "" },
                ].map((tool) => (
                  <button key={tool.name} onClick={() => { simulateAction(`ingest-${tool.name}`); setShowIngestModal(false); }}
                    className="w-full p-4 bg-white/5 border border-white/10 rounded-xl text-left hover:border-purple-500/30 transition-all">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-white text-sm">{tool.name}</span>
                      <span className="text-[10px] text-gray-500 flex items-center gap-1"><Star className="w-2.5 h-2.5" /> {tool.stars}</span>
                      {tool.badge && <span className="px-2 py-0.5 rounded text-[10px] bg-green-500/20 text-green-400">{tool.badge}</span>}
                    </div>
                    <p className="text-xs text-gray-400">{tool.desc}</p>
                  </button>
                ))}
              </div>
              <button onClick={() => setShowIngestModal(false)} className="w-full mt-4 px-4 py-2.5 bg-white/5 border border-white/10 text-gray-300 rounded-xl text-sm hover:bg-white/10 transition-colors">Cancel</button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
