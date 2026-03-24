import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LucideSmartphone,
  LucideTablet,
  LucideMonitor,
  LucidePlay,
  LucideApple,
  LucideWifi,
  LucideWifiOff,
  LucideRefreshCw,
  LucideCamera,
  LucideVideo,
  LucideUpload,
  LucideDownload,
  LucideSettings,
  LucideSearch,
  LucideCheck,
  LucideX,
  LucideLoader2,
  LucideRotateCw,
  LucideMaximize2,
  LucideZap,
  LucideGlobe,
  LucideBug,
  LucideQrCode,
  LucideActivity,
} from "lucide-react";
import { AnimatedGradientText } from "#/components/ui/animated-gradient-text";

type DeviceType = "phone" | "tablet";
type DevicePlatform = "ios" | "android";
type DeviceStatus = "available" | "in-use" | "offline";
type TestStatus = "idle" | "running" | "passed" | "failed";

interface TestDevice {
  id: string;
  name: string;
  type: DeviceType;
  platform: DevicePlatform;
  os: string;
  screenSize: string;
  resolution: string;
  status: DeviceStatus;
  isSimulator: boolean;
}

interface TestRun {
  id: string;
  name: string;
  device: string;
  status: TestStatus;
  duration?: string;
  passedTests?: number;
  failedTests?: number;
  timestamp: string;
}

const DEVICES: TestDevice[] = [
  { id: "1", name: "iPhone 16 Pro", type: "phone", platform: "ios", os: "iOS 18.3", screenSize: "6.3\"", resolution: "2622x1206", status: "available", isSimulator: true },
  { id: "2", name: "iPhone 15", type: "phone", platform: "ios", os: "iOS 17.5", screenSize: "6.1\"", resolution: "2556x1179", status: "available", isSimulator: true },
  { id: "3", name: "iPad Pro 12.9\"", type: "tablet", platform: "ios", os: "iPadOS 18.3", screenSize: "12.9\"", resolution: "2732x2048", status: "available", isSimulator: true },
  { id: "4", name: "Samsung Galaxy S24 Ultra", type: "phone", platform: "android", os: "Android 15", screenSize: "6.8\"", resolution: "3120x1440", status: "available", isSimulator: true },
  { id: "5", name: "Google Pixel 9 Pro", type: "phone", platform: "android", os: "Android 15", screenSize: "6.3\"", resolution: "2856x1280", status: "available", isSimulator: true },
  { id: "6", name: "Samsung Galaxy Tab S9", type: "tablet", platform: "android", os: "Android 14", screenSize: "11\"", resolution: "2560x1600", status: "available", isSimulator: true },
  { id: "7", name: "iPhone SE (3rd gen)", type: "phone", platform: "ios", os: "iOS 17.5", screenSize: "4.7\"", resolution: "1334x750", status: "offline", isSimulator: true },
  { id: "8", name: "Google Pixel 8", type: "phone", platform: "android", os: "Android 14", screenSize: "6.2\"", resolution: "2400x1080", status: "available", isSimulator: true },
];

const TEST_HISTORY: TestRun[] = [
  { id: "t1", name: "Login flow E2E", device: "iPhone 16 Pro", status: "passed", duration: "1m 23s", passedTests: 12, failedTests: 0, timestamp: "2 hours ago" },
  { id: "t2", name: "Checkout flow", device: "Galaxy S24 Ultra", status: "failed", duration: "2m 45s", passedTests: 8, failedTests: 3, timestamp: "5 hours ago" },
  { id: "t3", name: "Navigation tabs", device: "iPad Pro 12.9\"", status: "passed", duration: "0m 48s", passedTests: 6, failedTests: 0, timestamp: "1 day ago" },
];

const STATUS_CONFIG: Record<DeviceStatus, { color: string; label: string }> = {
  "available": { color: "text-green-400", label: "Available" },
  "in-use": { color: "text-yellow-400", label: "In Use" },
  "offline": { color: "text-gray-500", label: "Offline" },
};

const TEST_STATUS_CONFIG: Record<TestStatus, { color: string; bg: string; label: string }> = {
  idle: { color: "text-gray-400", bg: "bg-gray-500/20", label: "Idle" },
  running: { color: "text-blue-400", bg: "bg-blue-500/20", label: "Running" },
  passed: { color: "text-green-400", bg: "bg-green-500/20", label: "Passed" },
  failed: { color: "text-red-400", bg: "bg-red-500/20", label: "Failed" },
};

type TabView = "devices" | "testing" | "preview" | "history";

