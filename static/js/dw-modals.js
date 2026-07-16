/**
 * DynamicWorkspace — modales de mensajes y confirmación.
 * - Cola de mensajes flash (django.contrib.messages)
 * - dwConfirmWarning() sustituye confirm() nativo
 * - Escape cierra modales; foco al abrir/cerrar
 */
(function () {
    'use strict';

    const msgModal = document.getElementById('dw-msg-modal');
    const msgTitle = document.getElementById('dw-msg-title');
    const msgBody = document.getElementById('dw-msg-body');
    const msgHeader = document.getElementById('dw-msg-header');
    const msgBtn = document.getElementById('dw-msg-btn');
    const msgClose = document.getElementById('dw-msg-close');

    const confirmModal = document.getElementById('dw-confirm-modal');
    const confirmBody = document.getElementById('dw-confirm-body');
    const confirmTitle = document.getElementById('dw-confirm-title');
    const confirmOk = document.getElementById('dw-confirm-ok');
    const confirmCancel = document.getElementById('dw-confirm-cancel');
    const confirmClose = document.getElementById('dw-confirm-close');

    let messageQueue = [];
    let pendingConfirm = null;
    let focusBeforeModal = null;

    const MSG_VARIANTS = {
        error: {
            title: 'Error',
            headerClass: 'dw-modal-header dw-modal-header--error',
            btnClass: 'btn btn-danger',
            btnLabel: 'Aceptar',
        },
        success: {
            title: 'Operación exitosa',
            headerClass: 'dw-modal-header dw-modal-header--success',
            btnClass: 'btn btn-primary',
            btnLabel: 'Aceptar',
        },
        warning: {
            title: 'Advertencia',
            headerClass: 'dw-modal-header dw-modal-header--warning',
            btnClass: 'btn btn-secondary',
            btnLabel: 'Entendido',
        },
        info: {
            title: 'Información',
            headerClass: 'dw-modal-header dw-modal-header--info',
            btnClass: 'btn btn-primary',
            btnLabel: 'Aceptar',
        },
        default: {
            title: 'Mensaje',
            headerClass: 'dw-modal-header',
            btnClass: 'btn btn-primary',
            btnLabel: 'Aceptar',
        },
    };

    function resolveVariant(tags) {
        const t = String(tags || '').toLowerCase();
        if (t.includes('error')) return MSG_VARIANTS.error;
        if (t.includes('success')) return MSG_VARIANTS.success;
        if (t.includes('warning')) return MSG_VARIANTS.warning;
        if (t.includes('info')) return MSG_VARIANTS.info;
        return MSG_VARIANTS.default;
    }

    function lockBody() {
        document.body.classList.add('dw-modal-open');
    }

    function unlockBodyIfNoModal() {
        const msgOpen = msgModal && !msgModal.hidden;
        const confirmOpen = confirmModal && !confirmModal.hidden;
        if (!msgOpen && !confirmOpen) {
            document.body.classList.remove('dw-modal-open');
            if (focusBeforeModal && typeof focusBeforeModal.focus === 'function') {
                focusBeforeModal.focus();
            }
            focusBeforeModal = null;
        }
    }

    function openOverlay(modalEl, focusEl) {
        if (!modalEl) return;
        if (!focusBeforeModal) {
            focusBeforeModal = document.activeElement;
        }
        modalEl.hidden = false;
        lockBody();
        if (focusEl && typeof focusEl.focus === 'function') {
            focusEl.focus();
        }
    }

    function closeOverlay(modalEl) {
        if (!modalEl) return;
        modalEl.hidden = true;
        unlockBodyIfNoModal();
    }

    function showMessage(tags, text) {
        if (!msgModal || !msgBody || !msgTitle || !msgHeader || !msgBtn) return;

        const variant = resolveVariant(tags);
        msgTitle.textContent = variant.title;
        msgBody.textContent = text || '';
        msgHeader.className = variant.headerClass;
        msgBtn.className = variant.btnClass;
        msgBtn.textContent = variant.btnLabel;

        openOverlay(msgModal, msgBtn);
    }

    function enqueueMessage(tags, text) {
        messageQueue.push({ tags, text });
        if (msgModal && msgModal.hidden) {
            showNextMessage();
        }
    }

    function showNextMessage() {
        if (!messageQueue.length) return;
        const next = messageQueue.shift();
        showMessage(next.tags, next.text);
    }

    function hideMessageModal() {
        closeOverlay(msgModal);
        if (messageQueue.length) {
            window.setTimeout(showNextMessage, 120);
        }
    }

    function hideConfirmModal() {
        closeOverlay(confirmModal);
        pendingConfirm = null;
    }

    window.dwShowMessage = function (tags, text) {
        enqueueMessage(tags, text);
    };

    /**
     * Modal de confirmación (p. ej. eliminar registro).
     * @param {string} message
     * @param {function} onConfirm
     * @param {{ title?: string, okLabel?: string }} [options]
     */
    window.dwConfirmWarning = function (message, onConfirm, options) {
        if (!confirmModal || !confirmBody) return;

        const opts = options || {};
        pendingConfirm = typeof onConfirm === 'function' ? onConfirm : null;
        confirmBody.textContent = message || '';
        if (confirmTitle) {
            confirmTitle.textContent = opts.title || 'Advertencia';
        }
        if (confirmOk) {
            confirmOk.textContent = opts.okLabel || 'Confirmar';
        }

        openOverlay(confirmModal, confirmOk || confirmCancel);
    };

    function runConfirmAndClose() {
        const fn = pendingConfirm;
        hideConfirmModal();
        if (fn) fn();
    }

    if (msgBtn) msgBtn.addEventListener('click', hideMessageModal);
    if (msgClose) msgClose.addEventListener('click', hideMessageModal);
    if (msgModal) {
        msgModal.addEventListener('click', function (e) {
            if (e.target === msgModal) hideMessageModal();
        });
    }

    if (confirmOk) confirmOk.addEventListener('click', runConfirmAndClose);
    if (confirmCancel) confirmCancel.addEventListener('click', hideConfirmModal);
    if (confirmClose) confirmClose.addEventListener('click', hideConfirmModal);
    if (confirmModal) {
        confirmModal.addEventListener('click', function (e) {
            if (e.target === confirmModal) hideConfirmModal();
        });
    }

    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        if (confirmModal && !confirmModal.hidden) {
            hideConfirmModal();
            return;
        }
        if (msgModal && !msgModal.hidden) {
            hideMessageModal();
        }
    });

    function loadFlashMessages() {
        const el = document.getElementById('dw-flash-messages');
        if (!el) return;
        try {
            const items = JSON.parse(el.textContent);
            if (!Array.isArray(items)) return;
            items.forEach(function (item) {
                enqueueMessage(item.level || item.tags || 'info', item.text || item.message || '');
            });
        } catch (_err) {
            /* JSON inválido — ignorar */
        }
    }

    document.addEventListener('DOMContentLoaded', loadFlashMessages);
})();
