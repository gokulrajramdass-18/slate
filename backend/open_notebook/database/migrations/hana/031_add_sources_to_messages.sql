-- Migration 031: Add sources column to chat_messages table (HANA)
-- This allows storing citation sources (notebook sources + tool results) with each message

ALTER TABLE chat_messages ADD (sources NCLOB);
