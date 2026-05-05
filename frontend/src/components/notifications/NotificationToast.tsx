"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Notification } from "./NotificationCenter";

const getCategoryIcon = (category?: string) => {
  switch (category) {
    case "approval":
      return "✅";
    case "workflow":
      return "⚡";
    case "agent":
      return "🤖";
    case "schedule":
      return "📅";
    case "system":
      return "⚙️";
    default:
      return "📬";
  }
};

const getPriorityColors = (priority: string) => {
  switch (priority) {
    case "urgent":
      return {
        bg: "bg-red-50 dark:bg-red-950/30",
        border: "border-red-200 dark:border-red-800",
        accent: "bg-red-600",
      };
    case "high":
      return {
        bg: "bg-orange-50 dark:bg-orange-950/30",
        border: "border-orange-200 dark:border-orange-800",
        accent: "bg-orange-600",
      };
    case "normal":
      return {
        bg: "bg-blue-50 dark:bg-blue-950/30",
        border: "border-blue-200 dark:border-blue-800",
        accent: "bg-blue-600",
      };
    case "low":
      return {
        bg: "bg-gray-50 dark:bg-gray-800",
        border: "border-gray-200 dark:border-gray-700",
        accent: "bg-gray-600",
      };
    default:
      return {
        bg: "bg-blue-50 dark:bg-blue-950/30",
        border: "border-blue-200 dark:border-blue-800",
        accent: "bg-blue-600",
      };
  }
};

interface NotificationToastProps {
  notification: Notification;
  onClose: () => void;
  onAction?: (url: string) => void;
  autoHideDuration?: number;
}

export const NotificationToast: React.FC<NotificationToastProps> = ({
  notification,
  onClose,
  onAction,
  autoHideDuration = 8000,
}) => {
  const [progress, setProgress] = useState(100);
  const colors = getPriorityColors(notification.priority);

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((prev) => {
        const next = prev - (100 / (autoHideDuration / 100));
        if (next <= 0) {
          clearInterval(interval);
          onClose();
          return 0;
        }
        return next;
      });
    }, 100);

    return () => clearInterval(interval);
  }, [autoHideDuration, onClose]);

  const handleAction = () => {
    if (notification.action_url) {
      onAction?.(notification.action_url);
      onClose();
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: -50, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -20, scale: 0.95 }}
      transition={{
        type: "spring",
        stiffness: 500,
        damping: 30,
      }}
      className="relative w-full max-w-md"
    >
      {/* Backdrop blur */}
      <div className="absolute inset-0 bg-white/80 dark:bg-gray-900/80 backdrop-blur-xl rounded-2xl" />

      {/* Content */}
      <div
        className={cn(
          "relative rounded-2xl border-2 shadow-2xl overflow-hidden",
          colors.bg,
          colors.border
        )}
      >
        {/* Accent bar */}
        <div className={cn("h-1.5", colors.accent)} />

        {/* Main content */}
        <div className="p-5">
          <div className="flex items-start gap-4">
            {/* Icon with animation */}
            <motion.div
              initial={{ rotate: -10, scale: 0.8 }}
              animate={{ rotate: 0, scale: 1 }}
              transition={{
                type: "spring",
                stiffness: 260,
                damping: 20,
              }}
              className="text-4xl flex-shrink-0"
            >
              {getCategoryIcon(notification.category)}
            </motion.div>

            {/* Text content */}
            <div className="flex-1 min-w-0">
              <h4 className="font-bold text-base text-gray-900 dark:text-gray-100 mb-1">
                {notification.title}
              </h4>
              <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                {notification.message}
              </p>

              {/* Action button */}
              {notification.action_url && notification.action_label && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                  className="mt-3"
                >
                  <Button
                    size="sm"
                    onClick={handleAction}
                    className={cn(
                      "h-8 text-xs font-semibold",
                      colors.accent,
                      "hover:opacity-90 transition-opacity"
                    )}
                  >
                    {notification.action_label}
                    <ExternalLink className="w-3 h-3 ml-1.5" />
                  </Button>
                </motion.div>
              )}
            </div>

            {/* Close button */}
            <button
              onClick={onClose}
              className="flex-shrink-0 p-1 rounded-lg hover:bg-gray-200/50 dark:hover:bg-gray-700/50 transition-colors"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        </div>

        {/* Progress bar */}
        <div className="h-1 bg-gray-200/50 dark:bg-gray-700/50">
          <motion.div
            className={cn("h-full", colors.accent)}
            initial={{ width: "100%" }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.1, ease: "linear" }}
          />
        </div>
      </div>
    </motion.div>
  );
};

interface NotificationToastContainerProps {
  notifications: Notification[];
  onClose: (id: string) => void;
  onAction?: (url: string) => void;
  maxVisible?: number;
}

export const NotificationToastContainer: React.FC<NotificationToastContainerProps> = ({
  notifications,
  onClose,
  onAction,
  maxVisible = 3,
}) => {
  // Show only the most recent notifications
  const visibleNotifications = notifications.slice(0, maxVisible);

  return (
    <div className="fixed top-20 left-1/2 -translate-x-1/2 z-[9999] pointer-events-none">
      <div className="flex flex-col gap-3 pointer-events-auto">
        <AnimatePresence mode="popLayout">
          {visibleNotifications.map((notification, index) => (
            <motion.div
              key={notification.id}
              layout
              initial={{ opacity: 0, y: -50 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: 100 }}
              transition={{
                layout: { type: "spring", stiffness: 500, damping: 30 },
              }}
              style={{ zIndex: visibleNotifications.length - index }}
            >
              <NotificationToast
                notification={notification}
                onClose={() => onClose(notification.id)}
                onAction={onAction}
              />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Overflow indicator */}
      {notifications.length > maxVisible && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="mt-2 text-center"
        >
          <div className="inline-block px-4 py-2 bg-gray-900/90 backdrop-blur-lg text-white text-xs font-medium rounded-full shadow-lg">
            +{notifications.length - maxVisible} more notifications
          </div>
        </motion.div>
      )}
    </div>
  );
};
