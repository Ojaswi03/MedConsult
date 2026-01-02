/**
 * Availability Calendar JavaScript
 * Handles modal management and calendar interactions for doctor availability.
 */

document.addEventListener('DOMContentLoaded', function() {

    // ============ MODAL MANAGEMENT ============

    // Close modal on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeAllModals();
        }
    });

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
