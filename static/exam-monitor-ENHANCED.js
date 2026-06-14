/**
 * EXAM MONITORING SYSTEM - ENHANCED VERSION
 * Tracks all exam violations with detailed logging
 * 
 * Features:
 * - Tab/Window switching detection
 * - Browser blur/focus detection
 * - Back button detection
 * - Screenshot evidence capture
 * - Auto-upload to server
 * - Comprehensive console logging
 * 
 * Structure:
 * - ExamMonitor class for exam-specific instance
 * - Global examMonitor variable for cross-window access
 */

console.log('\n' + '='.repeat(80));
console.log('EXAM MONITOR - LOADING');
console.log('='.repeat(80));

class ExamMonitor {
    constructor(config = {}) {
        this.config = {
            participantId: config.participantId || null,
            sessionId: config.sessionId || null,
            uploadEndpoint: config.uploadEndpoint || '/api/record-violation',
            ...config
        };

        this.isActive = false;
        this.violations = [];
        this.uploadQueue = [];
        this.lastViolationTime = 0;
        this.violationDebounce = 2000; // Prevent spam
        this.examStartTime = null;
        this.examEndTime = null;
        this.hiddenStartTime = null; // Track visibility change duration
        this.eventsAttached = false;

        console.log('[MONITOR] Initialized with config:');
        console.log('  - Participant ID:', this.config.participantId);
        console.log('  - Session ID:', this.config.sessionId);
        console.log('  - Upload Endpoint:', this.config.uploadEndpoint);
        console.log('  - Debounce:', this.violationDebounce, 'ms');
    }

    /**
     * Start monitoring
     */
    start() {
        console.log('\n[MONITOR-START] Starting exam monitoring...');
        
        if (this.isActive) {
            console.log('[MONITOR-START] ⚠️ Monitor already active');
            return;
        }

        this.isActive = true;
        this.examStartTime = new Date();
        this.violations = [];

        console.log('[MONITOR-START] ✅ Monitor activated');
        console.log('[MONITOR-START] Exam start time:', this.examStartTime.toISOString());

        // Attach event listeners
        this.attachEventListeners();

        // Start upload processor
        this.startUploadProcessor();

        // Periodic status log
        this.statusInterval = setInterval(() => {
            this.logStatus();
        }, 30000);

        console.log('[MONITOR-START] Event listeners attached');
        console.log('[MONITOR-START] Upload processor started');
    }

    /**
     * Stop monitoring
     */
    stop() {
        console.log('\n[MONITOR-STOP] Stopping exam monitoring...');
        
        this.isActive = false;
        this.examEndTime = new Date();

        // Remove listeners
        document.removeEventListener('visibilitychange', this.onVisibilityChange.bind(this));
        window.removeEventListener('blur', this.onWindowBlur.bind(this));
        window.removeEventListener('focus', this.onWindowFocus.bind(this));
        window.removeEventListener('beforeunload', this.onWindowBeforeUnload.bind(this));
        document.removeEventListener('keydown', this.onKeyDown.bind(this));

        // Stop intervals
        if (this.statusInterval) clearInterval(this.statusInterval);
        if (this.uploadInterval) clearInterval(this.uploadInterval);

        console.log('[MONITOR-STOP] ✅ Monitor stopped');
        console.log('[MONITOR-STOP] Total violations recorded:', this.violations.length);
        console.log('[MONITOR-STOP] Duration:', this.getDurationSeconds(), 'seconds');

        // Process remaining queue
        this.processUploadQueue();
    }

