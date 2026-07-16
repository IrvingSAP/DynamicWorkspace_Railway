/**
 * DataTables — account_list (UA/US unificado)
 */
document.addEventListener('DOMContentLoaded', function () {
    if (typeof DataTable === 'undefined') {
        return;
    }

    const tableEl = document.getElementById('account-table');
    if (!tableEl || tableEl.dataset.dtInit === 'true') {
        return;
    }

    const filterEstado = document.getElementById('filter-estado');
    const filterCompany = document.getElementById('filter-company');
    let estadoValue = '';
    let companyValue = '';

    DataTable.ext.search.push(function (settings, _searchData, dataIndex) {
        const tableNode = settings.nTable;
        if (!tableNode || tableNode.id !== 'account-table') {
            return true;
        }
        const row = new DataTable.Api(settings).row(dataIndex).node();
        if (!row) {
            return true;
        }
        if (estadoValue && row.dataset.estado !== estadoValue) {
            return false;
        }
        if (companyValue && row.dataset.company !== companyValue) {
            return false;
        }
        return true;
    });

    const table = new DataTable('#account-table', {
        language: {
            ...DW_DATATABLES_ES,
            emptyTable: 'No hay usuarios registrados en su alcance.',
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

    if (filterCompany) {
        filterCompany.addEventListener('change', function () {
            companyValue = this.value;
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
