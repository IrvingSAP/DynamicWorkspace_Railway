/**
 * DataTables — plan_list
 */
document.addEventListener('DOMContentLoaded', function () {
    if (typeof DataTable === 'undefined') {
        return;
    }

    const tableEl = document.getElementById('plan-table');
    if (!tableEl || tableEl.dataset.dtInit === 'true') {
        return;
    }

    const filterEstado = document.getElementById('filter-estado');
    let estadoValue = '';

    DataTable.ext.search.push(function (settings, _searchData, dataIndex) {
        const tableNode = settings.nTable;
        if (!tableNode || tableNode.id !== 'plan-table') {
            return true;
        }
        if (!estadoValue) {
            return true;
        }
        const row = new DataTable.Api(settings).row(dataIndex).node();
        return row && row.dataset.estado === estadoValue;
    });

    const table = new DataTable('#plan-table', {
        language: {
            ...DW_DATATABLES_ES,
            emptyTable: 'No hay planes registrados.',
        },
        layout: DW_DATATABLES_LAYOUT,
        pageLength: 10,
        order: [[0, 'asc']],
        columnDefs: [
            { orderable: false, searchable: false, targets: -1, className: 'col-actions' },
        ],
    });

    tableEl.dataset.dtInit = 'true';

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
                || '¿Confirma que desea eliminar este registro?';
            window.dwConfirmWarning(message, function () {
                if (form) {
                    form.submit();
                }
            }, {
                title: 'Confirmar eliminación',
                okLabel: 'Eliminar',
            });
        });
    });
});
