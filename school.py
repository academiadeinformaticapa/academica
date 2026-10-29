from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import (db, User, Grade, Subject, TeacherSubject, StudentGrade,
                    Message, StudentExcludedSubject, GuardianStudent,
                    Assignment, GradeRecord, Exercise, ExerciseSubmission,
                    Forum, ForumGrade, ForumPost, SchoolPeriod)
from functools import wraps
import openpyxl
from io import BytesIO
from datetime import datetime

school_bp = Blueprint('school', __name__)

def school_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != 'school':
            flash('Acceso denegado', 'danger')
            return redirect(url_for('auth.index'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# DASHBOARD
# ============================================
@school_bp.route('/')
@login_required
@school_required
def dashboard():
    school = current_user.school
    teachers = User.query.filter_by(school_id=school.id, role='teacher').all()
    students = User.query.filter_by(school_id=school.id, role='student').all()
    grades = Grade.query.filter_by(school_id=school.id, archived=False).all()
    subjects_count = Subject.query.join(Grade).filter(Grade.school_id == school.id, Subject.archived == False).count()
    
    # Calcular días restantes de la licencia
    dias_restantes = None
    if school.license_expiry:
        delta = school.license_expiry - datetime.utcnow()
        dias_restantes = delta.days

    return render_template('school_dashboard.html',
                           school=school,
                           teachers=teachers,
                           students=students,
                           grades=grades,
                           subjects_count=subjects_count,
                           dias_restantes=dias_restantes)

@school_bp.route('/edit_school', methods=['GET', 'POST'])
@login_required
@school_required
def edit_school():
    school = current_user.school
    if request.method == 'POST':
        new_name = request.form['name'].strip()
        if not new_name:
            flash('El nombre no puede estar vacío', 'danger')
        else:
            school.name = new_name
            school.address = request.form.get('address', '').strip()
            school.phone = request.form.get('phone', '').strip()
            school.period_type = request.form.get('period_type', 'Trimestres')
            db.session.commit()
            flash('Datos actualizados correctamente', 'success')
            return redirect(url_for('school.dashboard'))
            
    return render_template('school_edit_school.html', school=school)

# ============================================
# PERÍODOS ESCOLARES
# ============================================
@school_bp.route('/periods', methods=['GET', 'POST'])
@login_required
@school_required
def manage_periods():
    school = current_user.school
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        start_date_str = request.form.get('start_date', '').strip()
        end_date_str = request.form.get('end_date', '').strip()
        
        if name and start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            db.session.add(SchoolPeriod(school_id=school.id, name=name, start_date=start_date, end_date=end_date))
            db.session.commit()
            flash(f'Período "{name}" creado correctamente', 'success')
        else:
            flash('Todos los campos son obligatorios', 'danger')
            
        return redirect(url_for('school.manage_periods'))
        
    periods = SchoolPeriod.query.filter_by(school_id=school.id).order_by(SchoolPeriod.start_date).all()
    return render_template('school_periods.html', periods=periods)

@school_bp.route('/periods/<int:period_id>/delete')
@login_required
@school_required
def delete_period(period_id):
    period = SchoolPeriod.query.get_or_404(period_id)
    if period.school_id == current_user.school_id:
        db.session.delete(period)
        db.session.commit()
        flash('Período eliminado', 'success')
    return redirect(url_for('school.manage_periods'))

# ============================================
# PROFESORES
# ============================================
@school_bp.route('/teachers')
@login_required
@school_required
def teachers_list():
    school = current_user.school
    teachers = User.query.filter_by(school_id=school.id, role='teacher').all()

    teachers_info = []
    for t in teachers:
        assignments = TeacherSubject.query.filter_by(teacher_id=t.id).all()
        subjects = []
        for a in assignments:
            subjects.append({
                'id': a.id,
                'subject_id': a.subject.id,
                'subject_name': a.subject.name,
                'grade_name': a.subject.grade.name if a.subject.grade else '—',
                'grade_id': a.subject.grade_id if a.subject.grade else None
            })
        teachers_info.append({
            'teacher': t,
            'subjects': subjects,
            'subjects_count': len(subjects)
        })

    return render_template('school_teachers.html', teachers_info=teachers_info)

@school_bp.route('/create_teacher', methods=['GET', 'POST'])
@login_required
@school_required
def create_teacher():
    if request.method == 'POST':
        email = (request.form['email'] or '').strip().lower()
        name = request.form['name'].strip()
        password = request.form['password']

        if User.query.filter_by(email=email).first():
            flash('Ya existe un usuario con ese correo', 'danger')
            return redirect(url_for('school.create_teacher'))

        user = User(email=email, name=name, role='teacher', school_id=current_user.school_id)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f'Profesor {name} creado correctamente', 'success')
        return redirect(url_for('school.create_teacher'))

    school = current_user.school
    teachers = User.query.filter_by(school_id=school.id, role='teacher').all()
    teachers_info = []
    for t in teachers:
        assignments = TeacherSubject.query.filter_by(teacher_id=t.id).all()
        subjects = [{'id': a.id, 'subject_name': a.subject.name, 'grade_name': a.subject.grade.name if a.subject.grade else '—'} for a in assignments]
        teachers_info.append({'teacher': t, 'subjects': subjects, 'subjects_count': len(subjects)})

    return render_template('school_create_teacher.html', teachers_info=teachers_info)

@school_bp.route('/edit_teacher/<int:teacher_id>', methods=['GET', 'POST'])
@login_required
@school_required
def edit_teacher(teacher_id):
    teacher = User.query.get_or_404(teacher_id)
    if teacher.school_id != current_user.school_id or teacher.role != 'teacher':
        flash('No puedes editar este profesor', 'danger')
        return redirect(url_for('school.teachers_list'))

    if request.method == 'POST':
        teacher.name = request.form['name'].strip()
        new_email = (request.form['email'] or '').strip().lower()
        
        if new_email != teacher.email and User.query.filter_by(email=new_email).first():
            flash('El nuevo correo ya está en uso', 'danger')
            return redirect(url_for('school.edit_teacher', teacher_id=teacher.id))
        
        teacher.email = new_email
        new_password = request.form.get('password')
        if new_password:
            teacher.set_password(new_password)

        db.session.commit()
        flash(f'Profesor {teacher.name} actualizado correctamente', 'success')
        return redirect(url_for('school.create_teacher'))

    return render_template('school_edit_teacher.html', teacher=teacher)

@school_bp.route('/delete_teacher/<int:teacher_id>')
@login_required
@school_required
def delete_teacher(teacher_id):
    teacher = User.query.get_or_404(teacher_id)
    if teacher.school_id != current_user.school_id or teacher.role != 'teacher':
        flash('No puedes eliminar este profesor', 'danger')
        return redirect(url_for('school.teachers_list'))

    TeacherSubject.query.filter_by(teacher_id=teacher.id).delete()
    
    assignments = Assignment.query.filter_by(teacher_id=teacher.id).all()
    for a in assignments:
        GradeRecord.query.filter_by(assignment_id=a.id).delete()
        db.session.delete(a)
        
    forums = Forum.query.filter_by(teacher_id=teacher.id).all()
    for f in forums:
        ForumPost.query.filter_by(forum_id=f.id).delete()
        db.session.delete(f)

    db.session.delete(teacher)
    db.session.commit()
    flash('Profesor eliminado permanentemente', 'success')
    return redirect(url_for('school.create_teacher'))

@school_bp.route('/assign_teacher', methods=['GET', 'POST'])
@login_required
@school_required
def assign_teacher():
    school = current_user.school
    teachers = User.query.filter_by(school_id=school.id, role='teacher').all()
    grades = Grade.query.filter_by(school_id=school.id, archived=False).all()

    if request.method == 'POST':
        teacher_id = request.form['teacher_id']
        subject_id = request.form['subject_id']
        existing = TeacherSubject.query.filter_by(teacher_id=teacher_id, subject_id=subject_id).first()
        if not existing:
            db.session.add(TeacherSubject(teacher_id=teacher_id, subject_id=subject_id))
            db.session.commit()
            flash('Asignación correcta', 'success')
        else:
            flash('Esa asignación ya existe', 'warning')
        return redirect(url_for('school.teachers_list'))

    subjects_by_grade = {g.id: Subject.query.filter_by(grade_id=g.id, archived=False).all() for g in grades}
    return render_template('school_assign_teacher.html',
                           teachers=teachers, grades=grades,
                           subjects_by_grade=subjects_by_grade)

@school_bp.route('/unassign_teacher_subject/<int:assignment_id>')
@login_required
@school_required
def unassign_teacher_subject(assignment_id):
    assignment = TeacherSubject.query.get_or_404(assignment_id)
    teacher = User.query.get(assignment.teacher_id)
    
    if not teacher or teacher.school_id != current_user.school_id:
        flash('No puedes modificar esta asignación', 'danger')
        return redirect(url_for('school.teachers_list'))

    subject_name = assignment.subject.name
    db.session.delete(assignment)
    db.session.commit()
    flash(f'Materia "{subject_name}" quitada a {teacher.name}', 'success')
    return redirect(url_for('school.teachers_list'))

# ============================================
# GRADOS
# ============================================
@school_bp.route('/grades', methods=['GET', 'POST'])
@login_required
@school_required
def manage_grades():
    school = current_user.school

    if request.method == 'POST':
        grade_name = request.form['grade_name'].strip()
        if not grade_name:
            flash('El nombre del grado no puede estar vacío', 'danger')
        elif Grade.query.filter_by(name=grade_name, school_id=school.id).first():
            flash('Ya existe un grado con ese nombre en tu institución', 'warning')
        else:
            db.session.add(Grade(name=grade_name, school_id=school.id))
            db.session.commit()
            flash(f'Grado "{grade_name}" creado correctamente', 'success')
        return redirect(url_for('school.manage_grades'))

    grades = Grade.query.filter_by(school_id=school.id).order_by(Grade.archived.asc(), Grade.name).all()

    grades_info = []
    for g in grades:
        subjects_count = Subject.query.filter_by(grade_id=g.id, archived=False).count()
        students_count = StudentGrade.query.filter_by(grade_id=g.id).count()
        grades_info.append({
            'grade': g,
            'subjects_count': subjects_count,
            'students_count': students_count
        })

    return render_template('school_grades.html', grades_info=grades_info)

@school_bp.route('/edit_grade/<int:grade_id>', methods=['GET', 'POST'])
@login_required
@school_required
def edit_grade(grade_id):
    grade = Grade.query.get_or_404(grade_id)

    if grade.school_id != current_user.school_id:
        flash('No puedes editar este grado', 'danger')
        return redirect(url_for('school.manage_grades'))

    if request.method == 'POST':
        new_name = request.form['grade_name'].strip()
        if not new_name:
            flash('El nombre del grado no puede estar vacío', 'danger')
        elif new_name != grade.name and Grade.query.filter_by(name=new_name, school_id=current_user.school_id).first():
            flash('Ya existe un grado con ese nombre en tu institución', 'warning')
        else:
            grade.name = new_name
            db.session.commit()
            flash(f'Grado actualizado correctamente a "{new_name}"', 'success')
            return redirect(url_for('school.manage_grades'))

    return render_template('school_edit_grade.html', grade=grade)

@school_bp.route('/toggle_archive_grade/<int:grade_id>')
@login_required
@school_required
def toggle_archive_grade(grade_id):
    grade = Grade.query.get_or_404(grade_id)
    if grade.school_id != current_user.school_id:
        return redirect(url_for('school.manage_grades'))
    
    grade.archived = not grade.archived
    db.session.commit()
    estado = "archivado" if grade.archived else "desarchivado"
    flash(f'Grado "{grade.name}" {estado} correctamente', 'success')
    return redirect(url_for('school.manage_grades'))

@school_bp.route('/delete_grade/<int:grade_id>')
@login_required
@school_required
def delete_grade(grade_id):
    grade = Grade.query.get_or_404(grade_id)
    if grade.school_id != current_user.school_id:
        flash('No puedes eliminar este grado', 'danger')
        return redirect(url_for('school.manage_grades'))

    subjects = Subject.query.filter_by(grade_id=grade.id).all()
    for s in subjects:
        StudentExcludedSubject.query.filter_by(subject_id=s.id).delete()
        TeacherSubject.query.filter_by(subject_id=s.id).delete()
        Subject.query.filter_by(id=s.id).delete()

    StudentGrade.query.filter_by(grade_id=grade.id).delete()
    db.session.delete(grade)
    db.session.commit()
    flash(f'Grado "{grade.name}" eliminado con sus materias', 'success')
    return redirect(url_for('school.manage_grades'))

# ============================================
# MATERIAS
# ============================================
@school_bp.route('/subjects', methods=['GET', 'POST'])
@login_required
@school_required
def manage_subjects():
    school = current_user.school
    grades = Grade.query.filter_by(school_id=school.id, archived=False).order_by(Grade.name).all()

    if request.method == 'POST':
        grade_id = request.form.get('grade_id')
        subject_name = request.form['subject_name'].strip()

        if not grade_id:
            flash('Debes seleccionar un grado', 'danger')
        elif not subject_name:
            flash('El nombre de la materia no puede estar vacío', 'danger')
        elif Subject.query.filter_by(name=subject_name, grade_id=grade_id).first():
            flash('Esa materia ya existe en ese grado', 'warning')
        else:
            db.session.add(Subject(name=subject_name, grade_id=grade_id))
            db.session.commit()
            grade = Grade.query.get(grade_id)
            flash(f'Materia "{subject_name}" agregada a {grade.name}', 'success')
        return redirect(url_for('school.manage_subjects'))

    grades_with_subjects = []
    for g in grades:
        subjects = Subject.query.filter_by(grade_id=g.id).order_by(Subject.archived.asc(), Subject.name).all()
        grades_with_subjects.append({'grade': g, 'subjects': subjects})

    all_subjects = Subject.query.join(Grade).filter(Grade.school_id == school.id, Subject.archived == False).order_by(Subject.name).all()

    return render_template('school_subjects.html',
                           grades_with_subjects=grades_with_subjects,
                           grades=grades,
                           all_subjects=all_subjects)

@school_bp.route('/clone_subject', methods=['POST'])
@login_required
@school_required
def clone_subject():
    source_id = request.form.get('source_subject_id')
    target_grade_id = request.form.get('target_grade_id')
    copy_teacher = request.form.get('copy_teacher') == 'on'

    source = Subject.query.get(source_id)
    target_grade = Grade.query.get(target_grade_id)

    if not source or not target_grade:
        flash('Datos inválidos', 'danger')
        return redirect(url_for('school.manage_subjects'))
    if source.grade.school_id != current_user.school_id or target_grade.school_id != current_user.school_id:
        flash('No tienes permiso', 'danger')
        return redirect(url_for('school.manage_subjects'))

    if Subject.query.filter_by(name=source.name, grade_id=target_grade.id).first():
        flash(f'La materia "{source.name}" ya existe en {target_grade.name}', 'warning')
        return redirect(url_for('school.manage_subjects'))

    new_subject = Subject(name=source.name, grade_id=target_grade.id)
    db.session.add(new_subject)
    db.session.flush()

    if copy_teacher:
        for ts in source.teachers:
            db.session.add(TeacherSubject(teacher_id=ts.teacher_id, subject_id=new_subject.id))

    db.session.commit()
    flash(f'Materia "{source.name}" añadida al grado {target_grade.name}', 'success')
    return redirect(url_for('school.manage_subjects'))

@school_bp.route('/toggle_archive_subject/<int:subject_id>')
@login_required
@school_required
def toggle_archive_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if subject.grade.school_id != current_user.school_id:
        return redirect(url_for('school.manage_subjects'))
    
    subject.archived = not subject.archived
    db.session.commit()
    estado = "archivada" if subject.archived else "desarchivada"
    flash(f'Materia "{subject.name}" {estado} correctamente', 'success')
    return redirect(url_for('school.manage_subjects'))

@school_bp.route('/delete_subject/<int:subject_id>')
@login_required
@school_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)

    if subject.grade.school_id != current_user.school_id:
        flash('No puedes eliminar esta materia', 'danger')
        return redirect(url_for('school.manage_subjects'))

    StudentExcludedSubject.query.filter_by(subject_id=subject.id).delete()
    TeacherSubject.query.filter_by(subject_id=subject.id).delete()

    tareas = Assignment.query.filter_by(subject_id=subject.id).all()
    for t in tareas:
        GradeRecord.query.filter_by(assignment_id=t.id).delete()
        db.session.delete(t)
        
    foros = Forum.query.filter_by(subject_id=subject.id).all()
    for f in foros:
        ForumPost.query.filter_by(forum_id=f.id).delete()
        db.session.delete(f)

    db.session.delete(subject)
    db.session.commit()
    flash(f'Materia "{subject.name}" eliminada', 'success')
    return redirect(url_for('school.manage_subjects'))

