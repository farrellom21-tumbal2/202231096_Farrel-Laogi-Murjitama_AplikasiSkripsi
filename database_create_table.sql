-- File SQL untuk membuat tabel sessions
-- Jalankan query ini di MySQL database Anda

CREATE TABLE IF NOT EXISTS sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_name VARCHAR(255) NOT NULL,
    exam_end_code VARCHAR(100) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    exam_url VARCHAR(500) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_session_name (session_name),
    INDEX idx_start_time (start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Query di bawah ini untuk testing/verifikasi:
-- SELECT * FROM sessions;
-- DESC sessions;

-- =====================================================

-- File SQL untuk membuat tabel participants
CREATE TABLE IF NOT EXISTS participants (
    id INT AUTO_INCREMENT PRIMARY KEY,
    participant_number VARCHAR(50) NOT NULL UNIQUE,
    participant_name VARCHAR(255) NOT NULL,
    face_photo_url VARCHAR(500),
    session_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    INDEX idx_participant_number (participant_number),
    INDEX idx_participant_name (participant_name),
    INDEX idx_session_id (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Query di bawah ini untuk testing/verifikasi participants:
-- SELECT * FROM participants;
-- DESC participants;

CREATE TABLE violations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    participant_id INT NOT NULL,
    violation_type VARCHAR(50) NOT NULL,
    description TEXT,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    duration_seconds INT NOT NULL,

    FOREIGN KEY (participant_id)
        REFERENCES participants(id)
        ON DELETE CASCADE
);
CREATE TABLE violation_evidence (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    violation_id BIGINT NOT NULL,
    image_url TEXT NOT NULL,           -- Cloudinary
    captured_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (violation_id)
        REFERENCES violations(id)
        ON DELETE CASCADE
);
CREATE TABLE final_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    participant_id INT UNIQUE NOT NULL,
    total_violations INT DEFAULT 0,
    total_violation_time INT DEFAULT 0, -- seconds
    final_decision ENUM('JUJUR', 'CURANG') NOT NULL,
    decided_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (participant_id)
        REFERENCES participants(id)
        ON DELETE CASCADE
);

-- ===================== EXAM ACTIVITY LOG =====================
CREATE TABLE exam_activity_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    participant_id INT NOT NULL,
    session_id INT NOT NULL,
    activity_type VARCHAR(50) NOT NULL, -- EXAM_START, VIOLATION_DETECTED, EXAM_END, TAB_CLOSE, TAB_REOPEN
    description TEXT,
    activity_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    extra_data JSON, -- Store violation_id, violation_type, etc.
    
    FOREIGN KEY (participant_id) REFERENCES participants(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    INDEX idx_participant_session (participant_id, session_id),
    INDEX idx_activity_type (activity_type),
    INDEX idx_timestamp (activity_timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;