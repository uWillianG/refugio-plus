function parseJsonScript(scriptId, fallbackValue) {
    const element = document.getElementById(scriptId);
    if (!element) {
        return fallbackValue;
    }

    try {
        return JSON.parse(element.textContent);
    } catch (error) {
        return fallbackValue;
    }
}

function setActiveButton(container, activeButton) {
    container.querySelectorAll('.option-chip').forEach((button) => button.classList.remove('selected'));
    activeButton.classList.add('selected');
}

function createChipButton(label, isEnabled) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `option-chip ${isEnabled ? '' : 'disabled'}`.trim();
    button.textContent = label;
    button.disabled = !isEnabled;
    return button;
}

function initializeCalendar() {
    const dateForm = document.getElementById('dateForm');
    const dateButton = document.getElementById('datePickerButton');
    const calendarPanel = document.getElementById('dateCalendarPanel');
    const selectedDateInput = document.getElementById('selectedDateInput');
    const prevMonthButton = document.getElementById('calendarPrevMonth');
    const nextMonthButton = document.getElementById('calendarNextMonth');
    const monthLabel = document.getElementById('calendarMonthLabel');
    const daysGrid = document.getElementById('calendarDaysGrid');

    if (
        !dateForm || !dateButton || !calendarPanel || !selectedDateInput ||
        !prevMonthButton || !nextMonthButton || !monthLabel || !daysGrid
    ) {
        return;
    }

    const monthFormatter = new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric' });
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const selectedDate = selectedDateInput.value ? new Date(`${selectedDateInput.value}T00:00:00`) : new Date(today);
    let selectedISO = selectedDateInput.value;
    let viewYear = selectedDate.getFullYear();
    let viewMonth = selectedDate.getMonth();

    function toISO(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    function openCalendar() {
        calendarPanel.hidden = false;
        calendarPanel.classList.add('open');
        dateButton.setAttribute('aria-expanded', 'true');
    }

    function closeCalendar() {
        calendarPanel.classList.remove('open');
        calendarPanel.hidden = true;
        dateButton.setAttribute('aria-expanded', 'false');
    }

    function selectDate(date) {
        selectedISO = toISO(date);
        selectedDateInput.value = selectedISO;
        closeCalendar();
        dateForm.submit();
    }

    function renderCalendar() {
        const firstDay = new Date(viewYear, viewMonth, 1);
        const monthStartWeekday = firstDay.getDay();
        const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();

        monthLabel.textContent = monthFormatter.format(firstDay);
        monthLabel.textContent = monthLabel.textContent.charAt(0).toUpperCase() + monthLabel.textContent.slice(1);

        daysGrid.innerHTML = '';

        for (let i = 0; i < monthStartWeekday; i += 1) {
            const empty = document.createElement('span');
            empty.className = 'date-calendar-day empty';
            daysGrid.appendChild(empty);
        }

        for (let day = 1; day <= daysInMonth; day += 1) {
            const date = new Date(viewYear, viewMonth, day);
            const iso = toISO(date);
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'date-calendar-day';
            button.textContent = day;

            if (date < today) {
                button.disabled = true;
            }

            if (iso === toISO(today)) {
                button.classList.add('today');
            }

            if (iso === selectedISO) {
                button.classList.add('selected');
            }

            button.addEventListener('click', () => selectDate(date));
            daysGrid.appendChild(button);
        }
    }

    dateButton.addEventListener('click', (event) => {
        event.stopPropagation();

        if (calendarPanel.hidden) {
            renderCalendar();
            openCalendar();
        } else {
            closeCalendar();
        }
    });

    prevMonthButton.addEventListener('click', () => {
        viewMonth -= 1;
        if (viewMonth < 0) {
            viewMonth = 11;
            viewYear -= 1;
        }
        renderCalendar();
    });

    nextMonthButton.addEventListener('click', () => {
        viewMonth += 1;
        if (viewMonth > 11) {
            viewMonth = 0;
            viewYear += 1;
        }
        renderCalendar();
    });

    document.addEventListener('click', (event) => {
        if (!calendarPanel.hidden && !calendarPanel.contains(event.target) && !dateButton.contains(event.target)) {
            closeCalendar();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !calendarPanel.hidden) {
            closeCalendar();
            dateButton.focus();
        }
    });
}

function initializeBookingModal() {
    const bookingModal = document.getElementById('courtBookingModal');
    if (!bookingModal) {
        return;
    }

    const sports = parseJsonScript('sportsData', []);
    const availability = parseJsonScript('availabilityData', {});

    const modalCourtName = document.getElementById('modalCourtName');
    const sportSelect = document.getElementById('modalSportSelect');
    const startHourGrid = document.getElementById('startHourGrid');
    const durationOptions = document.getElementById('durationOptions');
    const continueButton = document.getElementById('continueBookingBtn');

    const inputCourtId = document.getElementById('inputCourtId');
    const inputSportId = document.getElementById('inputSportId');
    const inputStartTime = document.getElementById('inputStartTime');
    const inputEndTime = document.getElementById('inputEndTime');

    if (!sportSelect || !durationOptions || !continueButton) {
        return;
    }

    // Hide the start hour section inside the modal — the user picks it from the card
    if (startHourGrid) {
        startHourGrid.closest('.modal-section').hidden = true;
    }

    const state = {
        courtId: null,
        sportId: null,
        startHour: null,
        endHour: null,
    };

    function closeModal() {
        bookingModal.classList.remove('open');
        bookingModal.setAttribute('aria-hidden', 'true');
    }

    function getSlotRow() {
        if (!state.courtId || !state.sportId || state.startHour === null) {
            return null;
        }
        const byCourt = availability[state.courtId] || {};
        const rows = byCourt[state.sportId] || [];
        return rows.find((r) => r.start_hour === state.startHour) || null;
    }

    function renderDurationOptions() {
        durationOptions.innerHTML = '';
        state.endHour = null;
        inputStartTime.value = '';
        inputEndTime.value = '';
        continueButton.disabled = true;

        const row = getSlotRow();
        if (!row) {
            return;
        }

        row.options.forEach((option) => {
            const button = createChipButton(option.label, option.status === 'available');

            if (option.status === 'available') {
                button.addEventListener('click', () => {
                    state.endHour = option.end_hour;
                    inputStartTime.value = option.start_label;
                    inputEndTime.value = option.end_label;
                    setActiveButton(durationOptions, button);
                    continueButton.disabled = false;
                });
            }

            durationOptions.appendChild(button);
        });
    }

    function openModal(courtId, courtName, startHour) {
        state.courtId = String(courtId);
        state.startHour = startHour;
        state.endHour = null;

        inputCourtId.value = state.courtId;
        inputStartTime.value = '';
        inputEndTime.value = '';
        continueButton.disabled = true;

        if (modalCourtName) {
            modalCourtName.textContent = courtName;
        }

        const modalStartHourLabel = document.getElementById('modalStartHourLabel');
        if (modalStartHourLabel) {
            const startLabel = `${String(startHour).padStart(2, '0')}:00`;
            modalStartHourLabel.textContent = `A partir de ${startLabel}`;
        }

        sportSelect.innerHTML = '';
        sports.forEach((sport, index) => {
            const option = document.createElement('option');
            option.value = String(sport.id);
            option.textContent = sport.name;
            sportSelect.appendChild(option);

            if (index === 0) {
                state.sportId = String(sport.id);
            }
        });

        sportSelect.value = state.sportId;
        inputSportId.value = state.sportId;

        renderDurationOptions();
        bookingModal.classList.add('open');
        bookingModal.setAttribute('aria-hidden', 'false');
    }

    sportSelect.addEventListener('change', () => {
        state.sportId = sportSelect.value;
        inputSportId.value = state.sportId;
        state.endHour = null;
        renderDurationOptions();
    });

    // Render start-hour chips directly on each court card
    document.querySelectorAll('.court-card').forEach((card) => {
        const courtId = card.dataset.courtId;
        const courtName = card.dataset.courtName;
        const grid = card.querySelector('.court-time-grid');
        if (!grid || !courtId) {
            return;
        }

        // Use the first sport's availability to show slots on the card
        const firstSportId = sports.length > 0 ? String(sports[0].id) : null;
        const rows = firstSportId
            ? (availability[courtId] || {})[firstSportId] || []
            : [];

        if (rows.length === 0) {
            grid.innerHTML = '<span style="font-size:12px;color:var(--color-text-secondary)">Sem horários disponíveis</span>';
            return;
        }

        rows.forEach((row) => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.textContent = row.start_label;
            chip.className = `time-slot ${row.status}`;
            chip.disabled = row.status !== 'available';

            if (row.status === 'available') {
                chip.addEventListener('click', () => {
                    openModal(courtId, courtName, row.start_hour);
                });
            }

            grid.appendChild(chip);
        });
    });

    document.querySelectorAll('[data-close-modal="true"]').forEach((node) => {
        node.addEventListener('click', closeModal);
    });

    const closeButton = document.getElementById('closeBookingModal');
    if (closeButton) {
        closeButton.addEventListener('click', closeModal);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initializeCalendar();
    initializeBookingModal();
});


