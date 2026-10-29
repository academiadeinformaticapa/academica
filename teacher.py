from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import (db, User, TeacherSubject, Subject, StudentGrade, Assignment,
                    GradeRecord, Attendance, Message, StudentExcludedSubject,
                    Forum, ForumPost, SubjectFile, Announcement,
                    Exercise, ExerciseSubmission,
                    ExerciseQuestion, QuestionOption, QuestionAnswer,
                    ForumGrade, TeacherProfile, CustomColumn, CustomGrade, SchoolPeriod)
from datetime import datetime, date
from functools import wraps
import os
from werkzeug.utils import secure_filename

teacher_bp = Blueprint('teacher', __name__)

def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != 'teacher':
            flash('Acceso denegado', 'danger')
            return redirect(url_for('auth.index'))
        return f(*args, **kwargs)
    return decorated_function

def get_enrolled_students(subject_id):
    subject = Subject.query.get(subject_id)
    if not subject:
        return []
    all_sgs = StudentGrade.query.filter_by(grade_id=subject.grade_id).all()
    excluded_student_ids = {e.student_id for e in StudentExcludedSubject.query.filter_by(subject_id=subject_id).all()}
    return [sg.student for sg in all_sgs if sg.student_id not in excluded_student_ids]

def allowed_file(filename):
    ALLOWED_EXT = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
                   'txt', 'png', 'jpg', 'jpeg', 'zip'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def get_school_periods(school_id):
    return SchoolPeriod.query.filter_by(school_id=school_id).order_by(SchoolPeriod.start_date).all()

# ============================================
# DASHBOARD Y PERFIL
# ============================================
@teacher_bp.route('/')
@login_required
@teacher_required
def dashboard():
    teacher_subjects = TeacherSubject.query.join(Subject).filter(
        TeacherSubject.teacher_id == current_user.id,
        Subject.archived == False
    ).all()

    pending_messages = Message.query.filter_by(
        receiver_id=current_user.id
    ).order_by(Message.timestamp.desc()).limit(6).all()

    recent_assignments = Assignment.query.join(Subject).filter(
        Assignment.teacher_id == current_user.id,
        Subject.archived == False
    ).order_by(Assignment.date_assigned.desc()).limit(5).all()

    return render_template('teacher_dashboard.html',
                           teacher_subjects=teacher_subjects,
                           pending_messages=pending_messages,
                           recent_assignments=recent_assignments,
                           messages_count=len(pending_messages))

@teacher_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@teacher_required
def profile():
    profile = TeacherProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = TeacherProfile(user_id=current_user.id)
        db.session.add(profile)
        db.session.commit()

    if request.method == 'POST':
        profile.phone = request.form.get('phone', '').strip()
        profile.contact_email = request.form.get('contact_email', '').strip()
        profile.degree = request.form.get('degree', '').strip()
        profile.bio = request.form.get('bio', '').strip()
        profile.show_contact = request.form.get('show_contact') == 'on'
        
        db.session.commit()
        flash('Perfil actualizado correctamente', 'success')
        return redirect(url_for('teacher.profile'))

    return render_template('teacher_profile.html', profile=profile)

# ============================================
# VER MATERIA
# ============================================
@teacher_bp.route('/subject/<int:subject_id>')
@login_required
@teacher_required
def view_subject(subject_id):
    ts = TeacherSubject.query.filter_by(teacher_id=current_user.id, subject_id=subject_id).first()
    if not ts:
        flash('No tienes acceso a esta materia', 'danger')
        return redirect(url_for('teacher.dashboard'))

    subject = Subject.query.get(subject_id)
    if not subject or subject.archived:
        flash('Esta materia ha sido archivada por la institución.', 'danger')
        return redirect(url_for('teacher.dashboard'))

    students = get_enrolled_students(subject_id)
    assignments = Assignment.query.filter_by(subject_id=subject.id).all()
    forums = Forum.query.filter_by(subject_id=subject.id).order_by(Forum.created_at.desc()).all()

    return render_template('teacher_view_subject.html',
                           subject=subject, students=students,
                           assignments=assignments, forums=forums)

