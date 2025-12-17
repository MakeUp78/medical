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
    plan = db.Column(db.String(20), default='starter')  # starter, professional, enterprise
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
    analyses_limit = db.Column(db.Integer, default=50)  # Default starter limit

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
            'plan': self.plan,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'trial_ends_at': self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            'analyses_count': self.analyses_count,
            'analyses_limit': self.analyses_limit
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
        plan = data.get('plan', 'starter')

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

        # Crea utente
        user = User(
            email=email,
            firstname=firstname,
            lastname=lastname,
            plan=plan,
            trial_ends_at=datetime.datetime.utcnow() + datetime.timedelta(days=14)
        )
        user.set_password(password)

        # Imposta limiti in base al piano
        if plan == 'starter':
            user.analyses_limit = 50
        elif plan == 'professional':
            user.analyses_limit = 200
        else:  # enterprise
            user.analyses_limit = -1  # Unlimited

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
    return google.authorize_redirect(redirect_uri)


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

        # Trova o crea utente
        user = User.query.filter_by(email=email).first()

        if not user:
            # Crea nuovo utente
            user = User(
                email=email,
                firstname=firstname,
                lastname=lastname,
                google_id=google_id,
                plan='starter',
                trial_ends_at=datetime.datetime.utcnow() + datetime.timedelta(days=14),
                analyses_limit=50
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
        return redirect('/?auth=error&message=Errore durante autenticazione Google')


# ===================================
# APPLE OAUTH ENDPOINTS
# ===================================

@app.route('/api/auth/apple/login')
def apple_login():
    """Inizia Apple Sign In"""
    redirect_uri = url_for('apple_callback', _external=True)
    return apple.authorize_redirect(redirect_uri)


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
        firstname = user_info.get('given_name', email.split('@')[0])
        lastname = user_info.get('family_name', '')

        # Trova o crea utente
        user = User.query.filter_by(email=email).first()

        if not user:
            user = User(
                email=email,
                firstname=firstname,
                lastname=lastname,
                apple_id=apple_id,
                plan='starter',
                trial_ends_at=datetime.datetime.utcnow() + datetime.timedelta(days=14),
                analyses_limit=50
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
    print("📡 Server running on http://localhost:5000")
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

    app.run(debug=True, port=5000)
