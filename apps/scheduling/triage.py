"""
Clinical triage helper for symptom intake.

NOT a diagnostic tool — only detects emergency red flags that require
immediate in-person care and must block telehealth booking.
"""

# Red-flag symptom/condition names that indicate potential emergencies.
# Matched case-insensitively against selected symptom names and reason text.
EMERGENCY_KEYWORDS = frozenset([
    # Cardiac
    'chest pain', 'chest tightness', 'chest pressure',
    # Stroke
    'sudden numbness', 'sudden weakness', 'face drooping', 'arm weakness',
    'speech difficulty', 'sudden confusion', 'sudden vision', 'severe headache',
    # Respiratory
    'difficulty breathing', 'shortness of breath', 'can\'t breathe',
    'breathing difficulty', 'choking',
    # Bleeding
    'severe bleeding', 'uncontrolled bleeding', 'coughing blood',
    'vomiting blood', 'blood in stool',
    # Mental health crisis
    'suicidal', 'suicide', 'self-harm', 'self harm', 'hurting myself',
    # Overdose
    'overdose',
    # Loss of consciousness
    'unconscious', 'passed out', 'fainting',
    # Anaphylaxis
    'anaphylaxis', 'severe allergic reaction', 'throat swelling',
])

EMERGENCY_MESSAGE = (
    "⚠️ Based on your symptoms, you may need immediate emergency care. "
    "Please call 911 or go to the nearest emergency room immediately. "
    "Do not use telehealth for emergencies."
)

DISCLAIMER = (
    "This is not a diagnosis. MedConsult helps connect you with licensed doctors "
    "for non-emergency consultations. Always seek emergency care for life-threatening symptoms."
)


def check_emergency_flags(symptom_names: list[str], reason_text: str = '') -> dict:
    """
    Check whether any selected symptoms or free-text reason contain emergency keywords.

    Returns:
        {
            'is_emergency': bool,
            'message': str,       # shown to patient if emergency
            'disclaimer': str,    # always shown
            'matched_flags': list # which keywords matched
        }
    """
    combined = ' '.join(symptom_names).lower() + ' ' + reason_text.lower()
    matched = [kw for kw in EMERGENCY_KEYWORDS if kw in combined]
    return {
        'is_emergency': bool(matched),
        'message': EMERGENCY_MESSAGE if matched else '',
        'disclaimer': DISCLAIMER,
        'matched_flags': matched,
    }
