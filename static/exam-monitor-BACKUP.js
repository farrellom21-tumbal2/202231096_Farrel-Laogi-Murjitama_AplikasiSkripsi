/**
 * Exam Proctoring Monitor Script
 * Monitors exam activity and detects violations
 * REALTIME STRATEGY: Upload violations immediately when detected
 * NEW: Persist monitoring even if tab closed until exam_end_code submitted
 */

class ExamProctorMonitor {
    constructor(config = {}) {
        this.examUrl = config.examUrl || '';
        this.participantId = config.participantId || null;
        this.sessionId = config.sessionId || null;
        this.maxViolations = config.maxViolations || 3;
        this.storageKey = 'exam_violations_' + this.participantId;
        this.examStateKey = 'exam_state_' + this.participantId;
        
        this.violations = this.loadViolations();
        this.isMonitoring = true;
        this.isExamEnded = false; // Track jika exam sudah ended dengan code
        this.tabIsActive = true;
        this.lastDetectedUrl = window.location.href;
        this.violationInProgress = null;
        this.uploadInProgress = new Set();
        
        // Screenshot counter (maksimal 2 screenshots pertama)
        this.screenshotCount = 0;
        this.maxScreenshots = 2;
        
        this.loadExamState();
        this.initMonitoring();
    }
    
    /**
     * Load exam state from localStorage
     */
    loadExamState() {
        try {
            const state = localStorage.getItem(this.examStateKey);
            if (state) {
                const parsed = JSON.parse(state);
                this.isExamEnded = parsed.isExamEnded || false;
            }
        } catch (e) {
            console.error('Error loading exam state:', e);
        }
    }
    
    /**
     * Save exam state to localStorage
     */
    saveExamState() {
        try {
            const state = {
                isExamEnded: this.isExamEnded,
                lastUpdate: new Date().toISOString()
            };
            localStorage.setItem(this.examStateKey, JSON.stringify(state));
        } catch (e) {
            console.error('Error saving exam state:', e);
        }
    }
    
    /**
     * Load violations from localStorage
     */
    loadViolations() {
        try {
            const stored = localStorage.getItem(this.storageKey);
            return stored ? JSON.parse(stored) : [];
        } catch (e) {
            console.error('Error loading violations:', e);
            return [];
        }
    }
    
