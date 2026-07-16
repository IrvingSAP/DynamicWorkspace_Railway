/**
 * SourceProfile wizard — capture mode panels, line-ending custom field
 */
(function () {
    document.querySelectorAll("[data-capture-params]").forEach(function (block) {
        var group = block.getAttribute("data-capture-params");
        var radios = document.querySelectorAll('input[name="' + group + '"]');
        if (!radios.length) return;

        function sync() {
            var selected = document.querySelector('input[name="' + group + '"]:checked');
            var mode = selected ? selected.value : "";
            document.querySelectorAll("[data-capture-panel]").forEach(function (panel) {
                panel.hidden = panel.getAttribute("data-capture-panel") !== mode;
            });
        }

        radios.forEach(function (radio) {
            radio.addEventListener("change", sync);
        });
        sync();
    });

    document.querySelectorAll("[data-line-ending-custom]").forEach(function (wrap) {
        var select = wrap.querySelector("select");
        var custom = wrap.querySelector("[data-custom-field]");
        if (!select || !custom) return;
        function sync() {
            custom.hidden = select.value !== "custom";
        }
        select.addEventListener("change", sync);
        sync();
    });
})();