    /**
     * Attach all event listeners
     */
    attachEventListeners() {
        console.log('[LISTENERS] Attaching event listeners...');

        try {
            // Tab/Window visibility change
            document.addEventListener('visibilitychange', this.onVisibilityChange.bind(this), false);
            console.log('[LISTENERS] ✓ visibilitychange listener attached');

            // Window blur (user switched window/tab)
            window.addEventListener('blur', this.onWindowBlur.bind(this), false);
            console.log('[LISTENERS] ✓ blur listener attached');

            // Window focus
            window.addEventListener('focus', this.onWindowFocus.bind(this), false);
            console.log('[LISTENERS] ✓ focus listener attached');

            // Before unload
            window.addEventListener('beforeunload', this.onWindowBeforeUnload.bind(this), false);
            console.log('[LISTENERS] ✓ beforeunload listener attached');

            // Keyboard - detect back button via Alt+Left
            document.addEventListener('keydown', this.onKeyDown.bind(this), false);
            console.log('[LISTENERS] ✓ keydown listener attached');

            // Prevent right-click context menu
            document.addEventListener('contextmenu', (e) => {
                console.log('[PREVENT] Right-click prevented');
                e.preventDefault();
                return false;
            }, false);
            console.log('[LISTENERS] ✓ contextmenu listener attached');

            // Prevent drag and drop
            document.addEventListener('drag', (e) => e.preventDefault(), false);
            document.addEventListener('drop', (e) => e.preventDefault(), false);
            console.log('[LISTENERS] ✓ drag/drop listeners attached');

            console.log('[LISTENERS] ✅ All listeners attached successfully');

        } catch (e) {
            console.error('[LISTENERS] ❌ Error attaching listeners:', e);
        }
    }

    /**
     * Event: Document visibility change
     * IMPROVED: Only records violation for actual tab switches, NOT window minimize
     */
    onVisibilityChange = function(event) {
        if (!this.isActive) return;

        const hidden = document.hidden;
        console.log(`\n[EVENT] visibilitychange - hidden: ${hidden}`);

        if (hidden) {
            // Document became hidden - could be tab switch OR window minimize
            // Don't record immediately - wait to see if window regains focus quickly (minimize)
            console.log('[EVENT] Document hidden - checking if actual tab switch...');
            this.hiddenStartTime = Date.now();
        } else {
            // Document became visible again
            if (this.hiddenStartTime) {
                const hiddenDuration = Date.now() - this.hiddenStartTime;
                
                // Only count as violation if hidden for > 2 seconds
                // Window minimize/restore usually takes < 1 second
                if (hiddenDuration > 2000) {
                    console.log(`[EVENT] ⚠️ TAB SWITCH DETECTED - Hidden for ${Math.floor(hiddenDuration/1000)}s`);
                    this.recordViolation('TAB_SWITCH', `User switched to another tab for ${Math.floor(hiddenDuration/1000)} seconds`, {
                        hidden_duration_ms: hiddenDuration,
                        timestamp: new Date().toISOString()
                    });
                } else {
                    console.log(`[EVENT] ✓ Window minimize/restore detected (${hiddenDuration}ms) - IGNORED`);
                }
                this.hiddenStartTime = null;
            }
        }
    }

    /**
     * Event: Window blur (loss of focus)
     * DISABLED: Window blur can happen during minimize/maximize, not just tab switch
     * Visibility change event is more reliable for detecting real tab switches
     */
    onWindowBlur = function(event) {
        if (!this.isActive) return;

        console.log(`\n[EVENT] blur - window lost focus (NOT RECORDED - use visibilitychange instead)`);
        // Don't record violation - visibility change is more reliable
        // Window blur can happen during minimize/maximize window operations
    }

    /**
     * Event: Window focus (regained focus)
     */
    onWindowFocus = function(event) {
        if (!this.isActive) return;

        console.log(`\n[EVENT] focus - window regained focus`);
        // Log but don't record violation - focus gain is not a violation itself
    }

    /**
     * Event: Before unload (user closing window)
     */
    onWindowBeforeUnload = function(event) {
        if (!this.isActive) return;

        console.log(`\n[EVENT] beforeunload - user closing window`);
        this.recordViolation('WINDOW_CLOSE', 'User attempted to close exam window', {
            timestamp: new Date().toISOString()
        });

        // Log violations immediately
        event.preventDefault();
        event.returnValue = '';
        
        // Try to upload queue synchronously
        this.processSyncUpload();
    }