# ============================================
# TAREAS TRADICIONALES
# ============================================
@teacher_bp.route('/create_assignment/<int:subject_id>', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_assignment(subject_id):
    ts = TeacherSubject.query.filter_by(teacher_id=current_user.id, subject_id=subject_id).first()
    if not ts:
        return redirect(url_for('teacher.dashboard'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description')
        period = request.form.get('period', 'General')
        date_assigned_str = request.form['date_assigned'].strip()
        date_assigned = datetime.strptime(date_assigned_str, '%Y-%m-%d')
        due_date_str = request.form.get('due_date', '').strip()
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else None
        type = request.form['type']

        assignment = Assignment(
            title=title, description=description,
            date_assigned=date_assigned, due_date=due_date,
            type=type, subject_id=subject_id,
            teacher_id=current_user.id, period=period
        )
        db.session.add(assignment)
        db.session.commit()
        flash('Tarea creada', 'success')
        return redirect(url_for('teacher.view_subject', subject_id=subject_id))

    return render_template('teacher_create_assignment.html', subject_id=subject_id)

@teacher_bp.route('/record_grades/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
@teacher_required
def record_grades(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    ts = TeacherSubject.query.filter_by(teacher_id=current_user.id, subject_id=assignment.subject_id).first()
    if not ts:
        return redirect(url_for('teacher.dashboard'))

    students = get_enrolled_students(assignment.subject_id)

    if request.method == 'POST':
        for student in students:
            grade_value = request.form.get(f'grade_{student.id}')
            if grade_value:
                record = GradeRecord.query.filter_by(assignment_id=assignment.id, student_id=student.id).first()
                if record:
                    record.grade = float(grade_value)
                else:
                    db.session.add(GradeRecord(assignment_id=assignment.id, student_id=student.id, grade=float(grade_value)))
        db.session.commit()
        flash('Notas guardadas', 'success')
        return redirect(url_for('teacher.view_subject', subject_id=assignment.subject_id))

    existing_grades = {gr.student_id: gr.grade for gr in GradeRecord.query.filter_by(assignment_id=assignment.id).all()}
    from models import AssignmentSubmission
    submissions = {sub.student_id: sub for sub in AssignmentSubmission.query.filter_by(assignment_id=assignment.id).all()}

    return render_template('teacher_record_grades.html',
                           assignment=assignment, students=students,
                           existing_grades=existing_grades, submissions=submissions)

# ============================================
# ASISTENCIA
# ============================================
@teacher_bp.route('/attendance/<int:subject_id>', methods=['GET', 'POST'])
@login_required
@teacher_required
def attendance(subject_id):
    ts = TeacherSubject.query.filter_by(teacher_id=current_user.id, subject_id=subject_id).first()
    if not ts:
        return redirect(url_for('teacher.dashboard'))

    subject = Subject.query.get(subject_id)
    students = get_enrolled_students(subject_id)

    if request.method == 'POST':
        att_date = request.form.get('date', date.today().strftime('%Y-%m-%d'))
        att_date = datetime.strptime(att_date, '%Y-%m-%d').date()
        for student in students:
            status = request.form.get(f'status_{student.id}')
            if status:
                Attendance.query.filter_by(date=att_date, student_id=student.id, subject_id=subject_id).delete()
                db.session.add(Attendance(date=att_date, status=status, student_id=student.id, subject_id=subject_id))
        db.session.commit()
        flash('Asistencia registrada', 'success')
        return redirect(url_for('teacher.attendance_matrix', subject_id=subject_id))

    today = date.today()
    attendances = {att.student_id: att.status for att in Attendance.query.filter_by(date=today, subject_id=subject_id).all()}

    return render_template('teacher_attendance.html', subject=subject, students=students, today=today, attendances=attendances)

@teacher_bp.route('/subject/<int:subject_id>/attendance_matrix')
@login_required
@teacher_required
def attendance_matrix(subject_id):
    ts = TeacherSubject.query.filter_by(teacher_id=current_user.id, subject_id=subject_id).first()
    if not ts:
        return redirect(url_for('teacher.dashboard'))

    subject = Subject.query.get(subject_id)
    students = get_enrolled_students(subject_id)

    raw_dates = db.session.query(Attendance.date).filter_by(subject_id=subject_id).distinct().order_by(Attendance.date.asc()).all()
    dates = [d[0] for d in raw_dates]

    attendance_data = {}
    for att in Attendance.query.filter_by(subject_id=subject_id).all():
        attendance_data[f"{att.student_id}_{att.date}"] = att.status

    return render_template('teacher_attendance_matrix.html', subject=subject, students=students, dates=dates, attendance_data=attendance_data)

# ============================================
# MENSAJES
# ============================================
@teacher_bp.route('/messages/<int:assignment_id>')
@login_required
@teacher_required
def view_messages(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    messages = Message.query.filter_by(assignment_id=assignment.id).order_by(Message.timestamp.desc()).all()
    return render_template('teacher_messages.html', assignment=assignment, messages=messages)

# ============================================
# FOROS
# ============================================
@teacher_bp.route('/subject/<int:subject_id>/forums/create', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_forum(subject_id):
    ts = TeacherSubject.query.filter_by(teacher_id=current_user.id, subject_id=subject_id).first()
    if not ts:
        return redirect(url_for('teacher.dashboard'))

    subject = Subject.query.get(subject_id)

    if request.method == 'POST':
        title = request.form['title'].strip()
        description = request.form.get('description', '').strip()
        period = request.form.get('period', 'General')
        if not title:
            flash('El título no puede estar vacío', 'danger')
        else:
            forum = Forum(title=title, description=description, subject_id=subject_id, teacher_id=current_user.id, period=period)
            db.session.add(forum)
            db.session.commit()
            flash(f'Foro "{title}" creado', 'success')
            return redirect(url_for('teacher.view_forum', forum_id=forum.id))

    return render_template('teacher_create_forum.html', subject=subject)

@teacher_bp.route('/forum/<int:forum_id>', methods=['GET', 'POST'])
@login_required
@teacher_required
def view_forum(forum_id):
    forum = Forum.query.get_or_404(forum_id)
    ts = TeacherSubject.query.filter_by(teacher_id=current_user.id, subject_id=forum.subject_id).first()
    if not ts:
        flash('No tienes acceso a este foro', 'danger')
        return redirect(url_for('teacher.dashboard'))

    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        if body:
            db.session.add(ForumPost(forum_id=forum.id, author_id=current_user.id, body=body))
            db.session.commit()
            flash('Comentario publicado', 'success')
        return redirect(url_for('teacher.view_forum', forum_id=forum.id))

    posts = forum.posts.order_by(ForumPost.timestamp.asc()).all()
    students = get_enrolled_students(forum.subject_id)
    existing_grades = {fg.student_id: fg for fg in ForumGrade.query.filter_by(forum_id=forum.id).all()}

    return render_template('forum_view.html', forum=forum, posts=posts, role='teacher', students=students, existing_grades=existing_grades)

@teacher_bp.route('/forum/<int:forum_id>/grade_student', methods=['POST'])
@login_required
@teacher_required
def grade_forum_student(forum_id):
    forum = Forum.query.get_or_404(forum_id)
    student_id = request.form.get('student_id')
    grade_str = request.form.get('grade', '').strip()
    feedback = request.form.get('feedback', '').strip()

    student = User.query.get(student_id)
    try:
        grade = float(grade_str) if grade_str else None
    except ValueError:
        grade = None

    fg = ForumGrade.query.filter_by(forum_id=forum.id, student_id=student.id).first()
    if not fg:
        fg = ForumGrade(forum_id=forum.id, student_id=student.id)
        db.session.add(fg)

    fg.grade = grade
    fg.feedback = feedback
    fg.graded_at = datetime.utcnow()
    db.session.commit()
    flash(f'Nota de {student.name} guardada', 'success')
    return redirect(url_for('teacher.view_forum', forum_id=forum.id))

@teacher_bp.route('/forum/<int:forum_id>/delete')
@login_required
@teacher_required
def delete_forum(forum_id):
    forum = Forum.query.get_or_404(forum_id)
    subject_id = forum.subject_id
    db.session.delete(forum)
    db.session.commit()
    flash('Foro eliminado', 'success')
    return redirect(url_for('teacher.view_subject', subject_id=subject_id))

@teacher_bp.route('/forum/post/<int:post_id>/delete')
@login_required
@teacher_required
def delete_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    forum = post.forum
    db.session.delete(post)
    db.session.commit()
    flash('Comentario eliminado', 'success')
    return redirect(url_for('teacher.view_forum', forum_id=forum.id))

# ============================================
# ARCHIVOS Y ANUNCIOS
# ============================================
@teacher_bp.route('/subject/<int:subject_id>/upload_file', methods=['POST'])
@login_required
@teacher_required
def upload_file(subject_id):
    file = request.files.get('file')
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()

    if not file or file.filename == '':
        flash('Selecciona un archivo', 'danger')
        return redirect(url_for('teacher.view_subject', subject_id=subject_id))

    if not title:
        title = file.filename

    original = file.filename
    safe = secure_filename(original)
    unique = f"sub{subject_id}_{int(datetime.utcnow().timestamp())}_{safe}"
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique)
    file.save(path)

    db.session.add(SubjectFile(subject_id=subject_id, teacher_id=current_user.id, title=title, description=description, filename=unique, original_filename=original))
    db.session.commit()
    flash(f'Archivo "{title}" subido', 'success')
    return redirect(url_for('teacher.view_subject', subject_id=subject_id))

@teacher_bp.route('/file/<int:file_id>/delete')
@login_required
@teacher_required
def delete_file(file_id):
    f = SubjectFile.query.get_or_404(file_id)
    subject_id = f.subject_id
    try:
        os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], f.filename))
    except Exception:
        pass
    db.session.delete(f)
    db.session.commit()
    flash('Archivo eliminado', 'success')
    return redirect(url_for('teacher.view_subject', subject_id=subject_id))

@teacher_bp.route('/subject/<int:subject_id>/announcement', methods=['POST'])
@login_required
@teacher_required
def create_announcement(subject_id):
    title = request.form.get('title', '').strip()
    body = request.form.get('body', '').strip()

    if not title or not body:
        flash('Título y mensaje son obligatorios', 'danger')
    else:
        db.session.add(Announcement(subject_id=subject_id, teacher_id=current_user.id, title=title, body=body))
        db.session.commit()
        flash('Anuncio publicado', 'success')
    return redirect(url_for('teacher.view_subject', subject_id=subject_id))

@teacher_bp.route('/announcement/<int:ann_id>/delete')
@login_required
@teacher_required
def delete_announcement(ann_id):
    a = Announcement.query.get_or_404(ann_id)
    subject_id = a.subject_id
    db.session.delete(a)
    db.session.commit()
    flash('Anuncio eliminado', 'success')
    return redirect(url_for('teacher.view_subject', subject_id=subject_id))

# ============================================
# EJERCICIOS (PARCIALES)
# ============================================
@teacher_bp.route('/subject/<int:subject_id>/create_exercise', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_exercise(subject_id):
    subject = Subject.query.get(subject_id)
    if request.method == 'POST':
        title = request.form['title'].strip()
        description = request.form['description'].strip()
        due_date_str = request.form.get('due_date', '').strip()
        max_grade = float(request.form.get('max_grade', '5.0'))
        max_attempts = int(request.form.get('max_attempts', '2'))
        time_limit = int(request.form.get('time_limit', '0'))
        period = request.form.get('period', 'General')

        due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else None

        ex = Exercise(subject_id=subject_id, teacher_id=current_user.id, title=title, description=description, due_date=due_date, max_grade=max_grade, max_attempts=max_attempts, time_limit=time_limit, period=period)
        db.session.add(ex)
        db.session.commit()
        flash(f'Ejercicio "{title}" creado.', 'success')
        return redirect(url_for('teacher.view_exercise', exercise_id=ex.id))

    return render_template('teacher_create_exercise.html', subject=subject)

@teacher_bp.route('/exercise/<int:exercise_id>')
@login_required
@teacher_required
def view_exercise(exercise_id):
    ex = Exercise.query.get_or_404(exercise_id)
    submissions = ex.submissions.order_by(ExerciseSubmission.submitted_at.desc()).all()
    all_students = get_enrolled_students(ex.subject_id)
    submitted_ids = {s.student_id for s in submissions}
    pending_students = [s for s in all_students if s.id not in submitted_ids]
    pending_grading = []

    return render_template('teacher_view_exercise.html', exercise=ex, submissions=submissions, pending_students=pending_students, pending_grading=pending_grading)

@teacher_bp.route('/exercise/<int:exercise_id>/delete')
@login_required
@teacher_required
def delete_exercise(exercise_id):
    ex = Exercise.query.get_or_404(exercise_id)
    subject_id = ex.subject_id
    for sub in ex.submissions.all():
        if sub.file_path:
            try: os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], sub.file_path))
            except Exception: pass
    db.session.delete(ex)
    db.session.commit()
    flash('Ejercicio eliminado', 'success')
    return redirect(url_for('teacher.view_subject', subject_id=subject_id))

@teacher_bp.route('/exercise/<int:exercise_id>/add_question', methods=['GET', 'POST'])
@login_required
@teacher_required
def add_question(exercise_id):
    ex = Exercise.query.get_or_404(exercise_id)
    if request.method == 'POST':
        q_type = request.form['question_type']
        q_text = request.form['question_text'].strip()
        points = float(request.form.get('points', '1'))

        order_index = len(ex.questions) + 1
        question = ExerciseQuestion(exercise_id=ex.id, order_index=order_index, question_type=q_type, question_text=q_text, points=points)

        if q_type == 'multiple_choice':
            db.session.add(question)
            db.session.flush()
            options_text = request.form.getlist('option_text')
            correct_index = request.form.get('correct_option', '0')
            for i, opt in enumerate(options_text):
                if opt.strip():
                    db.session.add(QuestionOption(question_id=question.id, option_text=opt.strip(), is_correct=(str(i) == correct_index)))
        elif q_type == 'true_false':
            question.correct_answer = request.form.get('tf_correct', 'true')
            db.session.add(question)
        elif q_type == 'fill_blank':
            question.correct_answer = request.form.get('fill_answer', '').strip()
            db.session.add(question)

        db.session.commit()
        flash('Pregunta agregada', 'success')
        return redirect(url_for('teacher.view_exercise', exercise_id=ex.id))

    return render_template('teacher_add_question.html', exercise=ex)

@teacher_bp.route('/question/<int:question_id>/delete')
@login_required
@teacher_required
def delete_question(question_id):
    q = ExerciseQuestion.query.get_or_404(question_id)
    ex = q.exercise
    db.session.delete(q)
    db.session.commit()
    flash('Pregunta eliminada', 'success')
    return redirect(url_for('teacher.view_exercise', exercise_id=ex.id))

# ============================================
# LIBRETA DE NOTAS Y EXTRAS
# ============================================
@teacher_bp.route('/subject/<int:subject_id>/gradebook', methods=['GET', 'POST'])
@login_required
@teacher_required
def gradebook(subject_id):
    ts = TeacherSubject.query.filter_by(teacher_id=current_user.id, subject_id=subject_id).first()
    if not ts:
        return redirect(url_for('teacher.dashboard'))

    subject = Subject.query.get(subject_id)
    students = get_enrolled_students(subject_id)
    
    periods = get_school_periods(current_user.school_id)
    selected_period_id = request.args.get('period', type=int)
    
    if not selected_period_id and periods:
        selected_period_id = periods[0].id

    selected_period = next((p for p in periods if p.id == selected_period_id), None)
    period_name = selected_period.name if selected_period else 'General'

    columns = []
    
    # Tareas (Muestra las del período actual O las que no tienen período)
    for a in Assignment.query.filter_by(subject_id=subject_id).order_by(Assignment.date_assigned).all():
        if a.period == period_name or not a.period or a.period == 'General':
            columns.append({'id': a.id, 'title': a.title, 'type': 'a'})
            
    # Parciales
    for ex in Exercise.query.filter_by(subject_id=subject_id).order_by(Exercise.created_at).all():
        if ex.period == period_name or not ex.period or ex.period == 'General':
            columns.append({'id': ex.id, 'title': ex.title, 'type': 'e'})
            
    # Foros
    for f in Forum.query.filter_by(subject_id=subject_id).order_by(Forum.created_at).all():
        if f.period == period_name or not f.period or f.period == 'General':
            columns.append({'id': f.id, 'title': f.title, 'type': 'f'})
            
    # Columnas personalizadas
    for c in CustomColumn.query.filter_by(subject_id=subject_id).all():
        columns.append({'id': c.id, 'title': c.title, 'type': 'c'})

    if request.method == 'POST':
        for col in columns:
            title_key = f"title_{col['type']}_{col['id']}"
            new_title = request.form.get(title_key)
            if new_title and new_title.strip() and new_title.strip() != col['title']:
                new_title = new_title.strip()
                if col['type'] == 'a': obj = Assignment.query.get(col['id'])
                elif col['type'] == 'e': obj = Exercise.query.get(col['id'])
                elif col['type'] == 'f': obj = Forum.query.get(col['id'])
                else: obj = CustomColumn.query.get(col['id'])
                if obj: obj.title = new_title

        for student in students:
            for col in columns:
                key = f"{col['type']}_{student.id}_{col['id']}"
                grade_val = request.form.get(key)
                if grade_val:
                    val_float = float(grade_val)
                    if col['type'] == 'a':
                        record = GradeRecord.query.filter_by(assignment_id=col['id'], student_id=student.id).first()
                        if record: record.grade = val_float
                        else: db.session.add(GradeRecord(assignment_id=col['id'], student_id=student.id, grade=val_float))
                    elif col['type'] == 'e':
                        record = ExerciseSubmission.query.filter_by(exercise_id=col['id'], student_id=student.id).first()
                        if record: record.grade = val_float
                        else: db.session.add(ExerciseSubmission(exercise_id=col['id'], student_id=student.id, grade=val_float, attempts=1, answer_text='[Calificado directo]'))
                    elif col['type'] == 'f':
                        record = ForumGrade.query.filter_by(forum_id=col['id'], student_id=student.id).first()
                        if record: record.grade = val_float
                        else: db.session.add(ForumGrade(forum_id=col['id'], student_id=student.id, grade=val_float))
                    elif col['type'] == 'c':
                        record = CustomGrade.query.filter_by(column_id=col['id'], student_id=student.id).first()
                        if record: record.grade = val_float
                        else: db.session.add(CustomGrade(column_id=col['id'], student_id=student.id, grade=val_float))
        db.session.commit()
        flash('Notas guardadas exitosamente', 'success')
        return redirect(url_for('teacher.gradebook', subject_id=subject_id, period=selected_period_id))

    existing_grades = {}
    for gr in GradeRecord.query.filter(GradeRecord.student_id.in_([s.id for s in students])).all():
        existing_grades[f"a_{gr.student_id}_{gr.assignment_id}"] = gr.grade
    for sub in ExerciseSubmission.query.filter(ExerciseSubmission.student_id.in_([s.id for s in students])).all():
        existing_grades[f"e_{sub.student_id}_{sub.exercise_id}"] = sub.grade
    for fg in ForumGrade.query.filter(ForumGrade.student_id.in_([s.id for s in students])).all():
        existing_grades[f"f_{fg.student_id}_{fg.forum_id}"] = fg.grade
    for cg in CustomGrade.query.join(CustomColumn).filter(CustomColumn.subject_id == subject_id, CustomGrade.student_id.in_([s.id for s in students])).all():
        existing_grades[f"c_{cg.student_id}_{cg.column_id}"] = cg.grade

    return render_template('teacher_gradebook.html', 
                           subject=subject, students=students, 
                           columns=columns, existing_grades=existing_grades,
                           periods=periods, selected_period=selected_period)

@teacher_bp.route('/subject/<int:subject_id>/add_custom_column', methods=['POST'])
@login_required
@teacher_required
def add_custom_column(subject_id):
    title = request.form.get('title', '').strip()
    if title:
        db.session.add(CustomColumn(subject_id=subject_id, title=title))
        db.session.commit()
    return redirect(url_for('teacher.gradebook', subject_id=subject_id))

@teacher_bp.route('/custom_column/<int:column_id>/delete')
@login_required
@teacher_required
def delete_custom_column(column_id):
    col = CustomColumn.query.get_or_404(column_id)
    subject_id = col.subject_id
    db.session.delete(col)
    db.session.commit()
    return redirect(url_for('teacher.gradebook', subject_id=subject_id))

@teacher_bp.route('/submission/<int:sub_id>/grade', methods=['POST'])
@login_required
@teacher_required
def grade_submission(sub_id):
    sub = ExerciseSubmission.query.get_or_404(sub_id)
    try:
        grade_str = request.form.get('grade', '').strip()
        sub.grade = float(grade_str) if grade_str else None
    except ValueError:
        sub.grade = None
    sub.feedback = request.form.get('feedback', '').strip()
    db.session.commit()
    flash(f'Nota de {sub.student.name} actualizada manualmente', 'success')
    return redirect(url_for('teacher.view_exercise', exercise_id=sub.exercise_id))