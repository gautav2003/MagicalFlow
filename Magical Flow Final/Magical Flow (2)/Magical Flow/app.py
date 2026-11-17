from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, session
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from functools import wraps
import os
import sqlite3
import random
import smtplib
import ssl
import json
import urllib.error
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from io import BytesIO

# Load environment variables from the hidden .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'magical_flow_super_secret_production_key')
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024
DB_NAME = 'MagicalFlow.db'
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5000/google/callback')

# ==================== OFFICIAL GMAIL SMTP CONFIGURATION (SSL PORT 465) ====================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

def send_official_email(recipient_email, subject_text, html_body):
    """Sends a professional HTML email via Gmail SMTP using SSL with a terminal backup log."""
    print(f"\n========================================")
    print(f"[*] EMAIL DISPATCH & CODE BACKUP")
    print(f"To: {recipient_email}")
    print(f"Subject: {subject_text}")
    print(f"========================================\n")
    
    try:
        if not SENDER_EMAIL or not SENDER_PASSWORD or "your_actual_email" in SENDER_EMAIL:
            print("[!] SMTP credentials not configured properly in .env.")
            return

        msg = MIMEMultipart('alternative')
        msg['From'] = f"Magical Flow <{SENDER_EMAIL}>"
        msg['To'] = recipient_email
        msg['Subject'] = subject_text
        
        msg.attach(MIMEText(html_body, 'html'))
        
        # Secure SSL connection on port 465 to prevent drop errors
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
            
        print(f"[*] Official email successfully dispatched via Gmail SMTP to {recipient_email}")
    except Exception as e:
        print(f"[!] SMTP Dispatch Error: {e}")
        print(f"[!] Note: Check your terminal backup above to grab your verification/recovery code for testing!")

# ==================== OFFICIAL GOOGLE OAUTH CONFIGURATION ====================
oauth = OAuth(app)

def google_oauth_configured():
    return bool(os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET'))

google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
    redirect_uri=GOOGLE_REDIRECT_URI,
)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS studio_recordings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            bpm INTEGER NOT NULL,
            duration INTEGER NOT NULL,
            mime_type TEXT NOT NULL,
            audio BLOB NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==================== AUTHENTICATION GUARD DECORATOR ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('signin'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_ai_configuration():
    return {'gemini_configured': bool(os.getenv('GEMINI_API_KEY'))}

# ==================== ROOT & HOME ROUTES (STRICTLY LOCKED) ====================
@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('signin'))
    return redirect(url_for('home'))

@app.route('/home')
def home():
    if 'user' not in session:
        return redirect(url_for('signin'))
    return render_template('Home.html')

# ==================== REGISTRATION & REAL EMAIL VERIFICATION ====================
@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            error = "Passwords do not match."
        else:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, email))
            existing_user = cursor.fetchone()
            conn.close()
            
            if existing_user:
                error = "Username or Email already exists."
            else:
                # Store pending registration details in session securely
                session['reg_username'] = username
                session['reg_email'] = email
                session['reg_password'] = password
                
                # Generate real 6-digit email verification code
                code = str(random.randint(100000, 999999))
                session['reg_auth_code'] = code
                
                verify_html = f"""
                <div style="background-color: #070311; color: #ffffff; padding: 30px; font-family: 'Inter', Arial, sans-serif; border-radius: 12px; border: 1px solid rgba(147, 51, 234, 0.4);">
                    <div style="text-align: center; margin-bottom: 20px;">
                        <h2 style="background: linear-gradient(135deg, #ffffff, #e879f9); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0;">Magical Flow</h2>
                        <p style="color: #c084fc; font-size: 11px; text-transform: uppercase; letter-spacing: 2px; margin-top: 5px;">Your Music . Your Way .</p>
                    </div>
                    <h3 style="color: #ffffff;">Welcome to the flow, {username}!</h3>
                    <p style="color: #a1a1aa; font-size: 13px; line-height: 1.6;">
                        Please use the secure real verification code below to activate your studio account:
                    </p>
                    <div style="background: #120822; padding: 15px; text-align: center; border-radius: 8px; border: 1px solid rgba(147, 51, 234, 0.3); margin: 20px 0;">
                        <h1 style="color: #38bdf8; letter-spacing: 8px; margin: 0;">{code}</h1>
                    </div>
                </div>
                """
                send_official_email(email, "Magical Flow - Account Email Verification Code", verify_html)
                
                return redirect(url_for('verify_register'))
                
    return render_template('Register.html', error=error)

