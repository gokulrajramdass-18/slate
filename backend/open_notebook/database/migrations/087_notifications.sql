-- Notification system for real-time user notifications
-- Supports approval pending, execution complete, agent activity, etc.

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    type TEXT NOT NULL,  -- 'approval_pending', 'execution_complete', 'agent_complete', 'schedule_triggered', 'workflow_failed', 'system'
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    category TEXT,  -- 'workflow', 'agent', 'approval', 'schedule', 'system'
    priority TEXT DEFAULT 'normal',  -- 'low', 'normal', 'high', 'urgent'

    -- Reference to the entity that triggered this notification
    entity_type TEXT,  -- 'workflow', 'agent', 'approval', 'schedule', 'execution'
    entity_id TEXT,

    -- Action link for navigation
    action_url TEXT,
    action_label TEXT,

    -- Metadata for additional context
    metadata TEXT,  -- JSON: { execution_id, workflow_name, agent_name, etc. }

    -- Status tracking
    is_read INTEGER DEFAULT 0,
    is_archived INTEGER DEFAULT 0,
    read_at TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,  -- Optional expiry for time-sensitive notifications

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(type);
CREATE INDEX IF NOT EXISTS idx_notifications_category ON notifications(category);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_entity ON notifications(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications(user_id, is_read, created_at DESC);