# ============================================
# ESTUDIANTES
# ============================================
@school_bp.route('/students')
@login_required
@school_required
def students_list():
    school = current_user.school
    grades = Grade.query.filter_by(school_id=school.id, archived=False).order_by(Grade.name).all()
    grade_id = request.args.get('grade_id', type=int)

    selected_grade = None
    students = []

    if grades:
        if grade_id:
            selected_grade = next((g for g in grades if g.id == grade_id), None)
        if not selected_grade:
            selected_grade = grades[0]

        student_grades = StudentGrade.query.filter_by(grade_id=selected_grade.id).all()
        student_ids = [sg.student_id for sg in student_grades]
        
        if student_ids:
            students = User.query.filter(User.id.in_(student_ids), User.role == 'student').order_by(User.name).all()

    all_students = User.query.filter_by(school_id=school.id, role='student').all()
    assigned_ids = {sg.student_id for sg in StudentGrade.query.filter(StudentGrade.grade_id.in_([g.id for g in grades])).all()}
    unassigned_students = [s for s in all_students if s.id not in assigned_ids]

    return render_template('school_students.html',
                           grades=grades, selected_grade=selected_grade,
                           students=students, unassigned_students=unassigned_students)

@school_bp.route('/grade/<int:grade_id>/students')
@login_required
@school_required
def grade_students(grade_id):
    grade = Grade.query.get_or_404(grade_id)
    if grade.school_id != current_user.school_id:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('school.dashboard'))
    
    student_grades = StudentGrade.query.filter_by(grade_id=grade.id).all()
    students = [sg.student for sg in student_grades]
    return render_template('school_grade_students.html', grade=grade, students=students)

