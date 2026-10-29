from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, User, School, Grade, TeacherSubject, StudentGrade, Message
from functools import wraps
from datetime import datetime, timedelta

super_admin_bp = Blueprint('super_admin', __name__)


def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != 'super_admin':
            flash('Acceso denegado', 'danger')
            return redirect(url_for('auth.index'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================
# DASHBOARD
# ============================================
@super_admin_bp.route('/')
@login_required
@super_admin_required
def dashboard():
    schools = School.query.all()
    schools_data = []
    total_teachers = 0
    total_students = 0
    total_grades = 0

    for school in schools:
        director = User.query.filter_by(school_id=school.id, role='school').first()
        teachers = User.query.filter_by(school_id=school.id, role='teacher').all()
        students = User.query.filter_by(school_id=school.id, role='student').all()
        grades_count = Grade.query.filter_by(school_id=school.id).count()

        total_teachers += len(teachers)
        total_students += len(students)
        total_grades += grades_count

        schools_data.append({
            'school': school,
            'director': director,
            'teachers_count': len(teachers),
            'students_count': len(students),
            'grades_count': grades_count,
        })

    return render_template('super_admin_dashboard.html',
                           schools_data=schools_data,
                           total_schools=len(schools),
                           total_teachers=total_teachers,
                           total_students=total_students,
                           total_grades=total_grades,
                           now=datetime.utcnow()) # <-- IMPORTANTE PARA LA FECHA


# ============================================
# CREAR INSTITUCIÓN
# ============================================
@super_admin_bp.route('/create_school', methods=['POST'])
@login_required
@super_admin_required
def create_school():
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']
    address = request.form.get('address', '')
    phone = request.form.get('phone', '')

    if User.query.filter_by(email=email).first():
        flash('Ya existe un usuario con ese correo', 'danger')
        return redirect(url_for('super_admin.dashboard'))

    school = School(name=name, address=address, phone=phone)
    
    # ⬇️ ASIGNAR AUTOMÁTICAMENTE LOS 45 DÍAS DE PRUEBA ⬇️
    school.license_expiry = datetime.utcnow() + timedelta(days=45)
    
    db.session.add(school)
    db.session.flush()

    user = User(email=email, name=f"Admin - {name}", role='school', school_id=school.id)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    flash('Institución creada correctamente. Se le han asignado 45 días de prueba.', 'success')
    return redirect(url_for('super_admin.dashboard'))


# ============================================
# VER DETALLE DE INSTITUCIÓN
# ============================================
@super_admin_bp.route('/school/<int:school_id>')
@login_required
@super_admin_required
def view_school(school_id):
    school = School.query.get_or_404(school_id)
    director = User.query.filter_by(school_id=school.id, role='school').first()
    teachers = User.query.filter_by(school_id=school.id, role='teacher').all()
    students = User.query.filter_by(school_id=school.id, role='student').all()
    grades = Grade.query.filter_by(school_id=school.id).all()
    guardians = User.query.filter_by(school_id=school.id, role='guardian').all()

    return render_template('super_admin_view_school.html',
                           school=school, director=director,
                           teachers=teachers, students=students,
                           grades=grades, guardians=guardians)


# ============================================
# ACTIVAR / SUSPENDER
# ============================================
@super_admin_bp.route('/toggle_school/<int:school_id>')
@login_required
@super_admin_required
def toggle_school(school_id):
    school = School.query.get_or_404(school_id)
    school.active = not school.active
    db.session.commit()
    estado = "activada" if school.active else "suspendida"
    flash(f'Institución {school.name} {estado}', 'success')
    return redirect(url_for('super_admin.dashboard'))


# ============================================
# ELIMINAR INSTITUCIÓN
# ============================================
@super_admin_bp.route('/delete_school/<int:school_id>')
@login_required
@super_admin_required
def delete_school(school_id):
    school = School.query.get_or_404(school_id)

    # Eliminar dependencias primero (evita dejar datos huérfanos)
    # 1. Grados de la escuela -> sus materias, asignaciones y exclusiones
    grades = Grade.query.filter_by(school_id=school.id).all()
    for g in grades:
        subjects = g.subjects
        for s in subjects:
            from models import StudentExcludedSubject, TeacherSubject
            StudentExcludedSubject.query.filter_by(subject_id=s.id).delete()
            TeacherSubject.query.filter_by(subject_id=s.id).delete()
            db.session.delete(s)
        db.session.delete(g)

    # 2. Usuarios de la escuela
    User.query.filter_by(school_id=school.id).delete()

    # 3. La escuela
    db.session.delete(school)
    db.session.commit()

    flash(f'Institución {school.name} eliminada permanentemente', 'success')
    return redirect(url_for('super_admin.dashboard'))


# ============================================
# ENVIAR NOTIFICACIÓN
# ============================================
@super_admin_bp.route('/send_notification/<int:school_id>', methods=['POST'])
@login_required
@super_admin_required
def send_notification(school_id):
    school = School.query.get_or_404(school_id)
    director = User.query.filter_by(school_id=school.id, role='school').first()

    if not director:
        flash('Esta institución no tiene directivo asignado', 'danger')
        return redirect(url_for('super_admin.dashboard'))

    subject = request.form['subject']
    body = request.form['body']

    msg = Message(sender_id=current_user.id,
                  receiver_id=director.id,
                  subject=subject,
                  body=body)
    db.session.add(msg)
    db.session.commit()

    flash(f'Notificación enviada al directivo de {school.name}', 'success')
    return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/reset_password/<int:school_id>', methods=['POST'])
@login_required
@super_admin_required
def reset_password(school_id):
    school = School.query.get_or_404(school_id)
    director = User.query.filter_by(school_id=school.id, role='school').first()
    
    if not director:
        flash('Esta institución no tiene directivo asignado', 'danger')
        return redirect(url_for('super_admin.dashboard'))

    new_password = request.form.get('new_password', '').strip()
    
    if not new_password or len(new_password) < 6:
        flash('La contraseña debe tener al menos 6 caracteres', 'danger')
        return redirect(url_for('super_admin.view_school', school_id=school.id))

    director.set_password(new_password)
    db.session.commit()
    flash(f'Contraseña del director {director.name} actualizada correctamente', 'success')
    
    return redirect(url_for('super_admin.view_school', school_id=school.id))

@super_admin_bp.route('/renew_license/<int:school_id>')
@login_required
@super_admin_required
def renew_license(school_id):
    school = School.query.get_or_404(school_id)
    
    ahora = datetime.utcnow()
    
    # Si el colegio está en prueba (o no tiene licencia), la licencia anual se calcula 
    # para que el tiempo total (prueba + licencia) sea exactamente de 365 días.
    if not school.license_expiry or school.license_expiry < ahora:
        # Si ya expiró o no tiene, le damos el año completo desde hoy.
        school.license_expiry = ahora + timedelta(days=365)
    else:
        # Si está en prueba, calculamos cuántos días le faltan para completar el año.
        # Sabemos que la prueba es de 45 días. Entonces, si aún no ha vencido, 
        # le sumamos (365 - 45) = 320 días a su fecha actual de vencimiento de prueba.
        # Esto da exactamente 365 días desde que se registró.
        school.license_expiry = school.license_expiry + timedelta(days=320)
        
    db.session.commit()
    flash(f'✅ Licencia Anual de "{school.name}" activada. Vence el {school.license_expiry.strftime("%d/%m/%Y")}', 'success')
    return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/remove_year/<int:school_id>')
@login_required
@super_admin_required
def remove_year(school_id):
    school = School.query.get_or_404(school_id)
    if school.license_expiry:
        school.license_expiry = school.license_expiry - timedelta(days=365)
        db.session.commit()
        flash(f'Se le restó 1 año a la licencia de {school.name}. Nueva fecha: {school.license_expiry.strftime("%d/%m/%Y")}', 'warning')
    return redirect(url_for('super_admin.dashboard'))