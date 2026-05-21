-- Migration 116: Add input_data to workflow_schedules
-- Stores user-provided values for the workflow's required input fields.
-- Captured once at schedule creation time and reused on every scheduled run.

ALTER TABLE workflow_schedules ADD COLUMN input_data TEXT;
