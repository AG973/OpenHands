import React, { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import { LucideUploadCloud, LucideFile, LucideImage, LucideArchive, LucideFolder, LucideX } from "lucide-react";

interface UploadedFileInfo {
  file: File;
  preview?: string;
  type: "image" | "archive" | "code" | "document" | "other";
}

function getFileType(file: File): UploadedFileInfo["type"] {
  if (file.type.startsWith("image/")) return "image";
  if (
    file.name.endsWith(".zip") ||
    file.name.endsWith(".tar") ||
    file.name.endsWith(".gz") ||
    file.name.endsWith(".rar") ||
    file.name.endsWith(".7z")
  )
    return "archive";
  if (
    file.name.endsWith(".ts") ||
    file.name.endsWith(".tsx") ||
    file.name.endsWith(".js") ||
    file.name.endsWith(".jsx") ||
    file.name.endsWith(".py") ||
    file.name.endsWith(".java") ||
    file.name.endsWith(".cpp") ||
    file.name.endsWith(".c") ||
    file.name.endsWith(".go") ||
    file.name.endsWith(".rs") ||
    file.name.endsWith(".rb") ||
    file.name.endsWith(".php") ||
    file.name.endsWith(".swift") ||
    file.name.endsWith(".kt") ||
    file.name.endsWith(".html") ||
    file.name.endsWith(".css") ||
    file.name.endsWith(".json") ||
    file.name.endsWith(".yaml") ||
    file.name.endsWith(".yml") ||
    file.name.endsWith(".md")
  )
    return "code";
  if (
    file.name.endsWith(".pdf") ||
    file.name.endsWith(".doc") ||
    file.name.endsWith(".docx") ||
    file.name.endsWith(".txt")
  )
    return "document";
  return "other";
}

function FileTypeIcon({ type }: { type: UploadedFileInfo["type"] }) {
  switch (type) {
    case "image":
      return <LucideImage className="w-5 h-5 text-green-400" />;
    case "archive":
      return <LucideArchive className="w-5 h-5 text-yellow-400" />;
    case "code":
      return <LucideFile className="w-5 h-5 text-blue-400" />;
    case "document":
      return <LucideFile className="w-5 h-5 text-purple-400" />;
    default:
      return <LucideFile className="w-5 h-5 text-gray-400" />;
  }
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface FileDropZoneProps {
  onFilesAccepted: (files: File[]) => void;
  maxSize?: number;
  maxFiles?: number;
  accept?: Record<string, string[]>;
  className?: string;
  compact?: boolean;
}

export function FileDropZone({
  onFilesAccepted,
  maxSize = 50 * 1024 * 1024, // 50MB default
  maxFiles = 20,
  accept,
  className = "",
  compact = false,
}: FileDropZoneProps) {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFileInfo[]>([]);

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const newFiles: UploadedFileInfo[] = acceptedFiles.map((file) => ({
        file,
        preview: file.type.startsWith("image/")
          ? URL.createObjectURL(file)
          : undefined,
        type: getFileType(file),
      }));
      setUploadedFiles((prev) => [...prev, ...newFiles]);
      onFilesAccepted(acceptedFiles);
    },
    [onFilesAccepted],
  );

  const removeFile = (index: number) => {
    setUploadedFiles((prev) => {
      const file = prev[index];
      if (file.preview) URL.revokeObjectURL(file.preview);
      return prev.filter((_, i) => i !== index);
    });
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    maxSize,
    maxFiles,
    accept,
  });

  return (
    <div className={className}>
      <div
        {...getRootProps()}
        className={`relative border-2 border-dashed rounded-2xl transition-all duration-300 cursor-pointer
          ${
            isDragActive
              ? "border-blue-500 bg-blue-500/10 scale-[1.02]"
              : "border-white/20 bg-white/5 hover:border-white/30 hover:bg-white/8"
          }
          ${compact ? "p-4" : "p-8"}
        `}
      >
        <input {...getInputProps()} />

        <AnimatePresence mode="wait">
          {isDragActive ? (
            <motion.div
              key="drag"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="flex flex-col items-center gap-3 text-blue-400"
            >
              <LucideUploadCloud className="w-12 h-12 animate-bounce" />
              <p className="text-lg font-medium">Drop files here</p>
            </motion.div>
          ) : (
            <motion.div
              key="idle"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center gap-3 text-gray-400"
            >
              <LucideUploadCloud className={compact ? "w-8 h-8" : "w-12 h-12"} />
              {!compact && (
                <>
                  <p className="text-lg font-medium text-white">
                    Drag & drop files here
                  </p>
                  <p className="text-sm">
                    or click to browse — supports images, zip files, code, repos
                  </p>
                  <div className="flex gap-4 mt-2">
                    <span className="flex items-center gap-1 text-xs">
                      <LucideImage className="w-3 h-3 text-green-400" /> Images
                    </span>
                    <span className="flex items-center gap-1 text-xs">
                      <LucideArchive className="w-3 h-3 text-yellow-400" /> ZIP
                      files
                    </span>
                    <span className="flex items-center gap-1 text-xs">
                      <LucideFolder className="w-3 h-3 text-blue-400" /> Repos
                    </span>
                    <span className="flex items-center gap-1 text-xs">
                      <LucideFile className="w-3 h-3 text-purple-400" /> Documents
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    Max {formatFileSize(maxSize)} per file, up to {maxFiles} files
                  </p>
                </>
              )}
              {compact && (
                <p className="text-sm">Drop files or click to upload</p>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Uploaded files list */}
      {uploadedFiles.length > 0 && (
        <div className="mt-4 space-y-2">
          <AnimatePresence>
            {uploadedFiles.map((fileInfo, index) => (
              <motion.div
                key={`${fileInfo.file.name}-${index}`}
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="flex items-center gap-3 p-3 bg-white/5 border border-white/10 rounded-xl"
              >
                {fileInfo.preview ? (
                  <img
                    src={fileInfo.preview}
                    alt={fileInfo.file.name}
                    className="w-10 h-10 rounded-lg object-cover"
                  />
                ) : (
                  <div className="w-10 h-10 rounded-lg bg-white/10 flex items-center justify-center">
                    <FileTypeIcon type={fileInfo.type} />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white truncate">
                    {fileInfo.file.name}
                  </p>
                  <p className="text-xs text-gray-400">
                    {formatFileSize(fileInfo.file.size)}
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(index);
                  }}
                  className="p-1 text-gray-400 hover:text-red-400 transition-colors"
                  aria-label={`Remove ${fileInfo.file.name}`}
                >
                  <LucideX className="w-4 h-4" />
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
