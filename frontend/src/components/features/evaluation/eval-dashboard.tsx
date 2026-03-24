import React, { useState } from "react";
import { motion } from "framer-motion";
import {
  LucideCheckCircle,
  LucideXCircle,
  LucideClock,
  LucideActivity,
  LucideCoins,
  LucideTrendingUp,
  LucideBarChart3,
  LucideCalendar,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { AnimatedGradientText } from "#/components/ui/animated-gradient-text";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  color: string;
  trend?: { value: number; positive: boolean };
}

function MetricCard({ title, value, subtitle, icon, color, trend }: MetricCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-5 rounded-2xl border border-white/10 bg-white/5 backdrop-blur-sm"
    >
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center bg-${color}-500/20`}>
          <span className={`text-${color}-400`}>{icon}</span>
        </div>
        {trend && (
          <span
            className={`flex items-center gap-1 text-xs px-2 py-1 rounded-full ${
              trend.positive
                ? "bg-green-500/10 text-green-400"
                : "bg-red-500/10 text-red-400"
            }`}
          >
            <LucideTrendingUp
              className={`w-3 h-3 ${!trend.positive ? "rotate-180" : ""}`}
            />
            {trend.value}%
          </span>
        )}
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-sm text-gray-400 mt-0.5">{title}</p>
      {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
    </motion.div>
  );
}

// Sample data for charts
const performanceData = [
  { date: "Mon", completed: 12, failed: 2 },
  { date: "Tue", completed: 15, failed: 1 },
  { date: "Wed", completed: 10, failed: 3 },
  { date: "Thu", completed: 18, failed: 2 },
  { date: "Fri", completed: 22, failed: 1 },
  { date: "Sat", completed: 8, failed: 0 },
  { date: "Sun", completed: 14, failed: 1 },
];

const errorDistribution = [
  { name: "Syntax Error", value: 25, color: "#EF4444" },
  { name: "Type Error", value: 20, color: "#F59E0B" },
  { name: "Runtime Error", value: 15, color: "#8B5CF6" },
  { name: "Network Error", value: 12, color: "#3B82F6" },
  { name: "Timeout", value: 8, color: "#06B6D4" },
  { name: "Other", value: 20, color: "#6B7280" },
];

const costData = [
  { date: "Week 1", tokens: 120000, cost: 2.4 },
  { date: "Week 2", tokens: 180000, cost: 3.6 },
  { date: "Week 3", tokens: 150000, cost: 3.0 },
  { date: "Week 4", tokens: 200000, cost: 4.0 },
];

const sessionHistory = [
  { id: "1", task: "Build user dashboard", status: "completed", duration: "12m", date: "2024-03-20", tokens: 15000 },
  { id: "2", task: "Fix login bug", status: "completed", duration: "5m", date: "2024-03-20", tokens: 8000 },
  { id: "3", task: "Deploy to AWS", status: "failed", duration: "18m", date: "2024-03-19", tokens: 22000 },
  { id: "4", task: "Add dark mode", status: "completed", duration: "8m", date: "2024-03-19", tokens: 12000 },
  { id: "5", task: "Write API tests", status: "completed", duration: "15m", date: "2024-03-18", tokens: 18000 },
  { id: "6", task: "Refactor database", status: "completed", duration: "25m", date: "2024-03-18", tokens: 30000 },
];

const customTooltipStyle = {
  backgroundColor: "#1a1a2e",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: "12px",
  padding: "8px 12px",
  color: "#fff",
  fontSize: "12px",
};

export function EvalDashboard() {
  const [timeRange, setTimeRange] = useState<"week" | "month" | "all">("week");

  return (
    <div className="h-full overflow-y-auto custom-scrollbar-always p-6 lg:p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <AnimatedGradientText as="h1" className="text-2xl font-bold" gradient="from-green-400 via-blue-400 to-purple-400">
            Evaluation Dashboard
          </AnimatedGradientText>
          <p className="text-sm text-gray-400 mt-1">Agent performance metrics and analytics</p>
        </div>
        <div className="flex bg-white/5 border border-white/10 rounded-xl overflow-hidden">
          {(["week", "month", "all"] as const).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-4 py-2 text-sm capitalize ${
                timeRange === range
                  ? "bg-white/10 text-white"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              {range === "all" ? "All Time" : `This ${range}`}
            </button>
          ))}
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <MetricCard
          title="Task Completion Rate"
          value="89%"
          subtitle="99 of 109 tasks"
          icon={<LucideCheckCircle className="w-5 h-5" />}
          color="green"
          trend={{ value: 5, positive: true }}
        />
        <MetricCard
          title="Average Task Time"
          value="11.2m"
          subtitle="Down from 14.5m"
          icon={<LucideClock className="w-5 h-5" />}
          color="blue"
          trend={{ value: 23, positive: true }}
        />
        <MetricCard
          title="Error Rate"
          value="8.3%"
          subtitle="10 errors this period"
          icon={<LucideXCircle className="w-5 h-5" />}
          color="red"
          trend={{ value: 3, positive: false }}
        />
        <MetricCard
          title="Token Usage"
          value="650K"
          subtitle="~$13.00 estimated cost"
          icon={<LucideCoins className="w-5 h-5" />}
          color="yellow"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Task Completion Chart */}
        <div className="p-5 rounded-2xl border border-white/10 bg-white/5">
          <div className="flex items-center gap-2 mb-4">
            <LucideBarChart3 className="w-4 h-4 text-blue-400" />
            <h3 className="text-sm font-medium text-white">Task Completion</h3>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={performanceData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="date" tick={{ fill: "#6B7280", fontSize: 12 }} axisLine={false} />
              <YAxis tick={{ fill: "#6B7280", fontSize: 12 }} axisLine={false} />
              <Tooltip contentStyle={customTooltipStyle} />
              <Bar dataKey="completed" fill="#3B82F6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="failed" fill="#EF4444" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Error Distribution */}
        <div className="p-5 rounded-2xl border border-white/10 bg-white/5">
          <div className="flex items-center gap-2 mb-4">
            <LucideActivity className="w-4 h-4 text-red-400" />
            <h3 className="text-sm font-medium text-white">Error Distribution</h3>
          </div>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width="50%" height={200}>
              <PieChart>
                <Pie
                  data={errorDistribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {errorDistribution.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={customTooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex-1 space-y-2">
              {errorDistribution.map((entry) => (
                <div key={entry.name} className="flex items-center gap-2">
                  <div
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: entry.color }}
                  />
                  <span className="text-xs text-gray-400 flex-1">{entry.name}</span>
                  <span className="text-xs text-white font-medium">{entry.value}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Cost Tracking */}
        <div className="p-5 rounded-2xl border border-white/10 bg-white/5 lg:col-span-2">
          <div className="flex items-center gap-2 mb-4">
            <LucideCoins className="w-4 h-4 text-yellow-400" />
            <h3 className="text-sm font-medium text-white">Token Usage & Cost</h3>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={costData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="date" tick={{ fill: "#6B7280", fontSize: 12 }} axisLine={false} />
              <YAxis yAxisId="tokens" tick={{ fill: "#6B7280", fontSize: 12 }} axisLine={false} />
              <YAxis yAxisId="cost" orientation="right" tick={{ fill: "#6B7280", fontSize: 12 }} axisLine={false} />
              <Tooltip contentStyle={customTooltipStyle} />
              <Line yAxisId="tokens" type="monotone" dataKey="tokens" stroke="#3B82F6" strokeWidth={2} dot={false} />
              <Line yAxisId="cost" type="monotone" dataKey="cost" stroke="#F59E0B" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Session History */}
      <div className="rounded-2xl border border-white/10 bg-white/5 overflow-hidden">
        <div className="flex items-center gap-2 p-5 border-b border-white/10">
          <LucideCalendar className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm font-medium text-white">Session History</h3>
        </div>
        <div className="divide-y divide-white/5">
          {sessionHistory.map((session) => (
            <div key={session.id} className="flex items-center gap-4 px-5 py-3 hover:bg-white/5 transition-colors">
              <div className={`w-2 h-2 rounded-full ${session.status === "completed" ? "bg-green-400" : "bg-red-400"}`} />
              <span className="text-sm text-white flex-1">{session.task}</span>
              <span className="text-xs text-gray-500">{session.duration}</span>
              <span className="text-xs text-gray-500">{session.tokens.toLocaleString()} tokens</span>
              <span className="text-xs text-gray-500">{session.date}</span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full ${
                  session.status === "completed"
                    ? "bg-green-500/10 text-green-400"
                    : "bg-red-500/10 text-red-400"
                }`}
              >
                {session.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
