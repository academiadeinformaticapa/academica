import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta-super-segura'
    
    # CONEXIÓN A SUPABASE (Con las comillas simples al inicio y final)
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres.rovpccxgemscxwhjzkwy:12demarzo81@aws-1-us-west-2.pooler.supabase.com:5432/postgres'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB