"""
Backend Flask per autenticazione e gestione utenti
Supporta login/registrazione standard, Google OAuth e Apple Sign In
"""

from flask import Flask, request, jsonify, redirect, url_for, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import os
import secrets
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Carica variabili d'ambiente dal file .env
load_dotenv()

# OAuth libraries
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
# Usa DATABASE_URL da .env, fallback a SQLite solo se non configurato
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///kimerika.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# JWT Configuration
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', secrets.token_hex(32))
app.config['JWT_EXPIRATION_DELTA'] = datetime.timedelta(days=7)

# OAuth Configuration
app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID', '')
app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET', '')
app.config['APPLE_CLIENT_ID'] = os.environ.get('APPLE_CLIENT_ID', '')
app.config['APPLE_CLIENT_SECRET'] = os.environ.get('APPLE_CLIENT_SECRET', '')

# Email Configuration (per recupero password)
app.config['SMTP_SERVER'] = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
app.config['SMTP_PORT'] = int(os.environ.get('SMTP_PORT', '587'))
app.config['SMTP_USERNAME'] = os.environ.get('SMTP_USERNAME', '')
app.config['SMTP_PASSWORD'] = os.environ.get('SMTP_PASSWORD', '')
app.config['FROM_EMAIL'] = os.environ.get('FROM_EMAIL', 'noreply@kimerika.com')

CORS(app)
db = SQLAlchemy(app)
oauth = OAuth(app)

# ===================================
# DATABASE MODELS
# ===================================