    /**
     * Event: Keyboard shortcuts
     */
    onKeyDown = function(event) {
        if (!this.isActive) return;

        // Alt + Left arrow = back button
        if (event.altKey && event.key === 'ArrowLeft') {
            console.log(`\n[EVENT] keydown - Alt+Left (Back button)`);
            this.recordViolation('BACK_BUTTON', 'User pressed back button (Alt+Left)', {
                keyCode: event.keyCode,
                timestamp: new Date().toISOString()
            });
            event.preventDefault();
            return false;
        }

        // Ctrl+W = close tab
        if ((event.ctrlKey || event.metaKey) && event.key === 'w') {
            console.log(`\n[EVENT] keydown - Ctrl+W (Close tab)`);
            this.recordViolation('CLOSE_TAB', 'User pressed Ctrl+W to close tab', {
                timestamp: new Date().toISOString()
            });
            event.preventDefault();
            return false;
        }

        // Ctrl+T = new tab
        if ((event.ctrlKey || event.metaKey) && event.key === 't') {
            console.log(`\n[EVENT] keydown - Ctrl+T (New tab)`);
            this.recordViolation('NEW_TAB', 'User tried to open new tab (Ctrl+T)', {
                timestamp: new Date().toISOString()
            });
            event.preventDefault();
            return false;
        }

        // F5 = refresh
        if (event.key === 'F5') {
            console.log(`\n[EVENT] keydown - F5 (Refresh)`);
            this.recordViolation('REFRESH_PAGE', 'User pressed F5 to refresh', {
                timestamp: new Date().toISOString()
            });
            event.preventDefault();
            return false;
        }
    }

    /**
     * Record a violation
     */
    async recordViolation(type, description, details = {}) {
        console.log(`\n[VIOLATION-RECORD] Type: ${type}`);
        console.log(`[VIOLATION-RECORD] Description: ${description}`);

        // Skip WINDOW_BLUR - not a real violation (can be from minimize/maximize)
        if (type === 'WINDOW_BLUR') {
            console.log(`[VIOLATION-RECORD] ↩️ SKIPPED WINDOW_BLUR (not a real violation)`);
            return;
        }

        // Debounce same violations
        const now = Date.now();
        if (now - this.lastViolationTime < this.violationDebounce) {
            console.log(`[VIOLATION-RECORD] ⏳ Debounced (${this.violationDebounce}ms)`);
            return;
        }
        this.lastViolationTime = now;

        try {
            // Capture screenshot
            console.log('[VIOLATION-RECORD] Capturing screenshot...');
            const screenshot = await this.captureScreenshot();

            // Create violation object
            const violation = {
                type,
                description,
                timestamp: new Date().toISOString(),
                duration_at_violation: this.getDurationSeconds(),
                screenshot_base64: screenshot,
                page_url: window.location.href,
                page_title: document.title,
                details
            };

            this.violations.push(violation);
            console.log('[VIOLATION-RECORD] ✅ Violation recorded');
            console.log(`[VIOLATION-RECORD] Total violations: ${this.violations.length}`);

            // Queue for upload
            this.uploadQueue.push(violation);
            console.log(`[VIOLATION-RECORD] Added to upload queue (${this.uploadQueue.length} pending)`);

            // Try immediate upload
            this.uploadViolationToServer(violation);

        } catch (e) {
            console.error('[VIOLATION-RECORD] ❌ Error recording violation:', e);
        }
    }

    /**
     * Capture screenshot evidence
     */
    async captureScreenshot() {
        try {
            console.log('[SCREENSHOT] Starting capture...');

            if (!window.html2canvas) {
                console.warn('[SCREENSHOT] ⚠️ html2canvas not available');
                return null;
            }

            const canvas = await html2canvas(document.body, {
                allowTaint: true,
                useCORS: true,
                backgroundColor: '#ffffff',
                logging: false,
                scale: 0.5 // Reduce size
            });

            const base64 = canvas.toDataURL('image/jpeg', 0.7);
            console.log('[SCREENSHOT] ✅ Screenshot captured:', base64.length, 'bytes');
            
            return base64;

        } catch (e) {
            console.error('[SCREENSHOT] ❌ Error capturing screenshot:', e);
            return null;
        }
    }

