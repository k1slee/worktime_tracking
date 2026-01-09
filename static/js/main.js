// Основные JavaScript функции для системы учета времени

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация всплывающих подсказок
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Инициализация всплывающих окон
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Подтверждение действий
    var confirmLinks = document.querySelectorAll('[data-confirm]');
    confirmLinks.forEach(function(link) {
        link.addEventListener('click', function(e) {
            if (!confirm(this.dataset.confirm)) {
                e.preventDefault();
            }
        });
    });

    // Динамическое обновление полей формы
    var masterSelect = document.getElementById('master');
    if (masterSelect) {
        masterSelect.addEventListener('change', function() {
            // Можно добавить логику для динамической загрузки сотрудников мастера
            console.log('Мастер изменен:', this.value);
        });
    }

    // Автоматическое заполнение дат для фильтров
    var today = new Date();
    var firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
    
    var startDateInput = document.getElementById('start_date');
    var endDateInput = document.getElementById('end_date');
    var dateFromInput = document.getElementById('date_from');
    var dateToInput = document.getElementById('date_to');
    
    if (startDateInput && !startDateInput.value) {
        startDateInput.valueAsDate = firstDay;
    }
    
    if (endDateInput && !endDateInput.value) {
        endDateInput.valueAsDate = today;
    }
    
    if (dateFromInput && !dateFromInput.value) {
        dateFromInput.valueAsDate = firstDay;
    }
    
    if (dateToInput && !dateToInput.value) {
        dateToInput.valueAsDate = today;
    }

    // Валидация форм
    var forms = document.querySelectorAll('.needs-validation');
    Array.prototype.slice.call(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // Автоматическое скрытие алертов через 5 секунд
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Кнопка "Наверх"
    var scrollToTopBtn = document.getElementById('scrollToTop');
    if (scrollToTopBtn) {
        window.addEventListener('scroll', function() {
            if (window.pageYOffset > 300) {
                scrollToTopBtn.style.display = 'block';
            } else {
                scrollToTopBtn.style.display = 'none';
            }
        });

        scrollToTopBtn.addEventListener('click', function() {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }

    // Динамическая подгрузка данных (если нужно)
    window.loadMoreData = function(url, containerId) {
        fetch(url)
            .then(response => response.text())
            .then(html => {
                document.getElementById(containerId).innerHTML += html;
            })
            .catch(error => console.error('Ошибка загрузки:', error));
    };
});

// Вспомогательные функции
function formatDate(date) {
    return new Date(date).toLocaleDateString('ru-RU');
}

function formatDateTime(dateTime) {
    return new Date(dateTime).toLocaleString('ru-RU');
}

// Экспорт функций для использования в других скриптах
window.WorkTimeUtils = {
    formatDate: formatDate,
    formatDateTime: formatDateTime
};