class User(db.Model):
    """Modello utente"""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)  # Nullable per OAuth users
    firstname = db.Column(db.String(50), nullable=False)
    lastname = db.Column(db.String(50), nullable=False)
    plan = db.Column(db.String(20), default='none')  # none, monthly, annual
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # OAuth fields
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    apple_id = db.Column(db.String(100), unique=True, nullable=True)

    # Trial and subscription
    trial_ends_at = db.Column(db.DateTime)
    subscription_ends_at = db.Column(db.DateTime)

    # Usage tracking
    analyses_count = db.Column(db.Integer, default=0)
    analyses_limit = db.Column(db.Integer, default=0)  # 0 = no plan, -1 = unlimited
    
    # Profile image
    profile_image = db.Column(db.String(255), nullable=True)  # Path to profile image
    
    # Additional profile info
    phone = db.Column(db.String(20), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    language = db.Column(db.String(5), default='it')  # Lingua preferita
    notifications_enabled = db.Column(db.Boolean, default=True)

    # Admin role
    role = db.Column(db.String(20), default='user', nullable=False)  # 'user' or 'admin'

    def set_password(self, password):
        """Hash e salva password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifica password"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Converti user in dizionario"""
        return {
            'id': self.id,
            'email': self.email,
            'firstname': self.firstname,
            'lastname': self.lastname,
            'role': self.role,
            'plan': self.plan,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'trial_ends_at': self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            'subscription_ends_at': self.subscription_ends_at.isoformat() if self.subscription_ends_at else None,
            'analyses_count': self.analyses_count,
            'analyses_limit': self.analyses_limit,
            'profile_image': self.profile_image,
            'phone': self.phone,
            'bio': self.bio,
            'language': self.language,
            'notifications_enabled': self.notifications_enabled,
            'has_google': self.google_id is not None,
            'has_apple': self.apple_id is not None,
            'has_password': self.password_hash is not None
        }


class PasswordResetToken(db.Model):
    """Token per reset password"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref='reset_tokens')


class AdminAuditLog(db.Model):
    """Audit log per azioni admin"""
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)  # e.g., 'user_deactivated', 'plan_changed'
    target_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    details = db.Column(db.JSON, nullable=True)  # Additional action details
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    admin = db.relationship('User', foreign_keys=[admin_id], backref='admin_actions')
    target_user = db.relationship('User', foreign_keys=[target_user_id])


class UserActivity(db.Model):
    """Tracciamento attività utenti nella webapp"""
    __tablename__ = 'user_activity'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)  # 'login', 'analysis', 'image_upload', 'video_upload', 'webcam_start'
    action_details = db.Column(db.JSON, nullable=True)  # Additional details
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, index=True)
    
    user = db.relationship('User', backref='activities')


# ===================================
# OAUTH SETUP
# ===================================

# Google OAuth
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# Apple OAuth
apple = oauth.register(
    name='apple',
    client_id=app.config['APPLE_CLIENT_ID'],
    client_secret=app.config['APPLE_CLIENT_SECRET'],
    server_metadata_url='https://appleid.apple.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'name email'}
)


# ===================================
# JWT UTILITIES
# ===================================

def generate_token(user_id):
    """Genera JWT token"""
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + app.config['JWT_EXPIRATION_DELTA'],
        'iat': datetime.datetime.utcnow()
    }
    token = jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')
    return token


def decode_token(token):
    """Decodifica JWT token"""
    try:
        payload = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def token_required(f):
    """Decorator per proteggere endpoint con JWT"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Get token from header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
            except IndexError:
                return jsonify({'success': False, 'message': 'Token format invalido'}), 401

        if not token:
            return jsonify({'success': False, 'message': 'Token mancante'}), 401

        # Decode token
        payload = decode_token(token)
        if not payload:
            return jsonify({'success': False, 'message': 'Token invalido o scaduto'}), 401

        # Get user
        user = User.query.get(payload['user_id'])
        if not user or not user.is_active:
            return jsonify({'success': False, 'message': 'Utente non trovato o disabilitato'}), 401

        # Pass user to endpoint
        return f(user, *args, **kwargs)

    return decorated


def admin_required(f):
    """Decorator per endpoint solo admin"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]
            except IndexError:
                return jsonify({'success': False, 'message': 'Token format invalido'}), 401

        if not token:
            return jsonify({'success': False, 'message': 'Token mancante'}), 401

        payload = decode_token(token)
        if not payload:
            return jsonify({'success': False, 'message': 'Token invalido o scaduto'}), 401

        user = User.query.get(payload['user_id'])
        if not user or not user.is_active:
            return jsonify({'success': False, 'message': 'Utente non trovato o disabilitato'}), 401

        if user.role != 'admin':
            return jsonify({'success': False, 'message': 'Accesso non autorizzato - richiesto ruolo admin'}), 403

        return f(user, *args, **kwargs)

    return decorated


# ===================================
# AUTHENTICATION ENDPOINTS
# ===================================

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    """Registrazione nuovo utente"""
    try:
        data = request.get_json()

        # Validazione
        required_fields = ['email', 'password', 'firstname', 'lastname']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'Campo {field} richiesto'
                }), 400

        email = data['email'].lower().strip()
        password = data['password']
        firstname = data['firstname'].strip()
        lastname = data['lastname'].strip()
        plan = data.get('plan', 'none')  # Default: nessun piano attivo

        # Verifica se email già esiste
        if User.query.filter_by(email=email).first():
            return jsonify({
                'success': False,
                'message': 'Email già registrata'
            }), 400

        # Validazione password
        if len(password) < 8:
            return jsonify({
                'success': False,
                'message': 'Password deve essere almeno 8 caratteri'
            }), 400

        # Crea utente (senza trial automatico - devono passare per demo + pagamento)
        user = User(
            email=email,
            firstname=firstname,
            lastname=lastname,
            plan=plan
            # trial_ends_at verrà impostato dopo l'acquisto
        )
        user.set_password(password)

        # Imposta limiti in base al piano
        plan_limits = {
            'none': 0,
            'monthly': -1,  # Illimitato
            'annual': -1    # Illimitato
        }
        user.analyses_limit = plan_limits.get(plan, 0)

        db.session.add(user)
        db.session.commit()

        # Genera token
        token = generate_token(user.id)

        return jsonify({
            'success': True,
            'message': 'Account creato con successo',
            'token': token,
            'user': user.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"Signup error: {e}")
        return jsonify({
            'success': False,
            'message': 'Errore durante la registrazione'
        }), 500


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login utente"""
    try:
        data = request.get_json()

        email = data.get('email', '').lower().strip()
        password = data.get('password', '')

        if not email or not password:
            return jsonify({
                'success': False,
                'message': 'Email e password richiesti'
            }), 400

        # Trova utente
        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            return jsonify({
                'success': False,
                'message': 'Credenziali non valide'
            }), 401

        if not user.is_active:
            return jsonify({
                'success': False,
                'message': 'Account disabilitato'
            }), 401

        # Aggiorna last login
        user.last_login = datetime.datetime.utcnow()
        db.session.commit()

        # Genera token
        token = generate_token(user.id)

        return jsonify({
            'success': True,
            'message': 'Login effettuato con successo',
            'token': token,
            'user': user.to_dict()
        })

    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({
            'success': False,
            'message': 'Errore durante il login'
        }), 500


@app.route('/api/auth/verify', methods=['GET'])
@token_required
def verify_token(user):
    """Verifica validità token"""
    return jsonify({
        'success': True,
        'user': user.to_dict()
    })


@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    """Richiesta reset password"""
    try:
        data = request.get_json()
        email = data.get('email', '').lower().strip()

        if not email:
            return jsonify({
                'success': False,
                'message': 'Email richiesta'
            }), 400

        user = User.query.filter_by(email=email).first()

        # Sempre ritorna successo per sicurezza (non rivelare se email esiste)
        if user:
            # Genera token reset
            reset_token = secrets.token_urlsafe(32)
            expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=1)

            token_obj = PasswordResetToken(
                user_id=user.id,
                token=reset_token,
                expires_at=expires_at
            )
            db.session.add(token_obj)
            db.session.commit()

            # Invia email (se configurato)
            send_password_reset_email(user, reset_token)

        return jsonify({
            'success': True,
            'message': 'Se l\'email esiste, riceverai le istruzioni per il reset'
        })

    except Exception as e:
        print(f"Forgot password error: {e}")
        return jsonify({
            'success': False,
            'message': 'Errore durante la richiesta'
        }), 500


