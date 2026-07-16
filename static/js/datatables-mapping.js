/**
 * DataTables — dms mapping project list (UF)
 */
document.addEventListener('DOMContentLoaded', function () {
    if (typeof DataTable === 'undefined') {
        return;
    }

    const tableEl = document.getElementById('dms-project-table');
    if (!tableEl || tableEl.dataset.dtInit === 'true') {
        return;
    }

    const filterVisibilidad = document.getElementById('filter-visibilidad');
    let visibilidadValue = '';

    DataTable.ext.search.push(function (settings, _searchData, dataIndex) {
        const tableNode = settings.nTable;
        if (!tableNode || tableNode.id !== 'dms-project-table') {
            return true;
        }
        const row = new DataTable.Api(settings).row(dataIndex).node();
        if (!row) {
            return true;
        }
        if (visibilidadValue && row.dataset.visibilidad !== visibilidadValue) {
            return false;
        }
        return true;
    });

    const table = new DataTable('#dms-project-table', {
        language: {
            ...DW_DATATABLES_ES,
            emptyTable: 'No hay proyectos DMS en tu alcance.',
        },
        layout: DW_DATATABLES_LAYOUT,
        pageLength: 10,
        order: [[0, 'asc']],
        columnDefs: [
            { orderable: false, searchable: false, targets: -1, className: 'col-actions' },
        ],
    });

    tableEl.dataset.dtInit = 'true';

    if (filterVisibilidad) {
        filterVisibilidad.addEventListener('change', function () {
            visibilidadValue = this.value;
            table.draw();
        });
    }
});
