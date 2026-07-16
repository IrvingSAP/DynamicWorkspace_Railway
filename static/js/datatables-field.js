/**
 * DataTables — field_list (UF / PA)
 */
document.addEventListener('DOMContentLoaded', function () {
    if (typeof DataTable === 'undefined') {
        return;
    }

    const tableEl = document.getElementById('field-table');
    if (!tableEl || tableEl.dataset.dtInit === 'true') {
        return;
    }

    const filterTipo = document.getElementById('filter-tipo');
    const filterEstado = document.getElementById('filter-estado');
    let tipoValue = '';
    let estadoValue = '';

    DataTable.ext.search.push(function (settings, _searchData, dataIndex) {
        const tableNode = settings.nTable;
        if (!tableNode || tableNode.id !== 'field-table') {
            return true;
        }
        const row = new DataTable.Api(settings).row(dataIndex).node();
        if (!row) {
            return true;
        }
        if (tipoValue && row.dataset.tipo !== tipoValue) {
            return false;
        }
        if (estadoValue && row.dataset.estado !== estadoValue) {
            return false;
        }
        return true;
    });

    const table = new DataTable('#field-table', {
        language: {
            ...DW_DATATABLES_ES,
            emptyTable: 'No hay campos definidos en este proyecto.',
        },
        layout: DW_DATATABLES_LAYOUT,
        pageLength: 10,
        order: [[0, 'asc']],
        columnDefs: [
            { orderable: false, searchable: false, targets: -1, className: 'col-actions' },
        ],
    });

    tableEl.dataset.dtInit = 'true';

    if (filterTipo) {
        filterTipo.addEventListener('change', function () {
            tipoValue = this.value;
            table.draw();
        });
    }

    if (filterEstado) {
        filterEstado.addEventListener('change', function () {
            estadoValue = this.value;
            table.draw();
        });
    }

    document.querySelectorAll('[data-dw-delete]').forEach(function (trigger) {
        trigger.addEventListener('click', function (e) {
            e.preventDefault();
            const form = trigger.closest('form');
            const message = trigger.dataset.dwDeleteMessage
                || '¿Confirma que desea desactivar este campo?';
            window.dwConfirmWarning(message, function () {
                if (form) {
                    form.submit();
                }
            }, {
                title: 'Confirmar desactivación',
                okLabel: 'Desactivar',
            });
        });
    });
});