@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """Reset password con token"""
    try:
        data = request.get_json()
        token = data.get('token')
        new_password = data.get('password')

        if not token or not new_password:
            return jsonify({
                'success': False,
                'message': 'Token e password richiesti'
            }), 400

        # Trova token
        reset_token = PasswordResetToken.query.filter_by(
            token=token,
            used=False
        ).first()

        if not reset_token:
            return jsonify({
                'success': False,
                'message': 'Token non valido'
            }), 400

        # Verifica scadenza
        if datetime.datetime.utcnow() > reset_token.expires_at:
            return jsonify({
                'success': False,
                'message': 'Token scaduto'
            }), 400

        # Valida password
        if len(new_password) < 8:
            return jsonify({
                'success': False,
                'message': 'Password deve essere almeno 8 caratteri'
            }), 400

        # Aggiorna password
        user = reset_token.user
        user.set_password(new_password)
        reset_token.used = True
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Password aggiornata con successo'
        })

    except Exception as e:
        db.session.rollback()
        print(f"Reset password error: {e}")
        return jsonify({
            'success': False,
            'message': 'Errore durante il reset'
        }), 500


# ===================================
# GOOGLE OAUTH ENDPOINTS
# ===================================

@app.route('/api/auth/google/login')
def google_login():
    """Inizia Google OAuth login"""
    redirect_uri = url_for('google_callback', _external=True)
    # Passa lo stato per distinguere login da signup
    return google.authorize_redirect(redirect_uri, state='login')


@app.route('/api/auth/google/signup')
def google_signup():
    """Inizia Google OAuth signup (registrazione)"""
    redirect_uri = url_for('google_callback', _external=True)
    # Salva il piano selezionato nella sessione
    plan = request.args.get('plan', 'starter')
    session['selected_plan'] = plan
    return google.authorize_redirect(redirect_uri, state='signup')


@app.route('/api/auth/google/callback')
def google_callback():
    """Callback Google OAuth"""
    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo')

        if not user_info:
            return redirect('/?auth=error&message=Impossibile ottenere informazioni utente')

        email = user_info.get('email')
        google_id = user_info.get('sub')
        firstname = user_info.get('given_name', '')
        lastname = user_info.get('family_name', '')

        # Recupera il piano selezionato dalla sessione
        selected_plan = session.pop('selected_plan', 'none')

        # Trova o crea utente
        user = User.query.filter_by(email=email).first()

        if not user:
            # Crea nuovo utente
            # Imposta limiti in base al piano
            plan_limits = {
                'none': 0,
                'monthly': -1,
                'annual': -1
            }
            analyses_limit = plan_limits.get(selected_plan, 0)

            user = User(
                email=email,
                firstname=firstname,
                lastname=lastname,
                google_id=google_id,
                plan=selected_plan,
                analyses_limit=analyses_limit
                # trial_ends_at verrà impostato dopo l'acquisto
            )
            db.session.add(user)
        else:
            # Aggiorna google_id se non presente
            if not user.google_id:
                user.google_id = google_id

        user.last_login = datetime.datetime.utcnow()
        db.session.commit()

        # Genera token
        jwt_token = generate_token(user.id)

        return redirect(f'/?auth=success&token={jwt_token}')

    except Exception as e:
        print(f"Google OAuth error: {e}")
        import traceback
        traceback.print_exc()
        return redirect('/?auth=error&message=Errore durante autenticazione Google')


# ===================================
# APPLE OAUTH ENDPOINTS
# ===================================

@app.route('/api/auth/apple/login')
def apple_login():
    """Inizia Apple Sign In"""
    redirect_uri = url_for('apple_callback', _external=True)
    return apple.authorize_redirect(redirect_uri, state='login')


@app.route('/api/auth/apple/signup')
def apple_signup():
    """Inizia Apple Sign In signup (registrazione)"""
    redirect_uri = url_for('apple_callback', _external=True)
    # Salva il piano selezionato nella sessione
    plan = request.args.get('plan', 'starter')
    session['selected_plan'] = plan
    return apple.authorize_redirect(redirect_uri, state='signup')


@app.route('/api/auth/apple/callback')
def apple_callback():
    """Callback Apple Sign In"""
    try:
        token = apple.authorize_access_token()
        user_info = token.get('userinfo')

        if not user_info:
            return redirect('/?auth=error&message=Impossibile ottenere informazioni utente')

        email = user_info.get('email')
        apple_id = user_info.get('sub')

        # Apple non fornisce sempre nome, usa email come fallback
        firstname = user_info.get('given_name', email.split('@')[0] if email else 'Utente')
        lastname = user_info.get('family_name', '')

        # Recupera il piano selezionato dalla sessione
        selected_plan = session.pop('selected_plan', 'none')

        # Trova o crea utente
        user = User.query.filter_by(email=email).first()

        if not user:
            # Imposta limiti in base al piano
            plan_limits = {
                'none': 0,
                'monthly': -1,
                'annual': -1
            }
            analyses_limit = plan_limits.get(selected_plan, 0)

            user = User(
                email=email,
                firstname=firstname,
                lastname=lastname,
                apple_id=apple_id,
                plan=selected_plan,
                analyses_limit=analyses_limit
                # trial_ends_at verrà impostato dopo l'acquisto
            )
            db.session.add(user)
        else:
            if not user.apple_id:
                user.apple_id = apple_id

        user.last_login = datetime.datetime.utcnow()
        db.session.commit()

        # Genera token
        jwt_token = generate_token(user.id)

        return redirect(f'/?auth=success&token={jwt_token}')

    except Exception as e:
        print(f"Apple OAuth error: {e}")
        import traceback
        traceback.print_exc()
        return redirect('/?auth=error&message=Errore durante autenticazione Apple')


