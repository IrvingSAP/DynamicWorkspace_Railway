/**
 * FilePipe / UF sidebar — group toggles + expand when icons-only
 */
(function () {
    if (document.documentElement.dataset.sidebarUfBound === "1") return;
    document.documentElement.dataset.sidebarUfBound = "1";

    function setFamilyOpen(group, open) {
        group.classList.toggle("is-open", open);
        var btn = group.querySelector(".sb-family-toggle");
        if (btn) btn.setAttribute("aria-expanded", open ? "true" : "false");
    }

    function closeOtherFamilies(keep) {
        document.querySelectorAll("[data-family]").forEach(function (group) {
            if (group !== keep) setFamilyOpen(group, false);
        });
    }

    function openFamilyWithActiveLink() {
        document.querySelectorAll("[data-family]").forEach(function (group) {
            var active = group.querySelector(".sidebar-sublink.is-active, .sb-app-help.is-active");
            setFamilyOpen(group, !!active);
        });
    }

    function bindToggle(selector, closestSel) {
        document.querySelectorAll(selector).forEach(function (btn) {
            btn.addEventListener("click", function () {
                var group = btn.closest(closestSel);
                if (!group) return;

                var iconsMode = document.documentElement.classList.contains("sidebar-icons");
                var mobile = window.matchMedia && window.matchMedia("(max-width: 768px)").matches;
                var isFamily = group.hasAttribute("data-family");

                if (iconsMode && !mobile) {
                    if (window.dwSidebarCollapse) {
                        window.dwSidebarCollapse.expand();
                    }
                    if (isFamily) closeOtherFamilies(group);
                    group.classList.add("is-open");
                    btn.setAttribute("aria-expanded", "true");
                    return;
                }

                if (isFamily) {
                    var willOpen = !group.classList.contains("is-open");
                    if (willOpen) closeOtherFamilies(group);
                    setFamilyOpen(group, willOpen);
                    return;
                }

                var open = group.classList.toggle("is-open");
                btn.setAttribute("aria-expanded", open ? "true" : "false");
            });
        });
    }

    openFamilyWithActiveLink();
    bindToggle(".sidebar-nav-group-toggle", ".sidebar-nav-group");
    bindToggle(".sb-family-toggle", "[data-family]");
})();
