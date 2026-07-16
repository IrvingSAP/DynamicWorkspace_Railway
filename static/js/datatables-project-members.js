/**
 * DataTables — project_members (UF)
 */
document.addEventListener('DOMContentLoaded', function () {
    if (typeof DataTable === 'undefined') {
        return;
    }

    const tableEl = document.getElementById('members-table');
    if (!tableEl || tableEl.dataset.dtInit === 'true') {
        return;
    }

    const filterEstado = document.getElementById('filter-estado');
    let estadoValue = '';

    DataTable.ext.search.push(function (settings, _searchData, dataIndex) {
        const tableNode = settings.nTable;
        if (!tableNode || tableNode.id !== 'members-table') {
            return true;
        }
        const row = new DataTable.Api(settings).row(dataIndex).node();
        if (!row) {
            return true;
        }
        if (estadoValue && row.dataset.estado !== estadoValue) {
            return false;
        }
        return true;
    });

    const table = new DataTable('#members-table', {
        language: {
            ...DW_DATATABLES_ES,
            emptyTable: 'No hay miembros en este proyecto.',
        },
        layout: DW_DATATABLES_LAYOUT,
        pageLength: 10,
        order: [[5, 'desc']],
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
});