# ===================================
# USER MANAGEMENT ENDPOINTS
# ===================================

@app.route('/api/user/profile', methods=['GET'])
@token_required
def get_profile(user):
    """Ottieni profilo utente"""
    return jsonify({
        'success': True,
        'user': user.to_dict()
    })


@app.route('/api/user/profile', methods=['PUT'])
@token_required
def update_profile(user):
    """Aggiorna profilo utente"""
    try:
        data = request.get_json()

        # Campi aggiornabili
        if 'firstname' in data:
            user.firstname = data['firstname'].strip()
        if 'lastname' in data:
            user.lastname = data['lastname'].strip()
        if 'phone' in data:
            user.phone = data['phone'].strip() if data['phone'] else None
        if 'bio' in data:
            user.bio = data['bio'].strip() if data['bio'] else None
        if 'language' in data:
            user.language = data['language']
        if 'notifications_enabled' in data:
            user.notifications_enabled = data['notifications_enabled']

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Profilo aggiornato',
            'user': user.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        print(f"Update profile error: {e}")
        return jsonify({
            'success': False,
            'message': 'Errore durante aggiornamento'
        }), 500


@app.route('/api/user/change-password', methods=['POST'])
@token_required
def change_password(user):
    """Cambia password utente"""
    try:
        data = request.get_json()
        
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not new_password:
            return jsonify({
                'success': False,
                'message': 'Nuova password richiesta'
            }), 400
        
        # Se l'utente ha una password (non OAuth only), verifica quella corrente
        if user.password_hash:
            if not current_password:
                return jsonify({
                    'success': False,
                    'message': 'Password corrente richiesta'
                }), 400
            
            if not user.check_password(current_password):
                return jsonify({
                    'success': False,
                    'message': 'Password corrente non valida'
                }), 401
        
        # Validazione nuova password
        if len(new_password) < 8:
            return jsonify({
                'success': False,
                'message': 'La password deve essere almeno 8 caratteri'
            }), 400
        
        user.set_password(new_password)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Password aggiornata con successo'
        })
    
    except Exception as e:
        db.session.rollback()
        print(f"Change password error: {e}")
        return jsonify({
            'success': False,
            'message': 'Errore durante aggiornamento password'
        }), 500


@app.route('/api/user/upload-avatar', methods=['POST'])
@token_required
def upload_avatar(user):
    """Upload immagine profilo"""
    try:
        if 'avatar' not in request.files:
            return jsonify({
                'success': False,
                'message': 'Nessun file caricato'
            }), 400
        
        file = request.files['avatar']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'Nessun file selezionato'
            }), 400
        
        # Verifica estensione
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            return jsonify({
                'success': False,
                'message': 'Formato file non supportato. Usa: png, jpg, jpeg, gif, webp'
            }), 400
        
        # Verifica dimensione (max 5MB)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 5 * 1024 * 1024:  # 5MB
            return jsonify({
                'success': False,
                'message': 'File troppo grande. Massimo 5MB'
            }), 400
        
        # Salva file
        upload_folder = os.path.join('webapp', 'static', 'avatars')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Nome file univoco
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"user_{user.id}_{secrets.token_hex(8)}.{ext}"
        filepath = os.path.join(upload_folder, filename)
        
        file.save(filepath)
        
        # Elimina vecchia immagine se esiste
        if user.profile_image:
            old_path = os.path.join('webapp', user.profile_image.lstrip('/'))
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except:
                    pass
        
        # Salva path nel database
        user.profile_image = f"/static/avatars/{filename}"
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Avatar caricato con successo',
            'profile_image': user.profile_image
        })
    
    except Exception as e:
        db.session.rollback()
        print(f"Upload avatar error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'Errore durante upload avatar'
        }), 500


@app.route('/api/user/delete-avatar', methods=['DELETE'])
@token_required
def delete_avatar(user):
    """Elimina immagine profilo"""
    try:
        if user.profile_image:
            # Elimina file
            filepath = os.path.join('webapp', user.profile_image.lstrip('/'))
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
            
            user.profile_image = None
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Avatar eliminato'
        })
    
    except Exception as e:
        db.session.rollback()
        print(f"Delete avatar error: {e}")
        return jsonify({
            'success': False,
            'message': 'Errore durante eliminazione avatar'
        }), 500


