from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20))
    name = db.Column(db.String(100), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=True)
    blocked = db.Column(db.Boolean, default=False)
    school = db.relationship('School', backref='members', foreign_keys=[school_id])
    teacher_subjects = db.relationship('TeacherSubject', backref='teacher', lazy='dynamic')
    guardian_students = db.relationship('GuardianStudent',
                                        foreign_keys='GuardianStudent.guardian_id',
                                        backref='guardian', lazy='dynamic')
    grade_records = db.relationship('GradeRecord',
                                    foreign_keys='GradeRecord.student_id',
                                    backref='grade_student',
                                    lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class School(db.Model):
    __tablename__ = 'schools'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    active = db.Column(db.Boolean, default=True)
    period_type = db.Column(db.String(20), default='Trimestres')
    license_expiry = db.Column(db.DateTime)


class Grade(db.Model):
    __tablename__ = 'grades'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'))
    archived = db.Column(db.Boolean, default=False)
    school = db.relationship('School', backref='grades')


class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    grade_id = db.Column(db.Integer, db.ForeignKey('grades.id'))
    archived = db.Column(db.Boolean, default=False)
    grade = db.relationship('Grade', backref='subjects')


class TeacherSubject(db.Model):
    __tablename__ = 'teacher_subjects'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    subject = db.relationship('Subject', backref='teachers')


class StudentGrade(db.Model):
    __tablename__ = 'student_grades'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    grade_id = db.Column(db.Integer, db.ForeignKey('grades.id'))
    student = db.relationship('User', foreign_keys=[student_id])
    grade = db.relationship('Grade', backref='students')


class Assignment(db.Model):
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    date_assigned = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime)
    type = db.Column(db.String(20))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    subject = db.relationship('Subject', backref='assignments')
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    period = db.Column(db.String(50))


class GradeRecord(db.Model):
    __tablename__ = 'grade_records'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    grade = db.Column(db.Float)
    assignment = db.relationship('Assignment', backref='records')
    student = db.relationship('User', foreign_keys=[student_id])


class Attendance(db.Model):
    __tablename__ = 'attendances'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20))
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    subject = db.relationship('Subject', backref='attendances')
    student = db.relationship('User', foreign_keys=[student_id])


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    receiver_role = db.Column(db.String(20))
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')


class GuardianStudent(db.Model):
    __tablename__ = 'guardian_students'
    id = db.Column(db.Integer, primary_key=True)
    guardian_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    student = db.relationship('User', foreign_keys=[student_id])


class StudentExcludedSubject(db.Model):
    __tablename__ = 'student_excluded_subjects'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    student = db.relationship('User', foreign_keys=[student_id])
    subject = db.relationship('Subject')
    __table_args__ = (db.UniqueConstraint('student_id', 'subject_id', name='uq_student_subject'),)


class Forum(db.Model):
    __tablename__ = 'forums'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    subject = db.relationship('Subject', backref='forums')
    teacher = db.relationship('User', foreign_keys=[teacher_id])
    posts = db.relationship('ForumPost', backref='forum', lazy='dynamic',
                            cascade='all, delete-orphan')
    period = db.Column(db.String(50))


