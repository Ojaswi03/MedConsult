/**
 * Availability Calendar JavaScript
 * Handles modal management, calendar interactions, keyboard navigation,
 * and WebSocket real-time updates for doctor availability.
 */

document.addEventListener('DOMContentLoaded', function() {

    // ============ CALENDAR STATE ============

    let currentWeekStart = null;
    let websocket = null;
    let isLoading = false;  // Prevent multiple simultaneous requests
    const calendarGrid = document.getElementById('calendar-grid');

    // Parse initial week start from the page
    function initializeWeekState() {
        const weekDisplay = document.querySelector('[data-week-start]');
        if (weekDisplay) {
            currentWeekStart = weekDisplay.dataset.weekStart;
        } else {
            // Fallback: get from navigation button URL
            const prevButton = document.querySelector('[hx-get*="week_start="]');
            if (prevButton) {
                const url = new URL(prevButton.getAttribute('hx-get'), window.location.origin);
                const prevWeek = url.searchParams.get('week_start');
                if (prevWeek) {
                    // Calculate current week from prev week (add 7 days)
                    const prevDate = new Date(prevWeek);
                    prevDate.setDate(prevDate.getDate() + 7);
                    currentWeekStart = prevDate.toISOString().split('T')[0];
                }
            }
        }
    }

    initializeWeekState();

    // ============ KEYBOARD NAVIGATION ============

    document.addEventListener('keydown', function(e) {
        // Ignore key repeat events (when key is held down)
        if (e.repeat) return;

        // Only handle arrow keys when not in an input field
        if (document.activeElement.tagName === 'INPUT' ||
            document.activeElement.tagName === 'TEXTAREA' ||
            document.activeElement.tagName === 'SELECT') {
            return;
        }

        // Don't navigate if a modal is open
        if (document.querySelector('[id$="-modal"]:not(.hidden)')) {
            if (e.key === 'Escape') {
                closeAllModals();
            }
            return;
        }

        if (e.key === 'ArrowLeft') {
            e.preventDefault();
            navigateWeek('prev');
        } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            navigateWeek('next');
        } else if (e.key === 'Escape') {
            closeAllModals();
        }
    });

    function navigateWeek(direction) {
        if (!currentWeekStart) {
            initializeWeekState();
            if (!currentWeekStart) return;
        }

        // Parse date parts to avoid timezone issues with new Date("YYYY-MM-DD")
        const [year, month, day] = currentWeekStart.split('-').map(Number);
        const currentDate = new Date(year, month - 1, day);  // month is 0-indexed

        if (direction === 'prev') {
            currentDate.setDate(currentDate.getDate() - 7);
        } else {
            currentDate.setDate(currentDate.getDate() + 7);
        }

        // Format as YYYY-MM-DD in local time
        const newYear = currentDate.getFullYear();
        const newMonth = String(currentDate.getMonth() + 1).padStart(2, '0');
        const newDay = String(currentDate.getDate()).padStart(2, '0');
        const newWeekStart = `${newYear}-${newMonth}-${newDay}`;

        loadWeek(newWeekStart);
    }

    function loadWeek(weekStart) {
        if (!calendarGrid) return;

        // Prevent multiple simultaneous requests
        if (isLoading) return;
        isLoading = true;

        // Add loading state
        calendarGrid.classList.add('opacity-50', 'transition-opacity');

        // Fetch new week data
        htmx.ajax('GET', `/doctor/availability/calendar/?week_start=${weekStart}`, {
            target: '#calendar-grid',
            swap: 'innerHTML'
        }).then(() => {
            currentWeekStart = weekStart;
            calendarGrid.classList.remove('opacity-50');
            updateNavigationButtons(weekStart);
            isLoading = false;
        }).catch(err => {
            console.error('Failed to load week:', err);
            calendarGrid.classList.remove('opacity-50');
            isLoading = false;
        });
    }

    function updateNavigationButtons(weekStart) {
        // Parse date parts to avoid timezone issues
        const [year, month, day] = weekStart.split('-').map(Number);
        const currentDate = new Date(year, month - 1, day);

        // Calculate prev week
        const prevDate = new Date(year, month - 1, day - 7);
        const prevWeek = `${prevDate.getFullYear()}-${String(prevDate.getMonth() + 1).padStart(2, '0')}-${String(prevDate.getDate()).padStart(2, '0')}`;

        // Calculate next week
        const nextDate = new Date(year, month - 1, day + 7);
        const nextWeek = `${nextDate.getFullYear()}-${String(nextDate.getMonth() + 1).padStart(2, '0')}-${String(nextDate.getDate()).padStart(2, '0')}`;

        // Update navigation buttons
        const prevButton = document.getElementById('prev-week-btn');
        const nextButton = document.getElementById('next-week-btn');

        if (prevButton) {
            prevButton.setAttribute('hx-get', `/doctor/availability/calendar/?week_start=${prevWeek}`);
            htmx.process(prevButton);
        }
        if (nextButton) {
            nextButton.setAttribute('hx-get', `/doctor/availability/calendar/?week_start=${nextWeek}`);
            htmx.process(nextButton);
        }

        // Update week display
        const endDate = new Date(currentDate);
        endDate.setDate(endDate.getDate() + 6);

        const weekDisplay = document.getElementById('week-display');
        if (weekDisplay) {
            const startStr = currentDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            const endStr = endDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
            weekDisplay.textContent = `${startStr} - ${endStr}`;
            weekDisplay.dataset.weekStart = weekStart;
        }
    }

    // Update state after HTMX swaps
    document.body.addEventListener('htmx:afterSwap', function(event) {
        if (event.detail.target.id === 'calendar-grid') {
            // Extract new week start from response if available
            const newWeekData = event.detail.target.querySelector('[data-week-start]');
            if (newWeekData) {
                currentWeekStart = newWeekData.dataset.weekStart;
                // Update the header week display to match
                updateNavigationButtons(currentWeekStart);
            }
            // Always reset loading state after swap
            isLoading = false;
        }
    });

    // ============ WEBSOCKET CONNECTION ============

    function connectWebSocket() {
        const doctorId = document.body.dataset.doctorId;
        if (!doctorId) return;

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/doctor/${doctorId}/calendar/`;

        websocket = new WebSocket(wsUrl);

        websocket.onopen = function() {
            console.log('Calendar WebSocket connected');
        };

        websocket.onmessage = function(event) {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        };

        websocket.onclose = function(event) {
            console.log('Calendar WebSocket closed, reconnecting in 5s...');
            setTimeout(connectWebSocket, 5000);
        };

        websocket.onerror = function(error) {
            console.error('Calendar WebSocket error:', error);
        };
    }

    function handleWebSocketMessage(data) {
        switch (data.type) {
            case 'slot_blocked':
                updateSlotUI(data.slot_id, 'blocked');
                break;
            case 'slot_unblocked':
                updateSlotUI(data.slot_id, 'available');
                break;
            case 'slot_deleted':
                removeSlotUI(data.slot_id);
                break;
            case 'slot_booked':
                updateSlotUI(data.slot_id, 'booked');
                break;
            case 'window_deleted':
                // Refresh the windows list
                htmx.ajax('GET', '/doctor/availability/', {
                    target: '#availability-windows-list',
                    swap: 'innerHTML'
                });
                // Refresh calendar
                if (currentWeekStart) {
                    loadWeek(currentWeekStart);
                }
                break;
            case 'window_created':
            case 'window_updated':
                // Refresh the windows list and calendar
                htmx.ajax('GET', '/doctor/availability/', {
                    target: '#availability-windows-list',
                    swap: 'innerHTML'
                });
                if (currentWeekStart) {
                    loadWeek(currentWeekStart);
                }
                break;
        }
    }

    function updateSlotUI(slotId, status) {
        const slotElement = document.querySelector(`[data-slot-id="${slotId}"]`);
        if (!slotElement) return;

        // Remove all status classes
        slotElement.classList.remove('bg-green-500', 'bg-red-500', 'bg-yellow-500', 'bg-gray-400');

        // Add new status class
        switch (status) {
            case 'available':
                slotElement.classList.add('bg-green-500');
                break;
            case 'booked':
                slotElement.classList.add('bg-red-500');
                break;
            case 'blocked':
                slotElement.classList.add('bg-gray-400');
                break;
        }
    }

    function removeSlotUI(slotId) {
        const slotElement = document.querySelector(`[data-slot-id="${slotId}"]`);
        if (slotElement) {
            slotElement.remove();
        }
    }

    // Initialize WebSocket if doctor ID is available
    if (document.body.dataset.doctorId) {
        connectWebSocket();
    }

    // ============ MODAL MANAGEMENT ============

    // Close modal on backdrop click
    document.querySelectorAll('[id$="-modal"]').forEach(modal => {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                this.classList.add('hidden');
            }
        });
    });

    function closeAllModals() {
        document.querySelectorAll('[id$="-modal"]').forEach(modal => {
            modal.classList.add('hidden');
        });
        // Also close slot action menu
        const slotMenu = document.getElementById('slot-action-menu');
        if (slotMenu) {
            slotMenu.classList.add('hidden');
        }
    }

    // Make closeAllModals available globally
    window.closeAllModals = closeAllModals;

    // ============ HTMX EVENT LISTENERS ============

    // Handle successful form submissions
    document.body.addEventListener('htmx:afterRequest', function(event) {
        if (event.detail.successful) {
            // Close modals on successful submission
            closeAllModals();

            // Reset forms
            const form = event.detail.elt;
            if (form && form.reset) {
                form.reset();
            }
        }
    });

    // Handle HTMX errors
    document.body.addEventListener('htmx:responseError', function(event) {
        console.error('HTMX Error:', event.detail);
    });

    // ============ DATE HELPERS ============

    // Set minimum date for date inputs to today
    const dateInputs = document.querySelectorAll('input[type="date"]');
    const today = new Date().toISOString().split('T')[0];

    dateInputs.forEach(input => {
        if (!input.hasAttribute('data-allow-past')) {
            input.setAttribute('min', today);
        }
    });

    // ============ RECURRING CHECKBOX TOGGLE ============

    const recurringCheckbox = document.getElementById('id_is_recurring');
    if (recurringCheckbox) {
        const endDateField = document.getElementById('id_end_date');
        const endDateContainer = endDateField ? endDateField.closest('div') : null;

        function toggleEndDateVisibility() {
            if (endDateContainer) {
                if (recurringCheckbox.checked) {
                    endDateContainer.style.display = 'block';
                } else {
                    endDateContainer.style.display = 'none';
                    if (endDateField) {
                        endDateField.value = '';
                    }
                }
            }
        }

        recurringCheckbox.addEventListener('change', toggleEndDateVisibility);
        // Initial state
        toggleEndDateVisibility();
    }

    // ============ FORM VALIDATION ============

    // Validate time fields
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(e) {
            const startTime = form.querySelector('[name="start_time"]');
            const endTime = form.querySelector('[name="end_time"]');

            if (startTime && endTime && startTime.value && endTime.value) {
                if (startTime.value >= endTime.value) {
                    e.preventDefault();
                    alert('End time must be after start time.');
                    return false;
                }
            }
        });
    });

});
