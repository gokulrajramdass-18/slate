"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import { CheckCircle, Clock, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api/client";

interface ApprovalDialogProps {
  approvalCount: number;
  latestApproval?: {
    id: string;
    prompt: string;
    workflow_name?: string;
    created_at: string;
    expires_at?: string;
  };
  onClose: () => void;
  onNavigateToApprovals: () => void;
}

export const ApprovalDialog: React.FC<ApprovalDialogProps> = ({
  approvalCount,
  latestApproval,
  onClose,
  onNavigateToApprovals,
}) => {
  const router = useRouter();
  const [isVisible, setIsVisible] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState<string>("");

  useEffect(() => {
    // Trigger animation after mount
    const timer = setTimeout(() => setIsVisible(true), 50);
    return () => clearTimeout(timer);
  }, []);

  // Calculate time remaining
  useEffect(() => {
    if (!(latestApproval as any)?.timeout_at) return;

    const updateTimeRemaining = () => {
      const now = new Date();
      const expiresAt = new Date((latestApproval as any).timeout_at!);
      const diffMs = expiresAt.getTime() - now.getTime();

      if (diffMs <= 0) {
        setTimeRemaining("Expired");
        return;
      }

      const hours = Math.floor(diffMs / (1000 * 60 * 60));
      const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

      if (hours > 0) {
        setTimeRemaining(`${hours}h ${minutes}m remaining`);
      } else {
        setTimeRemaining(`${minutes}m remaining`);
      }
    };

    updateTimeRemaining();
    const interval = setInterval(updateTimeRemaining, 60000); // Update every minute

    return () => clearInterval(interval);
  }, [(latestApproval as any)?.timeout_at]);

  const handleClose = () => {
    setIsVisible(false);
    setTimeout(onClose, 300);
  };

  const handleViewApprovals = () => {
    onNavigateToApprovals();
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
            className="fixed inset-0 bg-black/60 backdrop-blur-md z-[9998]"
            onClick={handleClose}
          />

          {/* Dialog */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.2 }}
            className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[9999] w-full max-w-lg px-4"
          >
            <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl overflow-hidden border border-gray-200 dark:border-gray-800">
              {/* Subtle gradient accent */}
              <div className="h-1 bg-gradient-to-r from-blue-500 to-purple-500" />

              {/* Content */}
              <div className="p-6">
                {/* Header with icon */}
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.1 }}
                  className="flex items-start gap-4 mb-6"
                >
                  <motion.div
                    className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-500 rounded-lg flex items-center justify-center flex-shrink-0"
                    animate={{
                      boxShadow: [
                        "0 0 0 0 rgba(59, 130, 246, 0)",
                        "0 0 0 8px rgba(59, 130, 246, 0.1)",
                        "0 0 0 0 rgba(59, 130, 246, 0)",
                      ],
                    }}
                    transition={{
                      duration: 2,
                      repeat: Infinity,
                      ease: "easeInOut",
                    }}
                  >
                    <motion.div
                      animate={{
                        scale: [1, 1.1, 1],
                      }}
                      transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: "easeInOut",
                      }}
                    >
                      <CheckCircle className="w-6 h-6 text-white" />
                    </motion.div>
                  </motion.div>

                  <div className="flex-1">
                    <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-1">
                      Approval Required
                    </h2>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {approvalCount === 1
                        ? "You have a workflow waiting for your approval"
                        : `You have ${approvalCount} workflows waiting for approval`}
                    </p>
                  </div>
                </motion.div>

                {/* Latest approval preview */}
                {latestApproval && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 mb-6 border border-gray-200 dark:border-gray-700"
                  >
                    <div className="flex items-start gap-3">
                      <motion.div
                        className="text-2xl flex-shrink-0"
                        animate={{
                          rotate: [0, -5, 5, 0],
                        }}
                        transition={{
                          duration: 3,
                          repeat: Infinity,
                          ease: "easeInOut",
                        }}
                      >
                        ✅
                      </motion.div>

                      <div className="flex-1 min-w-0">
                        {latestApproval.workflow_name && (
                          <h3 className="font-medium text-gray-900 dark:text-gray-100 mb-1">
                            {latestApproval.workflow_name}
                          </h3>
                        )}
                        <p className="text-sm text-gray-600 dark:text-gray-400 mb-2 line-clamp-2">
                          {latestApproval.prompt}
                        </p>

                        <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-500">
                          <div className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {timeRemaining || "Pending"}
                          </div>
                          {approvalCount > 1 && (
                            <motion.div
                              initial={{ scale: 0 }}
                              animate={{ scale: 1 }}
                              transition={{ delay: 0.3, type: "spring" }}
                              className="text-blue-600 dark:text-blue-400 font-medium"
                            >
                              +{approvalCount - 1} more
                            </motion.div>
                          )}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}

                {/* Action buttons */}
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3 }}
                  className="flex gap-3"
                >
                  <Button
                    onClick={handleClose}
                    variant="outline"
                    className="flex-1"
                  >
                    Later
                  </Button>

                  <Button
                    onClick={handleViewApprovals}
                    className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 group"
                  >
                    Review Approvals
                    <motion.div
                      className="ml-2"
                      animate={{ x: [0, 3, 0] }}
                      transition={{
                        duration: 1.5,
                        repeat: Infinity,
                        ease: "easeInOut",
                      }}
                    >
                      <ArrowRight className="w-4 h-4" />
                    </motion.div>
                  </Button>
                </motion.div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

