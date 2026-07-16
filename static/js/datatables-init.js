/**
 * Inicialización global de DataTables 2.
 * Manual: https://datatables.net/manual/
 */
const DW_DATATABLES_ES = {
    emptyTable: 'No hay datos disponibles',
    info: 'Mostrando _START_ a _END_ de _TOTAL_ registros',
    infoEmpty: 'Mostrando 0 a 0 de 0 registros',
    infoFiltered: '(filtrado de _MAX_ registros totales)',
    lengthMenu: 'Mostrar _MENU_ registros',
    loadingRecords: 'Cargando…',
    processing: 'Procesando…',
    search: 'Buscar:',
    searchPlaceholder: 'Buscar en la tabla…',
    zeroRecords: 'No se encontraron resultados',
    paginate: {
        first: 'Primero',
        last: 'Último',
        next: 'Siguiente',
        previous: 'Anterior',
    },
};

const DW_DATATABLES_LAYOUT = {
    topStart: {
        pageLength: {
            menu: [10, 25, 50],
        },
    },
    topEnd: {
        search: {
            placeholder: 'Buscar en la tabla…',
        },
    },
    bottomStart: 'info',
    bottomEnd: 'paging',
};

document.addEventListener('DOMContentLoaded', () => {
    if (typeof DataTable === 'undefined') {
        return;
    }

    // Tablas con init propio: class="dw-datatable" data-dt-custom="true"
    // + script dedicado (datatables-*.js). No llamar DataTable() inline si ya
    // se incluye datatables-init.js sobre la misma tabla.
    document.querySelectorAll('.dw-datatable').forEach((table) => {
        if (table.dataset.dtInit === 'true' || table.dataset.dtCustom === 'true') {
            return;
        }

        const defaultOrder = table.dataset.dtOrder
            ? JSON.parse(table.dataset.dtOrder)
            : [[0, 'asc']];

        new DataTable(table, {
            language: DW_DATATABLES_ES,
            layout: DW_DATATABLES_LAYOUT,
            pageLength: 10,
            order: defaultOrder,
            columnDefs: [{ orderable: false, searchable: false, targets: -1 }],
        });

        table.dataset.dtInit = 'true';
    });
});
