from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import (db, StudentGrade, Subject, GradeRecord, Attendance,
                    Assignment, Message, StudentExcludedSubject,
                    Forum, ForumPost, SubjectFile, Announcement,
                    Exercise, ExerciseSubmission,
                    ExerciseQuestion, QuestionOption, QuestionAnswer,
                    User, TeacherProfile, ForumGrade, StudentFileView, StudentForumView,
                    AssignmentSubmission, CustomColumn, CustomGrade, SchoolPeriod)
from datetime import datetime, timedelta
from functools import wraps
import os
from werkzeug.utils import secure_filename

student_bp = Blueprint('student', __name__)


def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != 'student':
            flash('Acceso denegado', 'danger')
            return redirect(url_for('auth.index'))
        return f(*args, **kwargs)
    return decorated_function


def allowed_file(filename):
    ALLOWED_EXT = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
                   'txt', 'png', 'jpg', 'jpeg', 'zip'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def get_school_periods(school_id):
    return SchoolPeriod.query.filter_by(school_id=school_id).order_by(SchoolPeriod.start_date).all()

@student_bp.route('/')
@login_required
@student_required
def dashboard():
    student_grade = StudentGrade.query.filter_by(student_id=current_user.id).first()
    if not student_grade:
        flash('No estás asignado a un grado', 'danger')
        return redirect(url_for('auth.index'))

    grade = student_grade.grade
    # Aquí está el filtro para no mostrar las archivadas
    all_subjects = Subject.query.filter_by(grade_id=grade.id, archived=False).all()
    
    excluded_ids = {e.subject_id for e in StudentExcludedSubject.query.filter_by(
        student_id=current_user.id
    ).all()}
    subjects = [s for s in all_subjects if s.id not in excluded_ids]

    subject_ids = [s.id for s in subjects]

    # ============================================
    # PENDIENTES: tareas (Assignment) + ejercicios (Exercise)
    # ============================================
    pending_items = []

    if subject_ids:
        # 1) Tareas tradicionales (Assignment)
        all_assignments = Assignment.query.filter(
            Assignment.subject_id.in_(subject_ids)
        ).all()

        graded_ids = {gr.assignment_id for gr in GradeRecord.query.filter_by(
            student_id=current_user.id
        ).all()}

        for a in all_assignments:
            if a.id not in graded_ids:
                pending_items.append({
                    'kind': 'assignment',
                    'icon': '📝',
                    'title': a.title,
                    'type_label': a.type.capitalize() if a.type else 'Tarea',
                    'subject_name': a.subject.name,
                    'due_date': a.due_date,
                    'link': url_for('student.view_subject', subject_id=a.subject_id),
                    'action_label': 'Ver tarea'
                })

        # 2) Ejercicios / parciales (Exercise)
        all_exercises = Exercise.query.filter(
            Exercise.subject_id.in_(subject_ids)
        ).all()

        exercise_ids = [ex.id for ex in all_exercises]
        submissions = {sub.exercise_id: sub for sub in ExerciseSubmission.query.filter(
            ExerciseSubmission.student_id == current_user.id,
            ExerciseSubmission.exercise_id.in_(exercise_ids)
        ).all()} if exercise_ids else {}

        for ex in all_exercises:
            sub = submissions.get(ex.id)
            max_attempts = ex.max_attempts or 1

            if not sub:
                pending_items.append({
                    'kind': 'exercise',
                    'icon': '✏️',
                    'title': ex.title,
                    'type_label': 'Parcial/Ejercicio',
                    'subject_name': ex.subject.name,
                    'due_date': ex.due_date,
                    'link': url_for('student.view_exercise', exercise_id=ex.id),
                    'action_label': 'Resolver'
                })
                continue

            total_points = sum(q.points for q in ex.questions) if ex.questions else ex.max_grade
            if sub.attempts < max_attempts and (sub.grade is None or sub.grade < total_points):
                pending_items.append({
                    'kind': 'exercise',
                    'icon': '🔁',
                    'title': ex.title,
                    'type_label': f'Intento {sub.attempts + 1} de {max_attempts}',
                    'subject_name': ex.subject.name,
                    'due_date': ex.due_date,
                    'link': url_for('student.view_exercise', exercise_id=ex.id),
                    'action_label': 'Mejorar nota'
                })

    pending_items.sort(key=lambda x: (x['due_date'] is None, x['due_date'] or datetime.max))

    return render_template('student_dashboard.html',
                           subjects=subjects, grade=grade,
                           pending_items=pending_items)