@app.route('/api/user/subscription', methods=['GET'])
@token_required
def get_subscription(user):
    """Ottieni dettagli abbonamento"""
    now = datetime.datetime.utcnow()
    
    # Calcola stato trial
    trial_active = user.trial_ends_at and user.trial_ends_at > now
    trial_days_left = (user.trial_ends_at - now).days if trial_active else 0
    
    # Calcola stato subscription
    # Un abbonamento è attivo se:
    # 1. Ha un piano diverso da 'none' E
    # 2. O non ha data di scadenza (illimitato) O ha una data futura
    has_paid_plan = user.plan in ['monthly', 'annual']
    subscription_active = has_paid_plan and (user.subscription_ends_at is None or user.subscription_ends_at > now)
    subscription_days_left = (user.subscription_ends_at - now).days if user.subscription_ends_at and user.subscription_ends_at > now else 0
    
    # Definizione limiti per piano
    plan_limits = {
        'none': {'analyses': 0, 'price': 0, 'name': 'Nessun Piano'},
        'monthly': {'analyses': -1, 'price': 69, 'name': 'Mensile'},
        'annual': {'analyses': -1, 'price': 49, 'name': 'Annuale'}
    }

    current_plan = plan_limits.get(user.plan, plan_limits['none'])
    
    return jsonify({
        'success': True,
        'subscription': {
            'plan': user.plan,
            'plan_name': current_plan['name'],
            'plan_price': current_plan['price'],
            'trial_active': trial_active,
            'trial_ends_at': user.trial_ends_at.isoformat() if user.trial_ends_at else None,
            'trial_days_left': trial_days_left,
            'subscription_active': subscription_active,
            'subscription_ends_at': user.subscription_ends_at.isoformat() if user.subscription_ends_at else None,
            'subscription_days_left': subscription_days_left,
            'analyses_count': user.analyses_count,
            'analyses_limit': user.analyses_limit,
            'analyses_remaining': user.analyses_limit - user.analyses_count if user.analyses_limit > 0 else -1,
            'can_analyze': (trial_active or subscription_active) and (user.analyses_limit == -1 or user.analyses_count < user.analyses_limit)
        }
    })


@app.route('/api/user/delete-account', methods=['DELETE'])
@token_required
def delete_account(user):
    """Elimina account utente"""
    try:
        data = request.get_json()
        password = data.get('password')
        
        # Verifica password se l'utente ne ha una
        if user.password_hash:
            if not password or not user.check_password(password):
                return jsonify({
                    'success': False,
                    'message': 'Password non valida'
                }), 401
        
        # Elimina avatar se esiste
        if user.profile_image:
            filepath = os.path.join('webapp', user.profile_image.lstrip('/'))
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
        
        # Elimina utente
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Account eliminato con successo'
        })
    
    except Exception as e:
        db.session.rollback()
        print(f"Delete account error: {e}")
        return jsonify({
            'success': False,
            'message': 'Errore durante eliminazione account'
        }), 500


@app.route('/api/user/usage', methods=['GET'])
@token_required
def get_usage(user):
    """Ottieni statistiche utilizzo"""
    trial_active = user.trial_ends_at and user.trial_ends_at > datetime.datetime.utcnow()

    return jsonify({
        'success': True,
        'usage': {
            'analyses_count': user.analyses_count,
            'analyses_limit': user.analyses_limit,
            'remaining': user.analyses_limit - user.analyses_count if user.analyses_limit > 0 else -1,
            'plan': user.plan,
            'trial_active': trial_active,
            'trial_ends_at': user.trial_ends_at.isoformat() if user.trial_ends_at else None
        }
    })


# ===================================
# ADMIN DASHBOARD ENDPOINTS
# ===================================

@app.route('/api/admin/dashboard/stats', methods=['GET'])
@admin_required
def get_dashboard_stats(admin):
    """Ottieni statistiche dashboard per admin"""
    try:
        now = datetime.datetime.utcnow()

        # User counts
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        inactive_users = User.query.filter_by(is_active=False).count()

        # New users statistics
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - datetime.timedelta(days=7)
        month_start = today_start - datetime.timedelta(days=30)

        new_users_today = User.query.filter(User.created_at >= today_start).count()
        new_users_week = User.query.filter(User.created_at >= week_start).count()
        new_users_month = User.query.filter(User.created_at >= month_start).count()

        # Subscription breakdown
        plan_stats = db.session.query(
            User.plan, db.func.count(User.id)
        ).group_by(User.plan).all()

        # Usage statistics
        total_analyses = db.session.query(db.func.sum(User.analyses_count)).scalar() or 0

        # Analyses per time period
        analyses_today = db.session.query(
            db.func.sum(User.analyses_count)
        ).join(UserActivity).filter(
            UserActivity.action_type == 'analysis',
            UserActivity.created_at >= today_start
        ).scalar() or 0
        
        analyses_week = db.session.query(
            db.func.sum(User.analyses_count)
        ).join(UserActivity).filter(
            UserActivity.action_type == 'analysis',
            UserActivity.created_at >= week_start
        ).scalar() or 0

        # Active trials
        active_trials = User.query.filter(
            User.trial_ends_at > now,
            User.subscription_ends_at.is_(None)
        ).count()

        # Recent activity (users logged in last 24 hours)
        recent_active = User.query.filter(
            User.last_login >= now - datetime.timedelta(hours=24)
        ).count()

        return jsonify({
            'success': True,
            'stats': {
                'users': {
                    'total': total_users,
                    'active': active_users,
                    'inactive': inactive_users,
                    'new_today': new_users_today,
                    'new_week': new_users_week,
                    'new_month': new_users_month,
                    'recent_active_24h': recent_active
                },
                'subscriptions': {
                    plan: count for plan, count in plan_stats
                },
                'usage': {
                    'total_analyses': total_analyses,
                    'analyses_today': analyses_today,
                    'analyses_week': analyses_week,
                    'active_trials': active_trials
                }
            }
        })
    except Exception as e:
        print(f"Dashboard stats error: {e}")
        return jsonify({'success': False, 'message': 'Errore nel recupero statistiche'}), 500