@app.route('/verify-register', methods=['GET', 'POST'])
def verify_register():
    error = None
    email = session.get('reg_email', 'your email')
    
    if request.method == 'POST':
        user_code = request.form.get('code')
        if user_code == session.get('reg_auth_code'):
            username = session.get('reg_username')
            email = session.get('reg_email')
            password = session.get('reg_password')
            
            try:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (username, email, password))
                conn.commit()
                conn.close()
                
                # Send official welcome email after successful verification
                welcome_html = f"""
                <div style="background-color: #070311; color: #ffffff; padding: 30px; font-family: 'Inter', Arial, sans-serif; border-radius: 12px; border: 1px solid rgba(147, 51, 234, 0.4);">
                    <div style="text-align: center; margin-bottom: 20px;">
                        <h2 style="background: linear-gradient(135deg, #ffffff, #e879f9); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0;">Magical Flow</h2>
                        <p style="color: #c084fc; font-size: 11px; text-transform: uppercase; letter-spacing: 2px; margin-top: 5px;">Your Music . Your Way .</p>
                    </div>
                    <h3 style="color: #ffffff;">Welcome to the flow, {username}!</h3>
                    <p style="color: #a1a1aa; font-size: 13px; line-height: 1.6;">
                        Your Magical Flow account has been officially created and verified.
                    </p>
                </div>
                """
                send_official_email(email, "Welcome to Magical Flow - Your Studio Access is Ready", welcome_html)
                
                # Clear temporary session storage
                session.pop('reg_username', None)
                session.pop('reg_email', None)
                session.pop('reg_password', None)
                session.pop('reg_auth_code', None)
                
                session['new_user_name'] = username
                return redirect(url_for('account_created'))
            except Exception as e:
                error = f"Database Error: {e}"
        else:
            error = "Invalid verification code. Please check your inbox."
            
    return render_template('VerifyRegister.html', email=email, prototype_code=session.get('reg_auth_code', '------'), error=error)

@app.route('/account-created')
def account_created():
    username = session.get('new_user_name', 'Artist')
    return render_template('AccountCreated.html', username=username)

# ==================== SIGN IN & 2FA AUTHENTICATION ====================
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    error = None
    message = request.args.get('msg')
    if request.method == 'POST':
        identifier = request.form.get('username')
        password = request.form.get('password')
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE (username = ? OR email = ?) AND password = ?", (identifier, identifier, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            session['pending_email'] = user[2]
            session['pending_username'] = user[1]
            code = str(random.randint(100000, 999999))
            session['auth_code'] = code
            
            code_html = f"""
            <div style="background-color: #070311; color: #ffffff; padding: 25px; font-family: sans-serif; border-radius: 10px;">
                <h3 style="color: #e879f9;">Magical Flow Security Verification</h3>
                <p style="color: #a1a1aa; font-size: 13px;">Your official 2FA sign-in verification code is:</p>
                <h1 style="color: #38bdf8; letter-spacing: 5px;">{code}</h1>
            </div>
            """
            send_official_email(user[2], "Magical Flow - Secure 2FA Login Code", code_html)
            
            return redirect(url_for('identity_check'))
        else:
            error = "Invalid username/email or password."
    return render_template('Signin.html', error=error, message=message)

@app.route('/identity-check', methods=['GET', 'POST'])
def identity_check():
    error = None
    email = session.get('pending_email', 'user@gmail.com')
    
    if request.method == 'POST':
        user_code = request.form.get('code')
        if user_code == session.get('auth_code'):
            session['user'] = session.get('pending_username')
            return redirect(url_for('home'))
        else:
            error = "Invalid verification code."
            
    return render_template('IdentityCheck.html', email=email, prototype_code=session.get('auth_code', '------'), error=error)

# ==================== FORGOT & RESET PASSWORD WORKFLOW ====================
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    error = None
    message = None
    if request.method == 'POST':
        email = request.form.get('email')
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            reset_code = str(random.randint(100000, 999999))
            session['reset_email'] = email
            session['reset_code'] = reset_code
            
            reset_html = f"""
            <div style="background-color: #070311; color: #ffffff; padding: 25px; font-family: sans-serif; border-radius: 10px;">
                <h3 style="color: #e879f9;">Magical Flow Password Recovery</h3>
                <p style="color: #a1a1aa; font-size: 13px;">Your official password reset code is:</p>
                <h1 style="color: #38bdf8; letter-spacing: 5px;">{reset_code}</h1>
            </div>
            """
            send_official_email(email, "Magical Flow - Password Reset Request", reset_html)
            return redirect(url_for('reset_password'))
        else:
            error = "Email address not found in our studio records."
            
    return render_template('ForgotPassword.html', error=error, message=message)

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    error = None
    email = session.get('reset_email', '')
    if request.method == 'POST':
        entered_code = request.form.get('code')
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if entered_code != session.get('reset_code'):
            error = "Invalid recovery code."
        elif new_password != confirm_password:
            error = "Passwords do not match."
        else:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password = ? WHERE email = ?", (new_password, email))
            conn.commit()
            conn.close()
            
            session.pop('reset_code', None)
            session.pop('reset_email', None)
            session['user'] = email.split('@')[0]
            return redirect(url_for('home'))
            
    return render_template('ResetPassword.html', email=email, error=error)

