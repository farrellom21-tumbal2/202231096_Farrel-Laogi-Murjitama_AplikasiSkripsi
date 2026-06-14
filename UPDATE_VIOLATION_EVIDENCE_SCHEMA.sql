-- Update violation_evidence table to support activity_id linking
-- This allows linking evidence to exam_activity_log instead of violations table

-- Add new columns to violation_evidence table
ALTER TABLE violation_evidence ADD COLUMN activity_id BIGINT AFTER id;
ALTER TABLE violation_evidence ADD COLUMN participant_id INT AFTER activity_id;
ALTER TABLE violation_evidence ADD COLUMN violation_type VARCHAR(100) AFTER participant_id;

-- Make violation_id nullable since we're primarily using activity_id
ALTER TABLE violation_evidence MODIFY COLUMN violation_id BIGINT NULL;

-- Create index on activity_id for faster lookups
CREATE INDEX idx_violation_evidence_activity_id ON violation_evidence(activity_id);
CREATE INDEX idx_violation_evidence_participant_id ON violation_evidence(participant_id);

-- Optional: Create a new foreign key for activity_id if you want database-level constraints
-- ALTER TABLE violation_evidence ADD FOREIGN KEY (activity_id) REFERENCES exam_activity_log(id) ON DELETE CASCADE;

-- Verify table structure
alter table violation_evidence add column created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