@school_bp.route('/create_student', methods=['GET', 'POST'])
@login_required
@school_required
def create_student():
    school = current_user.school
    grades = Grade.query.filter_by(school_id=school.id, archived=False).order_by(Grade.name).all()

    if request.method == 'POST':
        name = request.form['name'].strip()
        email = (request.form['email'] or '').strip().lower()
        password = request.form['password']
        grade_id = request.form.get('grade_id')

        if not grade_id:
            flash('Debes seleccionar el grado del estudiante', 'danger')
            return redirect(url_for('school.create_student'))

        if User.query.filter_by(email=email).first():
            flash('Ya existe un usuario con ese correo electrónico', 'danger')
            return redirect(url_for('school.create_student'))

        user = User(email=email, name=name, role='student', school_id=school.id)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        db.session.add(StudentGrade(student_id=user.id, grade_id=grade_id))
        db.session.commit()
        flash('Estudiante creado correctamente', 'success')
        return redirect(url_for('school.students_list'))

    return render_template('school_create_student.html', grades=grades)

@school_bp.route('/upload_students', methods=['GET', 'POST'])
@login_required
@school_required
def upload_students():
    school = current_user.school
    grades = Grade.query.filter_by(school_id=school.id, archived=False).all()

    if request.method == 'POST':
        file = request.files.get('file')
        grade_id = request.form.get('grade_id')

        if not file or file.filename == '' or not grade_id:
            flash('Archivo o grado no seleccionado', 'danger')
            return redirect(request.url)

        try:
            wb = openpyxl.load_workbook(BytesIO(file.read()), data_only=True)
            sheet = wb.active
            creados = 0
            razones = []

            for idx, row in enumerate(sheet.iter_rows(min_row=1, values_only=True), start=1):
                if not row or all(c is None for c in row): continue
                if len(row) < 3:
                    razones.append(f'Fila {idx}: faltan columnas')
                    continue
                
                name, email, password = str(row[0] or '').strip(), str(row[1] or '').strip().lower(), str(row[2] or '').strip()
                
                if not name or not email or not password:
                    razones.append(f'Fila {idx}: datos vacíos')
                    continue
                if idx == 1 and ('nombre' in name.lower() or 'email' in email.lower()):
                    continue 
                if User.query.filter_by(email=email).first():
                    razones.append(f'Fila {idx}: correo {email} ya existe')
                    continue

                user = User(email=email, name=name, role='student', school_id=school.id)
                user.set_password(password)
                db.session.add(user)
                db.session.flush()
                db.session.add(StudentGrade(student_id=user.id, grade_id=grade_id))
                creados += 1

            db.session.commit()
            flash(f'✅ {creados} estudiantes cargados.', 'success')
            for r in razones[:5]: flash(r, 'warning')
            if len(razones) > 5: flash(f'... y {len(razones)-5} errores más.', 'warning')

        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
        
        return redirect(url_for('school.students_list'))

    return render_template('school_upload_students.html', grades=grades)