    /**
     * Upload violation to server
     */
    async uploadViolationToServer(violation) {
        if (!this.config.participantId || !this.config.sessionId) {
            console.warn('[UPLOAD] ⚠️ Missing participant/session ID');
            return;
        }

        try {
            console.log('\n[UPLOAD-START] Uploading violation...');
            console.log('[UPLOAD-START] Type:', violation.type);
            console.log('[UPLOAD-START] URL:', violation.page_url);

            const payload = {
                participant_id: this.config.participantId,
                violation_type: violation.type,
                description: violation.description,
                startTime: violation.timestamp
            };

            if (violation.screenshot_base64) {
                payload.evidence = violation.screenshot_base64;
            }

            console.log('[UPLOAD] Sending payload:', JSON.stringify(payload));

            const response = await fetch(this.config.uploadEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload),
                timeout: 30000
            });

            const data = await response.json();

            if (response.ok) {
                console.log('[UPLOAD-SUCCESS] ✅ Violation uploaded successfully');
                console.log('[UPLOAD-SUCCESS] Violation ID:', data.violation_id);
                console.log('[UPLOAD-SUCCESS] Server response:', data);
                
                // Remove from queue
                const index = this.uploadQueue.indexOf(violation);
                if (index > -1) {
                    this.uploadQueue.splice(index, 1);
                }

            } else {
                console.error('[UPLOAD-FAILED] ❌ Server returned error:', data);
                console.log('[UPLOAD-FAILED] Status:', response.status);
                console.log('[UPLOAD-FAILED] Will retry...', violation.type);
            }

        } catch (e) {
            console.error('[UPLOAD-ERROR] ❌ Upload error:', e);
            console.log('[UPLOAD-ERROR] Will retry later');
        }
    }

    /**
     * Process upload queue periodically
     */
    startUploadProcessor() {
        console.log('[PROCESSOR] Starting upload processor...');

        this.uploadInterval = setInterval(() => {
            this.processUploadQueue();
        }, 10000); // Every 10 seconds

        console.log('[PROCESSOR] ✅ Processor started (10s interval)');
    }

    /**
     * Process all pending uploads
     */
    async processUploadQueue() {
        if (this.uploadQueue.length === 0) return;

        console.log(`\n[QUEUE-PROCESS] Processing ${this.uploadQueue.length} pending uploads...`);

        const queue = [...this.uploadQueue];
        for (const violation of queue) {
            await this.uploadViolationToServer(violation);
            // Small delay between uploads
            await new Promise(resolve => setTimeout(resolve, 500));
        }

        console.log(`[QUEUE-PROCESS] ✅ Queue processing complete`);
    }

    /**
     * Synchronous upload (for beforeunload)
     */
    processSyncUpload() {
        if (this.uploadQueue.length === 0) return;

        console.log(`\n[SYNC-UPLOAD] Processing ${this.uploadQueue.length} uploads synchronously...`);

        // Use fetch with keepalive for synchronous behavior
        this.uploadQueue.forEach(violation => {
            const payload = {
                participant_id: this.config.participantId,
                violation_type: violation.type,
                description: violation.description,
                startTime: violation.timestamp
            };
            
            if (violation.screenshot_base64) {
                payload.evidence = violation.screenshot_base64;
            }

            try {
                // Use keepalive to ensure request completes even if page unloads
                fetch(this.config.uploadEndpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                    keepalive: true
                }).catch(e => {
                    console.error('[SYNC-UPLOAD] Error:', e);
                });
            } catch (e) {
                console.error('[SYNC-UPLOAD] Fetch error:', e);
            }
        });

        console.log('[SYNC-UPLOAD] ✅ Sync upload initiated');
    }

    /**
     * End exam with code verification
     */
    endExamWithCode(code = null) {
        console.log('\n[END-EXAM] Ending exam...');
        
        if (!this.isActive) {
            console.log('[END-EXAM] ⚠️ Monitor not active');
            return;
        }

        // Process remaining uploads
        this.processUploadQueue();

        // Stop monitoring
        this.stop();

        console.log('[END-EXAM] ✅ Exam ended');
        console.log('[END-EXAM] Total violations:', this.violations.length);
    }

    /**
     * Get duration in seconds
     */
    getDurationSeconds() {
        if (!this.examStartTime) return 0;
        const endTime = this.examEndTime || new Date();
        return Math.floor((endTime - this.examStartTime) / 1000);
    }

    /**
     * Log status
     */
    logStatus() {
        if (!this.isActive) return;

        console.log(`\n[STATUS-LOG] Monitor Status at ${new Date().toLocaleTimeString()}`);
        console.log(`[STATUS-LOG] Active: ${this.isActive}`);
        console.log(`[STATUS-LOG] Duration: ${this.getDurationSeconds()}s`);
        console.log(`[STATUS-LOG] Violations: ${this.violations.length}`);
        console.log(`[STATUS-LOG] Upload Queue: ${this.uploadQueue.length}`);
    }

    /**
     * Get statistics
     */
    getStats() {
        return {
            isActive: this.isActive,
            totalViolations: this.violations.length,
            pendingUploads: this.uploadQueue.length,
            duration: this.getDurationSeconds(),
            violations: this.violations,
            startTime: this.examStartTime,
            endTime: this.examEndTime
        };
    }
}