@app.route('/api/admin/dashboard/registrations', methods=['GET'])
@admin_required
def get_registration_chart(admin):
    """Ottieni dati registrazioni per grafici"""
    try:
        period = request.args.get('period', 'month')  # week, month, year

        now = datetime.datetime.utcnow()

        if period == 'week':
            start_date = now - datetime.timedelta(days=7)
        elif period == 'month':
            start_date = now - datetime.timedelta(days=30)
        else:  # year
            start_date = now - datetime.timedelta(days=365)

        # Query registrations grouped by date
        registrations = db.session.query(
            db.func.date(User.created_at).label('date'),
            db.func.count(User.id).label('count')
        ).filter(
            User.created_at >= start_date
        ).group_by(
            db.func.date(User.created_at)
        ).order_by('date').all()

        return jsonify({
            'success': True,
            'data': [
                {'date': r.date.isoformat() if r.date else None, 'count': r.count}
                for r in registrations
            ]
        })
    except Exception as e:
        print(f"Registration chart error: {e}")
        return jsonify({'success': False, 'message': 'Errore nel recupero dati'}), 500


@app.route('/api/admin/users', methods=['GET'])
@admin_required
def list_users(admin):
    """Lista tutti gli utenti con paginazione e filtri"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '')
        plan_filter = request.args.get('plan', '')
        status_filter = request.args.get('status', '')  # active, inactive
        sort_by = request.args.get('sort', 'created_at')
        sort_order = request.args.get('order', 'desc')

        query = User.query

        # Search filter
        if search:
            search_term = f'%{search}%'
            query = query.filter(
                db.or_(
                    User.email.ilike(search_term),
                    User.firstname.ilike(search_term),
                    User.lastname.ilike(search_term)
                )
            )

        # Plan filter
        if plan_filter:
            query = query.filter(User.plan == plan_filter)

        # Status filter
        if status_filter == 'active':
            query = query.filter(User.is_active == True)
        elif status_filter == 'inactive':
            query = query.filter(User.is_active == False)

        # Sorting
        sort_column = getattr(User, sort_by, User.created_at)
        if sort_order == 'desc':
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Pagination
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            'success': True,
            'users': [u.to_dict() for u in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        })
    except Exception as e:
        print(f"List users error: {e}")
        return jsonify({'success': False, 'message': 'Errore nel recupero utenti'}), 500


@app.route('/api/admin/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user_detail(admin, user_id):
    """Ottieni dettagli utente"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'Utente non trovato'}), 404

        return jsonify({
            'success': True,
            'user': user.to_dict()
        })
    except Exception as e:
        print(f"Get user detail error: {e}")
        return jsonify({'success': False, 'message': 'Errore nel recupero utente'}), 500