export function MobileTestingLab() {
  const [activeTab, setActiveTab] = useState<TabView>("devices");
  const [filterPlatform, setFilterPlatform] = useState<DevicePlatform | "all">("all");
  const [selectedDevice, setSelectedDevice] = useState<TestDevice | null>(null);
  const [previewDevice, setPreviewDevice] = useState<TestDevice | null>(null);
  const [testRunning, setTestRunning] = useState(false);

  const filteredDevices = DEVICES.filter((d) =>
    filterPlatform === "all" || d.platform === filterPlatform,
  );

  const handleRunTest = (device: TestDevice) => {
    setSelectedDevice(device);
    setTestRunning(true);
    setTimeout(() => setTestRunning(false), 4000);
  };

  return (
    <div className="h-full overflow-y-auto custom-scrollbar-always p-6 lg:p-8">
      {/* Header */}
      <div className="mb-6">
        <AnimatedGradientText as="h1" className="text-2xl font-bold" gradient="from-teal-400 via-cyan-400 to-blue-400">
          Mobile Testing Lab
        </AnimatedGradientText>
        <p className="text-sm text-gray-400 mt-1">
          Test your apps on simulators, emulators, and real devices — preview live on any screen size
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 mb-6 border-b border-white/10 pb-3">
        {(
          [
            { key: "devices", label: "Device Farm", icon: <LucideSmartphone className="w-4 h-4" /> },
            { key: "testing", label: "Test Runner", icon: <LucideBug className="w-4 h-4" /> },
            { key: "preview", label: "Live Preview", icon: <LucideMaximize2 className="w-4 h-4" /> },
            { key: "history", label: "Test History", icon: <LucideActivity className="w-4 h-4" /> },
          ] as { key: TabView; label: string; icon: React.ReactNode }[]
        ).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "bg-teal-500/20 text-teal-400 border border-teal-500/30"
                : "text-gray-400 hover:text-white hover:bg-white/5"
            }`}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Device Farm Tab */}
      {activeTab === "devices" && (
        <div>
          {/* Platform filter */}
          <div className="flex gap-2 mb-4">
            {(
              [
                { id: "all", label: "All Devices" },
                { id: "ios", label: "iOS", icon: <LucideApple className="w-3 h-3" /> },
                { id: "android", label: "Android", icon: <LucidePlay className="w-3 h-3" /> },
              ] as { id: DevicePlatform | "all"; label: string; icon?: React.ReactNode }[]
            ).map((p) => (
              <button
                key={p.id}
                onClick={() => setFilterPlatform(p.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  filterPlatform === p.id
                    ? "bg-white/10 text-white border border-white/20"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                {p.icon} {p.label}
              </button>
            ))}
          </div>

          {/* Device grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredDevices.map((device) => (
              <motion.div
                key={device.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-4 bg-white/5 border border-white/10 rounded-2xl hover:border-white/20 transition-colors"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                      device.platform === "ios" ? "bg-gray-800" : "bg-green-900/50"
                    }`}>
                      {device.type === "tablet" ? (
                        <LucideTablet className="w-5 h-5 text-white" />
                      ) : (
                        <LucideSmartphone className="w-5 h-5 text-white" />
                      )}
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-white">{device.name}</h3>
                      <p className="text-xs text-gray-500">{device.os}</p>
                    </div>
                  </div>
                  <span className={`text-xs ${STATUS_CONFIG[device.status].color}`}>
                    {STATUS_CONFIG[device.status].label}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 mb-3 text-xs text-gray-400">
                  <div>
                    <p className="text-gray-600">Screen</p>
                    <p>{device.screenSize}</p>
                  </div>
                  <div>
                    <p className="text-gray-600">Resolution</p>
                    <p>{device.resolution}</p>
                  </div>
                  <div>
                    <p className="text-gray-600">Type</p>
                    <p>{device.isSimulator ? "Simulator" : "Physical"}</p>
                  </div>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => setPreviewDevice(device)}
                    disabled={device.status === "offline"}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-teal-500/20 text-teal-400 rounded-lg text-xs hover:bg-teal-500/30 disabled:opacity-40"
                  >
                    <LucideMaximize2 className="w-3 h-3" /> Preview
                  </button>
                  <button
                    onClick={() => handleRunTest(device)}
                    disabled={device.status === "offline"}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-white/5 text-gray-300 rounded-lg text-xs hover:bg-white/10 disabled:opacity-40"
                  >
                    <LucideBug className="w-3 h-3" /> Test
                  </button>
                  <button
                    disabled={device.status === "offline"}
                    className="flex items-center justify-center px-2 py-2 bg-white/5 text-gray-400 rounded-lg text-xs hover:bg-white/10 disabled:opacity-40"
                  >
                    <LucideCamera className="w-3 h-3" />
                  </button>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Add Physical Device */}
          <div className="mt-6 p-4 border border-dashed border-white/10 rounded-2xl text-center">
            <LucideQrCode className="w-8 h-8 text-gray-600 mx-auto mb-2" />
            <p className="text-sm text-gray-400 mb-1">Connect a Physical Device</p>
            <p className="text-xs text-gray-500 mb-3">
              Scan QR code with Expo Go app to test on your real phone, or connect via USB with ADB/Xcode
            </p>
            <button className="px-4 py-2 bg-white/5 border border-white/10 text-gray-300 rounded-xl text-xs hover:bg-white/10">
              Generate QR Code
            </button>
          </div>
        </div>
      )}

      {/* Test Runner Tab */}
      {activeTab === "testing" && (
        <div className="space-y-6">
          {/* Test Configuration */}
          <div className="p-5 bg-white/5 border border-white/10 rounded-2xl">
            <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
              <LucideBug className="w-4 h-4 text-teal-400" /> Test Configuration
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Test Framework</label>
                <div className="flex gap-2">
                  {["Maestro (YAML)", "Detox (JS)", "Appium", "XCUITest", "Espresso"].map((fw) => (
                    <button
                      key={fw}
                      className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-xs text-gray-300 hover:border-white/20"
                    >
                      {fw}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Test Target</label>
                <div className="flex gap-2">
                  {DEVICES.filter((d) => d.status === "available").slice(0, 4).map((d) => (
                    <button
                      key={d.id}
                      onClick={() => setSelectedDevice(d)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                        selectedDevice?.id === d.id
                          ? "border-teal-500/50 bg-teal-500/10 text-teal-400"
                          : "border-white/10 bg-white/5 text-gray-300 hover:border-white/20"
                      }`}
                    >
                      {d.platform === "ios" ? <LucideApple className="w-3 h-3" /> : <LucidePlay className="w-3 h-3" />}
                      {d.name}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Test File or Flow</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="tests/e2e/login.yaml or describe your test..."
                    className="flex-1 px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 text-sm focus:outline-none focus:border-teal-500/50"
                  />
                  <button className="flex items-center gap-1.5 px-4 py-2.5 bg-white/5 border border-white/10 text-gray-300 rounded-xl text-sm hover:bg-white/10">
                    <LucideUpload className="w-4 h-4" /> Upload
                  </button>
                </div>
              </div>

              <button
                onClick={() => selectedDevice && handleRunTest(selectedDevice)}
                disabled={!selectedDevice || testRunning}
                className="flex items-center justify-center gap-2 w-full px-4 py-3 bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-600 hover:to-cyan-600 text-white rounded-xl text-sm font-medium disabled:opacity-50"
              >
                {testRunning ? (
                  <>
                    <LucideLoader2 className="w-4 h-4 animate-spin" /> Running Tests...
                  </>
                ) : (
                  <>
                    <LucideZap className="w-4 h-4" /> Run Tests
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Test Output */}
          {testRunning && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="p-5 bg-[#0d1117] border border-white/10 rounded-2xl font-mono text-sm"
            >
              <div className="flex items-center gap-2 mb-3">
                <LucideLoader2 className="w-4 h-4 text-teal-400 animate-spin" />
                <span className="text-teal-400">Running tests on {selectedDevice?.name}...</span>
              </div>
              <div className="space-y-1 text-xs">
                <p className="text-green-400">✓ App launched successfully</p>
                <p className="text-green-400">✓ Home screen loaded</p>
                <p className="text-green-400">✓ Login button visible</p>
                <p className="text-yellow-400">● Tapping login button...</p>
                <p className="text-gray-500 animate-pulse">  Waiting for navigation...</p>
              </div>
            </motion.div>
          )}
        </div>
      )}

      {/* Live Preview Tab */}
      {activeTab === "preview" && (
        <div className="flex flex-col items-center">
          {/* Device selector */}
          <div className="flex gap-2 mb-6 flex-wrap justify-center">
            {DEVICES.filter((d) => d.status === "available").map((d) => (
              <button
                key={d.id}
                onClick={() => setPreviewDevice(d)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                  previewDevice?.id === d.id
                    ? "border-teal-500/50 bg-teal-500/10 text-teal-400"
                    : "border-white/10 bg-white/5 text-gray-300 hover:border-white/20"
                }`}
              >
                {d.platform === "ios" ? <LucideApple className="w-3 h-3" /> : <LucidePlay className="w-3 h-3" />}
                {d.name}
              </button>
            ))}
          </div>

          {/* Device Preview Frame */}
          {previewDevice ? (
            <div className="flex flex-col items-center">
              {/* Controls */}
              <div className="flex gap-2 mb-4">
                <button className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 text-gray-300 rounded-lg text-xs hover:bg-white/10">
                  <LucideRotateCw className="w-3 h-3" /> Rotate
                </button>
                <button className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 text-gray-300 rounded-lg text-xs hover:bg-white/10">
                  <LucideCamera className="w-3 h-3" /> Screenshot
                </button>
                <button className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 text-gray-300 rounded-lg text-xs hover:bg-white/10">
                  <LucideVideo className="w-3 h-3" /> Record
                </button>
                <button className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 text-gray-300 rounded-lg text-xs hover:bg-white/10">
                  <LucideRefreshCw className="w-3 h-3" /> Reload
                </button>
              </div>

              {/* Phone frame */}
              <div
                className={`relative rounded-[40px] border-4 border-gray-700 bg-black overflow-hidden shadow-2xl ${
                  previewDevice.type === "tablet" ? "w-[480px] h-[640px]" : "w-[280px] h-[560px]"
                }`}
              >
                {/* Notch / Dynamic Island */}
                {previewDevice.platform === "ios" && previewDevice.type === "phone" && (
                  <div className="absolute top-2 left-1/2 -translate-x-1/2 w-24 h-6 bg-black rounded-full z-10" />
                )}

                {/* Status bar */}
                <div className="h-10 bg-[#1a1a1a] flex items-center justify-between px-6 text-[10px] text-white">
                  <span>9:41</span>
                  <div className="flex gap-1">
                    <LucideWifi className="w-3 h-3" />
                    <LucideActivity className="w-3 h-3" />
                  </div>
                </div>

                {/* App content area */}
                <div className="flex-1 bg-[#0d1117] flex flex-col items-center justify-center h-[calc(100%-80px)] p-4">
                  <LucideGlobe className="w-12 h-12 text-teal-400/30 mb-4" />
                  <p className="text-sm text-white font-medium text-center">Live Preview</p>
                  <p className="text-xs text-gray-500 text-center mt-2">
                    Connect your app URL or scan QR code<br />to preview on {previewDevice.name}
                  </p>
                  <input
                    type="text"
                    placeholder="http://localhost:8081"
                    className="mt-4 w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-xs placeholder-gray-500 focus:outline-none focus:border-teal-500/50"
                  />
                  <button className="mt-2 w-full px-3 py-2 bg-teal-500 text-white rounded-lg text-xs font-medium hover:bg-teal-600">
                    Load App
                  </button>
                </div>

                {/* Home indicator */}
                <div className="h-10 bg-[#1a1a1a] flex items-center justify-center">
                  <div className="w-28 h-1 bg-white/30 rounded-full" />
                </div>
              </div>

              {/* Device info */}
              <div className="mt-4 text-center">
                <p className="text-sm text-white font-medium">{previewDevice.name}</p>
                <p className="text-xs text-gray-500">{previewDevice.os} &middot; {previewDevice.resolution} &middot; {previewDevice.screenSize}</p>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center py-16">
              <LucideSmartphone className="w-16 h-16 text-gray-600 mb-4" />
              <p className="text-gray-400 text-sm">Select a device above to preview your app</p>
            </div>
          )}
        </div>
      )}

      {/* Test History Tab */}
      {activeTab === "history" && (
        <div className="space-y-4">
          {TEST_HISTORY.map((test) => (
            <motion.div
              key={test.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="p-4 bg-white/5 border border-white/10 rounded-2xl"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${TEST_STATUS_CONFIG[test.status].bg}`}>
                    {test.status === "passed" ? (
                      <LucideCheck className={`w-4 h-4 ${TEST_STATUS_CONFIG[test.status].color}`} />
                    ) : test.status === "failed" ? (
                      <LucideX className={`w-4 h-4 ${TEST_STATUS_CONFIG[test.status].color}`} />
                    ) : (
                      <LucideLoader2 className={`w-4 h-4 ${TEST_STATUS_CONFIG[test.status].color} animate-spin`} />
                    )}
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-white">{test.name}</h3>
                    <p className="text-xs text-gray-500">{test.device} &middot; {test.timestamp}</p>
                  </div>
                </div>
                <span className={`px-2 py-1 rounded-lg text-xs ${TEST_STATUS_CONFIG[test.status].bg} ${TEST_STATUS_CONFIG[test.status].color}`}>
                  {TEST_STATUS_CONFIG[test.status].label}
                </span>
              </div>
              {test.duration && (
                <div className="flex items-center gap-4 text-xs text-gray-400 mt-2">
                  <span>Duration: {test.duration}</span>
                  {test.passedTests !== undefined && (
                    <span className="text-green-400">{test.passedTests} passed</span>
                  )}
                  {test.failedTests !== undefined && test.failedTests > 0 && (
                    <span className="text-red-400">{test.failedTests} failed</span>
                  )}
                </div>
              )}
            </motion.div>
          ))}

          {TEST_HISTORY.length === 0 && (
            <div className="text-center py-16">
              <LucideActivity className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400 text-sm">No test runs yet</p>
              <p className="text-gray-500 text-xs mt-1">Run your first test from the Test Runner tab</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