class ForumPost(db.Model):
    __tablename__ = 'forum_posts'
    id = db.Column(db.Integer, primary_key=True)
    forum_id = db.Column(db.Integer, db.ForeignKey('forums.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship('User', foreign_keys=[author_id])


class SubjectFile(db.Model):
    __tablename__ = 'subject_files'
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    filename = db.Column(db.String(300), nullable=False)
    original_filename = db.Column(db.String(300), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    subject = db.relationship('Subject', backref='files')
    teacher = db.relationship('User', foreign_keys=[teacher_id])


class Announcement(db.Model):
    __tablename__ = 'announcements'
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    subject = db.relationship('Subject', backref='announcements')
    teacher = db.relationship('User', foreign_keys=[teacher_id])


class Exercise(db.Model):
    __tablename__ = 'exercises'
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    due_date = db.Column(db.DateTime)
    max_grade = db.Column(db.Float, default=5.0)
    max_attempts = db.Column(db.Integer, default=2)
    time_limit = db.Column(db.Integer, default=0)  # ⬅️ NUEVO CAMPO AQUÍ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    subject = db.relationship('Subject', backref='exercises')
    teacher = db.relationship('User', foreign_keys=[teacher_id])
    submissions = db.relationship('ExerciseSubmission', backref='exercise',
                                  lazy='dynamic', cascade='all, delete-orphan')
    period = db.Column(db.String(50))


class ExerciseSubmission(db.Model):
    __tablename__ = 'exercise_submissions'
    id = db.Column(db.Integer, primary_key=True)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercises.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    answer_text = db.Column(db.Text)
    file_path = db.Column(db.String(300))
    original_filename = db.Column(db.String(300))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    grade = db.Column(db.Float)
    feedback = db.Column(db.Text)
    attempts = db.Column(db.Integer, default=0)
    attempt_started_at = db.Column(db.DateTime)  # ⬅️ NUEVO CAMPO AQUÍ
    student = db.relationship('User', foreign_keys=[student_id])


class ExerciseQuestion(db.Model):
    __tablename__ = 'exercise_questions'
    id = db.Column(db.Integer, primary_key=True)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercises.id'), nullable=False)
    order_index = db.Column(db.Integer, default=0)
    question_type = db.Column(db.String(20), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    points = db.Column(db.Float, default=1.0)
    correct_answer = db.Column(db.String(500))
    exercise = db.relationship('Exercise',
                               backref=db.backref('questions',
                                                  order_by='ExerciseQuestion.order_index',
                                                  cascade='all, delete-orphan'))
    options = db.relationship('QuestionOption', backref='question',
                              lazy='dynamic', cascade='all, delete-orphan')


class QuestionOption(db.Model):
    __tablename__ = 'question_options'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('exercise_questions.id'), nullable=False)
    option_text = db.Column(db.String(500), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)


class QuestionAnswer(db.Model):
    __tablename__ = 'question_answers'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('exercise_questions.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    selected_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id'), nullable=True)
    answer_text = db.Column(db.Text)
    true_false_value = db.Column(db.String(10))
    earned_points = db.Column(db.Float)
    feedback = db.Column(db.Text)
    question = db.relationship('ExerciseQuestion', backref='answers')
    student = db.relationship('User', foreign_keys=[student_id])
    selected_option = db.relationship('QuestionOption', foreign_keys=[selected_option_id])


class ForumGrade(db.Model):
    __tablename__ = 'forum_grades'
    id = db.Column(db.Integer, primary_key=True)
    forum_id = db.Column(db.Integer, db.ForeignKey('forums.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    grade = db.Column(db.Float)
    feedback = db.Column(db.Text)
    graded_at = db.Column(db.DateTime, default=datetime.utcnow)
    forum = db.relationship('Forum', backref='grades')
    student = db.relationship('User', foreign_keys=[student_id])
    __table_args__ = (db.UniqueConstraint('forum_id', 'student_id', name='uq_forum_student'),)


class TeacherProfile(db.Model):
    __tablename__ = 'teacher_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    contact_email = db.Column(db.String(120))
    degree = db.Column(db.String(150))
    bio = db.Column(db.Text)
    show_contact = db.Column(db.Boolean, default=True)
    user = db.relationship('User', backref=db.backref('teacher_profile', uselist=False))


class AssignmentSubmission(db.Model):
    __tablename__ = 'assignment_submissions'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    answer_text = db.Column(db.Text)
    file_path = db.Column(db.String(300))
    original_filename = db.Column(db.String(300))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    assignment = db.relationship('Assignment', backref=db.backref('submissions', cascade='all, delete-orphan'))
    student = db.relationship('User', foreign_keys=[student_id])


class CustomColumn(db.Model):
    __tablename__ = 'custom_columns'
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    subject = db.relationship('Subject', backref=db.backref('custom_columns', cascade='all, delete-orphan'))
    grades = db.relationship('CustomGrade', backref='column', cascade='all, delete-orphan')


class CustomGrade(db.Model):
    __tablename__ = 'custom_grades'
    id = db.Column(db.Integer, primary_key=True)
    column_id = db.Column(db.Integer, db.ForeignKey('custom_columns.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    grade = db.Column(db.Float)
    student = db.relationship('User', foreign_keys=[student_id])


class StudentFileView(db.Model):
    __tablename__ = 'student_file_views'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey('subject_files.id'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)


class StudentForumView(db.Model):
    __tablename__ = 'student_forum_views'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    forum_id = db.Column(db.Integer, db.ForeignKey('forums.id'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)

class SchoolPeriod(db.Model):
    __tablename__ = 'school_periods'
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    school = db.relationship('School', backref='periods')
 