@student_bp.route('/subject/<int:subject_id>')
@login_required
@student_required
def view_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)

    # Verificar si está archivada
    if subject.archived:
        flash('Esta materia ha sido archivada por la institución.', 'warning')
        return redirect(url_for('student.dashboard'))

    student_grade = StudentGrade.query.filter_by(student_id=current_user.id).first()
    if not student_grade or student_grade.grade_id != subject.grade_id:
        flash('No tienes acceso a esta materia', 'danger')
        return redirect(url_for('student.dashboard'))

    excluded = StudentExcludedSubject.query.filter_by(
        student_id=current_user.id, subject_id=subject.id
    ).first()
    if excluded:
        flash('No cursas esta materia', 'warning')
        return redirect(url_for('student.dashboard'))

    assignments = Assignment.query.filter_by(subject_id=subject.id).all()

    grade_records = {gr.assignment_id: gr.grade for gr in GradeRecord.query.filter(
        GradeRecord.student_id == current_user.id,
        GradeRecord.assignment_id.in_([a.id for a in assignments])
    ).all()}

    attendances = Attendance.query.filter_by(
        student_id=current_user.id, subject_id=subject.id
    ).all()

    forums = Forum.query.filter_by(subject_id=subject.id).order_by(
        Forum.created_at.desc()
    ).all()

    my_submissions = {sub.assignment_id: sub for sub in AssignmentSubmission.query.filter_by(student_id=current_user.id).all()}

    return render_template('student_view_subject.html', 
                           subject=subject,
                           assignments=assignments, 
                           grade_records=grade_records,
                           attendances=attendances, 
                           forums=forums,
                           my_submissions=my_submissions)