@app.route('/api/admin/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_user_status(admin, user_id):
    """Attiva/Disattiva un utente"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'Utente non trovato'}), 404

        # Prevent self-deactivation
        if user.id == admin.id:
            return jsonify({'success': False, 'message': 'Non puoi disattivare il tuo account'}), 400

        user.is_active = not user.is_active

        # Log action
        log = AdminAuditLog(
            admin_id=admin.id,
            action='user_activated' if user.is_active else 'user_deactivated',
            target_user_id=user.id,
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()

        status = 'attivato' if user.is_active else 'disattivato'
        return jsonify({
            'success': True,
            'message': f'Utente {status} con successo',
            'user': user.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        print(f"Toggle user status error: {e}")
        return jsonify({'success': False, 'message': 'Errore durante operazione'}), 500


@app.route('/api/admin/users/<int:user_id>/change-plan', methods=['POST'])
@admin_required
def change_user_plan(admin, user_id):
    """Cambia piano abbonamento utente"""
    try:
        data = request.get_json()
        new_plan = data.get('plan')

        # Piani validi
        valid_plans = ['none', 'monthly', 'annual']
        if new_plan not in valid_plans:
            return jsonify({'success': False, 'message': 'Piano non valido. Piani disponibili: none, monthly, annual'}), 400

        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'Utente non trovato'}), 404

        old_plan = user.plan
        user.plan = new_plan

        # Update analyses limit based on plan
        plan_limits = {
            'none': 0,
            'monthly': -1,  # Illimitato
            'annual': -1    # Illimitato
        }
        user.analyses_limit = plan_limits.get(new_plan, 0)

        # Log action
        log = AdminAuditLog(
            admin_id=admin.id,
            action='plan_changed',
            target_user_id=user.id,
            details={'old_plan': old_plan, 'new_plan': new_plan},
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Piano aggiornato a {new_plan}',
            'user': user.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        print(f"Change plan error: {e}")
        return jsonify({'success': False, 'message': 'Errore durante operazione'}), 500


@app.route('/api/admin/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def admin_reset_password(admin, user_id):
    """Admin reset password utente"""
    try:
        data = request.get_json()
        new_password = data.get('new_password')

        if not new_password or len(new_password) < 8:
            return jsonify({'success': False, 'message': 'Password deve essere almeno 8 caratteri'}), 400

        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'Utente non trovato'}), 404

        user.set_password(new_password)

        # Log action
        log = AdminAuditLog(
            admin_id=admin.id,
            action='password_reset',
            target_user_id=user.id,
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Password reimpostata con successo'
        })
    except Exception as e:
        db.session.rollback()
        print(f"Reset password error: {e}")
        return jsonify({'success': False, 'message': 'Errore durante operazione'}), 500


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(admin, user_id):
    """Elimina account utente"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'Utente non trovato'}), 404

        # Prevent self-deletion
        if user.id == admin.id:
            return jsonify({'success': False, 'message': 'Non puoi eliminare il tuo account'}), 400

        # Prevent deleting other admins
        if user.role == 'admin':
            return jsonify({'success': False, 'message': 'Non puoi eliminare altri amministratori'}), 400

        # Delete avatar if exists
        if user.profile_image:
            filepath = os.path.join('webapp', user.profile_image.lstrip('/'))
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass

        # Log action before deletion
        log = AdminAuditLog(
            admin_id=admin.id,
            action='user_deleted',
            target_user_id=None,  # User will be deleted
            details={'deleted_email': user.email, 'deleted_name': f'{user.firstname} {user.lastname}'},
            ip_address=request.remote_addr
        )
        db.session.add(log)

        db.session.delete(user)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Utente eliminato con successo'
        })
    except Exception as e:
        db.session.rollback()
        print(f"Delete user error: {e}")
        return jsonify({'success': False, 'message': 'Errore durante eliminazione'}), 500


