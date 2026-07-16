/**
 * field_create / field_update — paneles condicionales por field_type
 */
document.addEventListener('DOMContentLoaded', function () {
    const typeSelect = document.getElementById('field_type');
    if (!typeSelect) {
        return;
    }

    const panels = {
        text: document.getElementById('panel-text'),
        number: document.getElementById('panel-number'),
        select: document.getElementById('panel-select'),
    };

    function syncPanels() {
        const value = typeSelect.value;
        Object.values(panels).forEach(function (panel) {
            if (panel) {
                panel.classList.remove('is-visible');
            }
        });

        if (value === 'text_short' || value === 'text_long') {
            if (panels.text) {
                panels.text.classList.add('is-visible');
            }
        } else if (value === 'integer' || value === 'decimal') {
            if (panels.number) {
                panels.number.classList.add('is-visible');
            }
        } else if (value === 'select') {
            if (panels.select) {
                panels.select.classList.add('is-visible');
            }
        }
    }

    typeSelect.addEventListener('change', syncPanels);
    syncPanels();
});
