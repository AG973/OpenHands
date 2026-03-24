import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { LucideX, LucideCheck, LucideLoader2, LucideShield } from "lucide-react";
import type { IntegrationData } from "./integration-card";

interface ConnectionWizardProps {
  integration: IntegrationData;
  onConnect: (config: Record<string, string>) => void;
  onClose: () => void;
}

export function ConnectionWizard({
  integration,
  onConnect,
  onClose,
}: ConnectionWizardProps) {
  const [step, setStep] = useState<"config" | "testing" | "success" | "error">("config");
  const [config, setConfig] = useState<Record<string, string>>({});
  const [errorMessage, setErrorMessage] = useState("");

  const handleSubmit = () => {
    setStep("testing");
    // Simulate connection test
    setTimeout(() => {
      const allFieldsFilled = integration.configFields.every(
        (f) => config[f.key]?.trim(),
      );
      if (allFieldsFilled) {
        setStep("success");
        setTimeout(() => {
          onConnect(config);
        }, 1500);
      } else {
        setStep("error");
        setErrorMessage("Please fill in all required fields");
      }
    }, 2000);
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
        className="bg-[#0d1117] border border-white/10 rounded-2xl w-full max-w-md"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center text-xl">
              {integration.icon}
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">
                Connect {integration.name}
              </h3>
              <p className="text-xs text-gray-500">{integration.authMethod}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg"
            aria-label="Close wizard"
          >
            <LucideX className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5">
          <AnimatePresence mode="wait">
            {step === "config" && (
              <motion.div
                key="config"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-4"
              >
                <div className="flex items-center gap-2 p-3 bg-blue-500/10 border border-blue-500/20 rounded-xl">
                  <LucideShield className="w-4 h-4 text-blue-400 shrink-0" />
                  <p className="text-xs text-blue-300">
                    Your credentials are stored securely and only used for this connection.
                  </p>
                </div>

                {integration.configFields.map((field) => (
                  <div key={field.key}>
                    <label className="block text-sm text-gray-400 mb-1.5">
                      {field.label}
                    </label>
                    <input
                      type={field.type}
                      value={config[field.key] || ""}
                      onChange={(e) =>
                        setConfig({ ...config, [field.key]: e.target.value })
                      }
                      placeholder={field.placeholder}
                      className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 text-sm focus:outline-none focus:border-blue-500/50"
                    />
                  </div>
                ))}

                <button
                  onClick={handleSubmit}
                  className="w-full py-2.5 bg-blue-500 hover:bg-blue-600 text-white rounded-xl text-sm font-medium transition-colors"
                >
                  Test Connection & Save
                </button>
              </motion.div>
            )}

            {step === "testing" && (
              <motion.div
                key="testing"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="flex flex-col items-center py-8"
              >
                <LucideLoader2 className="w-12 h-12 text-blue-400 animate-spin mb-4" />
                <p className="text-white font-medium">Testing connection...</p>
                <p className="text-sm text-gray-400 mt-1">
                  Verifying your credentials
                </p>
              </motion.div>
            )}

            {step === "success" && (
              <motion.div
                key="success"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="flex flex-col items-center py-8"
              >
                <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mb-4">
                  <LucideCheck className="w-8 h-8 text-green-400" />
                </div>
                <p className="text-white font-medium">Connected!</p>
                <p className="text-sm text-gray-400 mt-1">
                  {integration.name} is ready to use
                </p>
              </motion.div>
            )}

            {step === "error" && (
              <motion.div
                key="error"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="flex flex-col items-center py-8"
              >
                <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center mb-4">
                  <LucideX className="w-8 h-8 text-red-400" />
                </div>
                <p className="text-white font-medium">Connection Failed</p>
                <p className="text-sm text-red-400 mt-1">{errorMessage}</p>
                <button
                  onClick={() => setStep("config")}
                  className="mt-4 px-4 py-2 bg-white/10 text-white rounded-xl text-sm hover:bg-white/20 transition-colors"
                >
                  Try Again
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </motion.div>
  );
}