// Global instance accessible from parent window
let examMonitor = null;

/**
 * Initialize exam monitor
 */
function initializeExamMonitor(config) {
    console.log('\n[INIT] Initializing ExamMonitor...');
    console.log('[INIT] Config:', config);

    examMonitor = new ExamMonitor({
        participantId: config.participantId,
        sessionId: config.sessionId,
        uploadEndpoint: config.uploadEndpoint || '/api/record-violation'
    });

    // Start monitoring
    examMonitor.start();

    // Make available globally
    window.examMonitor = examMonitor;

    console.log('[INIT] ✅ ExamMonitor initialized and started');
    console.log('[INIT] Instance available as window.examMonitor');
}

/**
 * Initialize on page load if in proctored exam context
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('\n[PAGE-LOAD] Exam page loaded');

    // Get parameters from URL
    const params = new URLSearchParams(window.location.search);
    const participantId = params.get('participant_id');
    const sessionId = params.get('session_id');

    if (participantId && sessionId) {
        console.log('[PAGE-LOAD] Proctored exam detected');
        console.log('[PAGE-LOAD] Participant ID:', participantId);
        console.log('[PAGE-LOAD] Session ID:', sessionId);

        // Initialize monitor
        initializeExamMonitor({
            participantId: parseInt(participantId),
            sessionId: parseInt(sessionId)
        });

        // Show monitoring status
        const statusDiv = document.querySelector('[data-monitor-status]');
        if (statusDiv) {
            statusDiv.innerHTML = '🟢 <strong>Monitoring Active</strong>';
            statusDiv.style.color = '#28a745';
            console.log('[PAGE-LOAD] Status indicator updated');
        }

    } else {
        console.log('[PAGE-LOAD] ⚠️ Not a proctored exam or missing parameters');
    }
});

/**
 * Cleanup on page unload
 */
window.addEventListener('unload', function() {
    if (examMonitor && examMonitor.isActive) {
        console.log('\n[PAGE-UNLOAD] Page unloading...');
        examMonitor.stop();
        console.log('[PAGE-UNLOAD] Monitor stopped');
    }
});

console.log('='.repeat(80));
console.log('EXAM MONITOR - LOADED SUCCESSFULLY');
console.log('='.repeat(80) + '\n');
