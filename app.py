from flask import Flask, send_from_directory
from config import Config
from models import db, User
from auth import auth_bp
from super_admin import super_admin_bp
from school import school_bp
from teacher import teacher_bp
from student import student_bp
from guardian import guardian_bp
from flask_login import LoginManager
import os


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Asegurar carpeta de uploads
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    app.register_blueprint(auth_bp)
    app.register_blueprint(super_admin_bp, url_prefix='/super_admin')
    app.register_blueprint(school_bp, url_prefix='/school')
    app.register_blueprint(teacher_bp, url_prefix='/teacher')
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(guardian_bp, url_prefix='/guardian')

    # Ruta para descargar archivos subidos
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(role='super_admin').first():
            admin = User(email='admin@laacademia.com', name='Administrador', role='super_admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Super admin creado: admin@laacademia.com / admin123")
    app.run(debug=True, host='0.0.0.0', port=5000)