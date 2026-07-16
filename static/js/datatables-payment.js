/**
 * DataTables — payment_list
 */
document.addEventListener('DOMContentLoaded', function () {
    if (typeof DataTable === 'undefined') {
        return;
    }

    const tableEl = document.getElementById('payment-table');
    if (!tableEl || tableEl.dataset.dtInit === 'true') {
        return;
    }

    const filterMetodo = document.getElementById('filter-metodo');
    let metodoValue = '';

    DataTable.ext.search.push(function (settings, _searchData, dataIndex) {
        const tableNode = settings.nTable;
        if (!tableNode || tableNode.id !== 'payment-table') {
            return true;
        }
        if (!metodoValue) {
            return true;
        }
        const row = new DataTable.Api(settings).row(dataIndex).node();
        return row && row.dataset.metodo === metodoValue;
    });

    const table = new DataTable('#payment-table', {
        language: {
            ...DW_DATATABLES_ES,
            emptyTable: 'No hay pagos registrados.',
        },
        layout: DW_DATATABLES_LAYOUT,
        pageLength: 10,
        order: [[4, 'desc']],
        columnDefs: [
            { orderable: false, searchable: false, targets: -1, className: 'col-actions' },
        ],
    });

    tableEl.dataset.dtInit = 'true';

    if (filterMetodo) {
        filterMetodo.addEventListener('change', function () {
            metodoValue = this.value;
            table.draw();
        });
    }
});
