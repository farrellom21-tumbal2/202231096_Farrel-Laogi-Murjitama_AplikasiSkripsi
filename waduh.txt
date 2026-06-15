#!/usr/bin/env python3
"""
FULL TESTING GUIDE - Violation Detection System
Gunakan ini untuk debugging system
"""

print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                    VIOLATION DETECTION SYSTEM - FULL TEST                   ║
╚════════════════════════════════════════════════════════════════════════════╝

STEP 1: Periksa Backend
═══════════════════════════════════════════════════════════════════════════════

Periksa apakah Flask server running:
  • Buka PowerShell baru
  • Jalankan: python app.py
  • Server harus start di http://localhost:5000

STEP 2: Test API Langsung  
═══════════════════════════════════════════════════════════════════════════════

Gunakan test_violations_simple.py untuk test API:
  • Buka PowerShell baru di folder project
  • Jalankan: python test_violations_simple.py
  • Ini akan:
    1. POST violation tanpa evidence
    2. POST violation dengan fake evidence
    3. Cek apakah data masuk database

Perhatikan output console:
  ✓ Jika [OK] muncul di Flask console = data diterima dan processed
  ✓ Jika [DB] muncul = data insert ke database
  ✓ Jika ✅ muncul = transaction successful

STEP 3: Test Browser Manual
═══════════════════════════════════════════════════════════════════════════════

1. Login ke participant dashboard
2. Klik "Mulai Ujian" 
3. Tunggu proctored-exam page terbuka di tab baru
4. Di tab exam:
   • Buka Browser Console (F12) untuk lihat debug logs
   • Coba trigger violations:
     - Tab switch: Alt+Tab (keluar dari browser tab)
     - Window blur: Click ke window lain
     - Back button: Tekan Back atau Alt+Left arrow
     - Minimize: Windows key + D atau minimize window

5. Di Flask console, perhatikan output:
   ✓ "VIOLATION DETECTED IN WRAPPER:" = wrapper page detected violation
   ✓ "[POST] RECORD-VIOLATION ENDPOINT CALLED" = API endpoint hit
   ✓ "[DATA]" = data diterima dari client
   ✓ "[IMG]" = screenshot upload attempt
   ✓ "[DB] INSERTING INTO VIOLATIONS TABLE" = database insert
   ✓ "TRANSACTION COMMITTED" = berhasil

6. Setelah submit exam_end_code, check database:
   • SELECT * FROM violations WHERE participant_id = 2 ORDER BY id DESC;
   • Harus ada violations dengan violation_type: TAB_SWITCH, WINDOW_BLUR, BACK_BUTTON

STEP 4: Logout Button Issue - Debug
═══════════════════════════════════════════════════════════════════════════════

Jika logout button tidak enable setelah submit code:

1. Browser console check:
   • Buka F12 → Console
   • Cek apakah ada JavaScript errors
   • Setelah submit code, periksa "[LOGOUT] Button enabled" message

2. Network tab check:
   • F12 → Network
   • Submit exam end code
   • Cari POST /api/end-exam request
   • Periksa response status dan body
   • Response harus: {"status": "success", ...}

3. Flask console check:
   • Cari POST /api/end-exam endpoint call
   • Check apakah exam_end_code match dengan expected code

TROUBLESHOOTING
═══════════════════════════════════════════════════════════════════════════════

Problem: Violations tidak muncul di database
├─ Check: Flask console ada [DB] INSERTING message?
│  └─ NO: Ada error di screenshot upload atau database connection
│  └─ YES: Check database violations table
├─ Check: Database violations table empty?
│  └─ Run: SELECT COUNT(*) FROM violations;
│  └─ Pastikan participant_id = 2 ada di participants table

Problem: Logout button tidak responsive
├─ Check: exam_end_code input tidak accept value?
│  └─ Click input, type code, perhatikan value update
├─ Check: Submit button click tidak trigger?
│  └─ F12 Console → Network → POST /api/end-exam
│  └─ Lihat response apakah status: 'success'
├─ Check: Response ok tapi button tidak enable?
│  └─ JavaScript error di console
│  └─ Run di console: document.getElementById('logout-btn').disabled = false

Problem: Wrapper page tidak load exam
├─ Check: proctored-exam.html ada?
│  └─ File browser: templates/proctored-exam.html
├─ Check: Flask console ada GET /proctored-exam?
│  └─ Jika ada, page loading
│  └─ Jika tidak, route tidak hit (check participant_dashboard onclick)
├─ Check: Exam iframe src kosong?
│  └─ F12 → Elements → <iframe> → check src attribute
│  └─ Harus ada URL dari request parameters

EXPECTED BEHAVIOR
═══════════════════════════════════════════════════════════════════════════════

NORMAL FLOW:
┌─────────────┐
│  Dashboard  │
└──────┬──────┘
       │ Click "Mulai Ujian"
       │ → Call startExamMonitoring()
       │ → Open /proctored-exam window
       ↓
┌──────────────────┐
│  Proctored Page  │ (wrapper dengan monitoring)
│  ┌────────────┐  │
│  │   Exam     │  │ (Google Forms atau test-exam)
│  │  in iFrame │  │
│  └────────────┘  │
└────┬─────────────┘
     │ Perform violation
     │ → recordViolation() called
     │ → Screenshot captured (html2canvas)
     │ → POST /api/record-violation
     ↓
┌──────────────────┐
│  Flask Backend   │
│ record_violation │
└────┬─────────────┘
     │ Validate & Process
     │ → Upload screenshot to Cloudinary
     │ → Insert to violations table
     │ → Insert to violation_evidence table
     ↓
┌──────────────────┐
│  MySQL Database  │
│  violations ✓    │
│  violation_      │
│  evidence ✓      │
└──────────────────┘

TESTING CHECKLIST
═══════════════════════════════════════════════════════════════════════════════

□ Flask server running (python app.py)
□ MySQL database connected (check .env)
□ Cloudinary credentials configured (check .env)
□ Test API with test_violations_simple.py PASSED
□ Browser login successful
□ Click "Mulai Ujian" opens new tab
□ Proctored page header visible with monitoring status
□ Perform TAB_SWITCH violation → counter increments
□ Perform WINDOW_BLUR violation → counter increments  
□ Perform BACK_BUTTON violation → counter increments
□ Check database: violations table has records
□ Submit exam end code successfully
□ Logout button becomes enabled
□ Click logout works

═══════════════════════════════════════════════════════════════════════════════
QUICK DEBUG COMMANDS
═══════════════════════════════════════════════════════════════════════════════

# Check database violations
mysql> SELECT * FROM violations WHERE participant_id = 2 ORDER BY id DESC LIMIT 5;

# Check violation evidence
mysql> SELECT v.id, v.violation_type, ve.image_url 
       FROM violations v 
       LEFT JOIN violation_evidence ve ON v.id = ve.violation_id
       WHERE v.participant_id = 2;

# Clear test violations
mysql> DELETE FROM violations WHERE participant_id = 2 AND start_time > DATE_SUB(NOW(), INTERVAL 1 HOUR);

# Check exam session data
mysql> SELECT * FROM sessions WHERE id = 2;
mysql> SELECT * FROM participants WHERE id = 2;

═══════════════════════════════════════════════════════════════════════════════
""")
