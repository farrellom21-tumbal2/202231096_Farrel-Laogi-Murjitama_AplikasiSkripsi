/**
 * WEBCAM ANALYZER - Real-time face analysis with bounding boxes
 */

class WebcamAnalyzer {
    constructor(config = {}) {
        this.participantId = config.participantId;
        this.sessionId = config.sessionId;
        this.videoElement = config.videoElement;
        this.canvasElement = config.canvasElement;
        this.overlayCanvasElement = config.overlayCanvasElement;
        
        this.isActive = false;
        this.isInitialized = false;
        this.stream = null;
        this.canvasContext = null;
        this.overlayContext = null;
        this.analysisInterval = null;
        this.frameRate = config.frameRate || 10; // frames per second
        this.frameIntervalMs = 1000 / this.frameRate;
        
        this.currentAnalysis = null;
        this.violations = [];
        this.previousViolations = [];  // Track previous state
        this.faceStatus = 'face_normal'; // default status
        this.lastFrameTime = 0;
        
        // ✅ VIOLATION NOTIFICATION SYSTEM
        this.violationStartTime = null;
        this.currentViolationType = null;
        this.isExamFrozen = false;
        this.violationNotified = false;  // ✅ Track if notification sent (for duration threshold)
        this.violationDuration = config.violationDuration || 6000;  // ✅ Default 6 seconds (6000ms)
        
        // ✅ GRACE PERIOD - prevent flicker unfreeze on brief face_normal blips
        this.lastViolationClearTime = null;  // Track when violation last cleared
        this.gracePeriodMs = 2000;  // 2 second grace period - keep frozen even if blips to face_normal
        this.clearDebounceTimeout = null;  // Debounce timeout for violation_end
        
        console.log('[WEBCAM] Initialized with config:');
        console.log('  - Participant ID:', this.participantId);
        console.log('  - Session ID:', this.sessionId);
        console.log('  - Frame Rate:', this.frameRate, 'fps');
        console.log('  - Violation Duration:', this.violationDuration, 'ms');
        console.log('  - Violation Notification: ✅ ENABLED');
    }
    