@school_bp.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
@login_required
@school_required
def edit_student(student_id):
    student = User.query.get_or_404(student_id)
    if student.school_id != current_user.school_id or student.role != 'student':
        flash('No puedes editar este estudiante', 'danger')
        return redirect(url_for('school.students_list'))

    grades = Grade.query.filter_by(school_id=current_user.school_id, archived=False).all()
    sg = StudentGrade.query.filter_by(student_id=student.id).first()
    current_grade = sg.grade_id if sg else None

    if request.method == 'POST':
        student.name = request.form['name'].strip()
        new_email = (request.form['email'] or '').strip().lower()
        
        if new_email != student.email and User.query.filter_by(email=new_email).first():
            flash('El correo ya está en uso', 'danger')
            return redirect(url_for('school.edit_student', student_id=student.id))
        student.email = new_email

        if request.form.get('password'):
            student.set_password(request.form['password'])

        new_grade_id = request.form.get('grade_id')
        StudentGrade.query.filter_by(student_id=student.id).delete()
        if new_grade_id:
            db.session.add(StudentGrade(student_id=student.id, grade_id=new_grade_id))

        db.session.commit()
        flash('Estudiante actualizado', 'success')
        return redirect(url_for('school.students_list'))

    return render_template('school_edit_student.html', student=student, grades=grades, current_grade=current_grade)

