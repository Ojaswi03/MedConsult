"""
Builds the knowledge graph nodes + edges from ORM state and git history.
No PHI - only IDs, roles, statuses, counts, and timestamps.
"""
import subprocess
import logging
from datetime import datetime, timezone as dt_timezone
from django.utils import timezone

logger = logging.getLogger(__name__)


def _run_git(cmd):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            cwd=_get_base_dir()
        )
        return result.stdout.strip() if result.returncode == 0 else ''
    except Exception:
        return ''


def _get_base_dir():
    from django.conf import settings
    return str(settings.BASE_DIR)


def _safe_isoformat(dt):
    if dt is None:
        return None
    if hasattr(dt, 'isoformat'):
        return dt.isoformat()
    return str(dt)


# ── Node builders ────────────────────────────────────────────────────────────

def _build_project_node():
    git_head = _run_git(['git', 'rev-parse', 'HEAD'])
    branch = _run_git(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
    last_msg = _run_git(['git', 'log', '-1', '--pretty=%s'])
    last_date = _run_git(['git', 'log', '-1', '--pretty=%ci'])
    return {
        'id': 'project_medconsult',
        'type': 'project',
        'label': 'MedConsult',
        'data': {
            'git_head': git_head[:7] if git_head else '',
            'git_head_full': git_head,
            'branch': branch,
            'last_commit_message': last_msg,
            'last_commit_date': last_date,
            'framework': 'Django 5.2',
        },
    }


def _build_app_nodes():
    from django.apps import apps as django_apps
    nodes = []
    local_apps = [
        'accounts', 'scheduling', 'dashboard', 'adminpanel',
        'support', 'payments', 'messaging', 'consultations',
        'api', 'knowledge_graph',
    ]
    for app_label in local_apps:
        try:
            app_config = django_apps.get_app_config(app_label)
            model_names = [m.__name__ for m in app_config.get_models()]
            nodes.append({
                'id': f'app_{app_label}',
                'type': 'app',
                'label': app_label,
                'data': {
                    'models': model_names,
                    'model_count': len(model_names),
                },
            })
        except LookupError:
            pass
    return nodes


def _build_user_nodes():
    from apps.accounts.models import User
    nodes = []
    for user in User.objects.only('id', 'role', 'is_email_verified', 'is_active', 'date_joined'):
        nodes.append({
            'id': f'user_{user.id}',
            'type': 'user',
            'label': user.role,
            'data': {
                'role': user.role,
                'is_email_verified': user.is_email_verified,
                'is_active': user.is_active,
                'joined': _safe_isoformat(user.date_joined),
            },
        })
    return nodes


def _build_appointment_nodes():
    from apps.scheduling.models import Appointment
    nodes = []
    for appt in Appointment.objects.only('id', 'status', 'created_at'):
        nodes.append({
            'id': f'appointment_{appt.id}',
            'type': 'appointment',
            'label': appt.status,
            'data': {
                'status': appt.status,
                'created_at': _safe_isoformat(appt.created_at),
            },
        })
    return nodes


def _build_slot_nodes():
    from apps.scheduling.models import Slot
    nodes = []
    for slot in Slot.objects.only('id', 'appointment_type', 'start_datetime', 'doctor_id', 'is_booked', 'is_blocked'):
        if slot.is_booked:
            status = 'booked'
        elif slot.is_blocked:
            status = 'blocked'
        else:
            status = 'available'
        nodes.append({
            'id': f'slot_{slot.id}',
            'type': 'slot',
            'label': status,
            'data': {
                'status': status,
                'type': slot.appointment_type,
                'start_datetime': _safe_isoformat(slot.start_datetime),
                'doctor_id': slot.doctor_id,
            },
        })
    return nodes


def _build_conversation_nodes():
    try:
        from apps.messaging.models import Conversation
        nodes = []
        for conv in Conversation.objects.only('id', 'patient_id', 'doctor_id', 'is_active', 'created_at'):
            msg_count = conv.messages.count() if hasattr(conv, 'messages') else 0
            nodes.append({
                'id': f'conversation_{conv.id}',
                'type': 'conversation',
                'label': 'chat',
                'data': {
                    'patient_id': conv.patient_id,
                    'doctor_id': conv.doctor_id,
                    'is_active': conv.is_active,
                    'message_count': msg_count,
                    'created_at': _safe_isoformat(conv.created_at),
                },
            })
        return nodes
    except Exception as e:
        logger.warning("Could not build conversation nodes: %s", e)
        return []


def _build_payment_nodes():
    try:
        from apps.payments.models import Payment
        nodes = []
        for payment in Payment.objects.only('id', 'status', 'amount', 'created_at'):
            nodes.append({
                'id': f'payment_{payment.id}',
                'type': 'payment',
                'label': payment.status,
                'data': {
                    'status': payment.status,
                    'amount': str(payment.amount),
                    'created_at': _safe_isoformat(payment.created_at),
                },
            })
        return nodes
    except Exception as e:
        logger.warning("Could not build payment nodes: %s", e)
        return []


def _build_system_health_node():
    try:
        from apps.accounts.models import DoctorProfile
        from apps.scheduling.models import Slot, Appointment

        pending_verifications = DoctorProfile.objects.filter(verification_status='pending').count()
        active_slots = Slot.objects.filter(is_booked=False, is_blocked=False).count()
        scheduled_appointments = Appointment.objects.filter(status='scheduled').count()

        return {
            'id': 'system_health',
            'type': 'system_health',
            'label': 'System Health',
            'data': {
                'pending_verifications': pending_verifications,
                'active_slots': active_slots,
                'scheduled_appointments': scheduled_appointments,
                'checked_at': _safe_isoformat(timezone.now()),
            },
        }
    except Exception as e:
        logger.warning("Could not build system_health node: %s", e)
        return None


def _build_git_commit_nodes(limit=20):
    log = _run_git([
        'git', 'log', f'-{limit}',
        '--pretty=format:%H|%s|%ci|%an',
        '--name-only',
    ])
    if not log:
        return []

    nodes = []
    entries = log.split('\n\n')
    for entry in entries:
        lines = [l for l in entry.strip().split('\n') if l]
        if not lines:
            continue
        parts = lines[0].split('|', 3)
        if len(parts) < 3:
            continue
        commit_hash, message, date = parts[0], parts[1], parts[2]
        files_changed = lines[1:] if len(lines) > 1 else []
        nodes.append({
            'id': f'git_commit_{commit_hash[:7]}',
            'type': 'git_commit',
            'label': commit_hash[:7],
            'data': {
                'hash': commit_hash[:7],
                'hash_full': commit_hash,
                'message': message,
                'date': date,
                'files_changed': files_changed[:10],
                'files_count': len(files_changed),
            },
        })
    return nodes


# ── Edge builders ────────────────────────────────────────────────────────────

def _build_edges(user_nodes, appointment_nodes, slot_nodes, payment_nodes):
    edges = []

    # appointment → slot (via appointment.slot_id)
    try:
        from apps.scheduling.models import Appointment
        for appt in Appointment.objects.only('id', 'slot_id', 'patient_id'):
            if appt.slot_id:
                edges.append({
                    'id': f'e_appointment_{appt.id}_slot_{appt.slot_id}',
                    'source': f'appointment_{appt.id}',
                    'target': f'slot_{appt.slot_id}',
                    'label': 'books',
                })
            if appt.patient_id:
                edges.append({
                    'id': f'e_user_{appt.patient_id}_appointment_{appt.id}',
                    'source': f'user_{appt.patient_id}',
                    'target': f'appointment_{appt.id}',
                    'label': 'booked',
                })
    except Exception as e:
        logger.warning("Could not build appointment edges: %s", e)

    # payment → appointment
    try:
        from apps.payments.models import Payment
        for payment in Payment.objects.only('id', 'appointment_id'):
            if payment.appointment_id:
                edges.append({
                    'id': f'e_payment_{payment.id}_appointment_{payment.appointment_id}',
                    'source': f'payment_{payment.id}',
                    'target': f'appointment_{payment.appointment_id}',
                    'label': 'paid_for',
                })
    except Exception as e:
        logger.warning("Could not build payment edges: %s", e)

    return edges


# ── Summary builder ──────────────────────────────────────────────────────────

def _build_summary():
    summary = {}
    try:
        from apps.accounts.models import User
        summary['total_users'] = User.objects.count()
        summary['patients'] = User.objects.filter(role='patient').count()
        summary['doctors'] = User.objects.filter(role='doctor').count()
        summary['admins'] = User.objects.filter(role__in=('platform_owner', 'platform_admin')).count()
    except Exception:
        pass
    try:
        from apps.accounts.models import DoctorProfile
        summary['pending_verifications'] = DoctorProfile.objects.filter(verification_status='pending').count()
    except Exception:
        pass
    try:
        from apps.scheduling.models import Slot, Appointment
        summary['active_slots'] = Slot.objects.filter(is_booked=False, is_blocked=False).count()
        summary['total_appointments'] = Appointment.objects.count()
        summary['scheduled_appointments'] = Appointment.objects.filter(status='scheduled').count()
    except Exception:
        pass
    try:
        from apps.payments.models import Payment
        summary['total_payments'] = Payment.objects.count()
    except Exception:
        pass
    try:
        from apps.messaging.models import Conversation
        summary['total_conversations'] = Conversation.objects.count()
    except Exception:
        pass
    return summary


# ── App structure builder ────────────────────────────────────────────────────

def _build_app_structure():
    from django.apps import apps as django_apps
    structure = {}
    local_apps = [
        'accounts', 'scheduling', 'dashboard', 'adminpanel',
        'support', 'payments', 'messaging', 'consultations',
        'api', 'knowledge_graph',
    ]
    for app_label in local_apps:
        try:
            app_config = django_apps.get_app_config(app_label)
            structure[app_label] = {
                'models': [m.__name__ for m in app_config.get_models()],
            }
        except LookupError:
            pass
    return structure


# ── Main entry point ─────────────────────────────────────────────────────────

def build_graph(quick=False):
    """
    Build the full knowledge graph dict.
    quick=True: only project + system_health (fast, for git hook).
    """
    import django
    django_version = django.get_version()

    git_head = _run_git(['git', 'rev-parse', 'HEAD'])

    project_node = _build_project_node()

    if quick:
        system_node = _build_system_health_node()
        nodes = [project_node]
        if system_node:
            nodes.append(system_node)
        return {
            'metadata': {
                'git_head': git_head,
                'generated_at': timezone.now().isoformat(),
                'django_version': django_version,
                'quick': True,
            },
            'nodes': nodes,
            'edges': [],
        }

    user_nodes = _build_user_nodes()
    appointment_nodes = _build_appointment_nodes()
    slot_nodes = _build_slot_nodes()
    conversation_nodes = _build_conversation_nodes()
    payment_nodes = _build_payment_nodes()
    system_node = _build_system_health_node()

    nodes = (
        [project_node]
        + user_nodes
        + appointment_nodes
        + slot_nodes
        + conversation_nodes
        + payment_nodes
    )
    if system_node:
        nodes.append(system_node)

    edges = _build_edges(user_nodes, appointment_nodes, slot_nodes, payment_nodes)

    recent_commits = []
    try:
        log = _run_git(['git', 'log', '--oneline', '--format=%H|%s|%ai', '-5'])
        for line in log.splitlines():
            parts = line.split('|', 2)
            if len(parts) == 3:
                recent_commits.append({'hash': parts[0][:7], 'message': parts[1], 'date': parts[2]})
    except Exception:
        pass

    return {
        'metadata': {
            'git_head': git_head,
            'generated_at': timezone.now().isoformat(),
            'django_version': django_version,
            'quick': False,
        },
        'summary': _build_summary(),
        'recent_changes': recent_commits,
        'app_structure': _build_app_structure(),
        'nodes': nodes,
        'edges': edges,
    }
