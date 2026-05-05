"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import { Bell, X, ArrowRight, Sparkles, Inbox } from "lucide-react";
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

const getPriorityGradient = (priority: string) => {
  switch (priority) {
    case "urgent":
      return "from-red-500 via-pink-500 to-rose-500";
    case "high":
      return "from-orange-500 via-amber-500 to-yellow-500";
    case "normal":
      return "from-blue-500 via-indigo-500 to-purple-500";
    case "low":
      return "from-gray-400 via-gray-500 to-gray-600";
    default:
      return "from-blue-500 via-indigo-500 to-purple-500";
  }
};

interface NotificationDialogProps {
  notification: Notification;
  onClose: () => void;
}

export const NotificationDialog: React.FC<NotificationDialogProps> = ({
  notification,
  onClose,
}) => {
  const router = useRouter();
  const [isVisible, setIsVisible] = useState(false);
  const gradient = getPriorityGradient(notification.priority);

  useEffect(() => {
    // Trigger animation after mount
    const timer = setTimeout(() => setIsVisible(true), 50);
    return () => clearTimeout(timer);
  }, []);

  const handleClose = () => {
    setIsVisible(false);
    setTimeout(onClose, 300);
  };

  const handleViewDetails = () => {
    if (notification.action_url) {
      router.push(notification.action_url);
    }
    handleClose();
  };

  return (
    <AnimatePresence>
      {isVisible && (
        <>
          {/* Backdrop with blur */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-[9998]"
            onClick={handleClose}
          />

          {/* Dialog */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8, y: 50 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.8, y: 50 }}
            transition={{
              type: "spring",
              stiffness: 400,
              damping: 25,
            }}
            className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[9999] w-full max-w-lg px-4"
          >
            <div className="relative bg-white dark:bg-gray-900 rounded-3xl shadow-2xl overflow-hidden border-2 border-gray-200 dark:border-gray-700">
              {/* Animated gradient border glow */}
              <motion.div
                className={cn(
                  "absolute inset-0 opacity-20 blur-2xl",
                  `bg-gradient-to-br ${gradient}`
                )}
                animate={{
                  scale: [1, 1.2, 1],
                  opacity: [0.2, 0.3, 0.2],
                }}
                transition={{
                  duration: 3,
                  repeat: Infinity,
                  ease: "easeInOut",
                }}
              />

              {/* Content */}
              <div className="relative">
                {/* Close button */}
                <button
                  onClick={handleClose}
                  className="absolute top-4 right-4 p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors z-10"
                >
                  <X className="w-5 h-5 text-gray-500" />
                </button>

                {/* Header with animated icon */}
                <div className="pt-8 pb-4 px-8 text-center">
                  <motion.div
                    initial={{ scale: 0, rotate: -180 }}
                    animate={{ scale: 1, rotate: 0 }}
                    transition={{
                      type: "spring",
                      stiffness: 260,
                      damping: 20,
                      delay: 0.1,
                    }}
                    className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 shadow-lg mb-4 relative"
                  >
                    {/* Pulsing rings */}
                    <motion.div
                      className="absolute inset-0 rounded-full bg-blue-500"
                      animate={{
                        scale: [1, 1.5, 1.5],
                        opacity: [0.5, 0, 0],
                      }}
                      transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: "easeOut",
                      }}
                    />
                    <motion.div
                      className="absolute inset-0 rounded-full bg-purple-500"
                      animate={{
                        scale: [1, 1.8, 1.8],
                        opacity: [0.5, 0, 0],
                      }}
                      transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: "easeOut",
                        delay: 0.5,
                      }}
                    />

                    {/* Bell icon */}
                    <motion.div
                      animate={{
                        rotate: [0, -15, 15, -15, 15, 0],
                      }}
                      transition={{
                        duration: 0.8,
                        repeat: Infinity,
                        repeatDelay: 2,
                      }}
                    >
                      <Bell className="w-10 h-10 text-white" fill="white" />
                    </motion.div>

                    {/* Sparkles */}
                    <motion.div
                      className="absolute -top-2 -right-2"
                      animate={{
                        scale: [1, 1.2, 1],
                        rotate: [0, 180, 360],
                      }}
                      transition={{
                        duration: 2,
                        repeat: Infinity,
                      }}
                    >
                      <Sparkles className="w-6 h-6 text-yellow-400" fill="currentColor" />
                    </motion.div>
                  </motion.div>

                  <motion.h2
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2"
                  >
                    New Notification!
                  </motion.h2>

                  <motion.p
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    className="text-sm text-gray-500 dark:text-gray-400"
                  >
                    You have a pending notification waiting for your attention
                  </motion.p>
                </div>

                {/* Notification preview */}
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.4 }}
                  className="mx-8 mb-6"
                >
                  <div className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-850 rounded-2xl p-6 border border-gray-200 dark:border-gray-700 shadow-inner">
                    <div className="flex items-start gap-4">
                      <motion.div
                        animate={{
                          scale: [1, 1.1, 1],
                        }}
                        transition={{
                          duration: 1.5,
                          repeat: Infinity,
                        }}
                        className="text-4xl flex-shrink-0"
                      >
                        {getCategoryIcon(notification.category)}
                      </motion.div>

                      <div className="flex-1 min-w-0">
                        <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">
                          {notification.title}
                        </h3>
                        <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                          {notification.message}
                        </p>

                        {/* Priority badge */}
                        <div className="mt-3 flex items-center gap-2">
                          <span
                            className={cn(
                              "inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold",
                              notification.priority === "urgent" && "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
                              notification.priority === "high" && "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
                              notification.priority === "normal" && "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
                              notification.priority === "low" && "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300"
                            )}
                          >
                            {notification.priority.toUpperCase()}
                          </span>

                          {notification.category && (
                            <span className="text-xs text-gray-500 dark:text-gray-400">
                              {notification.category}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </motion.div>

                {/* Action buttons */}
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.5 }}
                  className="px-8 pb-8 flex gap-3"
                >
                  <Button
                    onClick={handleClose}
                    variant="outline"
                    className="flex-1 h-12 rounded-xl border-2"
                  >
                    Dismiss
                  </Button>

                  {notification.action_url && (
                    <Button
                      onClick={handleViewDetails}
                      className="flex-1 h-12 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-lg shadow-blue-500/30 border-0 group"
                    >
                      {notification.action_label || "View Details"}
                      <motion.div
                        className="ml-1"
                        animate={{ x: [0, 3, 0] }}
                        transition={{
                          duration: 1,
                          repeat: Infinity,
                          ease: "easeInOut",
                        }}
                      >
                        <ArrowRight className="w-4 h-4" />
                      </motion.div>
                    </Button>
                  )}
                </motion.div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

interface NotificationDialogManagerProps {
  notifications: Notification[];
  onDismiss: (id: string) => void;
}

export const NotificationDialogManager: React.FC<NotificationDialogManagerProps> = ({
  notifications,
  onDismiss,
}) => {
  const [currentNotification, setCurrentNotification] = useState<Notification | null>(null);

  useEffect(() => {
    // Show the first unread high-priority or urgent notification as a dialog
    const priorityNotification = notifications.find(
      (n) => !n.is_read && (n.priority === "urgent" || n.priority === "high")
    );

    if (priorityNotification && !currentNotification) {
      setCurrentNotification(priorityNotification);
    }
  }, [notifications, currentNotification]);

  const handleClose = () => {
    if (currentNotification) {
      onDismiss(currentNotification.id);
    }
    setCurrentNotification(null);
  };

  if (!currentNotification) return null;

  return (
    <NotificationDialog
      notification={currentNotification}
      onClose={handleClose}
    />
  );
};