@school_bp.route('/delete_student/<int:student_id>')
@login_required
@school_required
def delete_student(student_id):
    student = User.query.get_or_404(student_id)
    if student.school_id != current_user.school_id or student.role != 'student':
        flash('No puedes eliminar este estudiante', 'danger')
        return redirect(url_for('school.students_list'))

    StudentGrade.query.filter_by(student_id=student.id).delete()
    StudentExcludedSubject.query.filter_by(student_id=student.id).delete()
    db.session.delete(student)
    db.session.commit()
    flash('Estudiante eliminado', 'success')
    return redirect(url_for('school.students_list'))

@school_bp.route('/toggle_block_student/<int:student_id>')
@login_required
@school_required
def toggle_block_student(student_id):
    student = User.query.get_or_404(student_id)
    if student.school_id != current_user.school_id:
        return redirect(url_for('school.students_list'))

    student.blocked = not student.blocked
    db.session.commit()
    flash(f'Estudiante {"bloqueado" if student.blocked else "desbloqueado"}', 'success' if not student.blocked else 'warning')
    return redirect(url_for('school.students_list'))

@school_bp.route('/student/<int:student_id>/subjects', methods=['GET', 'POST'])
@login_required
@school_required
def manage_student_subjects(student_id):
    student = User.query.get_or_404(student_id)
    if student.school_id != current_user.school_id:
        return redirect(url_for('school.students_list'))

    sg = StudentGrade.query.filter_by(student_id=student.id).first()
    if not sg:
        flash('El estudiante no tiene grado asignado', 'warning')
        return redirect(url_for('school.edit_student', student_id=student.id))

    all_subjects = Subject.query.filter_by(grade_id=sg.grade_id, archived=False).order_by(Subject.name).all()

    if request.method == 'POST':
        action = request.form.get('action')
        subject_id = request.form.get('subject_id')

        if action == 'exclude':
            if not StudentExcludedSubject.query.filter_by(student_id=student.id, subject_id=subject_id).first():
                db.session.add(StudentExcludedSubject(student_id=student.id, subject_id=subject_id))
                db.session.commit()
                flash('Materia quitada', 'success')
        elif action == 'restore':
            StudentExcludedSubject.query.filter_by(student_id=student.id, subject_id=subject_id).delete()
            db.session.commit()
            flash('Materia devuelta', 'success')

        return redirect(url_for('school.manage_student_subjects', student_id=student.id))

    excluded_ids = {e.subject_id for e in StudentExcludedSubject.query.filter_by(student_id=student.id).all()}
    subjects_info = [{'subject': s, 'is_excluded': s.id in excluded_ids} for s in all_subjects]

    return render_template('school_student_subjects.html', student=student, grade=sg.grade, subjects_info=subjects_info)

