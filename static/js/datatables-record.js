/**
 * DataTables — record_list / record_expand (UF)
 */
document.addEventListener('DOMContentLoaded', function () {
    if (typeof DataTable === 'undefined') {
        return;
    }

    const tableEl = document.getElementById('record-table');
    if (!tableEl || tableEl.dataset.dtInit === 'true') {
        return;
    }

    const filterSelect = document.getElementById('filter-select');
    let filterValue = '';
    const updatedColIndex = parseInt(tableEl.dataset.updatedColIndex || '0', 10);
    const hasActionsCol = tableEl.querySelector('.col-actions') !== null;
    const isExpandMode = tableEl.dataset.expandMode === 'true'
        || document.body.classList.contains('record-expand');
    const pageLength = parseInt(tableEl.dataset.pageLength || '10', 10);

    DataTable.ext.search.push(function (settings, _searchData, dataIndex) {
        const tableNode = settings.nTable;
        if (!tableNode || tableNode.id !== 'record-table') {
            return true;
        }
        const row = new DataTable.Api(settings).row(dataIndex).node();
        if (!row) {
            return true;
        }
        if (filterValue && row.dataset.filterValue !== filterValue) {
            return false;
        }
        return true;
    });

    const columnDefs = [];
    if (hasActionsCol) {
        columnDefs.push({
            orderable: false,
            searchable: false,
            targets: -1,
            className: 'col-actions',
        });
    }

    const dtOptions = {
        language: {
            ...DW_DATATABLES_ES,
            emptyTable: 'No hay registros en este proyecto.',
        },
        layout: DW_DATATABLES_LAYOUT,
        pageLength: Number.isNaN(pageLength) ? 10 : pageLength,
        order: [[updatedColIndex, 'desc']],
        columnDefs: columnDefs,
    };

    if (isExpandMode) {
        dtOptions.scrollY = 'calc(100vh - 148px)';
        dtOptions.scrollCollapse = true;
        dtOptions.fixedHeader = false;
    }

    const table = new DataTable('#record-table', dtOptions);

    tableEl.dataset.dtInit = 'true';

    if (filterSelect) {
        filterSelect.addEventListener('change', function () {
            filterValue = this.value;
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