interface ApprovalDialogManagerProps {
  userId?: string;
}

export const ApprovalDialogManager: React.FC<ApprovalDialogManagerProps> = ({
  userId,
}) => {
  const router = useRouter();
  const [showDialog, setShowDialog] = useState(false);
  const [approvalData, setApprovalData] = useState<{
    count: number;
    latest?: any;
  } | null>(null);
  const [shownApprovalIds, setShownApprovalIds] = useState<Set<string>>(new Set());
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);

  console.log("🎯 ApprovalDialogManager initialized with userId:", userId);

  // Fetch approvals from API
  const fetchApprovals = useCallback(async () => {
    if (!userId) return;

    try {
      const response = await apiClient.get(
        `/workflow-approvals/inbox`,
        {
          params: { status_filter: 'pending' },
          headers: {
            'X-User-ID': userId,
          },
        }
      );

      const data = response.data;
      console.log("📋 Approvals fetched:", data);

      if (data && Array.isArray(data) && data.length > 0) {
        const latestApproval = data[0];

        // On initial load, mark all existing approvals as "already shown" without displaying dialog
        if (isInitialLoad) {
          console.log("🔄 Initial load - marking existing approvals as shown without displaying dialog");
          const existingIds = new Set(data.map((a: any) => a.id));
          setShownApprovalIds(existingIds);
          setIsInitialLoad(false);
          return;
        }

        // Check if there's a new approval we haven't shown yet
        const hasNewApproval = !shownApprovalIds.has(latestApproval.id);

        console.log("🔍 Latest approval ID:", latestApproval.id);
        console.log("🔍 Has new approval:", hasNewApproval);
        console.log("🔍 Already shown IDs:", Array.from(shownApprovalIds));

        if (hasNewApproval) {
          console.log("✅ Showing dialog for new approval!");
          setApprovalData({
            count: data.length,
            latest: latestApproval,
          });
          setShowDialog(true);

          // Mark this approval as shown
          setShownApprovalIds(prev => new Set(prev).add(latestApproval.id));
        } else {
          console.log("ℹ️ Approval already shown, skipping dialog");
        }
      } else {
        console.log("ℹ️ No pending approvals");
        // No pending approvals
        setApprovalData(null);
        setShowDialog(false);
      }
    } catch (error: any) {
      // Silently fail if backend is not available - this is expected when backend is down
      if (error.code === 'ERR_NETWORK' || error.message?.includes('Network Error')) {
        console.log("⚠️ Backend not available - skipping approval fetch");
      } else {
        console.error("❌ Failed to fetch approvals:", error);
      }
    }
  }, [userId, shownApprovalIds, isInitialLoad]);

  // Setup WebSocket connection for real-time updates
  useEffect(() => {
    if (!userId) return;

    const API_BASE_URL = "http://localhost:5055";
    const wsUrl = `${API_BASE_URL.replace("http", "ws")}/api/notifications/ws/${userId}`;

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log("✓ Approval dialog WebSocket connected");
      };

      ws.onmessage = (event) => {
        try {
          if (event.data === "pong") return;

          const data = JSON.parse(event.data);
          console.log("📨 WebSocket message received:", data);

          // Check for new approval notifications
          if (data.type === "new_notification") {
            const notification = data.notification;
            console.log("🔔 Notification category:", notification?.category);

            if (notification?.category === "approval") {
              console.log("✅ New approval notification detected!");
              // Fetch latest approvals
              fetchApprovals();
            }
          }
        } catch (err) {
          console.error("Error parsing WebSocket message:", err);
        }
      };

      ws.onerror = (error) => {
        // Silently handle WebSocket errors when backend is unavailable
        console.log("⚠️ Approval WebSocket not available");
      };

      ws.onclose = () => {
        console.log("✗ Approval WebSocket disconnected");
      };

      wsRef.current = ws;

      // Send ping every 30 seconds
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("ping");
        }
      }, 30000);

      return () => {
        clearInterval(pingInterval);
        if (wsRef.current) {
          wsRef.current.close();
          wsRef.current = null;
        }
      };
    } catch (err) {
      // Silently handle WebSocket connection errors when backend is unavailable
      console.log("⚠️ Failed to connect approval WebSocket - backend may not be running");
    }
  }, [userId, fetchApprovals]);

  // Initial fetch and polling fallback
  useEffect(() => {
    if (!userId) return;

    // Initial fetch
    fetchApprovals();

    // Poll every 15 seconds as fallback
    const interval = setInterval(fetchApprovals, 15000);

    return () => clearInterval(interval);
  }, [userId, fetchApprovals]);

  const handleClose = () => {
    setShowDialog(false);
  };

  const handleNavigateToApprovals = () => {
    setShowDialog(false);
    router.push("/approvals");
  };

  if (!showDialog || !approvalData) return null;

  return (
    <ApprovalDialog
      approvalCount={approvalData.count}
      latestApproval={approvalData.latest}
      onClose={handleClose}
      onNavigateToApprovals={handleNavigateToApprovals}
    />
  );
};
