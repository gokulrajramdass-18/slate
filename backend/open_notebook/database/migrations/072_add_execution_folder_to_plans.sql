-- Add execution_folder_id to workspace_plans for organizing template execution results
ALTER TABLE workspace_plans ADD COLUMN execution_folder_id TEXT;
