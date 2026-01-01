/**
 * Signup Wizard JavaScript
 * Handles:
 * - Camera/Microphone testing (cross-browser compatible)
 * - Gender "Other" field toggle
 * - Date formatting (MM/DD/YYYY)
 * - Phone number formatting
 * - Form validation feedback
 */

document.addEventListener('DOMContentLoaded', function() {

    // ============ GENDER OTHER FIELD TOGGLE ============
    const genderRadios = document.querySelectorAll('input[name="gender"]');
    const genderOtherContainer = document.getElementById('gender-other-container');

    if (genderRadios.length && genderOtherContainer) {
        function toggleGenderOther() {
            const selectedGender = document.querySelector('input[name="gender"]:checked');
            if (selectedGender && selectedGender.value === 'other') {
                genderOtherContainer.classList.remove('hidden');
                genderOtherContainer.querySelector('input').required = true;
            } else {
                genderOtherContainer.classList.add('hidden');
                genderOtherContainer.querySelector('input').required = false;
            }
        }

        genderRadios.forEach(radio => {
            radio.addEventListener('change', toggleGenderOther);
        });

        // Check on load
        toggleGenderOther();
    }

    // ============ DATE FORMAT (MM/DD/YYYY) ============
    const dobInput = document.getElementById('date_of_birth') || document.querySelector('input[name="date_of_birth"]');
    if (dobInput && dobInput.type === 'text') {
        dobInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            let formatted = '';

            if (value.length > 0) {
                // Month
                formatted = value.slice(0, 2);
                if (value.length >= 2) {
                    formatted += '/' + value.slice(2, 4);
                }
                if (value.length >= 4) {
                    formatted += '/' + value.slice(4, 8);
                }
            }

            e.target.value = formatted;
        });

        // Validate date on blur
        dobInput.addEventListener('blur', function(e) {
            const value = e.target.value;
            const regex = /^(0[1-9]|1[0-2])\/(0[1-9]|[12][0-9]|3[01])\/\d{4}$/;

            if (value && !regex.test(value)) {
                e.target.classList.add('border-red-500');
            } else {
                e.target.classList.remove('border-red-500');
            }
        });
    }

    // ============ PHONE NUMBER FORMATTING ============
    const phoneInput = document.getElementById('phone') || document.querySelector('input[name="phone"]');
    if (phoneInput) {
        phoneInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            let formatted = '';

            if (value.length > 0) {
                if (value.length <= 3) {
                    formatted = '(' + value;
                } else if (value.length <= 6) {
                    formatted = '(' + value.slice(0, 3) + ') ' + value.slice(3);
                } else {
                    formatted = '(' + value.slice(0, 3) + ') ' + value.slice(3, 6) + '-' + value.slice(6, 10);
                }
            }

            e.target.value = formatted;
        });
    }

    // ============ CAMERA/MICROPHONE TESTING ============
    const testMediaBtn = document.getElementById('test-media-btn');
    const videoPreview = document.getElementById('video-preview');
    const mediaPlaceholder = document.getElementById('media-placeholder');
    const testStatus = document.getElementById('test-status');
    const testOverlay = document.getElementById('test-overlay');
    const audioLevelContainer = document.getElementById('audio-level-container');
    const audioMeter = document.getElementById('audio-meter');
    const testResult = document.getElementById('test-result');
    const browserWarning = document.getElementById('browser-warning');
    const browserWarningMessage = document.getElementById('browser-warning-message');
    const cameraMicTestedCheckbox = document.querySelector('input[name="camera_mic_tested"]');

    let mediaStream = null;
    let audioContext = null;
    let analyser = null;
    let animationId = null;
    let isTestRunning = false;

    // Check browser compatibility
    function checkBrowserCompatibility() {
        const issues = [];

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            issues.push('Your browser does not support camera/microphone access. Please use a modern browser like Chrome, Firefox, Safari, or Edge.');
        }

        if (!window.AudioContext && !window.webkitAudioContext) {
            issues.push('Your browser does not support audio processing.');
        }

        // Check for secure context (HTTPS or localhost)
        if (!window.isSecureContext) {
            issues.push('Camera/microphone access requires a secure connection (HTTPS). Please access this page via HTTPS.');
        }

        return issues;
    }

    // Show browser warning if needed
    function showBrowserWarning() {
        const issues = checkBrowserCompatibility();

        if (issues.length > 0 && browserWarning && browserWarningMessage) {
            browserWarningMessage.textContent = issues.join(' ');
            browserWarning.classList.remove('hidden');

            if (testMediaBtn) {
                testMediaBtn.disabled = true;
                testMediaBtn.classList.add('opacity-50', 'cursor-not-allowed');
            }
            return true;
        }
        return false;
    }

    // Start media test
    async function startMediaTest() {
        if (isTestRunning) {
            stopMediaTest();
            return;
        }

        try {
            isTestRunning = true;

            // Show loading overlay
            if (testOverlay) {
                testOverlay.classList.remove('hidden');
            }

            if (testStatus) {
                testStatus.innerHTML = '<span class="text-blue-600">Requesting access...</span>';
            }

            // Request camera and microphone access
            const constraints = {
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: 'user'
                },
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true
                }
            };

            mediaStream = await navigator.mediaDevices.getUserMedia(constraints);

            // Hide overlay
            if (testOverlay) {
                testOverlay.classList.add('hidden');
            }

            // Show video preview
            if (videoPreview) {
                videoPreview.srcObject = mediaStream;
                videoPreview.classList.remove('hidden');
            }
            if (mediaPlaceholder) {
                mediaPlaceholder.classList.add('hidden');
            }

            // Setup audio level meter
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            audioContext = new AudioContextClass();

            // Handle autoplay policy (especially in Safari)
            if (audioContext.state === 'suspended') {
                await audioContext.resume();
            }

            const source = audioContext.createMediaStreamSource(mediaStream);
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);

            if (audioLevelContainer) {
                audioLevelContainer.classList.remove('hidden');
            }

            // Animate audio meter
            function updateAudioMeter() {
                if (!analyser) return;

                const dataArray = new Uint8Array(analyser.frequencyBinCount);
                analyser.getByteFrequencyData(dataArray);

                // Calculate average volume
                const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
                const percentage = Math.min(100, (average / 128) * 100);

                if (audioMeter) {
                    audioMeter.style.width = percentage + '%';

                    // Change color based on level
                    if (percentage > 60) {
                        audioMeter.classList.remove('bg-green-500', 'bg-yellow-500');
                        audioMeter.classList.add('bg-red-500');
                    } else if (percentage > 30) {
                        audioMeter.classList.remove('bg-green-500', 'bg-red-500');
                        audioMeter.classList.add('bg-yellow-500');
                    } else {
                        audioMeter.classList.remove('bg-yellow-500', 'bg-red-500');
                        audioMeter.classList.add('bg-green-500');
                    }
                }

                animationId = requestAnimationFrame(updateAudioMeter);
            }
            updateAudioMeter();

            // Update UI
            if (testStatus) {
                testStatus.innerHTML = '<span class="text-green-600">Camera and microphone working!</span>';
            }

            if (testMediaBtn) {
                testMediaBtn.innerHTML = `
                    <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
                    </svg>
                    Stop Test
                `;
                testMediaBtn.classList.remove('bg-blue-600', 'hover:bg-blue-700');
                testMediaBtn.classList.add('bg-gray-600', 'hover:bg-gray-700');
            }

            // Show success result
            if (testResult) {
                testResult.classList.remove('hidden');
            }

            // Mark as tested
            if (cameraMicTestedCheckbox) {
                cameraMicTestedCheckbox.checked = true;
            }

        } catch (error) {
            console.error('Media access error:', error);
            isTestRunning = false;

            if (testOverlay) {
                testOverlay.classList.add('hidden');
            }

            let errorMessage = 'Unable to access camera/microphone.';

            if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
                errorMessage = 'Permission denied. Please allow camera and microphone access in your browser settings.';
            } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
                errorMessage = 'No camera or microphone found on this device.';
            } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
                errorMessage = 'Camera or microphone is in use by another application.';
            } else if (error.name === 'OverconstrainedError') {
                errorMessage = 'Camera does not meet the required specifications.';
            } else if (error.name === 'SecurityError') {
                errorMessage = 'Security error. Please access this page via HTTPS.';
            }

            if (testStatus) {
                testStatus.innerHTML = `<span class="text-red-600">${errorMessage}</span>`;
            }
        }
    }

    // Stop media test
    function stopMediaTest() {
        isTestRunning = false;

        // Stop all media tracks
        if (mediaStream) {
            mediaStream.getTracks().forEach(track => track.stop());
            mediaStream = null;
        }

        // Close audio context
        if (audioContext) {
            audioContext.close();
            audioContext = null;
            analyser = null;
        }

        // Cancel animation
        if (animationId) {
            cancelAnimationFrame(animationId);
            animationId = null;
        }

        // Reset UI
        if (videoPreview) {
            videoPreview.srcObject = null;
            videoPreview.classList.add('hidden');
        }
        if (mediaPlaceholder) {
            mediaPlaceholder.classList.remove('hidden');
        }
        if (audioLevelContainer) {
            audioLevelContainer.classList.add('hidden');
        }
        if (audioMeter) {
            audioMeter.style.width = '0%';
        }
        if (testStatus) {
            testStatus.innerHTML = '';
        }

        if (testMediaBtn) {
            testMediaBtn.innerHTML = `
                <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                          d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                Start Test
            `;
            testMediaBtn.classList.remove('bg-gray-600', 'hover:bg-gray-700');
            testMediaBtn.classList.add('bg-blue-600', 'hover:bg-blue-700');
        }
    }

    // Initialize camera/mic test
    if (testMediaBtn) {
        // Check browser compatibility on load
        const hasIssues = showBrowserWarning();

        if (!hasIssues) {
            testMediaBtn.addEventListener('click', function(e) {
                e.preventDefault();
                if (isTestRunning) {
                    stopMediaTest();
                } else {
                    startMediaTest();
                }
            });
        }
    }

    // Cleanup on page unload
    window.addEventListener('beforeunload', function() {
        stopMediaTest();
    });

    // Also cleanup when navigating away (for single-page apps)
    window.addEventListener('pagehide', function() {
        stopMediaTest();
    });

    // ============ ROUTING NUMBER VALIDATION ============
    const routingInput = document.querySelector('input[name="routing_number"]');
    if (routingInput) {
        routingInput.addEventListener('input', function(e) {
            // Only allow digits
            e.target.value = e.target.value.replace(/\D/g, '').slice(0, 9);
        });
    }

    // ============ FILE UPLOAD PREVIEW ============
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                // Create or update file name display
                let fileInfo = input.parentElement.querySelector('.file-info');
                if (!fileInfo) {
                    fileInfo = document.createElement('p');
                    fileInfo.className = 'file-info mt-2 text-sm text-gray-600';
                    input.parentElement.appendChild(fileInfo);
                }

                const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
                fileInfo.innerHTML = `
                    <span class="font-medium">${file.name}</span>
                    <span class="text-gray-400">(${sizeMB} MB)</span>
                `;

                // Validate file size
                if (file.size > 10 * 1024 * 1024) {
                    fileInfo.innerHTML += '<br><span class="text-red-600">File is too large. Maximum size is 10MB.</span>';
                }
            }
        });
    });

});
