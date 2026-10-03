/**
 * Cyber Incident Reporting Portal — Main JavaScript
 * Client-side validation, UI interactions, notification polling.
 */

document.addEventListener('DOMContentLoaded', function () {
    initSidebar();
    initFlashMessages();
    initNotifications();
    initFileUpload();
    initFormValidation();
    initConfirmDialogs();
    initSearchFilters();
});


/* ── Sidebar Toggle (Mobile) ─────────────────────────────── */
function initSidebar() {
    const toggle = document.getElementById('sidebarToggle');
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');

    if (toggle && sidebar) {
        toggle.addEventListener('click', function () {
            sidebar.classList.toggle('open');
            if (overlay) overlay.classList.toggle('show');
        });
    }

    if (overlay) {
        overlay.addEventListener('click', function () {
            sidebar.classList.remove('open');
            overlay.classList.remove('show');
        });
    }
}


/* ── Flash Messages Auto-Dismiss ─────────────────────────── */
function initFlashMessages() {
    const flashes = document.querySelectorAll('.flash-msg');
    flashes.forEach(function (el) {
        // Click to dismiss immediately
        el.addEventListener('click', function () {
            el.style.animation = 'flashFadeOut 0.3s ease forwards';
            setTimeout(() => el.remove(), 300);
        });

        // Auto-remove after animation ends (~4.5s)
        setTimeout(() => {
            if (el.parentNode) el.remove();
        }, 5000);
    });
}


/* ── Notifications ───────────────────────────────────────── */
function initNotifications() {
    const bell = document.getElementById('notifBell');
    const dropdown = document.getElementById('notifDropdown');

    if (bell && dropdown) {
        bell.addEventListener('click', function (e) {
            e.stopPropagation();
            dropdown.classList.toggle('show');
        });

        document.addEventListener('click', function (e) {
            if (!dropdown.contains(e.target) && e.target !== bell) {
                dropdown.classList.remove('show');
            }
        });
    }

    // Mark all as read
    const markAllBtn = document.getElementById('markAllRead');
    if (markAllBtn) {
        markAllBtn.addEventListener('click', function (e) {
            e.preventDefault();
            fetch('/notifications/mark-all-read', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCSRFToken(),
                    'Content-Type': 'application/json'
                }
            }).then(resp => {
                if (resp.ok) {
                    document.querySelectorAll('.notif-item.unread').forEach(el => {
                        el.classList.remove('unread');
                    });
                    const badge = document.querySelector('.notification-badge');
                    if (badge) badge.style.display = 'none';
                }
            });
        });
    }

    // Poll for new notifications every 30 seconds
    setInterval(pollNotifications, 30000);
}

function pollNotifications() {
    fetch('/notifications/count')
        .then(resp => resp.json())
        .then(data => {
            const badge = document.querySelector('.notification-badge');
            if (badge) {
                if (data.count > 0) {
                    badge.textContent = data.count;
                    badge.style.display = 'flex';
                } else {
                    badge.style.display = 'none';
                }
            }
        })
        .catch(() => {});
}


/* ── File Upload (Drag & Drop + Preview) ─────────────────── */
function initFileUpload() {
    const uploadZone = document.querySelector('.upload-zone');
    const fileInput = document.getElementById('evidenceFiles');
    const previewContainer = document.querySelector('.file-preview');

    if (!uploadZone || !fileInput) return;

    uploadZone.addEventListener('click', () => fileInput.click());

    uploadZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', function () {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', function (e) {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        fileInput.files = e.dataTransfer.files;
        showFilePreview(fileInput.files, previewContainer);
    });

    fileInput.addEventListener('change', function () {
        showFilePreview(this.files, previewContainer);
    });
}

function showFilePreview(files, container) {
    if (!container) return;
    container.innerHTML = '';

    const allowedExts = ['png','jpg','jpeg','gif','bmp','webp',
                         'pdf','doc','docx','txt','csv','xlsx',
                         'mp4','avi','mkv','mov','webm'];
    const maxSize = 16 * 1024 * 1024; // 16 MB

    Array.from(files).forEach(function (file) {
        const ext = file.name.split('.').pop().toLowerCase();
        let icon = 'bi-file-earmark';
        if (['png','jpg','jpeg','gif','bmp','webp'].includes(ext)) icon = 'bi-file-image';
        else if (['pdf'].includes(ext)) icon = 'bi-file-pdf';
        else if (['doc','docx'].includes(ext)) icon = 'bi-file-word';
        else if (['mp4','avi','mkv','mov','webm'].includes(ext)) icon = 'bi-file-play';

        let sizeStr = formatFileSize(file.size);
        let error = '';
        if (!allowedExts.includes(ext)) error = ' (Invalid type!)';
        if (file.size > maxSize) error = ' (Too large!)';

        const item = document.createElement('div');
        item.className = 'file-preview-item';
        item.innerHTML = `
            <i class="bi ${icon}" style="font-size:1.3rem;color:var(--accent-primary)"></i>
            <span>${file.name} <small class="text-cyber-muted">(${sizeStr})</small>
                  ${error ? '<span style="color:var(--danger)">' + error + '</span>' : ''}</span>
        `;
        container.appendChild(item);
    });
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}


/* ── Client-Side Form Validation ─────────────────────────── */
function initFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();

                // Scroll to the first invalid field so the user can see what's wrong
                const firstInvalid = form.querySelector(':invalid');
                if (firstInvalid) {
                    firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstInvalid.focus();
                }
            }
            form.classList.add('was-validated');
        });
    });

    // Password confirmation
    const confirmPwd = document.getElementById('confirmPassword');
    const password = document.getElementById('password');
    if (confirmPwd && password) {
        confirmPwd.addEventListener('input', function () {
            if (this.value !== password.value) {
                this.setCustomValidity('Passwords do not match');
            } else {
                this.setCustomValidity('');
            }
        });
    }

    // Password strength indicator
    if (password) {
        const strengthBar = document.getElementById('passwordStrength');
        if (strengthBar) {
            password.addEventListener('input', function () {
                const val = this.value;
                let strength = 0;
                if (val.length >= 8) strength++;
                if (/[A-Z]/.test(val)) strength++;
                if (/[0-9]/.test(val)) strength++;
                if (/[^A-Za-z0-9]/.test(val)) strength++;

                const colors = ['#ff5252', '#ff5252', '#ffab40', '#00e676', '#00e676'];
                const widths = ['0%', '25%', '50%', '75%', '100%'];
                strengthBar.style.width = widths[strength];
                strengthBar.style.background = colors[strength];
            });
        }
    }
}


/* ── Confirm Dialogs ─────────────────────────────────────── */
function initConfirmDialogs() {
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            if (!confirm(el.getAttribute('data-confirm'))) {
                e.preventDefault();
            }
        });
    });
}


/* ── Search & Filter Auto-Submit ─────────────────────────── */
function initSearchFilters() {
    const filterSelects = document.querySelectorAll('.auto-filter');
    filterSelects.forEach(function (sel) {
        sel.addEventListener('change', function () {
            this.closest('form').submit();
        });
    });
}


/* ── CSRF Token Helper ───────────────────────────────────── */
function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}
