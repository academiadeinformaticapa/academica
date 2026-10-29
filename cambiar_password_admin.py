from app import create_app
from models import db, User

app = create_app()

with app.app_context():
    # Buscamos al usuario con rol de super_admin
    admin = User.query.filter_by(role='super_admin').first()
    
    if admin:
        print(f"Usuario encontrado: {admin.email}")
        nueva_clave = input("Escribe tu nueva contraseña: ")
        
        # Encriptamos y guardamos la nueva contraseña
        admin.set_password(nueva_clave)
        db.session.commit()
        
        print("✅ ¡Contraseña cambiada exitosamente! Ya puedes iniciar sesión con la nueva clave.")
    else:
        print("❌ No se encontró ningún Súper Admin en la base de datos.")