/**
 * EXAM PROCTORING MONITOR - FIXED VERSION
 * Critical: Ensures violations are uploaded to server reliably
 * Strategy: Simple, direct upload - no promises, no delays
 */

class ExamProctorMonitor {
    constructor(config = {}) {
        console.log('\n' + '='.repeat(80));
        console.log('[MONITOR] INITIALIZING EXAM PROCTORING MONITOR');
        console.log('='.repeat(80));
        
        this.examUrl = config.examUrl || '';
        this.participantId = config.participantId || null;
        this.sessionId = config.sessionId || null;
        this.maxViolations = config.maxViolations || 10;
        
        // State tracking
        this.isMonitoring = true;
        this.isExamEnded = false;
        this.tabIsActive = true;
        this.violationInProgress = null;
        this.uploadInProgress = false;
        
        // Storage keys
        this.storageKey = 'exam_violations_' + this.participantId;
        this.examStateKey = 'exam_state_' + this.participantId;
        
        // Violations list (for local tracking)
        this.violations = this.loadViolations();
        this.screenshotCount = 0;
        this.maxScreenshots = 3;
        
        console.log(`[MONITOR] Config:`);
        console.log(`   Participant ID: ${this.participantId}`);
        console.log(`   Session ID: ${this.sessionId}`);
        console.log(`   Exam URL: ${this.examUrl.substring(0, 50)}...`);
        console.log(`   Max Violations: ${this.maxViolations}`);
        
        this.loadExamState();
        this.initMonitoring();
        
        console.log('[MONITOR] INITIALIZATION COMPLETE');
        console.log('='.repeat(80) + '\n');
    }
    
    // ===== STATE MANAGEMENT =====
    
    loadExamState() {
        try {
            const state = localStorage.getItem(this.examStateKey);
            if (state) {
                const parsed = JSON.parse(state);
                this.isExamEnded = parsed.isExamEnded || false;
                console.log(`[STATE] Loaded exam state: ${this.isExamEnded ? 'ENDED' : 'ACTIVE'}`);
            }
        } catch (e) {
            console.error('[STATE] Error loading exam state:', e);
        }
    }
    
    saveExamState() {
        try {
            const state = {
                isExamEnded: this.isExamEnded,
                lastUpdate: new Date().toISOString()
            };
            localStorage.setItem(this.examStateKey, JSON.stringify(state));
        } catch (e) {
            console.error('[STATE] Error saving exam state:', e);
        }
    }
    
    loadViolations() {
        try {
            const stored = localStorage.getItem(this.storageKey);
            return stored ? JSON.parse(stored) : [];
        } catch (e) {
            console.error('[STATE] Error loading violations:', e);
            return [];
        }
    }
    