@student_bp.route('/send_message/<int:assignment_id>', methods=['POST'])
@login_required
@student_required
def send_message(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    body = request.form['body']

    excluded = StudentExcludedSubject.query.filter_by(
        student_id=current_user.id, subject_id=assignment.subject_id
    ).first()
    if excluded:
        flash('No cursas esta materia', 'danger')
        return redirect(url_for('student.dashboard'))

    db.session.add(Message(
        sender_id=current_user.id, receiver_id=assignment.teacher_id,
        subject=f'Consulta sobre {assignment.title}', body=body,
        assignment_id=assignment.id
    ))
    db.session.commit()
    flash('Mensaje enviado al profesor', 'success')
    return redirect(url_for('student.view_subject', subject_id=assignment.subject_id))


# ============================================
# FOROS
# ============================================
@student_bp.route('/forum/<int:forum_id>', methods=['GET', 'POST'])
@login_required
@student_required
def view_forum(forum_id):
    forum = Forum.query.get_or_404(forum_id)

    student_grade = StudentGrade.query.filter_by(student_id=current_user.id).first()
    if not student_grade or student_grade.grade_id != forum.subject.grade_id:
        flash('No tienes acceso a este foro', 'danger')
        return redirect(url_for('student.dashboard'))

    excluded = StudentExcludedSubject.query.filter_by(
        student_id=current_user.id, subject_id=forum.subject_id
    ).first()
    if excluded:
        flash('No cursas esta materia', 'warning')
        return redirect(url_for('student.dashboard'))

    # Marcar como visto
    if not StudentForumView.query.filter_by(student_id=current_user.id, forum_id=forum.id).first():
        db.session.add(StudentForumView(student_id=current_user.id, forum_id=forum.id))
        db.session.commit()

    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        if body:
            db.session.add(ForumPost(
                forum_id=forum.id, author_id=current_user.id, body=body
            ))
            db.session.commit()
            flash('Comentario publicado', 'success')
        return redirect(url_for('student.view_forum', forum_id=forum.id))

    posts = forum.posts.order_by(ForumPost.timestamp.asc()).all()
    return render_template('forum_view.html',
                           forum=forum, posts=posts,
                           role='student')


# ============================================
# EJERCICIOS
# ============================================
@student_bp.route('/exercise/<int:exercise_id>', methods=['GET', 'POST'])
@login_required
@student_required
def view_exercise(exercise_id):
    ex = Exercise.query.get_or_404(exercise_id)

    student_grade = StudentGrade.query.filter_by(student_id=current_user.id).first()
    if not student_grade or student_grade.grade_id != ex.subject.grade_id:
        flash('Sin acceso a este ejercicio', 'danger')
        return redirect(url_for('student.dashboard'))

    excluded = StudentExcludedSubject.query.filter_by(
        student_id=current_user.id, subject_id=ex.subject_id
    ).first()
    if excluded:
        flash('No cursas esta materia', 'warning')
        return redirect(url_for('student.dashboard'))

    submission = ExerciseSubmission.query.filter_by(
        exercise_id=ex.id, student_id=current_user.id
    ).first()

    questions = ex.questions
    MAX_ATTEMPTS = ex.max_attempts or 1
    current_attempts = submission.attempts if submission else 0
    can_attempt = current_attempts < MAX_ATTEMPTS

    # SI ES UN INTENTO NUEVO Y TIENE PREGUNTAS, INICIAMOS EL RELOJ
    if request.method == 'GET' and questions and can_attempt:
        if not submission:
            submission = ExerciseSubmission(
                exercise_id=ex.id, student_id=current_user.id,
                attempts=0, attempt_started_at=datetime.utcnow()
            )
            db.session.add(submission)
            db.session.commit()
        elif submission.attempt_started_at is None:
            # Si ya existía pero no tenía reloj (ej. empezando el 2do intento)
            submission.attempt_started_at = datetime.utcnow()
            db.session.commit()

    if request.method == 'POST':
        if not can_attempt:
            flash(f'Ya usaste tus {MAX_ATTEMPTS} intentos.', 'danger')
            return redirect(url_for('student.view_exercise', exercise_id=ex.id))

        if questions:
            total_earned = 0
            for q in questions:
                ans = QuestionAnswer.query.filter_by(
                    question_id=q.id, student_id=current_user.id
                ).first()
                if not ans:
                    ans = QuestionAnswer(question_id=q.id, student_id=current_user.id)
                    db.session.add(ans)

                if q.question_type == 'multiple_choice':
                    opt_id = request.form.get(f'q_{q.id}_option')
                    if opt_id:
                        ans.selected_option_id = int(opt_id)
                        opt = QuestionOption.query.get(int(opt_id))
                        if opt and opt.is_correct: ans.earned_points = q.points
                        else: ans.earned_points = 0
                elif q.question_type == 'true_false':
                    tf = request.form.get(f'q_{q.id}_tf', '')
                    ans.true_false_value = tf
                    if tf == q.correct_answer: ans.earned_points = q.points
                    else: ans.earned_points = 0
                elif q.question_type == 'fill_blank':
                    ans.answer_text = request.form.get(f'q_{q.id}_fill', '').strip()
                    ans.earned_points = None

                if ans.earned_points is not None:
                    total_earned += ans.earned_points

            if not submission:
                submission = ExerciseSubmission(
                    exercise_id=ex.id, student_id=current_user.id,
                    answer_text='[Respuestas a preguntas]'
                )
                db.session.add(submission)
            
            submission.attempts = current_attempts + 1
            submission.submitted_at = datetime.utcnow()
            submission.attempt_started_at = None # Se limpia para el próximo intento
            submission.grade = total_earned
            db.session.commit()

            intentos_restantes = MAX_ATTEMPTS - submission.attempts
            if intentos_restantes > 0:
                flash(f'Examen enviado. Te quedan {intentos_restantes} intento(s).', 'success')
            else:
                flash('Examen enviado. Ya usaste todos tus intentos.', 'success')

            return redirect(url_for('student.view_exercise', exercise_id=ex.id))

        # Modo simple (sin preguntas) - igual que antes
        # ... (código de subir archivo) ...
        return redirect(url_for('student.view_exercise', exercise_id=ex.id))

    answers_map = {}
    for q in questions:
        a = QuestionAnswer.query.filter_by(question_id=q.id, student_id=current_user.id).first()
        if a:
            answers_map[q.id] = a

    return render_template('student_view_exercise.html',
                           exercise=ex, submission=submission,
                           questions=questions, answers_map=answers_map,
                           current_attempts=current_attempts,
                           max_attempts=MAX_ATTEMPTS,
                           can_attempt=can_attempt)

# ============================================
# CALIFICACIONES UNIFICADAS
# ============================================
@student_bp.route('/grades')
@login_required
@student_required
def grades():
    student_grade = StudentGrade.query.filter_by(student_id=current_user.id).first()
    if not student_grade:
        flash('No estás asignado a un grado', 'danger')
        return redirect(url_for('auth.index'))

    grade = student_grade.grade
    all_subjects = Subject.query.filter_by(grade_id=grade.id, archived=False).all()
    excluded_ids = {e.subject_id for e in StudentExcludedSubject.query.filter_by(student_id=current_user.id).all()}
    subjects = [s for s in all_subjects if s.id not in excluded_ids]
    
    subject_id = request.args.get('subject_id', type=int)
    selected_subject = next((s for s in subjects if s.id == subject_id), subjects[0] if subjects else None)
    
    periods = get_school_periods(current_user.school_id)
    
    report_data = []
    final_average = None
    columns = []
    my_grades = {}

    if selected_subject:
        total_final_sum = 0
        count_final = 0

        # Calcular promedio por período
        for p in periods:
            p_grades = []
            
            for a in Assignment.query.filter_by(subject_id=selected_subject.id).all():
                if a.period == p.name or not a.period or a.period == 'General':
                    gr = GradeRecord.query.filter_by(assignment_id=a.id, student_id=current_user.id).first()
                    if gr and gr.grade is not None: p_grades.append(gr.grade)
            
            for ex in Exercise.query.filter_by(subject_id=selected_subject.id).all():
                if ex.period == p.name or not ex.period or ex.period == 'General':
                    sub = ExerciseSubmission.query.filter_by(exercise_id=ex.id, student_id=current_user.id).first()
                    if sub and sub.grade is not None: p_grades.append(sub.grade)
                    
            for f in Forum.query.filter_by(subject_id=selected_subject.id).all():
                if f.period == p.name or not f.period or f.period == 'General':
                    fg = ForumGrade.query.filter_by(forum_id=f.id, student_id=current_user.id).first()
                    if fg and fg.grade is not None: p_grades.append(fg.grade)
                    
            for c in CustomColumn.query.filter_by(subject_id=selected_subject.id).all():
                cg = CustomGrade.query.filter_by(column_id=c.id, student_id=current_user.id).first()
                if cg and cg.grade is not None: p_grades.append(cg.grade)

            if p_grades:
                p_avg = sum(p_grades) / len(p_grades)
                report_data.append({'period': p, 'average': p_avg})
                total_final_sum += p_avg
                count_final += 1
            else:
                report_data.append({'period': p, 'average': None})

        if count_final > 0:
            final_average = total_final_sum / count_final

        # --- NUEVO: Cargar columnas para el desglose ---
        for a in Assignment.query.filter_by(subject_id=selected_subject.id).order_by(Assignment.date_assigned).all():
            columns.append({'id': a.id, 'title': a.title, 'type': 'a', 'period': a.period or 'General'})
        for ex in Exercise.query.filter_by(subject_id=selected_subject.id).order_by(Exercise.created_at).all():
            columns.append({'id': ex.id, 'title': ex.title, 'type': 'e', 'period': ex.period or 'General'})
        for f in Forum.query.filter_by(subject_id=selected_subject.id).order_by(Forum.created_at).all():
            columns.append({'id': f.id, 'title': f.title, 'type': 'f', 'period': f.period or 'General'})
        for c in CustomColumn.query.filter_by(subject_id=selected_subject.id).all():
            columns.append({'id': c.id, 'title': c.title, 'type': 'c', 'period': 'General'})

        # --- NUEVO: Cargar notas del estudiante para el desglose ---
        for col in columns:
            grade_val = None
            if col['type'] == 'a':
                gr = GradeRecord.query.filter_by(assignment_id=col['id'], student_id=current_user.id).first()
                if gr: grade_val = gr.grade
            elif col['type'] == 'e':
                sub = ExerciseSubmission.query.filter_by(exercise_id=col['id'], student_id=current_user.id).first()
                if sub: grade_val = sub.grade
            elif col['type'] == 'f':
                fg = ForumGrade.query.filter_by(forum_id=col['id'], student_id=current_user.id).first()
                if fg: grade_val = fg.grade
            elif col['type'] == 'c':
                cg = CustomGrade.query.filter_by(column_id=col['id'], student_id=current_user.id).first()
                if cg: grade_val = cg.grade
            my_grades[f"{col['type']}_{col['id']}"] = grade_val

    return render_template('student_grades.html',
                           subjects=subjects, selected_subject=selected_subject,
                           report_data=report_data, final_average=final_average, grade=grade,
                           columns=columns, my_grades=my_grades)

@student_bp.route('/teacher/<int:teacher_id>')
@login_required
@student_required
def view_teacher(teacher_id):
    teacher = User.query.get_or_404(teacher_id)
    if teacher.role != 'teacher':
        flash('Usuario no válido', 'danger')
        return redirect(url_for('student.dashboard'))
    
    profile = TeacherProfile.query.filter_by(user_id=teacher.id).first()
    if not profile or not profile.show_contact:
        flash('El profesor no ha compartido su información de contacto.', 'warning')
        return redirect(url_for('student.dashboard'))
        
    return render_template('shared_teacher_profile.html', teacher=teacher, profile=profile, role='student')

@student_bp.route('/file/<int:file_id>/download')
@login_required
@student_required
def download_file(file_id):
    f = SubjectFile.query.get_or_404(file_id)
    
    # Marcar como visto
    if not StudentFileView.query.filter_by(student_id=current_user.id, file_id=f.id).first():
        db.session.add(StudentFileView(student_id=current_user.id, file_id=f.id))
        db.session.commit()
        
    return redirect(url_for('uploaded_file', filename=f.filename))

@student_bp.route('/assignment/<int:assignment_id>/submit', methods=['POST'])
@login_required
@student_required
def submit_assignment(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # Verificar que la tarea sea de su grado
    student_grade = StudentGrade.query.filter_by(student_id=current_user.id).first()
    if not student_grade or student_grade.grade_id != assignment.subject.grade_id:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('student.dashboard'))

    answer = request.form.get('answer_text', '').strip()
    file = request.files.get('file')

    saved_filename = None
    original_name = None

    if file and file.filename != '':
        if not allowed_file(file.filename):
            flash('Tipo de archivo no permitido', 'danger')
            return redirect(url_for('student.view_subject', subject_id=assignment.subject_id))
        
        original_name = file.filename
        safe = secure_filename(original_name)
        unique = f"asig{assignment.id}_{current_user.id}_{int(datetime.utcnow().timestamp())}_{safe}"
        file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique))
        saved_filename = unique

    # Buscar si ya había entregado antes
    sub = AssignmentSubmission.query.filter_by(assignment_id=assignment.id, student_id=current_user.id).first()
    if sub:
        sub.answer_text = answer
        if saved_filename:
            # Borrar archivo viejo si existía
            if sub.file_path:
                try:
                    os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], sub.file_path))
                except Exception:
                    pass
            sub.file_path = saved_filename
            sub.original_filename = original_name
        sub.submitted_at = datetime.utcnow()
        flash('Tarea actualizada correctamente', 'success')
    else:
        db.session.add(AssignmentSubmission(
            assignment_id=assignment.id, student_id=current_user.id,
            answer_text=answer, file_path=saved_filename,
            original_filename=original_name
        ))
        flash('Tarea entregada exitosamente', 'success')

    db.session.commit()
    return redirect(url_for('student.view_subject', subject_id=assignment.subject_id))