    /**
     * Save violations to localStorage
     */
    saveViolations() {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(this.violations));
        } catch (e) {
            console.error('Error saving violations:', e);
        }
    }
    
    /**
     * Initialize monitoring systems
     */
    initMonitoring() {
        // Monitor visibility changes (tab switching)
        document.addEventListener('visibilitychange', () => this.handleVisibilityChange());
        
        // Monitor window focus
        window.addEventListener('focus', () => this.handleWindowFocus());
        window.addEventListener('blur', () => this.handleWindowBlur());
        
        // Monitor page unload
        window.addEventListener('beforeunload', () => this.handleBeforeUnload());
        
        // Monitor URL/tab changes using periodic check
        this.startUrlMonitoring();
        
        // Monitor back button
        window.addEventListener('popstate', () => this.handleBackButton());
        
        console.log('Exam Proctoring Monitor initialized');
    }
    
    /**
     * Handle visibility changes (tab switch)
     */
    handleVisibilityChange() {
        if (document.hidden) {
            // Tab became inactive
            this.tabIsActive = false;
            console.log('Tab hidden/minimized - Violation detected');
            this.recordViolation('TAB_SWITCH', 'Peserta meninggalkan tab ujian');
        } else {
            // Tab became active again
            this.tabIsActive = true;
            this.endCurrentViolation();
            this.showAlert('⚠️ Selamat datang kembali! Aktivitas Anda sedang dipantau.');
        }
    }
    
    /**
     * Handle window blur (switch to another window)
     */
    handleWindowBlur() {
        console.log('Window blur - Violation detected');
        this.recordViolation('WINDOW_BLUR', 'Peserta beralih ke window lain');
    }
    
    /**
     * Handle window focus
     */
    handleWindowFocus() {
        if (!this.tabIsActive) {
            return; // Still on another tab
        }
        this.endCurrentViolation();
    }
    
    /**
     * Handle back button press
     */
    handleBackButton() {
        console.log('Back button pressed - Violation detected');
        this.recordViolation('BACK_BUTTON', 'Peserta menekan tombol back');
    }
    
    /**
     * Handle before unload (refresh, close tab)
     */
    handleBeforeUnload() {
        if (this.violationInProgress) {
            this.endCurrentViolation();
        }
    }
    
    /**
     * Start URL/Tab monitoring (check every 1 second)
     */
    startUrlMonitoring() {
        setInterval(() => {
            if (!this.isMonitoring || !this.examUrl) return;
            
            const currentUrl = window.location.href;
            const isSameDomain = this.isSameExamDomain(currentUrl);
            
            if (!isSameDomain && !this.isAllowedPage(currentUrl)) {
                console.log('URL mismatch - Violation detected');
                this.recordViolation('URL_MISMATCH', 'Peserta mengakses URL di luar halaman ujian');
            }
        }, 1000);
    }
    
    /**
     * Check if URL is same as exam URL domain
     */
    isSameExamDomain(url) {
        try {
            const examDomain = new URL(this.examUrl).hostname;
            const currentDomain = new URL(url).hostname;
            return examDomain === currentDomain;
        } catch (e) {
            return false;
        }
    }
    
    /**
     * Check if page is allowed (dashboard, etc)
     */
    isAllowedPage(url) {
        const allowedPatterns = [
            '/participant/dashboard',
            '/participant/logout'
        ];
        
        return allowedPatterns.some(pattern => url.includes(pattern));
    }
    
    /**
     * Record a violation
     */
    recordViolation(violationType, description) {
        // Don't record violations jika exam sudah ended
        if (this.isExamEnded) {
            console.log('Exam already ended - violation not recorded');
            return;
        }
        
        // If there's already a violation in progress, end it first
        if (this.violationInProgress) {
            this.endCurrentViolation();
        }
        
        // Create new violation
        this.violationInProgress = {
            type: violationType,
            description: description,
            startTime: new Date(),
            evidence: null,
            dbId: null // Will be filled from server response
        };
        
        console.log(`[VIOLATION] ${violationType} - ${description}`);
        
        // Show alert to participant IMMEDIATELY
        this.showAlert(`[PELANGGARAN]\n\n${description}\n\nAktivitas Anda sedang dicatat dan akan dilaporkan.`);
        
        // Capture screenshot as evidence (async, non-blocking)
        // IMPORTANT: Always upload, even if screenshot fails
        this.captureEvidence()
            .then(() => {
                console.log(`[UPLOAD] Violation ${violationType} ready for upload`);
                this.uploadViolationToServer();
            })
            .catch((err) => {
                console.error(`[CAPTURE_ERROR] ${err}`);
                console.log('[UPLOAD] Uploading violation WITHOUT screenshot');
                // Still upload violation even if screenshot fails
                this.uploadViolationToServer();
            });
    }
    
    /**
     * End current violation
     */
    endCurrentViolation() {
        if (!this.violationInProgress) return;
        
        const violation = {
            type: this.violationInProgress.type,
            description: this.violationInProgress.description,
            startTime: this.violationInProgress.startTime.toISOString(),
            endTime: new Date().toISOString(),
            durationSeconds: Math.floor((new Date() - this.violationInProgress.startTime) / 1000),
            evidence: this.violationInProgress.evidence,
            dbId: this.violationInProgress.dbId
        };
        
        this.violations.push(violation);
        this.saveViolations();
        
        console.log('✅ Violation ended and saved', violation);
        
        this.violationInProgress = null;
    }
    
    /**
     * Capture screenshot as evidence using canvas (LIMITED TO 2 SCREENSHOTS)
     */
    async captureEvidence() {
        return new Promise(async (resolve, reject) => {
            try {
                // Check if we've already reached screenshot limit
                if (this.screenshotCount >= this.maxScreenshots) {
                    console.log(`⚠️ Screenshot limit reached (${this.screenshotCount}/${this.maxScreenshots}). No more screenshots will be captured.`);
                    if (this.violationInProgress) {
                        this.violationInProgress.evidence = null;
                    }
                    resolve(null);
                    return;
                }
                
                console.log(`📸 Attempting to capture screenshot ${this.screenshotCount + 1}/${this.maxScreenshots}...`);
                
                // Try using html2canvas if available
                if (typeof html2canvas !== 'undefined') {
                    console.log('📷 Using html2canvas library...');
                    
                    const canvas = await html2canvas(document.body, {
                        allowTaint: true,
                        useCORS: true,
                        scale: 0.5,
                        backgroundColor: '#ffffff',
                        logging: false,
                        timeout: 5000
                    });
                    
                    // Convert to JPEG data URL with 80% quality
                    const jpegData = canvas.toDataURL('image/jpeg', 0.8);
                    
                    if (this.violationInProgress) {
                        this.violationInProgress.evidence = jpegData;
                        this.screenshotCount++;
                        
                        const sizeKB = (jpegData.length / 1024).toFixed(2);
                        console.log(`✅ Screenshot ${this.screenshotCount} captured successfully (${sizeKB} KB)`);
                    }
                    
                    resolve(jpegData);
                } else {
                    // Fallback: use canvas from current view
                    console.log('⚠️ html2canvas not available. Using fallback canvas...');
                    
                    const canvas = document.createElement('canvas');
                    canvas.width = Math.min(window.innerWidth, 1920);
                    canvas.height = Math.min(window.innerHeight, 1080);
                    
                    const ctx = canvas.getContext('2d');
                    ctx.fillStyle = '#ffffff';
                    ctx.fillRect(0, 0, canvas.width, canvas.height);
                    
                    // Draw content
                    ctx.fillStyle = '#333333';
                    ctx.font = 'bold 20px Arial';
                    ctx.fillText('Exam Proctoring Evidence', 20, 50);
                    
                    ctx.font = '14px Arial';
                    ctx.fillText(`Violation Type: ${this.violationInProgress ? this.violationInProgress.type : 'UNKNOWN'}`, 20, 100);
                    ctx.fillText(`Captured at: ${new Date().toLocaleString()}`, 20, 130);
                    ctx.fillText(`Screenshot ${this.screenshotCount + 1} of ${this.maxScreenshots}`, 20, 160);
                    ctx.fillText(`URL: ${window.location.href}`, 20, 190);
                    
                    const jpegData = canvas.toDataURL('image/jpeg', 0.8);
                    
                    if (this.violationInProgress) {
                        this.violationInProgress.evidence = jpegData;
                        this.screenshotCount++;
                        
                        const sizeKB = (jpegData.length / 1024).toFixed(2);
                        console.log(`✅ Fallback screenshot ${this.screenshotCount} captured successfully (${sizeKB} KB)`);
                    }
                    
                    resolve(jpegData);
                }
            } catch (e) {
                console.error('❌ Error capturing evidence:', e);
                if (this.violationInProgress) {
                    this.violationInProgress.evidence = null;
                }
                reject(e);
            }
        });
    }
    
    /**
     * Show alert popup
     */
    showAlert(message) {
        // Create custom modal alert
        const alertId = 'exam_alert_' + Date.now();
        const alertHtml = `
            <div id="${alertId}" class="exam-alert-overlay">
                <div class="exam-alert-box">
                    <div class="exam-alert-content">
                        ${message.split('\n').map(line => `<p>${line}</p>`).join('')}
                    </div>
                    <button class="exam-alert-btn" onclick="document.getElementById('${alertId}').remove()">
                        Mengerti
                    </button>
                </div>
            </div>
        `;
        
        // Inject CSS if not already done
        if (!document.getElementById('exam-alert-styles')) {
            const style = document.createElement('style');
            style.id = 'exam-alert-styles';
            style.textContent = `
                .exam-alert-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.5);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 10000;
                }
                
                .exam-alert-box {
                    background: white;
                    border-radius: 10px;
                    padding: 30px;
                    max-width: 400px;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
                    text-align: center;
                    border-left: 5px solid #dc3545;
                }
                
                .exam-alert-content {
                    margin-bottom: 20px;
                    color: #333;
                }
                
                .exam-alert-content p {
                    margin: 10px 0;
                    font-size: 14px;
                    line-height: 1.5;
                }
                
                .exam-alert-btn {
                    background: #dc3545;
                    color: white;
                    border: none;
                    padding: 10px 30px;
                    border-radius: 5px;
                    cursor: pointer;
                    font-weight: 600;
                    font-size: 14px;
                }
                
                .exam-alert-btn:hover {
                    background: #c82333;
                }
            `;
            document.head.appendChild(style);
        }
        
        // Inject alert
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = alertHtml;
        document.body.appendChild(tempDiv.firstElementChild);
    }
    
    /**
     * Get all violations summary
     */
    getViolationsSummary() {
        const summary = {
            totalViolations: this.violations.length,
            totalDurationSeconds: 0,
            violations: this.violations,
            violationTypes: {}
        };
        
        this.violations.forEach(v => {
            summary.totalDurationSeconds += v.durationSeconds;
            summary.violationTypes[v.type] = (summary.violationTypes[v.type] || 0) + 1;
        });
        
        return summary;
    }
    
    /**
     * Clear all violations (for new session)
     */
    clearViolations() {
        this.violations = [];
        this.saveViolations();
        localStorage.removeItem(this.storageKey);
    }
    
    /**
     * Stop monitoring
     */
    stopMonitoring() {
        this.isMonitoring = false;
        if (this.violationInProgress) {
            this.endCurrentViolation();
        }
        console.log('Exam Proctoring Monitor stopped');
    }
    
    /**
     * Upload violation to server in realtime (logs to violations table)
     */
    async uploadViolationToServer() {
        console.log('\n' + '='.repeat(80));
        console.log('[UPLOAD] UPLOADING VIOLATION TO SERVER');
        console.log('='.repeat(80));
        
        if (!this.violationInProgress) {
            console.error('[UPLOAD] ERROR: No violation in progress!');
            return;
        }
        
        const violation = this.violationInProgress;
        const uploadId = `${this.participantId}_${violation.startTime.getTime()}`;
        
        console.log(`[UPLOAD] Violation ID: ${uploadId}`);
        console.log(`[UPLOAD] Type: ${violation.type}`);
        console.log(`[UPLOAD] Participant: ${this.participantId}, Session: ${this.sessionId}`);
        
        // Prevent duplicate uploads
        if (this.uploadInProgress.has(uploadId)) {
            console.log('[UPLOAD] WARNING: Upload already in progress for this violation');
            return;
        }
        
        this.uploadInProgress.add(uploadId);
        
        try {
            const payload = {
                participant_id: this.participantId,
                session_id: this.sessionId,
                violation_type: violation.type,
                description: violation.description,
                startTime: violation.startTime.toISOString(),
                evidence: violation.evidence  // Base64 screenshot
            };
            
            console.log('[UPLOAD] Payload prepared');
            console.log(`   Participant ID: ${this.participantId}`);
            console.log(`   Session ID: ${this.sessionId}`);
            console.log(`   Violation Type: ${violation.type}`);
            console.log(`   Description: ${violation.description.substring(0, 60)}...`);
            console.log(`   Evidence: ${violation.evidence ? 'YES (' + (violation.evidence.length / 1024).toFixed(2) + ' KB)' : 'NO'}`);
            
            console.log('[UPLOAD] Sending POST /api/record-violation...');
            console.log('[UPLOAD] Waiting for server response...');
            
            const response = await fetch('/api/record-violation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload),
                timeout: 30000
            });
            
            console.log(`[UPLOAD] Response Status: ${response.status} ${response.statusText}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('[UPLOAD] Response Data:', data);
            
            if (data.status === 'success') {
                console.log('✓✓✓ VIOLATION UPLOADED SUCCESSFULLY ✓✓✓');
                console.log(`   Violation ID: ${data.violation_id}`);
                console.log(`   Evidence URL: ${data.evidence_url || 'None'}`);
                console.log('='.repeat(80) + '\n');
                
                // Store the violation ID from server
                if (this.violationInProgress) {
                    this.violationInProgress.dbId = data.violation_id;
                    this.violationInProgress.uploaded = true;
                }
            } else {
                console.error('✗ SERVER RETURNED ERROR ✗');
                console.error(`   Error: ${data.message || 'Unknown error'}`);
                console.log('='.repeat(80) + '\n');
                if (this.violationInProgress) {
                    this.violationInProgress.uploadAttempted = true;
                }
            }
        } catch (error) {
            console.error('✗ UPLOAD FAILED ✗');
            console.error(`   Error: ${error.message}`);
            if (error.stack) {
                console.error('   Stack:', error.stack);
            }
            console.log('='.repeat(80) + '\n');
            if (this.violationInProgress) {
                this.violationInProgress.uploadAttempted = true;
            }
        } finally {
            this.uploadInProgress.delete(uploadId);
        }
    }
    
    /**
     * Mark exam as ended (via exam_end_code)
     */
    endExamWithCode() {
        this.isExamEnded = true;
        this.isMonitoring = false;
        this.saveExamState();
        
        if (this.violationInProgress) {
            this.endCurrentViolation();
        }
        
        console.log('Exam ended with code - monitoring stopped');
    }
}

// Export for use
if (typeof window !== 'undefined') {
    window.ExamProctorMonitor = ExamProctorMonitor;
}