    saveViolations() {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(this.violations));
        } catch (e) {
            console.error('[STATE] Error saving violations:', e);
        }
    }
    
    // ===== EVENT LISTENERS =====
    
    initMonitoring() {
        console.log('[MONITOR] Attaching event listeners...');
        
        try {
            // Tab visibility changes (most reliable violation detector)
            document.addEventListener('visibilitychange', (e) => {
                console.log('[EVENT] visibilitychange fired');
                this.handleVisibilityChange();
            });
            
            // Window focus events
            window.addEventListener('focus', (e) => {
                console.log('[EVENT] focus fired');
                this.handleWindowFocus();
            });
            
            window.addEventListener('blur', (e) => {
                console.log('[EVENT] blur fired');
                this.handleWindowBlur();
            });
            
            // Back button / Navigation
            window.addEventListener('popstate', (e) => {
                console.log('[EVENT] popstate fired (back button)');
                this.handleBackButton();
            });
            
            // Page unload
            window.addEventListener('beforeunload', (e) => {
                console.log('[EVENT] beforeunload fired');
                this.handleBeforeUnload();
            });
            
            console.log('[MONITOR] All event listeners attached successfully');
            
            // Start periodic URL monitoring
            this.startUrlMonitoring();
            
        } catch (e) {
            console.error('[MONITOR] Error attaching event listeners:', e);
        }
    }
    
    // ===== EVENT HANDLERS =====
    
    handleVisibilityChange() {
        if (document.hidden) {
            console.log('[DETECT] TAB HIDDEN - Recording violation');
            this.recordViolation('TAB_SWITCH', 'Peserta meninggalkan tab ujian');
        } else {
            console.log('[DETECT] TAB VISIBLE AGAIN - Ending violation');
            this.endCurrentViolation();
        }
    }
    
    handleWindowBlur() {
        console.log('[DETECT] WINDOW BLUR - Recording violation');
        this.recordViolation('WINDOW_BLUR', 'Peserta beralih ke window lain');
    }
    
    handleWindowFocus() {
        if (this.tabIsActive && this.violationInProgress) {
            console.log('[DETECT] WINDOW FOCUS - Ending violation');
            this.endCurrentViolation();
        }
    }
    
    handleBackButton() {
        console.log('[DETECT] BACK BUTTON - Recording violation');
        this.recordViolation('BACK_BUTTON', 'Peserta menekan tombol back browser');
    }
    
    handleBeforeUnload() {
        console.log('[DETECT] BEFORE UNLOAD - Finalizing violations');
        if (this.violationInProgress) {
            this.endCurrentViolation();
        }
    }
    
    startUrlMonitoring() {
        console.log('[MONITOR] Starting URL monitoring interval');
        setInterval(() => {
            if (!this.isMonitoring || !this.examUrl) return;
            
            const currentUrl = window.location.href;
            const isSameDomain = this.isSameExamDomain(currentUrl);
            
            if (!isSameDomain && !this.isAllowedPage(currentUrl)) {
                console.log('[DETECT] URL MISMATCH - Recording violation');
                this.recordViolation('URL_MISMATCH', `Peserta mengakses URL tidak diizinkan: ${currentUrl}`);
            }
        }, 2000);
    }
    
    isSameExamDomain(url) {
        try {
            const examDomain = new URL(this.examUrl).hostname;
            const currentDomain = new URL(url).hostname;
            return examDomain === currentDomain;
        } catch (e) {
            return false;
        }
    }
    
    isAllowedPage(url) {
        const allowedPatterns = [
            '/participant/dashboard',
            '/participant/logout',
            '/login'
        ];
        return allowedPatterns.some(pattern => url.includes(pattern));
    }
    
    // ===== VIOLATION RECORDING =====
    
    recordViolation(violationType, description) {
        console.log('\n' + '='.repeat(80));
        console.log(`[RECORD] NEW VIOLATION DETECTED: ${violationType}`);
        console.log('='.repeat(80));
        
        // Check if exam already ended
        if (this.isExamEnded) {
            console.log('[RECORD] ⚠️ EXAM ALREADY ENDED - Not recording violation');
            return;
        }
        
        // Check if max violations reached
        if (this.violations.length >= this.maxViolations) {
            console.log(`[RECORD] ⚠️ MAX VIOLATIONS REACHED (${this.maxViolations}) - Not recording`);
            return;
        }
        
        // End previous violation if exists
        if (this.violationInProgress) {
            console.log('[RECORD] Ending previous violation first...');
            this.endCurrentViolation();
        }
        
        // Create violation object
        this.violationInProgress = {
            type: violationType,
            description: description,
            startTime: new Date(),
            evidence: null,
            screenshotUrl: null,
            uploadedAt: null,
            uploadStatus: 'pending'
        };
        
        console.log(`[RECORD] Violation created:`);
        console.log(`   Type: ${violationType}`);
        console.log(`   Description: ${description}`);
        console.log(`   Time: ${this.violationInProgress.startTime.toISOString()}`);
        
        // Show alert to participant
        this.showAlert(`⚠️ PELANGGARAN TERDETEKSI\n\n${description}\n\nAktivitas Anda sedang dicatat dan akan dilaporkan.`);
        
        // Try to capture evidence (non-blocking)
        this.captureEvidenceAsync();
        
        // Upload violation immediately (don't wait for screenshot)
        console.log('[RECORD] Starting upload process...');
        this.uploadViolationToServer();
    }
    
    endCurrentViolation() {
        if (!this.violationInProgress) {
            console.log('[END] No violation in progress');
            return;
        }
        
        const violation = {
            type: this.violationInProgress.type,
            description: this.violationInProgress.description,
            startTime: this.violationInProgress.startTime.toISOString(),
            endTime: new Date().toISOString(),
            durationSeconds: Math.floor((new Date() - this.violationInProgress.startTime) / 1000),
            evidence: this.violationInProgress.evidence,
            uploadStatus: this.violationInProgress.uploadStatus
        };
        
        this.violations.push(violation);
        this.saveViolations();
        
        console.log(`[END] Violation ended:`);
        console.log(`   Type: ${violation.type}`);
        console.log(`   Duration: ${violation.durationSeconds} seconds`);
        console.log(`   Upload Status: ${violation.uploadStatus}`);
        
        this.violationInProgress = null;
    }
    
    // ===== SCREENSHOT CAPTURE =====
    
    async captureEvidenceAsync() {
        if (this.screenshotCount >= this.maxScreenshots) {
            console.log(`[SCREENSHOT] Limit reached (${this.screenshotCount}/${this.maxScreenshots})`);
            return null;
        }
        
        try {
            console.log(`[SCREENSHOT] Attempting to capture screenshot ${this.screenshotCount + 1}/${this.maxScreenshots}...`);
            
            // Try html2canvas first
            if (typeof html2canvas !== 'undefined') {
                console.log('[SCREENSHOT] Using html2canvas library...');
                
                const canvas = await html2canvas(document.body, {
                    allowTaint: true,
                    useCORS: true,
                    scale: 0.5,
                    backgroundColor: '#ffffff',
                    logging: false,
                    timeout: 5000
                });
                
                const jpegData = canvas.toDataURL('image/jpeg', 0.8);
                const sizeKB = (jpegData.length / 1024).toFixed(2);
                
                if (this.violationInProgress) {
                    this.violationInProgress.evidence = jpegData;
                    this.screenshotCount++;
                    console.log(`[SCREENSHOT] ✓ Screenshot captured (${sizeKB} KB)`);
                }
                
                return jpegData;
            } else {
                console.log('[SCREENSHOT] html2canvas not available, using fallback...');
                
                const canvas = document.createElement('canvas');
                canvas.width = Math.min(window.innerWidth, 1920);
                canvas.height = Math.min(window.innerHeight, 1080);
                
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = '#ffffff';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                
                ctx.fillStyle = '#333333';
                ctx.font = 'bold 20px Arial';
                ctx.fillText('Exam Proctoring Evidence', 20, 50);
                
                ctx.font = '14px Arial';
                ctx.fillText(`Violation: ${this.violationInProgress?.type || 'UNKNOWN'}`, 20, 100);
                ctx.fillText(`Time: ${new Date().toLocaleString()}`, 20, 130);
                ctx.fillText(`URL: ${window.location.href}`, 20, 160);
                
                const jpegData = canvas.toDataURL('image/jpeg', 0.8);
                const sizeKB = (jpegData.length / 1024).toFixed(2);
                
                if (this.violationInProgress) {
                    this.violationInProgress.evidence = jpegData;
                    this.screenshotCount++;
                    console.log(`[SCREENSHOT] ✓ Fallback screenshot captured (${sizeKB} KB)`);
                }
                
                return jpegData;
            }
        } catch (e) {
            console.error('[SCREENSHOT] ✗ Error capturing screenshot:', e);
            return null;
        }
    }
    
    // ===== UPLOAD TO SERVER =====
    
    async uploadViolationToServer() {
        if (this.uploadInProgress) {
            console.log('[UPLOAD] Upload already in progress, skipping...');
            return;
        }
        
        if (!this.violationInProgress) {
            console.error('[UPLOAD] No violation in progress!');
            return;
        }
        
        this.uploadInProgress = true;
        const violation = this.violationInProgress;
        
        console.log('\n' + '='.repeat(80));
        console.log('[UPLOAD] UPLOADING VIOLATION TO SERVER');
        console.log('='.repeat(80));
        
        try {
            const payload = {
                participant_id: this.participantId,
                session_id: this.sessionId,
                violation_type: violation.type,
                description: violation.description,
                startTime: violation.startTime.toISOString(),
                evidence: violation.evidence || null
            };
            
            console.log('[UPLOAD] Payload prepared:');
            console.log(`   Participant ID: ${this.participantId}`);
            console.log(`   Session ID: ${this.sessionId}`);
            console.log(`   Violation Type: ${violation.type}`);
            console.log(`   Start Time: ${violation.startTime.toISOString()}`);
            console.log(`   Description: ${violation.description}`);
            console.log(`   Evidence: ${violation.evidence ? (violation.evidence.length / 1024).toFixed(2) + ' KB' : 'NO'}`);
            
            console.log('[UPLOAD] Sending POST request to /api/record-violation...');
            console.log('[UPLOAD] Endpoint: http://localhost:5000/api/record-violation');
            console.log('[UPLOAD] Method: POST');
            console.log('[UPLOAD] Content-Type: application/json');
            
            // Critical: Use timeout and explicit error handling
            const controller = new AbortController();
            const timeoutId = setTimeout(() => {
                controller.abort();
                console.error('[UPLOAD] ✗ Request timeout after 15 seconds');
            }, 15000);
            
            const response = await fetch('/api/record-violation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(payload),
                signal: controller.signal,
                credentials: 'same-origin'
            });
            
            clearTimeout(timeoutId);
            
            console.log(`[UPLOAD] Response received:`);
            console.log(`   Status: ${response.status} ${response.statusText}`);
            console.log(`   Headers:`, {
                'Content-Type': response.headers.get('content-type'),
                'Content-Length': response.headers.get('content-length')
            });
            
            if (!response.ok) {
                console.error(`[UPLOAD] ✗ HTTP error: ${response.status} ${response.statusText}`);
                const text = await response.text();
                console.error(`[UPLOAD] Response body: ${text.substring(0, 200)}`);
                
                if (this.violationInProgress) {
                    this.violationInProgress.uploadStatus = `failed_http_${response.status}`;
                }
                return;
            }
            
            let data;
            try {
                data = await response.json();
            } catch (e) {
                console.error('[UPLOAD] ✗ Error parsing JSON response:', e);
                console.log('[UPLOAD] Response text:', await response.text());
                
                if (this.violationInProgress) {
                    this.violationInProgress.uploadStatus = 'failed_json_parse';
                }
                return;
            }
            
            console.log('[UPLOAD] Response data:', data);
            
            if (data && data.status === 'success') {
                console.log('\n✅✅✅ VIOLATION UPLOADED SUCCESSFULLY ✅✅✅');
                console.log(`   Violation ID: ${data.violation_id}`);
                console.log(`   Message: ${data.message}`);
                console.log(`   Evidence URL: ${data.evidence_url || 'Not uploaded'}`);
                console.log('='.repeat(80) + '\n');
                
                if (this.violationInProgress) {
                    this.violationInProgress.uploadStatus = 'success';
                    this.violationInProgress.uploadedAt = new Date().toISOString();
                }
            } else {
                console.error('\n❌ SERVER RETURNED ERROR ❌');
                console.error(`   Status: ${data?.status}`);
                console.error(`   Message: ${data?.message || 'No message'}`);
                console.log('='.repeat(80) + '\n');
                
                if (this.violationInProgress) {
                    this.violationInProgress.uploadStatus = 'failed_server_error';
                }
            }
        } catch (error) {
            console.error('\n❌ UPLOAD FAILED ❌');
            console.error(`   Error type: ${error.name}`);
            console.error(`   Error message: ${error.message}`);
            if (error.stack) {
                console.error(`   Stack: ${error.stack}`);
            }
            console.log('='.repeat(80) + '\n');
            
            if (this.violationInProgress) {
                this.violationInProgress.uploadStatus = `failed_${error.name}`;
            }
        } finally {
            this.uploadInProgress = false;
        }
    }
    
    // ===== ALERT MODAL =====
    
    showAlert(message) {
        const alertId = 'exam_alert_' + Date.now();
        const lines = message.split('\n');
        
        const alertHtml = `
            <div id="${alertId}" class="exam-alert-overlay">
                <div class="exam-alert-box">
                    <div class="exam-alert-icon">⚠️</div>
                    <div class="exam-alert-content">
                        ${lines.map(line => `<p>${line}</p>`).join('')}
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
                    background: rgba(0, 0, 0, 0.7);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 99999;
                    font-family: Arial, sans-serif;
                }
                
                .exam-alert-box {
                    background: white;
                    border-radius: 12px;
                    padding: 30px;
                    max-width: 450px;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
                    text-align: center;
                    border-left: 6px solid #dc3545;
                    animation: slideIn 0.3s ease-out;
                }
                
                @keyframes slideIn {
                    from {
                        transform: translateY(-20px);
                        opacity: 0;
                    }
                    to {
                        transform: translateY(0);
                        opacity: 1;
                    }
                }
                
                .exam-alert-icon {
                    font-size: 40px;
                    margin-bottom: 15px;
                }
                
                .exam-alert-content {
                    margin-bottom: 25px;
                    color: #333;
                }
                
                .exam-alert-content p {
                    margin: 8px 0;
                    font-size: 15px;
                    line-height: 1.6;
                    font-weight: 400;
                }
                
                .exam-alert-content p:first-child {
                    font-weight: 600;
                    font-size: 16px;
                    color: #dc3545;
                }
                
                .exam-alert-btn {
                    background: #dc3545;
                    color: white;
                    border: none;
                    padding: 12px 35px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: 600;
                    font-size: 15px;
                    transition: all 0.2s;
                }
                
                .exam-alert-btn:hover {
                    background: #c82333;
                    transform: translateY(-2px);
                    box-shadow: 0 4px 12px rgba(220, 53, 69, 0.3);
                }
                
                .exam-alert-btn:active {
                    transform: translateY(0);
                }
            `;
            document.head.appendChild(style);
        }
        
        // Inject alert
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = alertHtml;
        document.body.appendChild(tempDiv.firstElementChild);
    }
    
    // ===== PUBLIC METHODS =====
    
    getViolationsSummary() {
        const summary = {
            totalViolations: this.violations.length,
            totalDurationSeconds: 0,
            pendingUploads: 0,
            violations: this.violations,
            violationTypes: {}
        };
        
        this.violations.forEach(v => {
            summary.totalDurationSeconds += v.durationSeconds || 0;
            summary.violationTypes[v.type] = (summary.violationTypes[v.type] || 0) + 1;
            if (v.uploadStatus !== 'success') {
                summary.pendingUploads++;
            }
        });
        
        return summary;
    }
    
    stopMonitoring() {
        console.log('\n[MONITOR] STOPPING EXAM PROCTORING MONITOR');
        this.isMonitoring = false;
        if (this.violationInProgress) {
            this.endCurrentViolation();
        }
    }
    
    endExamWithCode() {
        console.log('\n[EXAM] EXAM ENDED WITH CODE');
        this.isExamEnded = true;
        this.isMonitoring = false;
        this.saveExamState();
        
        if (this.violationInProgress) {
            this.endCurrentViolation();
        }
        
        console.log('[EXAM] Monitoring stopped');
    }
}

// Export to global scope
if (typeof window !== 'undefined') {
    window.ExamProctorMonitor = ExamProctorMonitor;
}

console.log('[MONITOR] ExamProctorMonitor class loaded and ready for instantiation');
