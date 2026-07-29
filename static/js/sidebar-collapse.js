/**
 * Sidebar collapse — icons-only mode with localStorage persistence.
 * Key: dw.sidebar.collapsed ("1" | "0")
 * Class on <html>: sidebar-icons
 */
(function () {
    "use strict";

    var STORAGE_KEY = "dw.sidebar.collapsed";
    var CLASS_NAME = "sidebar-icons";
    var MQ_MOBILE = "(max-width: 768px)";

    function isMobile() {
        return window.matchMedia && window.matchMedia(MQ_MOBILE).matches;
    }

    function readCollapsed() {
        try {
            return localStorage.getItem(STORAGE_KEY) === "1";
        } catch (e) {
            return false;
        }
    }

    function writeCollapsed(collapsed) {
        try {
            localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0");
        } catch (e) {
            /* ignore quota / private mode */
        }
    }

    function apply(collapsed) {
        document.documentElement.classList.toggle(CLASS_NAME, !!collapsed);
        var btn = document.getElementById("sidebar-collapse-btn");
        if (btn) {
            btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
            btn.setAttribute(
                "title",
                collapsed ? "Expandir menú" : "Minimizar menú"
            );
            var label = btn.querySelector(".sidebar-link-label");
            if (label) {
                label.textContent = collapsed ? "Expandir" : "Minimizar";
            }
        }
    }

    function setCollapsed(collapsed) {
        collapsed = !!collapsed;
        writeCollapsed(collapsed);
        apply(collapsed);
    }

    function toggle() {
        if (isMobile()) return;
        setCollapsed(!document.documentElement.classList.contains(CLASS_NAME));
    }

    function expand() {
        setCollapsed(false);
    }

    window.dwSidebarCollapse = {
        toggle: toggle,
        expand: expand,
        setCollapsed: setCollapsed,
        isCollapsed: function () {
            return document.documentElement.classList.contains(CLASS_NAME);
        },
    };

    apply(readCollapsed());

    document.addEventListener("DOMContentLoaded", function () {
        apply(readCollapsed());
        var btn = document.getElementById("sidebar-collapse-btn");
        if (btn) {
            btn.addEventListener("click", function (event) {
                event.preventDefault();
                toggle();
            });
        }
    });
})();