@school_bp.route('/student/<int:student_id>/report')
@login_required
@school_required
def student_report(student_id):
    student = User.query.get_or_404(student_id)
    if student.school_id != current_user.school_id:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('school.dashboard'))

    student_grade = StudentGrade.query.filter_by(student_id=student.id).first()
    if not student_grade:
        flash('El estudiante no tiene grado asignado', 'warning')
        return redirect(url_for('school.students_list'))

    grade = student_grade.grade
    subjects = Subject.query.filter_by(grade_id=grade.id, archived=False).all()

    grades_by_subject = []
    for subject in subjects:
        items = []
        assignments = Assignment.query.filter_by(subject_id=subject.id).all()
        for a in assignments:
            gr = GradeRecord.query.filter_by(assignment_id=a.id, student_id=student.id).first()
            items.append({'type': '📝 Tarea', 'title': a.title, 'date': a.date_assigned, 'grade': gr.grade if gr else None, 'max': 5.0})

        exercises = Exercise.query.filter_by(subject_id=subject.id).all()
        for ex in exercises:
            sub = ExerciseSubmission.query.filter_by(exercise_id=ex.id, student_id=student.id).first()
            total = sum(q.points for q in ex.questions) if ex.questions else ex.max_grade
            items.append({'type': '✏️ Parcial', 'title': ex.title, 'date': sub.submitted_at if sub else ex.created_at, 'grade': sub.grade if sub else None, 'max': total})

        forums = Forum.query.filter_by(subject_id=subject.id).all()
        for f in forums:
            fg = ForumGrade.query.filter_by(forum_id=f.id, student_id=student.id).first()
            items.append({'type': '💬 Foro', 'title': f.title, 'date': f.created_at, 'grade': fg.grade if fg else None, 'max': 5.0})

        items.sort(key=lambda x: x['date'] or datetime.min, reverse=True)
        calificados = [i for i in items if i['grade'] is not None]
        promedio = sum(i['grade'] for i in calificados) / len(calificados) if calificados else None

        grades_by_subject.append({'subject': subject, 'items': items, 'promedio': promedio})

    return render_template('school_student_report.html', student=student, grade=grade, grades_by_subject=grades_by_subject)