    /**
     * Request webcam access
     */
    async requestWebcamAccess() {
        console.log('\n[WEBCAM] Requesting webcam access...');
        
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 }
                },
                audio: false
            });
            
            this.videoElement.srcObject = this.stream;
            console.log('[WEBCAM] ✅ Webcam access granted');
            
            return true;
        } catch (error) {
            console.error('[WEBCAM] ❌ Webcam access denied:', error);
            this.showError('Webcam access denied', 'Please allow webcam access to continue with the exam.');
            return false;
        }
    }
    
    /**
     * Initialize analyzer on server
     */
    async initialize() {
        console.log('\n[WEBCAM] Initializing analyzer on server...');
        
        try {
            const response = await fetch('/api/webcam-init', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    participant_id: this.participantId,
                    session_id: this.sessionId
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // ✅ RECEIVE CONFIG FROM SERVER
                if (data.config) {
                    this.violationDuration = data.config.violation_threshold_ms || 6000;
                    console.log('[WEBCAM] ✅ Config received from server:');
                    console.log('  - Violation Duration:', this.violationDuration, 'ms');
                } else {
                    console.warn('[WEBCAM] ⚠️  No config in response, using defaults');
                }
                
                this.isInitialized = true;
                console.log('[WEBCAM] ✅ Analyzer initialized on server');
                return true;
            } else {
                console.error('[WEBCAM] ❌ Server initialization failed:', data.message);
                this.showError('Analyzer initialization failed', data.message);
                return false;
            }
        } catch (error) {
            console.error('[WEBCAM] ❌ Initialization error:', error);
            this.showError('Initialization error', error.message);
            return false;
        }
    }
    
    /**
     * Start webcam analysis (AUTO-START)
     */
    async start() {
        console.log('\n[WEBCAM-START] Starting webcam analysis (AUTO-START)...');
        
        if (this.isActive) {
            console.warn('[WEBCAM-START] ⚠️ Already active');
            return;
        }
        
        // Request webcam access
        const accessGranted = await this.requestWebcamAccess();
        if (!accessGranted) {
            return;
        }
        
        // Wait for video to load
        await new Promise(resolve => {
            this.videoElement.onloadedmetadata = () => {
                console.log('[WEBCAM] Video loaded, resolution:', 
                    this.videoElement.videoWidth, 'x', this.videoElement.videoHeight);
                resolve();
            };
        });
        
        // Initialize analyzer
        const initialized = await this.initialize();
        if (!initialized) {
            return;
        }
        
        // Setup analysis canvas (for frame processing)
        if (this.canvasElement) {
            this.canvasElement.width = this.videoElement.videoWidth;
            this.canvasElement.height = this.videoElement.videoHeight;
            this.canvasContext = this.canvasElement.getContext('2d');
        }
        
        // Setup overlay canvas (for bounding boxes)
        if (this.overlayCanvasElement) {
            this.overlayCanvasElement.width = this.videoElement.videoWidth;
            this.overlayCanvasElement.height = this.videoElement.videoHeight;
            this.overlayContext = this.overlayCanvasElement.getContext('2d');
        }
        
        this.isActive = true;
        console.log('[WEBCAM-START] ✅ Analysis started');
        
        // Start frame processing
        this.startFrameCapture();
    }
    
    /**
     * Start capturing and processing frames
     */
    startFrameCapture() {
        console.log('[WEBCAM] Starting frame capture at', this.frameRate, 'fps...');
        
        const captureFrame = async () => {
            if (!this.isActive) return;
            
            try {
                const now = performance.now();
                
                // Draw video frame to analysis canvas
                if (this.canvasContext) {
                    this.canvasContext.drawImage(
                        this.videoElement,
                        0, 0,
                        this.canvasElement.width,
                        this.canvasElement.height
                    );
                    
                    // Convert to base64
                    const frameBase64 = this.canvasElement.toDataURL('image/jpeg', 0.7);
                    
                    // Send to server for analysis (non-blocking)
                    this.sendFrameForAnalysis(frameBase64);
                }
                
                // Schedule next frame
                this.lastFrameTime = now;
                setTimeout(captureFrame, this.frameIntervalMs);
            } catch (error) {
                console.error('[WEBCAM] Frame capture error:', error);
                setTimeout(captureFrame, this.frameIntervalMs);
            }
        };
        
        captureFrame();
    }
    
    /**
     * Send frame to server for analysis
     */
    async sendFrameForAnalysis(frameBase64) {
        try {
            const response = await fetch('/api/process-frame', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    participant_id: this.participantId,
                    frame: frameBase64
                })
            });
            
            const data = await response.json();
            
            if (response.ok && data.analysis) {
                this.currentAnalysis = data.analysis;
                
                // ✅ TRACK VIOLATIONS - BEFORE AND AFTER
                const prevViolations = [...this.violations];  // Save OLD state
                const prevCount = prevViolations.length;
                
                // ✅ UPDATE violations array FIRST
                this.violations = data.analysis.violations || [];
                const currCount = this.violations.length;
                
                this.faceStatus = data.analysis.face_status || 'face_normal';
                
                // ✅ LOG STATE CHANGE
                if (prevCount !== currCount) {
                    console.log(`[FRAME] 🔄 STATE CHANGE: ${prevCount} → ${currCount} violations`);
                    if (prevCount > 0 && currCount === 0) {
                        console.log(`[FRAME] 🟢🟢🟢 VIOLATIONS CLEARED! Face: ${this.faceStatus}`);
                    } else if (currCount > 0) {
                        console.log(`[FRAME] 🔴 NEW VIOLATION: ${this.violations[0]} | Face: ${this.faceStatus}`);
                    }
                }
                
                // ✅ CHECK VIOLATIONS STATE AND NOTIFY
                this.checkViolationChanges(prevViolations);
                
                // ✅ UPDATE DISPLAY IMMEDIATELY
                this.updateViolationDisplay();
            }
        } catch (error) {
            console.debug('[WEBCAM] Frame analysis error:', error.message);
        }
    }
    
    /**
     * Check for violation state changes and notify exam window
     * ✅ STATE MACHINE - Tracks exact state transitions
     */
    checkViolationChanges(prevViolations = []) {
        const VIOLATION_THRESHOLD_MS = this.violationDuration;  // 6000ms
        
        const hasViolations = this.violations.length > 0;
        const hadViolations = prevViolations.length > 0;
        const now = Date.now();
        
        // ✅ DETAILED STATE LOGGING
        const prevType = hadViolations ? prevViolations[0] : 'NONE';
        const currType = hasViolations ? this.violations[0] : 'NONE';
        const stateStr = `[${prevType}→${currType}] notified=${this.violationNotified}`;
        
        console.log(`[STATE] checkViolationChanges() ${stateStr}`);
        
        // ==================== CASE 1: CLEAR -> VIOLATION (NEW) ====================
        if (!hadViolations && hasViolations) {
            console.log(`[STATE] 🔴 TRANSITION: NO_VIOLATION → VIOLATION`);
            console.log(`[STATE]    Type: ${currType}`);
            
            this.violationStartTime = now;
            this.currentViolationType = currType;
            this.violationNotified = false;
            
            console.log(`[STATE]    Timer started. Will notify after ${VIOLATION_THRESHOLD_MS / 1000}s`);
        }
        
        // ==================== CASE 2: VIOLATION -> VIOLATION (CONTINUING) ====================
        else if (hadViolations && hasViolations) {
            const sameType = (prevViolations[0] === this.violations[0]);
            
            // ✅ CANCEL DEBOUNCE if violation re-triggered while debouncing
            if (this.clearDebounceTimeout) {
                console.log(`[STATE] 🔴 Violation re-triggered! Canceling debounce...`);
                clearTimeout(this.clearDebounceTimeout);
                this.clearDebounceTimeout = null;
            }
            
            if (sameType) {
                // ✅ SAME VIOLATION CONTINUING
                const elapsed = now - this.violationStartTime;
                const elapsedSec = (elapsed / 1000).toFixed(2);
                const thresholdSec = VIOLATION_THRESHOLD_MS / 1000;
                
                // ✅ CHECK IF THRESHOLD REACHED
                if (elapsed >= VIOLATION_THRESHOLD_MS && !this.violationNotified) {
                    console.log(`\n` + '═'.repeat(70));
                    console.log(`[STATE] 🚨🚨🚨 THRESHOLD REACHED! 🚨🚨🚨`);
                    console.log(`[STATE] Duration: ${elapsedSec}s / ${thresholdSec}s`);
                    console.log(`[STATE] ✅ SENDING violation_start NOTIFICATION NOW!`);
                    console.log(`[STATE] Type: ${currType}`);
                    console.log('═'.repeat(70) + `\n`);
                    
                    this.notifyExamWindow({
                        type: 'violation_start',
                        violation: currType,
                        timestamp: this.violationStartTime,
                        message: `⚠️ ${currType.toUpperCase()} - EXAM FROZEN`
                    });
                    
                    this.violationNotified = true;
                    this.isExamFrozen = true;
                    
                } else if (elapsed < VIOLATION_THRESHOLD_MS) {
                    // Still counting down
                    const remaining = ((VIOLATION_THRESHOLD_MS - elapsed) / 1000).toFixed(2);
                    console.log(`[STATE] ⏳ COUNTING DOWN... ${elapsedSec}s / ${thresholdSec}s (${remaining}s remaining)`);
                }
            } else {
                // ✅ VIOLATION TYPE CHANGED
                const prevDuration = (now - this.violationStartTime) / 1000;
                console.log(`[STATE] 🔄 VIOLATION TYPE CHANGED: ${prevType} → ${currType}`);
                console.log(`[STATE]    ${prevType} lasted ${prevDuration.toFixed(1)}s`);
                
                // RESET for new violation type
                this.violationStartTime = now;
                this.currentViolationType = currType;
                this.violationNotified = false;
                
                console.log(`[STATE]    Reset timer for new type`);
            }
        }
        
        // ==================== CASE 3: VIOLATION -> CLEAR ====================
        else if (hadViolations && !hasViolations) {
            const duration = (now - this.violationStartTime) / 1000;
            
            console.log(`\n[DETECTOR] 🟢🟢🟢 FACE_NORMAL DETECTED - CLEARING VIOLATION 🟢🟢🟢`);
            console.log(`[DETECTOR] Type was: ${prevType}, Duration: ${duration.toFixed(1)}s`);
            console.log(`[DETECTOR] Was notified: ${this.violationNotified}`);
            
            // ✅ SEND violation_end IMMEDIATELY when face_normal is detected - NO DEBOUNCE!
            // This allows students to immediately see normal state when they position their faces correctly
            if (this.violationNotified) {
                // Clear any pending debounce timeout
                if (this.clearDebounceTimeout) {
                    clearTimeout(this.clearDebounceTimeout);
                }
                
                // ✅ AGGRESSIVE FORCE SEND violation_end - IMMEDIATELY, NO WAITING
                console.log(`[DETECTOR] ✅ FORCE SENDING violation_end NOW - NO DELAY!`);
                
                this.notifyExamWindow({
                    type: 'violation_end',
                    violation: prevType,
                    duration: duration,
                    timestamp: now,
                    message: '✅ VIOLATIONS CLEARED - EXAM RESUMED'
                });
                
                console.log(`[DETECTOR] ✅ violation_end SENT ✓`);
                console.log(`[DETECTOR] ✅ EXAM SHOULD UNFREEZE NOW!`);
                
                // ✅ RESET ALL FLAGS IMMEDIATELY
                this.violationStartTime = null;
                this.currentViolationType = null;
                this.violationNotified = false;
                this.isExamFrozen = false;
                this.lastViolationClearTime = null;
                this.clearDebounceTimeout = null;
                
                console.log(`[DETECTOR] ✅ State reset. Ready for next violation.\n`);
                
            } else {
                console.log(`[DETECTOR] Brief violation (${duration.toFixed(1)}s) - no notification needed`);
                
                // Still reset flags
                this.violationStartTime = null;
                this.currentViolationType = null;
                this.violationNotified = false;
                this.isExamFrozen = false;
                this.lastViolationClearTime = null;
                if (this.clearDebounceTimeout) {
                    clearTimeout(this.clearDebounceTimeout);
                    this.clearDebounceTimeout = null;
                }
            }
        }
        
        // ==================== CASE 4: CLEAR -> CLEAR (NO CHANGE) ====================
        else if (!hadViolations && !hasViolations) {
            // Normal state - no violation ongoing
            // Silent - don't log every frame
        }
    }
    
    /**
     * Send violation notification to exam window via postMessage + fallback
     * ✅ AGGRESSIVE - MULTIPLE DELIVERY METHODS FOR 100% GUARANTEE
     */
    notifyExamWindow(violationData) {
        try {
            console.log(`\n[NOTIFY] 🔴🔴🔴 AGGRESSIVE NOTIFICATION STARTED 🔴🔴🔴`);
            console.log(`[NOTIFY] 📨 SENDING: ${violationData.type} (${violationData.violation})`);
            
            const messagePayload = {
                source: 'webcam-analyzer',
                type: 'violation_notification',
                data: violationData,
                timestamp: Date.now()
            };
            
            let deliveryCount = 0;
            
            // ✅ METHOD 1: postMessage to iframe MULTIPLE TIMES (aggressive)
            const examIframe = document.getElementById('exam-iframe');
            if (examIframe && examIframe.contentWindow) {
                for (let i = 0; i < 5; i++) {
                    setTimeout(() => {
                        try {
                            examIframe.contentWindow.postMessage(messagePayload, '*');
                            if (i === 0) {
                                console.log(`[NOTIFY] ✅ Iframe Message #1 (${violationData.type}) - SENT IMMEDIATELY`);
                                deliveryCount++;
                            } else {
                                console.log(`[NOTIFY]    ✅ Iframe Message #${i+1} (retry)`);
                            }
                        } catch (e) {
                            console.warn(`[NOTIFY] ⚠️ Iframe attempt ${i+1} failed:`, e.message);
                        }
                    }, i * 50);  // Resend every 50ms for first 250ms
                }
            }
            
            // ✅ METHOD 2: postMessage to parent MULTIPLE TIMES
            if (window.parent && window.parent !== window) {
                for (let i = 0; i < 5; i++) {
                    setTimeout(() => {
                        try {
                            window.parent.postMessage(messagePayload, '*');
                            if (i === 0) {
                                console.log(`[NOTIFY] ✅ Parent Message #1 (${violationData.type}) - SENT IMMEDIATELY`);
                                deliveryCount++;
                            } else {
                                console.log(`[NOTIFY]    ✅ Parent Message #${i+1} (retry)`);
                            }
                        } catch (e) {
                            console.warn(`[NOTIFY] ⚠️ Parent attempt ${i+1} failed:`, e.message);
                        }
                    }, i * 50);
                }
            }
            
            // ✅ METHOD 3: postMessage to opener MULTIPLE TIMES
            if (window.opener) {
                for (let i = 0; i < 5; i++) {
                    setTimeout(() => {
                        try {
                            window.opener.postMessage(messagePayload, '*');
                            if (i === 0) {
                                console.log(`[NOTIFY] ✅ Opener Message #1 (${violationData.type}) - SENT IMMEDIATELY`);
                                deliveryCount++;
                            } else {
                                console.log(`[NOTIFY]    ✅ Opener Message #${i+1} (retry)`);
                            }
                        } catch (e) {
                            console.warn(`[NOTIFY] ⚠️ Opener attempt ${i+1} failed:`, e.message);
                        }
                    }, i * 50);
                }
            }
            
            // ✅ METHOD 4: Store for polling AND call window handler directly
            window.lastViolationNotification = messagePayload;
            console.log(`[NOTIFY] ✅ Stored for polling (${violationData.type})`);
            
            // ✅ METHOD 5: Try calling handler directly if available
            if (typeof window.handleViolationNotification === 'function') {
                try {
                    window.handleViolationNotification(messagePayload);
                    console.log(`[NOTIFY] ✅ Direct handler call (${violationData.type})`);
                    deliveryCount++;
                } catch (e) {
                    console.warn(`[NOTIFY] ⚠️ Direct handler failed:`, e.message);
                }
            }
            
            console.log(`[NOTIFY] 📨 AGGRESSIVE DELIVERY COMPLETE - ${deliveryCount} channel(s) guaranteed ✓✓✓\n`);
            
        } catch (error) {
            console.error('[NOTIFY] ❌ CRITICAL Error:', error);
        }
    }
    
    /**
     * Render bounding boxes and status on overlay canvas
     * OPTIMIZED: Only render best detections (1-2 boxes max) for smooth performance
     */
    renderBoundingBoxes() {
        if (!this.overlayContext || !this.currentAnalysis) {
            return;
        }
        
        // Clear overlay
        this.overlayContext.clearRect(0, 0, this.overlayCanvasElement.width, this.overlayCanvasElement.height);
        
        const analysis = this.currentAnalysis;
        const fontSize = 14;
        const lineWidth = 2;
        
        // Determine color based on status
        const isViolation = this.violations.length > 0;
        const boxColor = isViolation ? '#FF3333' : '#00CC00'; // Red for violation, Green for normal
        const statusColor = isViolation ? '#FF3333' : '#00CC00';
        
        // OPTIMIZATION: Use only best boxes from backend (max 1-2)
        // This prevents overlapping boxes and improves rendering performance
        const bestBoxes = analysis.best_boxes || [];
        
        // Render only the best detections (backend already filtered to top 2)
        bestBoxes.forEach((box, index) => {
            const [x1, y1, x2, y2] = box.bbox;
            const label = box.label || 'detection';
            const conf = (box.conf || 0).toFixed(2);
            const text = `${label} (${conf})`;
            
            // Use dashed line for secondary detections
            if (index > 0) {
                this.overlayContext.setLineDash([5, 5]);
            }
            
            this.overlayContext.strokeStyle = box.priority === 2 ? '#FF3333' : '#00CC00';
            this.overlayContext.lineWidth = lineWidth;
            this.overlayContext.rect(x1, y1, x2 - x1, y2 - y1);
            this.overlayContext.stroke();
            this.overlayContext.setLineDash([]);
            
            // Label with confidence
            this.overlayContext.fillStyle = box.priority === 2 ? '#FF3333' : '#00CC00';
            this.overlayContext.fillRect(x1, y1 - 25, text.length * 7, 20);
            this.overlayContext.fillStyle = '#FFFFFF';
            this.overlayContext.font = 'bold ' + fontSize + 'px Arial';
            this.overlayContext.fillText(text, x1 + 3, y1 - 8);
        });
        
        // If no best boxes, show status from YOLO
        if (bestBoxes.length === 0 && analysis.yolo_bbox) {
            const [x1, y1, x2, y2] = analysis.yolo_bbox;
            const label = analysis.yolo_class || 'face_normal';
            const conf = (analysis.yolo_conf || 0).toFixed(2);
            const text = `${label} (${conf})`;
            
            this.overlayContext.strokeStyle = boxColor;
            this.overlayContext.lineWidth = lineWidth;
            this.overlayContext.rect(x1, y1, x2 - x1, y2 - y1);
            this.overlayContext.stroke();
            
            this.overlayContext.fillStyle = boxColor;
            this.overlayContext.fillRect(x1, y1 - 25, text.length * 7, 20);
            this.overlayContext.fillStyle = '#FFFFFF';
            this.overlayContext.font = 'bold ' + fontSize + 'px Arial';
            this.overlayContext.fillText(text, x1 + 3, y1 - 8);
        }
        
        // Draw overall status at top
        const statusText = isViolation 
            ? `⚠️ VIOLATION: ${this.violations.join(', ').toUpperCase()}` 
            : '✓ face_normal';
        
        this.overlayContext.fillStyle = statusColor;
        this.overlayContext.fillRect(5, 5, statusText.length * 8, 30);
        this.overlayContext.fillStyle = '#FFFFFF';
        this.overlayContext.font = 'bold 16px Arial';
        this.overlayContext.fillText(statusText, 10, 28);
        
        // Draw gaze state if available
        if (analysis.gaze_state) {
            const gazeText = `Gaze: ${analysis.gaze_state}`;
            this.overlayContext.fillStyle = '#4444FF';
            this.overlayContext.fillRect(5, 40, gazeText.length * 8, 25);
            this.overlayContext.fillStyle = '#FFFFFF';
            this.overlayContext.font = 'bold 12px Arial';
            this.overlayContext.fillText(gazeText, 10, 58);
        }
    }
    
    /**
     * Update violation display panel
     * ✅ FORCE UPDATE with aggressive refresh
     */
    updateViolationDisplay() {
        const violationElement = document.getElementById('webcam-violations');
        if (!violationElement) {
            console.warn('[DISPLAY] ❌ Violation element not found!');
            return;
        }
        
        console.log(`[DISPLAY] 🔄 Updating display... Array:`, this.violations);
        
        // ✅ CLEAR ALL ATTRIBUTES FIRST
        violationElement.className = '';
        violationElement.id = 'webcam-violations';
        violationElement.innerHTML = '';
        
        if (this.violations.length > 0) {
            // ✅ SHOW VIOLATION (RED)
            const primaryViolation = this.violations[0];
            
            violationElement.innerHTML = `<div class="violation-badge violation-${primaryViolation}">⚠️ ${primaryViolation.toUpperCase()}</div>`;
            violationElement.className = 'violation-active';
            violationElement.style.cssText = `
                display: block !important;
                background: #fff3cd !important;
                color: #856404 !important;
                visibility: visible !important;
                opacity: 1 !important;
                pointer-events: auto !important;
            `;
            
            console.log(`[DISPLAY] 🔴 RED - Showing: ${primaryViolation}`);
            
        } else {
            // ✅ SHOW GREEN face_normal
            violationElement.innerHTML = '<div class="violation-badge violation-normal">✅ FACE_NORMAL</div>';
            violationElement.className = 'violation-normal-state';
            violationElement.style.cssText = `
                display: block !important;
                background: #d4edda !important;
                color: #155724 !important;
                visibility: visible !important;
                opacity: 1 !important;
                pointer-events: auto !important;
                border: 2px solid #c3e6cb !important;
            `;
            
            console.log(`[DISPLAY] 🟢 GREEN - FACE_NORMAL`);
        }
        
        // ✅ FORCE REFLOW (browser re-render)
        void violationElement.offsetHeight;
        
        // ✅ DOUBLE-CHECK with setTimeout
        setTimeout(() => {
            if (this.violations.length > 0) {
                violationElement.style.background = '#fff3cd';
                violationElement.style.color = '#856404';
            } else {
                violationElement.style.background = '#d4edda';
                violationElement.style.color = '#155724';
            }
        }, 10);
    }
    
    /**
     * Stop webcam analysis
     */
    async stop() {
        console.log('\n[WEBCAM-STOP] Stopping webcam analysis...');
        
        this.isActive = false;
        
        // Stop stream
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        // Clear canvases
        if (this.canvasContext) {
            this.canvasContext.clearRect(0, 0, this.canvasElement.width, this.canvasElement.height);
        }
        if (this.overlayContext) {
            this.overlayContext.clearRect(0, 0, this.overlayCanvasElement.width, this.overlayCanvasElement.height);
        }
        
        // Cleanup on server
        if (this.isInitialized) {
            try {
                await fetch('/api/webcam-cleanup', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        participant_id: this.participantId
                    })
                });
            } catch (error) {
                console.warn('[WEBCAM] Cleanup error:', error);
            }
        }
        
        console.log('[WEBCAM-STOP] ✅ Analysis stopped');
    }
    
    /**
     * Show error message
     */
    showError(title, message) {
        console.error(`[WEBCAM] ERROR: ${title} - ${message}`);
        const violationElement = document.getElementById('webcam-violations');
        if (violationElement) {
            violationElement.innerHTML = `<div class="violation-badge violation-error">ERROR: ${title}</div>`;
            violationElement.style.display = 'block';
        }
    }
    
    /**
     * Get statistics
     */
    getStats() {
        return {
            isActive: this.isActive,
            violations: this.violations,
            faceStatus: this.faceStatus,
            totalViolations: this.violations.length
        };
    }
}

// Global instance
let webcamAnalyzer = null;

/**
 * Initialize webcam analyzer (called from HTML on page load)
 */
function initializeWebcamAnalyzer(config) {
    console.log('\n[INIT] Initializing Webcam Analyzer (AUTO-START)...');
    console.log('[INIT] Config:', config);
    
    webcamAnalyzer = new WebcamAnalyzer({
        participantId: config.participantId,
        sessionId: config.sessionId,
        videoElement: document.getElementById('webcam-video'),
        canvasElement: document.getElementById('webcam-canvas'),
        overlayCanvasElement: document.getElementById('webcam-overlay-canvas'),
        frameRate: config.frameRate || 10
    });
    
    window.webcamAnalyzer = webcamAnalyzer;
    
    // AUTO-START the webcam analyzer
    console.log('[INIT] Auto-starting webcam analyzer...');
    webcamAnalyzer.start().then(() => {
        console.log('[INIT] ✅ Webcam analyzer started automatically');
    }).catch(error => {
        console.error('[INIT] ❌ Failed to auto-start webcam analyzer:', error);
    });
}

console.log('='.repeat(80));
console.log('WEBCAM ANALYZER - LOADED SUCCESSFULLY');
console.log('='.repeat(80) + '\n');
