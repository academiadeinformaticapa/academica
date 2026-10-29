from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import (db, GuardianStudent, User, StudentGrade, Subject,
                    GradeRecord, Attendance, StudentExcludedSubject,
                    Message, Assignment, TeacherSubject, TeacherProfile)
from functools import wraps

guardian_bp = Blueprint('guardian', __name__)


def guardian_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != 'guardian':
            flash('Acceso denegado', 'danger')
            return redirect(url_for('auth.index'))
        return f(*args, **kwargs)
    return decorated_function


@guardian_bp.route('/')
@login_required
@guardian_required
def dashboard():
    guardian_students = GuardianStudent.query.filter_by(guardian_id=current_user.id).all()
    students = [gs.student for gs in guardian_students]

    # Últimos mensajes recibidos
    received = Message.query.filter_by(receiver_id=current_user.id).order_by(
        Message.timestamp.desc()
    ).limit(5).all()

    # Mensajes enviados
    sent = Message.query.filter_by(sender_id=current_user.id).order_by(
        Message.timestamp.desc()
    ).limit(5).all()

    return render_template('guardian_dashboard.html',
                           students=students,
                           received_messages=received,
                           sent_messages=sent,
                           received_count=len(received),
                           sent_count=len(sent))


@guardian_bp.route('/student/<int:student_id>')
@login_required
@guardian_required
def view_student(student_id):
    # Verificar que el estudiante pertenezca al acudiente
    gs = GuardianStudent.query.filter_by(
        guardian_id=current_user.id, student_id=student_id
    ).first()
    if not gs:
        flash('No tienes acceso a este estudiante', 'danger')
        return redirect(url_for('guardian.dashboard'))

    student = User.query.get(student_id)
    student_grade = StudentGrade.query.filter_by(student_id=student.id).first()
    if not student_grade:
        flash('El estudiante no tiene grado asignado', 'warning')
        return redirect(url_for('guardian.dashboard'))

    grade = student_grade.grade

    # Materias del grado, menos las que le fueron quitadas y menos las archivadas
    all_subjects = Subject.query.filter_by(grade_id=grade.id, archived=False).all()
    
    excluded_ids = {e.subject_id for e in StudentExcludedSubject.query.filter_by(
        student_id=student.id
    ).all()}
    subjects = [s for s in all_subjects if s.id not in excluded_ids]

    # Para cada materia, obtener tareas, notas y asistencia
    subject_data = []
    for subject in subjects:
        assignments = subject.assignments
        grade_records = {gr.assignment_id: gr.grade for gr in GradeRecord.query.filter(
            GradeRecord.student_id == student.id,
            GradeRecord.assignment_id.in_([a.id for a in assignments])
        ).all()}
        attendances = Attendance.query.filter_by(
            student_id=student.id, subject_id=subject.id
        ).all()
        # Lista de profesores de esa materia
        teachers = TeacherSubject.query.filter_by(subject_id=subject.id).all()

        subject_data.append({
            'subject': subject,
            'assignments': assignments,
            'grade_records': grade_records,
            'attendances': attendances,
            'teachers': [t.teacher for t in teachers]
        })

    return render_template('guardian_view_student.html',
                           student=student, grade=grade,
                           subject_data=subject_data)

# ============================================
# MENSAJES DEL ACUDIENTE
# ============================================
@guardian_bp.route('/messages')
@login_required
@guardian_required
def messages():
    received = Message.query.filter_by(receiver_id=current_user.id).order_by(
        Message.timestamp.desc()
    ).all()
    sent = Message.query.filter_by(sender_id=current_user.id).order_by(
        Message.timestamp.desc()
    ).all()
    return render_template('guardian_messages.html',
                           received=received, sent=sent)


@guardian_bp.route('/send_message', methods=['GET', 'POST'])
@login_required
@guardian_required
def send_message():
    """Enviar mensaje al directivo o a un profesor."""
    # Traer todos los profesores de la institución del acudiente
    school_id = current_user.school_id
    teachers = User.query.filter_by(school_id=school_id, role='teacher').all()
    directors = User.query.filter_by(school_id=school_id, role='school').all()

    if request.method == 'POST':
        receiver_id = request.form.get('receiver_id')
        subject = request.form.get('subject', '').strip()
        body = request.form.get('body', '').strip()

        if not receiver_id or not subject or not body:
            flash('Todos los campos son obligatorios', 'danger')
            return redirect(url_for('guardian.send_message'))

        receiver = User.query.get(receiver_id)
        if not receiver or receiver.school_id != school_id:
            flash('Destinatario inválido', 'danger')
            return redirect(url_for('guardian.send_message'))

        msg = Message(
            sender_id=current_user.id,
            receiver_id=receiver.id,
            subject=subject,
            body=body
        )
        db.session.add(msg)
        db.session.commit()
        flash(f'Mensaje enviado a {receiver.name}', 'success')
        return redirect(url_for('guardian.messages'))

    return render_template('guardian_send_message.html',
                           teachers=teachers, directors=directors)


@guardian_bp.route('/message/<int:message_id>')
@login_required
@guardian_required
def view_message(message_id):
    msg = Message.query.get_or_404(message_id)
    if msg.sender_id != current_user.id and msg.receiver_id != current_user.id:
        flash('No tienes acceso a este mensaje', 'danger')
        return redirect(url_for('guardian.messages'))
    return render_template('guardian_view_message.html', msg=msg)

@guardian_bp.route('/teacher/<int:teacher_id>')
@login_required
@guardian_required
def view_teacher(teacher_id):
    teacher = User.query.get_or_404(teacher_id)
    if teacher.role != 'teacher':
        flash('Usuario no válido', 'danger')
        return redirect(url_for('guardian.dashboard'))
    
    profile = TeacherProfile.query.filter_by(user_id=teacher.id).first()
    if not profile or not profile.show_contact:
        flash('El profesor no ha compartido su información de contacto.', 'warning')
        return redirect(url_for('guardian.dashboard'))
        
    return render_template('shared_teacher_profile.html', teacher=teacher, profile=profile, role='guardian') 