# ============================================
# ACUDIENTES
# ============================================
@school_bp.route('/guardians')
@login_required
@school_required
def guardians_list():
    school = current_user.school
    guardians = User.query.filter_by(school_id=school.id, role='guardian').all()

    guardian_students = {}
    for g in guardians:
        links = GuardianStudent.query.filter_by(guardian_id=g.id).all()
        guardian_students[g.id] = [link.student for link in links]

    return render_template('school_guardians.html', guardians=guardians, guardian_students=guardian_students)

@school_bp.route('/create_guardian', methods=['GET', 'POST'])
@login_required
@school_required
def create_guardian():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = (request.form['email'] or '').strip().lower()
        password = request.form['password']

        if User.query.filter_by(email=email).first():
            flash('Ya existe un usuario con ese correo', 'danger')
            return redirect(url_for('school.create_guardian'))

        user = User(email=email, name=name, role='guardian', school_id=current_user.school_id)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f'Acudiente {name} creado', 'success')
        return redirect(url_for('school.link_guardian', guardian_id=user.id))

    return render_template('school_create_guardian.html')

@school_bp.route('/link_guardian/<int:guardian_id>', methods=['GET', 'POST'])
@login_required
@school_required
def link_guardian(guardian_id):
    guardian = User.query.get_or_404(guardian_id)
    if guardian.school_id != current_user.school_id:
        return redirect(url_for('school.guardians_list'))

    students = User.query.filter_by(school_id=current_user.school_id, role='student').all()

    if request.method == 'POST':
        action = request.form.get('action')
        student_id = request.form.get('student_id')

        if action == 'link' and not GuardianStudent.query.filter_by(guardian_id=guardian.id, student_id=student_id).first():
            db.session.add(GuardianStudent(guardian_id=guardian.id, student_id=student_id))
            db.session.commit()
            flash('Estudiante vinculado', 'success')
        elif action == 'unlink':
            GuardianStudent.query.filter_by(guardian_id=guardian.id, student_id=student_id).delete()
            db.session.commit()
            flash('Estudiante desvinculado', 'success')

        return redirect(url_for('school.link_guardian', guardian_id=guardian.id))

    linked_ids = {link.student_id for link in GuardianStudent.query.filter_by(guardian_id=guardian.id).all()}
    students_info = []
    for s in students:
        sg = StudentGrade.query.filter_by(student_id=s.id).first()
        students_info.append({'student': s, 'grade': sg.grade.name if sg else None, 'is_linked': s.id in linked_ids})

    return render_template('school_link_guardian.html', guardian=guardian, students_info=students_info)