@app.route('/api/admin/audit-log', methods=['GET'])
@admin_required
def get_audit_log(admin):
    """Ottieni log audit admin"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        pagination = AdminAuditLog.query.order_by(
            AdminAuditLog.created_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)

        logs = []
        for log in pagination.items:
            logs.append({
                'id': log.id,
                'admin_email': log.admin.email if log.admin else 'Unknown',
                'action': log.action,
                'target_user_email': log.target_user.email if log.target_user else None,
                'details': log.details,
                'ip_address': log.ip_address,
                'created_at': log.created_at.isoformat() if log.created_at else None
            })

        return jsonify({
            'success': True,
            'logs': logs,
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        })
    except Exception as e:
        print(f"Audit log error: {e}")
        return jsonify({'success': False, 'message': 'Errore nel recupero log'}), 500


@app.route('/api/admin/analytics/usage', methods=['GET'])
@admin_required
def get_usage_analytics(admin):
    """Ottieni analytics dettagliate sull'utilizzo della webapp"""
    try:
        period = request.args.get('period', 'week')  # week, month, year
        
        now = datetime.datetime.utcnow()
        if period == 'week':
            start_date = now - datetime.timedelta(days=7)
        elif period == 'month':
            start_date = now - datetime.timedelta(days=30)
        else:  # year
            start_date = now - datetime.timedelta(days=365)
        
        # Activity breakdown by type
        activity_counts = db.session.query(
            UserActivity.action_type,
            db.func.count(UserActivity.id).label('count')
        ).filter(
            UserActivity.created_at >= start_date
        ).group_by(UserActivity.action_type).all()
        
        # Daily activity trend
        daily_activity = db.session.query(
            db.func.date(UserActivity.created_at).label('date'),
            db.func.count(UserActivity.id).label('count')
        ).filter(
            UserActivity.created_at >= start_date
        ).group_by(db.func.date(UserActivity.created_at)).order_by('date').all()
        
        # Most active users
        most_active = db.session.query(
            User.id,
            User.firstname,
            User.lastname,
            User.email,
            db.func.count(UserActivity.id).label('activity_count')
        ).join(UserActivity).filter(
            UserActivity.created_at >= start_date
        ).group_by(User.id).order_by(db.desc('activity_count')).limit(10).all()
        
        # Peak usage hours
        hourly_usage = db.session.query(
            db.func.extract('hour', UserActivity.created_at).label('hour'),
            db.func.count(UserActivity.id).label('count')
        ).filter(
            UserActivity.created_at >= start_date
        ).group_by('hour').order_by('hour').all()
        
        return jsonify({
            'success': True,
            'analytics': {
                'activity_breakdown': {act: count for act, count in activity_counts},
                'daily_trend': [
                    {'date': d.date.isoformat() if d.date else None, 'count': d.count}
                    for d in daily_activity
                ],
                'most_active_users': [
                    {
                        'id': u.id,
                        'name': f'{u.firstname} {u.lastname}',
                        'email': u.email,
                        'activity_count': u.activity_count
                    }
                    for u in most_active
                ],
                'hourly_usage': [
                    {'hour': int(h.hour) if h.hour else 0, 'count': h.count}
                    for h in hourly_usage
                ]
            }
        })
    except Exception as e:
        print(f"Usage analytics error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Errore nel recupero analytics'}), 500


@app.route('/api/user/track-activity', methods=['POST'])
@token_required
def track_user_activity(user):
    """Traccia attività utente nella webapp"""
    try:
        data = request.get_json()
        action_type = data.get('action_type')  # 'login', 'analysis', 'image_upload', etc.
        action_details = data.get('details', {})
        
        if not action_type:
            return jsonify({'success': False, 'message': 'Tipo azione richiesto'}), 400
        
        activity = UserActivity(
            user_id=user.id,
            action_type=action_type,
            action_details=action_details,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        db.session.add(activity)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Attività tracciata'})
    except Exception as e:
        db.session.rollback()
        print(f"Track activity error: {e}")
        return jsonify({'success': False, 'message': 'Errore nel tracciamento'}), 500


# ===================================
# EMAIL UTILITIES
# ===================================

def send_password_reset_email(user, token):
    """Invia email di reset password"""
    try:
        if not app.config['SMTP_USERNAME']:
            print("SMTP non configurato, skip email")
            return

        reset_url = f"https://yourdomain.com/reset-password?token={token}"

        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Reset Password - Kimerika Evolution'
        msg['From'] = app.config['FROM_EMAIL']
        msg['To'] = user.email

        text = f"""
        Ciao {user.firstname},

        Hai richiesto il reset della password per il tuo account Kimerika Evolution.

        Clicca sul link seguente per reimpostare la password:
        {reset_url}

        Il link è valido per 1 ora.

        Se non hai richiesto il reset, ignora questa email.

        Grazie,
        Team Kimerika Evolution
        """

        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2>Reset Password</h2>
                <p>Ciao {user.firstname},</p>
                <p>Hai richiesto il reset della password per il tuo account Kimerika Evolution.</p>
                <p>
                    <a href="{reset_url}" style="background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; display: inline-block;">
                        Reimposta Password
                    </a>
                </p>
                <p>Il link è valido per 1 ora.</p>
                <p>Se non hai richiesto il reset, ignora questa email.</p>
                <p>Grazie,<br>Team Kimerika Evolution</p>
            </body>
        </html>
        """

        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)

        with smtplib.SMTP(app.config['SMTP_SERVER'], app.config['SMTP_PORT']) as server:
            server.starttls()
            server.login(app.config['SMTP_USERNAME'], app.config['SMTP_PASSWORD'])
            server.send_message(msg)

        print(f"Reset email inviata a {user.email}")

    except Exception as e:
        print(f"Errore invio email: {e}")


# ===================================
# INITIALIZATION
# ===================================

def init_db():
    """Inizializza database"""
    with app.app_context():
        db.create_all()
        print("✅ Database inizializzato")


if __name__ == '__main__':
    init_db()

    print("🚀 Kimerika Evolution Auth Server")
    print("=" * 50)
    print("📡 Server running on http://0.0.0.0:5000 (tutte le interfacce)")
    print("🔐 API Base URL: http://localhost:5000/api")
    print("")
    print("Endpoints disponibili:")
    print("  POST /api/auth/signup - Registrazione")
    print("  POST /api/auth/login - Login")
    print("  GET  /api/auth/verify - Verifica token")
    print("  POST /api/auth/forgot-password - Recupero password")
    print("  GET  /api/auth/google/login - Google OAuth")
    print("  GET  /api/auth/apple/login - Apple Sign In")
    print("  GET  /api/user/profile - Profilo utente")
    print("  PUT  /api/user/profile - Aggiorna profilo")
    print("  GET  /api/user/usage - Statistiche utilizzo")
    print("")
    print("Admin Endpoints:")
    print("  GET  /api/admin/dashboard/stats - Statistiche dashboard")
    print("  GET  /api/admin/dashboard/registrations - Dati registrazioni")
    print("  GET  /api/admin/users - Lista utenti")
    print("  GET  /api/admin/users/<id> - Dettagli utente")
    print("  POST /api/admin/users/<id>/toggle-status - Attiva/Disattiva")
    print("  POST /api/admin/users/<id>/change-plan - Cambia piano")
    print("  POST /api/admin/users/<id>/reset-password - Reset password")
    print("  DELETE /api/admin/users/<id> - Elimina utente")
    print("  GET  /api/admin/audit-log - Log attivita admin")
    print("")

    app.run(debug=True, host="0.0.0.0", port=5000)
