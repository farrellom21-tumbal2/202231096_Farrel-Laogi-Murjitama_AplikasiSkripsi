# =====================================================
# DATABASE MIGRATION SCRIPT
# Violation Evidence Table Update
# =====================================================
# Run this script to update violation_evidence table
# for linking with exam_activity_log instead of violations table
# =====================================================

# Step 1: Add new columns to violation_evidence table
ALTER TABLE violation_evidence ADD COLUMN activity_id BIGINT AFTER id;
ALTER TABLE violation_evidence ADD COLUMN participant_id INT AFTER activity_id;
ALTER TABLE violation_evidence ADD COLUMN violation_type VARCHAR(100) AFTER participant_id;

# Step 2: Modify violation_id to be nullable (since we can now reference activity_id)
ALTER TABLE violation_evidence MODIFY COLUMN violation_id BIGINT NULL;

# Step 3: Create indexes for better query performance
CREATE INDEX idx_violation_evidence_activity_id ON violation_evidence(activity_id);
CREATE INDEX idx_violation_evidence_participant_id ON violation_evidence(participant_id);
CREATE INDEX idx_violation_evidence_violation_type ON violation_evidence(violation_type);

# Step 4: Verify table structure
DESCRIBE violation_evidence;

# =====================================================
# VERIFICATION QUERIES
# =====================================================

# Check if new columns exist
SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'violation_evidence' 
ORDER BY ORDINAL_POSITION;

# Check if indexes created
SHOW INDEX FROM violation_evidence;

# Count existing records (before migration, should be 0 or old data)
SELECT COUNT(*) as total_evidence_records FROM violation_evidence;

# =====================================================
# BACKWARD COMPATIBILITY
# =====================================================

# The violation_id column is still available for backward compatibility
# If you have old violations in violations table, you can link them:
# UPDATE violation_evidence SET violation_id = ... WHERE violation_id IS NULL;

# =====================================================
# NEW QUERIES
# =====================================================

# Query 1: Get violations with evidence from activity log
SELECT 
    ea.id as activity_id,
    ea.participant_id,
    ea.activity_type,
    ea.description,
    ea.activity_timestamp,
    ve.image_url,
    ve.violation_type,
    ve.captured_at,
    JSON_EXTRACT(ea.extra_data, '$.evidence_captured') as evidence_captured
FROM exam_activity_log ea
LEFT JOIN violation_evidence ve ON ea.id = ve.activity_id
WHERE ea.activity_type = 'VIOLATION_DETECTED'
ORDER BY ea.activity_timestamp DESC;

# Query 2: Get evidence for specific participant
SELECT 
    ve.activity_id,
    ve.participant_id,
    ve.violation_type,
    ve.image_url,
    ve.captured_at
FROM violation_evidence ve
WHERE ve.participant_id = ?
ORDER BY ve.captured_at DESC;

# Query 3: Get violation statistics
SELECT 
    p.id,
    p.participant_name,
    COUNT(DISTINCT ea.id) as total_violations,
    COUNT(DISTINCT ve.id) as violations_with_evidence,
    (COUNT(DISTINCT ve.id) / COUNT(DISTINCT ea.id) * 100) as evidence_percentage
FROM participants p
LEFT JOIN exam_activity_log ea ON p.id = ea.participant_id 
    AND ea.activity_type = 'VIOLATION_DETECTED'
LEFT JOIN violation_evidence ve ON ea.id = ve.activity_id
GROUP BY p.id, p.participant_name
ORDER BY total_violations DESC;

# Query 4: Get violations without evidence
SELECT 
    ea.id as activity_id,
    ea.participant_id,
    ea.description,
    ea.activity_timestamp,
    COUNT(ve.id) as evidence_count
FROM exam_activity_log ea
LEFT JOIN violation_evidence ve ON ea.id = ve.activity_id
WHERE ea.activity_type = 'VIOLATION_DETECTED'
GROUP BY ea.id
HAVING COUNT(ve.id) = 0
ORDER BY ea.activity_timestamp DESC;

# Query 5: Get violations with evidence
SELECT 
    ea.id as activity_id,
    ea.participant_id,
    ea.description,
    ea.activity_timestamp,
    ve.violation_type,
    ve.image_url,
    ve.captured_at
FROM exam_activity_log ea
JOIN violation_evidence ve ON ea.id = ve.activity_id
WHERE ea.activity_type = 'VIOLATION_DETECTED'
ORDER BY ea.activity_timestamp DESC;

# =====================================================
# MAINTENANCE QUERIES
# =====================================================

# Clean up: Delete evidence records for deleted participants
# (assuming participants have ON DELETE CASCADE)
# This should be handled automatically by database constraints

# Verify referential integrity
SELECT 
    COUNT(*) as total_evidence,
    COUNT(CASE WHEN activity_id IS NOT NULL THEN 1 END) as with_activity_id,
    COUNT(CASE WHEN violation_id IS NOT NULL THEN 1 END) as with_violation_id,
    COUNT(CASE WHEN activity_id IS NULL AND violation_id IS NULL THEN 1 END) as orphaned
FROM violation_evidence;

# =====================================================
# ROLLBACK SCRIPT (if needed)
# =====================================================

# To revert changes:
/*
ALTER TABLE violation_evidence DROP COLUMN activity_id;
ALTER TABLE violation_evidence DROP COLUMN participant_id;
ALTER TABLE violation_evidence DROP COLUMN violation_type;
ALTER TABLE violation_evidence MODIFY COLUMN violation_id BIGINT NOT NULL;

DROP INDEX idx_violation_evidence_activity_id ON violation_evidence;
DROP INDEX idx_violation_evidence_participant_id ON violation_evidence;
DROP INDEX idx_violation_evidence_violation_type ON violation_evidence;
*/

# =====================================================
# ADDITIONAL INDEXES (optional, for better performance)
# =====================================================

# If you have large datasets, add these indexes:
# CREATE INDEX idx_violation_evidence_created ON violation_evidence(captured_at);
# CREATE INDEX idx_violation_evidence_image_url ON violation_evidence(image_url(100));

# =====================================================
# COMPRESSION (optional, for large image URLs)
# =====================================================

# If image_url column gets very large, compress it:
# ALTER TABLE violation_evidence MODIFY COLUMN image_url VARCHAR(500) NOT NULL;
# (Cloudinary URLs are typically ~200-300 chars, safe with VARCHAR 500)

# =====================================================
# FINAL VERIFICATION
# =====================================================

# Run this to confirm migration successful
SELECT 
    'violation_evidence columns' as check_item,
    COUNT(*) as count
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'violation_evidence'
UNION ALL
SELECT 
    'violation_evidence indexes' as check_item,
    COUNT(*) as count
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_NAME = 'violation_evidence' AND SEQ_IN_INDEX = 1;