@school_bp.route('/delete_guardian/<int:guardian_id>')
@login_required
@school_required
def delete_guardian(guardian_id):
    guardian = User.query.get_or_404(guardian_id)
    if guardian.school_id != current_user.school_id:
        return redirect(url_for('school.guardians_list'))

    GuardianStudent.query.filter_by(guardian_id=guardian.id).delete()
    db.session.delete(guardian)
    db.session.commit()
    flash('Acudiente eliminado', 'success')
    return redirect(url_for('school.guardians_list'))

@school_bp.route('/toggle_block_guardian/<int:guardian_id>')
@login_required
@school_required
def toggle_block_guardian(guardian_id):
    guardian = User.query.get_or_404(guardian_id)
    if guardian.school_id != current_user.school_id:
        return redirect(url_for('school.guardians_list'))

    guardian.blocked = not guardian.blocked
    db.session.commit()
    flash(f'Acudiente {"bloqueado" if guardian.blocked else "desbloqueado"}', 'success' if not guardian.blocked else 'warning')
    return redirect(url_for('school.guardians_list'))

# ============================================
# MENSAJES MASIVOS
# ============================================
@school_bp.route('/send_message', methods=['POST'])
@login_required
@school_required
def send_message():
    receiver_role = request.form['receiver_role']
    subject = request.form['subject']
    body = request.form['body']
    msg = Message(sender_id=current_user.id, receiver_role=receiver_role, subject=subject, body=body)
    db.session.add(msg)
    db.session.commit()
    flash('Mensaje enviado', 'success')
    return redirect(url_for('school.dashboard'))