# ==================== OFFICIAL GOOGLE OAUTH ROUTES ====================
@app.route('/google-login', endpoint='google_login')
def google_login():
    if not google_oauth_configured():
        return redirect(url_for('signin', msg='Google sign-in is not configured.'))

    redirect_uri = GOOGLE_REDIRECT_URI
    return google.authorize_redirect(redirect_uri)

app.add_url_rule('/google-login', endpoint='google_auth', view_func=google_login)

@app.route('/google/callback')
def google_callback():
    try:
        if not google_oauth_configured():
            return redirect(url_for('signin', msg='Google sign-in is not configured.'))

        token = google.authorize_access_token()
        user_info = token.get('userinfo')

        if user_info:
            email = user_info['email']
            username = user_info.get('name', email.split('@')[0])

            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()

            if not user:
                cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                               (username, email, 'GOOGLE_OAUTH_AUTHENTICATED'))
                conn.commit()

                welcome_html = f"""
                <div style="background-color: #070311; color: #ffffff; padding: 30px; font-family: 'Inter', Arial, sans-serif; border-radius: 12px; border: 1px solid rgba(147, 51, 234, 0.4);">
                    <h2 style="color: #e879f9;">Welcome to Magical Flow, {username}!</h2>
                    <p style="color: #a1a1aa; font-size: 13px;">Your Google account has been successfully linked to Magical Flow.</p>
                </div>
                """
                send_official_email(email, "Welcome to Magical Flow via Google Sign-In", welcome_html)

            conn.close()

            session['user'] = username
            session['new_user_name'] = username
            return redirect(url_for('home'))

    except Exception as e:
        print(f"[!] Google OAuth Callback Error: {e}")
        return redirect(url_for('signin', msg='Google authentication failed. Check the Google OAuth client and redirect URI configuration.'))

    return redirect(url_for('signin'))

# ==================== ARTIST SUPPORT & MAYA CHAT API ====================
@app.route('/artist-support')
@login_required
def artist_support():
    return render_template('ArtistSupport.html')

def local_artist_support_reply(query):
    query_lower = query.lower()

    if any(word in query_lower for word in ('generate music', 'make music', 'create a song', 'compose', 'instrumental')):
        return (
            "Use Beginner mode to create a playable instrumental arrangement: describe the sound, then choose a "
            "genre, mood, tempo, and instruments. The browser-based generator is included and needs no API key; "
            "it arranges instruments rather than generating a finished audio recording with a cloud AI model. "
            "For external AI-produced audio, a separate provider and its terms/pricing apply."
        )
    if any(word in query_lower for word in ('lyric', 'write a song', 'songwriting', 'chorus', 'verse')):
        return (
            "For a strong song draft, tell Maya the theme, point of view, genre, mood, and structure "
            "(for example: verse, chorus, verse, chorus, bridge, final chorus). In Beginner mode, use a "
            "specific prompt describing tempo, instruments, energy changes, and whether you want vocals or "
            "an instrumental. Add your own details and revise the result to make it yours."
        )
    if any(word in query_lower for word in ('mix', 'master', 'eq', 'frequency', 'volume', 'compression', 'balance')):
        return (
            "Start with a clean balance: lower track levels to leave headroom, high-pass only parts that do not "
            "need deep bass, and make small EQ moves while listening in context. Use gentle compression to "
            "control peaks, check the kick and bass together, and compare the master at a quieter volume. "
            "Avoid clipping and export a WAV for a lossless master."
        )
    if any(word in query_lower for word in ('export', 'download', 'wav', 'save', 'my music')):
        return (
            "In Pro Studio, use Save to keep the current project in this browser, or Export Project to download "
            "the project data. The Beginner and Pro Studio output screens provide their own playback and export "
            "controls. Browser-saved projects stay on this device unless you export them."
        )
    if any(word in query_lower for word in ('account', '2fa', 'verification', 'email', 'login', 'sign in', 'password', 'reset')):
        return (
            "For sign-in trouble, check that you are using the registered email or username. Use Forgot Password "
            "on the sign-in page to start a password reset. Never share your password, verification code, or API key in chat."
        )
    return (
        "I can help with songwriting, Beginner mode prompts, arranging, mixing, mastering, exports, and account "
        "navigation. Add a Gemini API key to the local .env file to enable Maya's AI chat; the built-in music "
        "arrangement tools continue to work without an external key."
    )

