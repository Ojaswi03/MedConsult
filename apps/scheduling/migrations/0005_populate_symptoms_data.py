from django.db import migrations


def populate_data(apps, schema_editor):
    """Populate body parts, conditions, symptom categories, and symptoms."""
    BodyPart = apps.get_model('scheduling', 'BodyPart')
    Condition = apps.get_model('scheduling', 'Condition')
    SymptomCategory = apps.get_model('scheduling', 'SymptomCategory')
    Symptom = apps.get_model('scheduling', 'Symptom')

    # ==========================================================================
    # BODY PARTS AND CONDITIONS
    # ==========================================================================

    body_parts_data = {
        'head_neck': [
            ('Head & Brain', [
                'Migraine', 'Tension headache', 'Concussion', 'Stroke',
                'Brain tumor', 'Epilepsy', 'Vertigo (central causes)'
            ]),
            ('Eyes', [
                'Conjunctivitis', 'Dry eye syndrome', 'Glaucoma', 'Cataract',
                'Retinal detachment', 'Diabetic retinopathy'
            ]),
            ('Ears', [
                'Otitis media / externa', 'Tinnitus', 'Hearing loss',
                'Vertigo (peripheral causes)', 'Earwax impaction'
            ]),
            ('Nose & Sinuses', [
                'Allergic rhinitis', 'Sinusitis', 'Nasal polyps',
                'Deviated septum', 'Epistaxis (nosebleeds)'
            ]),
            ('Mouth, Teeth & Throat', [
                'Pharyngitis', 'Tonsillitis', 'Dental caries', 'Gingivitis',
                'Oral ulcers', 'Laryngitis'
            ]),
            ('Neck', [
                'Cervical spondylosis', 'Muscle strain', 'Lymphadenopathy',
                'Thyroid nodules'
            ]),
        ],
        'torso': [
            ('Chest & Lungs', [
                'Asthma', 'Bronchitis', 'Pneumonia', 'COPD',
                'Pulmonary embolism', 'Lung cancer'
            ]),
            ('Heart', [
                'Hypertension', 'Coronary artery disease', 'Heart failure',
                'Arrhythmias', 'Myocardial infarction'
            ]),
            ('Abdomen', [
                'Gastritis', 'Peptic ulcer disease', 'Appendicitis',
                'Hernia', 'Irritable bowel syndrome'
            ]),
        ],
        'organs': [
            ('Liver & Gallbladder', [
                'Fatty liver disease', 'Hepatitis', 'Cirrhosis',
                'Gallstones', 'Cholecystitis'
            ]),
            ('Pancreas', [
                'Pancreatitis', 'Diabetes mellitus', 'Pancreatic cancer'
            ]),
            ('Intestines', [
                'Constipation', 'Diarrhea', "Crohn's disease",
                'Ulcerative colitis', 'Intestinal obstruction'
            ]),
            ('Kidneys & Urinary Tract', [
                'Urinary tract infection', 'Kidney stones',
                'Chronic kidney disease', 'Acute kidney injury'
            ]),
            ('Male Reproductive System', [
                'Erectile dysfunction', 'Prostatitis',
                'Benign prostatic hyperplasia', 'Testicular torsion'
            ]),
            ('Female Reproductive System', [
                'Polycystic ovary syndrome', 'Endometriosis',
                'Uterine fibroids', 'Pelvic inflammatory disease'
            ]),
        ],
        'limbs': [
            ('Bones & Joints', [
                'Osteoarthritis', 'Rheumatoid arthritis', 'Osteoporosis',
                'Fractures', 'Gout'
            ]),
            ('Muscles & Tendons', [
                'Muscle strain', 'Tendinitis', 'Fibromyalgia', 'Myositis'
            ]),
        ],
        'systems': [
            ('Skin', [
                'Eczema', 'Psoriasis', 'Acne', 'Fungal infections', 'Skin cancer'
            ]),
            ('Nervous System', [
                'Peripheral neuropathy', 'Multiple sclerosis',
                "Parkinson's disease", 'Sciatica'
            ]),
            ('Immune System', [
                'Autoimmune disorders', 'Allergies', 'Immunodeficiency disorders'
            ]),
        ],
    }

    order = 0
    for category, body_parts in body_parts_data.items():
        for body_part_name, conditions in body_parts:
            order += 1
            body_part = BodyPart.objects.create(
                name=body_part_name,
                category=category,
                display_order=order,
                is_active=True
            )
            cond_order = 0
            for condition_name in conditions:
                cond_order += 1
                Condition.objects.create(
                    body_part=body_part,
                    name=condition_name,
                    display_order=cond_order,
                    is_active=True
                )

    # ==========================================================================
    # SYMPTOM CATEGORIES AND SYMPTOMS
    # ==========================================================================

    symptoms_data = {
        'Pain-Related': [
            'Headache', 'Chest pain', 'Abdominal pain', 'Joint pain',
            'Muscle pain', 'Nerve pain (burning, tingling)'
        ],
        'General / Systemic': [
            'Fever', 'Fatigue', 'Weight loss', 'Weight gain',
            'Night sweats', 'Weakness'
        ],
        'Respiratory': [
            'Shortness of breath', 'Cough', 'Wheezing',
            'Chest tightness', 'Coughing blood'
        ],
        'Cardiovascular': [
            'Palpitations', 'Dizziness', 'Fainting',
            'Swelling of legs', 'Cold extremities'
        ],
        'Gastrointestinal': [
            'Nausea', 'Vomiting', 'Diarrhea', 'Constipation',
            'Bloating', 'Blood in stool'
        ],
        'Neurological': [
            'Numbness', 'Tingling', 'Seizures', 'Tremors',
            'Memory loss', 'Loss of coordination'
        ],
        'Urinary': [
            'Painful urination', 'Frequent urination', 'Blood in urine',
            'Urinary retention', 'Incontinence'
        ],
        'Reproductive': [
            'Irregular periods', 'Pelvic pain', 'Erectile dysfunction',
            'Infertility', 'Abnormal discharge'
        ],
        'Skin & Hair': [
            'Rash', 'Itching', 'Hair loss', 'Skin discoloration',
            'Non-healing wounds'
        ],
        'Psychological / Cognitive': [
            'Anxiety', 'Depression', 'Insomnia', 'Mood swings', 'Confusion'
        ],
    }

    cat_order = 0
    for category_name, symptoms in symptoms_data.items():
        cat_order += 1
        category = SymptomCategory.objects.create(
            name=category_name,
            display_order=cat_order,
            is_active=True
        )
        sym_order = 0
        for symptom_name in symptoms:
            sym_order += 1
            Symptom.objects.create(
                category=category,
                name=symptom_name,
                display_order=sym_order,
                is_active=True
            )


def reverse_data(apps, schema_editor):
    """Remove all populated data."""
    BodyPart = apps.get_model('scheduling', 'BodyPart')
    SymptomCategory = apps.get_model('scheduling', 'SymptomCategory')
    BodyPart.objects.all().delete()
    SymptomCategory.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0004_bodypart_symptomcategory_condition_symptom'),
    ]

    operations = [
        migrations.RunPython(populate_data, reverse_data),
    ]
