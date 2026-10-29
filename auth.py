from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, School
from datetime import datetime, timedelta  # <-- AQUÍ ESTÁ LA SOLUCIÓN

auth_bp = Blueprint('auth', __name__)

CONTACT_EMAIL = 'academiadeinformaticapa@gmail.com'

@auth_bp.route('/')
def index():
    return render_template('index.html', contact_email=CONTACT_EMAIL)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if user.role != 'super_admin' and user.school:
                # 1. Verificar si la institución está suspendida manualmente
                if not user.school.active:
                    flash('Tu institución ha sido suspendida. Contacta al administrador.', 'danger')
                    return render_template('login.html')

                # 2. Verificar si la licencia expiró
                if user.school.license_expiry and datetime.utcnow() > user.school.license_expiry:
                    flash('⏳ Tu licencia de uso ha expirado. Por favor, contacta al administrador para renovar tu suscripción anual ($10).', 'danger')
                    return render_template('login.html')

            login_user(user)
            if user.role == 'super_admin':
                return redirect(url_for('super_admin.dashboard'))
            elif user.role == 'school':
                return redirect(url_for('school.dashboard'))
            elif user.role == 'teacher':
                return redirect(url_for('teacher.dashboard'))
            elif user.role == 'student':
                return redirect(url_for('student.dashboard'))
            elif user.role == 'guardian':
                return redirect(url_for('guardian.dashboard'))
        else:
            flash('Correo o contraseña incorrectos', 'danger')
    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    if request.method == 'POST':
        school_name = request.form.get('school_name', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip()
        director_name = request.form.get('director_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        errors = []
        if not school_name: errors.append('El nombre de la institución es obligatorio.')
        if not director_name: errors.append('El nombre del directivo es obligatorio.')
        if not email: errors.append('El correo es obligatorio.')
        if not password or len(password) < 6: errors.append('La contraseña debe tener al menos 6 caracteres.')
        if password != password2: errors.append('Las contraseñas no coinciden.')
        if User.query.filter_by(email=email).first(): errors.append('Ya existe una cuenta con ese correo electrónico.')
        if School.query.filter_by(name=school_name).first(): errors.append('Ya existe una institución con ese nombre.')

        if errors:
            for e in errors: flash(e, 'danger')
            return render_template('register.html', school_name=school_name, address=address, phone=phone, director_name=director_name, email=email)

        # CREAR INSTITUCIÓN ACTIVA DESDE EL PRIMER MOMENTO
        school = School(name=school_name, address=address, phone=phone, active=True) # <-- Cambiado a True
        school.license_expiry = datetime.utcnow() + timedelta(days=45) # <-- Asigna 45 días
        
        db.session.add(school)
        db.session.flush()

        director = User(email=email, name=director_name, role='school', school_id=school.id)
        director.set_password(password)
        db.session.add(director)
        db.session.commit()

        # MENSAJE DE ÉXITO Y REDIRECCIÓN AL LOGIN
        flash(f'¡Institución "{school_name}" registrada con éxito! Tienes 45 días de prueba gratis. Ya puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/pending_activation/<int:school_id>')
def pending_activation(school_id):
    school = School.query.get_or_404(school_id)
    return render_template('pending_activation.html',
                           school=school,
                           contact_email=CONTACT_EMAIL)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.index'))