def generate_gemini_reply(query, history):
    api_key = os.getenv('GEMINI_API_KEY')
    model = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY is not configured.')

    contents = []
    for item in history:
        role = 'model' if item['role'] == 'assistant' else 'user'
        contents.append({'role': role, 'parts': [{'text': item['content']}]})
    contents.append({'role': 'user', 'parts': [{'text': query}]})

    payload = {
        'systemInstruction': {
            'parts': [{
                'text': (
                    "You are Maya, the practical artist-support assistant inside Magical Flow, a browser-based "
                    "music studio. Help beginners and experienced artists with songwriting, original music "
                    "prompts, arrangement, mixing, mastering, studio navigation, and exports. Give clear "
                    "step-by-step answers, ask a focused follow-up when useful, and distinguish the app's "
                    "browser-based instrumental arranger from external AI audio-generation services. Never "
                    "claim to have generated or saved audio. Do not request or reveal passwords, verification "
                    "codes, or API keys. Keep answers concise and do not provide legal, medical, or financial advice."
                )
            }]
        },
        'contents': contents,
        'generationConfig': {'temperature': 0.7, 'maxOutputTokens': 700},
    }
    url = 'https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent'.format(
        urllib.parse.quote(model, safe='-._')
    )
    request_data = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'x-goog-api-key': api_key},
        method='POST',
    )

    try:
        with urllib.request.urlopen(request_data, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        try:
            provider_error = json.loads(error.read().decode('utf-8')).get('error', {}).get('message')
        except (ValueError, AttributeError):
            provider_error = None
        raise RuntimeError(provider_error or 'Gemini returned HTTP {}.'.format(error.code)) from error
    except urllib.error.URLError as error:
        raise RuntimeError('Could not connect to Gemini: {}'.format(error.reason)) from error
    except (TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError('Gemini did not return a valid response.') from error

    try:
        parts = result['candidates'][0]['content']['parts']
        reply = '\n'.join(
            part['text'] for part in parts
            if isinstance(part, dict) and isinstance(part.get('text'), str)
        ).strip()
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError('Gemini returned an empty or unsupported response.') from error
    if not reply:
        raise RuntimeError('Gemini returned an empty response.')
    return reply

@app.route('/api/support-chat', methods=['POST'])
def support_chat():
    if 'user' not in session:
        return jsonify({'error': 'Please sign in to use Maya.'}), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Send a JSON object with a query.'}), 400
    query = data.get('query')
    if not isinstance(query, str) or not query.strip():
        return jsonify({'error': 'Enter a question for Maya.'}), 400
    query = query.strip()
    if len(query) > 2000:
        return jsonify({'error': 'Please keep each message under 2,000 characters.'}), 400

    history = data.get('history', [])
    if not isinstance(history, list):
        return jsonify({'error': 'Chat history must be a list.'}), 400
    clean_history = []
    for item in history[-8:]:
        if (
            isinstance(item, dict)
            and item.get('role') in ('user', 'assistant')
            and isinstance(item.get('content'), str)
        ):
            content = item['content'].strip()
            if content:
                clean_history.append({'role': item['role'], 'content': content[:2000]})

    if not os.getenv('GEMINI_API_KEY'):
        return jsonify({'reply': local_artist_support_reply(query), 'mode': 'local'})

    try:
        reply = generate_gemini_reply(query, clean_history)
    except RuntimeError as error:
        app.logger.warning('Maya AI request failed: %s', error)
        return jsonify({'error': 'Maya could not reach Gemini. {}'.format(error)}), 502
    return jsonify({'reply': reply, 'mode': 'gemini'})

# ==================== NAVIGATION ====================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('signin'))

@app.route('/account')
@login_required
def account():
    return render_template('account.html')

# ==================== STUDIO MODE ROUTES ====================
@app.route('/select-mode')
@login_required
def select_mode():
    return render_template('Selectmode.html')

@app.route('/beginner-mode', methods=['GET', 'POST'])
@login_required
def beginner_mode():
    if request.method == 'POST':
        return render_template(
            'Beginneroutput.html',
            prompt=request.form.get('prompt', '').strip(),
            bpm=request.form.get('bpm', ''),
            key=request.form.get('genre', ''),
            duration='',
        )
    return render_template('Beginnermode.html')

@app.route('/beginner-output')
@login_required
def beginner_output():
    return render_template(
        'Beginneroutput.html',
        prompt=request.args.get('prompt', '').strip(),
    )

@app.route('/pro-studio-mode')
@login_required
def pro_studio_mode():
    return render_template('Prostudiomode.html')

@app.route('/pro-studio-output', methods=['GET', 'POST'])
@login_required
def studio_output():
    recording_id = request.form.get('recording_id') if request.method == 'POST' else request.args.get('recording_id')
    recording = None
    if recording_id:
        try:
            recording_id = int(recording_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid recording ID.'}), 400
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        recording = conn.execute(
            'SELECT id, title, bpm, duration, mime_type FROM studio_recordings WHERE id = ? AND username = ?',
            (recording_id, session['user']),
        ).fetchone()
        conn.close()
        if recording is None:
            return jsonify({'error': 'Recording not found.'}), 404
        recording = dict(recording)
        recording['audio_url'] = url_for('studio_recording_audio', recording_id=recording_id)

    if request.method == 'POST':
        return render_template(
            'Prostudiooutput.html',
            prompt=request.form.get('prompt', ''),
            bpm=request.form.get('bpm', ''),
            key=request.form.get('key_scale', ''),
            duration='',
            recording=recording,
        )
    return render_template('Prostudiooutput.html', recording=recording)

@app.route('/api/studio-recordings', methods=['POST'])
@login_required
def save_studio_recording():
    recording_file = request.files.get('audio')
    if recording_file is None:
        return jsonify({'error': 'No audio recording was uploaded.'}), 400
    if not recording_file.mimetype.startswith('audio/'):
        return jsonify({'error': 'The uploaded file must be audio.'}), 400

    audio = recording_file.stream.read(app.config['MAX_CONTENT_LENGTH'] + 1)
    if not audio:
        return jsonify({'error': 'The uploaded recording is empty.'}), 400
    if len(audio) > app.config['MAX_CONTENT_LENGTH']:
        return jsonify({'error': 'The recording exceeds the 32 MB upload limit.'}), 413

    try:
        bpm = int(request.form.get('bpm', '96'))
        duration = int(request.form.get('duration', '0'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Tempo and duration must be valid numbers.'}), 400
    if not 40 <= bpm <= 240 or duration < 1:
        return jsonify({'error': 'Tempo must be 40–240 BPM and duration must be positive.'}), 400

    title = request.form.get('title', '').strip()[:100] or 'Pro Studio Recording'
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.execute(
        '''INSERT INTO studio_recordings (username, title, bpm, duration, mime_type, audio)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (session['user'], title, bpm, duration, recording_file.mimetype, sqlite3.Binary(audio)),
    )
    recording_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return jsonify({
        'recording_id': recording_id,
        'output_url': url_for('studio_output', recording_id=recording_id),
    }), 201

@app.route('/studio-recordings/<int:recording_id>/audio')
@login_required
def studio_recording_audio(recording_id):
    conn = sqlite3.connect(DB_NAME)
    recording = conn.execute(
        'SELECT audio, mime_type FROM studio_recordings WHERE id = ? AND username = ?',
        (recording_id, session['user']),
    ).fetchone()
    conn.close()
    if recording is None:
        return jsonify({'error': 'Recording not found.'}), 404
    return send_file(
        BytesIO(recording[0]),
        mimetype=recording[1],
        as_attachment=False,
        conditional=True,
        download_name='studio-recording',
    )

@app.route('/my-music')
@login_required
def my_music():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    recordings = conn.execute(
        '''SELECT id, title, bpm, duration, created_at
           FROM studio_recordings WHERE username = ? ORDER BY id DESC''',
        (session['user'],),
    ).fetchall()
    conn.close()
    music_recordings = [
        {
            'title': item['title'],
            'genre': 'Pro Studio',
            'bpm': item['bpm'],
            'key': 'Studio',
            'duration': '{}:{:02d}'.format(item['duration'] // 60, item['duration'] % 60),
            'description': 'Recorded microphone and live beat mix',
            'type': 'Recordings',
            'date': item['created_at'][:10],
            'fav': False,
            'color': 'from-orange-400 to-red-600',
            'audio_url': url_for('studio_recording_audio', recording_id=item['id']),
        }
        for item in recordings
    ]
    return render_template('MyMusic.html', recordings=music_recordings)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
    