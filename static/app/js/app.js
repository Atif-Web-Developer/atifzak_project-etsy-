/*
 * Atif-Zak Analytics – layout behaviour for the Velzon theme.
 * Replaces Velzon's demo app.js with only what this project uses.
 */
(function () {
    'use strict';

    var html = document.documentElement;
    var body = document.body;

    function store(key, value) {
        try { localStorage.setItem(key, value); } catch (e) { /* storage unavailable */ }
    }

    /* ------------------------------------------------------------ Sidebar */
    var hamburger = document.getElementById('topnav-hamburger-icon');
    var hamburgerIcon = document.querySelector('.hamburger-icon');

    function toggleSidebar() {
        var w = document.documentElement.clientWidth;
        if (w <= 767) {
            body.classList.toggle('vertical-sidebar-enable');
            html.setAttribute('data-sidebar-size', 'lg');
            return;
        }
        body.classList.remove('vertical-sidebar-enable');
        var current = html.getAttribute('data-sidebar-size');
        var next = (current === 'lg') ? 'sm' : 'lg';
        html.setAttribute('data-sidebar-size', next);
        if (hamburgerIcon) hamburgerIcon.classList.toggle('open', next === 'sm');
        if (w > 1024) store('az-sidebar-size', next);
    }

    function onResize() {
        var w = document.documentElement.clientWidth;
        if (w <= 767) {
            html.setAttribute('data-sidebar-size', 'lg');
            if (hamburgerIcon) hamburgerIcon.classList.remove('open');
        } else {
            body.classList.remove('vertical-sidebar-enable');
            if (w <= 1024) html.setAttribute('data-sidebar-size', 'sm');
            else {
                var saved = null;
                try { saved = localStorage.getItem('az-sidebar-size'); } catch (e) {}
                html.setAttribute('data-sidebar-size', saved === 'sm' ? 'sm' : 'lg');
            }
            if (hamburgerIcon) hamburgerIcon.classList.toggle('open', html.getAttribute('data-sidebar-size') === 'sm');
        }
    }

    if (hamburger) hamburger.addEventListener('click', toggleSidebar);
    window.addEventListener('resize', onResize);
    onResize();

    var overlay = document.querySelector('.vertical-overlay');
    if (overlay) overlay.addEventListener('click', function () { body.classList.remove('vertical-sidebar-enable'); });

    // "Pin" button shown in the collapsed (hover) sidebar.
    var hoverBtn = document.getElementById('vertical-hover');
    if (hoverBtn) hoverBtn.addEventListener('click', function () {
        var size = html.getAttribute('data-sidebar-size');
        html.setAttribute('data-sidebar-size', size === 'sm-hover' ? 'sm-hover-active' : 'sm-hover');
    });

    // Keep the active menu item in view.
    var active = document.querySelector('#navbar-nav .nav-link.active');
    if (active && active.scrollIntoView) {
        setTimeout(function () {
            var holder = document.querySelector('#scrollbar .simplebar-content-wrapper');
            if (holder && active.offsetTop > holder.clientHeight - 100) holder.scrollTop = active.offsetTop - 150;
        }, 50);
    }

    /* --------------------------------------------------------- Dark mode */
    document.querySelectorAll('.light-dark-mode').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var next = html.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-bs-theme', next);
            store('az-theme', next);
            document.dispatchEvent(new CustomEvent('themechange', { detail: next }));
        });
    });

    /* -------------------------------------------------------- Fullscreen */
    document.querySelectorAll('[data-toggle="fullscreen"]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            if (!document.fullscreenElement) document.documentElement.requestFullscreen && document.documentElement.requestFullscreen();
            else document.exitFullscreen && document.exitFullscreen();
        });
    });
    document.addEventListener('fullscreenchange', function () {
        body.classList.toggle('fullscreen-enable', !!document.fullscreenElement);
    });

    /* ------------------------------------------------------- Back to top */
    var backToTop = document.getElementById('back-to-top');
    if (backToTop) {
        window.addEventListener('scroll', function () {
            backToTop.style.display = (window.scrollY > 200) ? 'block' : 'none';
        });
        backToTop.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
    }

    /* ---------------------------------------------------- Module search */
    var search = document.getElementById('module-search');
    var results = document.getElementById('module-search-results');
    if (search && results) {
        var items = results.querySelectorAll('[data-search]');
        var empty = document.getElementById('module-search-empty');
        search.addEventListener('input', function () {
            var q = search.value.trim().toLowerCase();
            var shown = 0;
            items.forEach(function (a) {
                var hit = !q || a.getAttribute('data-search').indexOf(q) !== -1;
                a.classList.toggle('d-none', !hit);
                if (hit) shown++;
            });
            if (empty) empty.classList.toggle('d-none', shown > 0);
            results.classList.toggle('show', q.length > 0);
        });
        search.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                var first = results.querySelector('[data-search]:not(.d-none)');
                if (first) window.location = first.href;
            } else if (e.key === 'Escape') {
                search.value = ''; results.classList.remove('show');
            }
        });
        document.addEventListener('click', function (e) {
            if (!results.contains(e.target) && e.target !== search) results.classList.remove('show');
        });
    }

    /* ----------------------------------------------- Toasts & tooltips */
    document.querySelectorAll('.app-toast').forEach(function (el) { new bootstrap.Toast(el).show(); });

    // Messages sent with extra_tags='swal' ("Title::Body") open as SweetAlert popups, one after another.
    var popups = Array.prototype.map.call(document.querySelectorAll('.app-swal'), function (el) {
        var parts = el.getAttribute('data-message').split('::');
        var level = el.getAttribute('data-level');
        return {
            icon: { success: 'success', warning: 'warning', danger: 'error' }[level] || 'info',
            title: parts.length > 1 ? parts[0] : '',
            text: parts.length > 1 ? parts.slice(1).join('::') : parts[0],
            confirmButtonText: 'OK',
            customClass: { confirmButton: 'btn btn-primary w-xs' },
            buttonsStyling: false,
            timer: level === 'success' ? 4000 : undefined,
            timerProgressBar: level === 'success'
        };
    });
    (function next() {
        if (!popups.length || !window.Swal) return;
        Swal.fire(popups.shift()).then(next);
    })();
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) { new bootstrap.Tooltip(el); });
    if (window.Waves) { Waves.init(); }

    window.appToast = function (message, level) {
        level = level || 'success';
        var icon = { success: 'ri-checkbox-circle-fill', danger: 'ri-error-warning-fill', warning: 'ri-alert-fill' }[level] || 'ri-information-fill';
        var wrap = document.getElementById('app-toasts');
        var el = document.createElement('div');
        el.className = 'toast app-toast border-0 overflow-hidden';
        el.setAttribute('role', 'alert');
        el.innerHTML = '<div class="toast-body d-flex align-items-start gap-2 bg-' + level + '-subtle text-' + level + '-emphasis">' +
            '<i class="fs-18 ' + icon + '"></i><div class="flex-grow-1 fw-medium"></div>' +
            '<button type="button" class="btn-close btn-sm" data-bs-dismiss="toast" aria-label="Close"></button></div>';
        el.querySelector('.flex-grow-1').textContent = message;
        wrap.appendChild(el);
        el.addEventListener('hidden.bs.toast', function () { el.remove(); });
        new bootstrap.Toast(el, { delay: 5000 }).show();
    };

    /* ------------------------------------------- Confirmation dialogs */
    // <form data-confirm="Delete this user?" data-confirm-button="Delete"> asks before submitting.
    document.addEventListener('submit', function (e) {
        var form = e.target;
        var text = form.getAttribute('data-confirm');
        if (!text || form.dataset.confirmed === '1' || !window.Swal) return;
        e.preventDefault();
        Swal.fire({
            title: form.getAttribute('data-confirm-title') || 'Are you sure?',
            text: text,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: form.getAttribute('data-confirm-button') || 'Yes, continue',
            cancelButtonText: 'Cancel',
            customClass: { confirmButton: 'btn btn-danger w-xs me-2', cancelButton: 'btn btn-light w-xs' },
            buttonsStyling: false,
            reverseButtons: false
        }).then(function (r) {
            if (r.isConfirmed) { form.dataset.confirmed = '1'; form.submit(); }
        });
    });

    /* ----------------------------------------------- Password toggles */
    document.querySelectorAll('.password-addon').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var input = btn.parentElement.querySelector('input');
            if (!input) return;
            var show = input.type === 'password';
            input.type = show ? 'text' : 'password';
            var i = btn.querySelector('i');
            if (i) i.className = (show ? 'ri-eye-off-fill' : 'ri-eye-fill') + ' align-middle';
        });
    });

    /* ------------------------------------------------- AJAX CSRF helper */
    window.getCookie = function (name) {
        var match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
        return match ? decodeURIComponent(match[1]) : null;
    };
    if (window.jQuery) {
        jQuery.ajaxSetup({
            beforeSend: function (xhr, settings) {
                if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                    xhr.setRequestHeader('X-CSRFToken', window.getCookie('csrftoken'));
                }
            }
        });
    }
})();
