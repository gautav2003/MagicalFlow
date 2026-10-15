from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
import os
import sqlite3
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables from the hidden .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = 'magical_flow_super_secret_production_key'
DB_NAME = 'MagicalFlow.db'

# ==================== OFFICIAL GMAIL SMTP CONFIGURATION ====================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

def send_official_email(recipient_email, subject_text, html_body):
    """Sends a professional, officially styled HTML email via Gmail SMTP."""
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = f"Magical Flow <{SENDER_EMAIL}>"
        msg['To'] = recipient_email
        msg['Subject'] = subject_text
        
        msg.attach(MIMEText(html_body, 'html'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
        server.quit()
        print(f"[*] Official email successfully dispatched to {recipient_email}")
    except Exception as e:
        print(f"[!] SMTP Dispatch Error: {e}")

# ==================== OFFICIAL GOOGLE OAUTH CONFIGURATION ====================
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
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
    conn.commit()
    conn.close()

init_db()

# ==================== MAIN HOME ROUTE ====================
@app.route('/')
def home():
    return render_template('Home.html')

# ==================== REGISTRATION ROUTE WITH WELCOME EMAIL ====================
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
            try:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (username, email, password))
                conn.commit()
                conn.close()
                
                # Dispatch Official Welcome Email to User's Gmail Inbox
                welcome_html = f"""
                <div style="background-color: #070311; color: #ffffff; padding: 30px; font-family: 'Inter', Arial, sans-serif; border-radius: 12px; border: 1px solid rgba(147, 51, 234, 0.4);">
                    <div style="text-align: center; margin-bottom: 20px;">
                        <h2 style="background: linear-gradient(135deg, #ffffff, #e879f9); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0;">Magical Flow</h2>
                        <p style="color: #c084fc; font-size: 11px; text-transform: uppercase; letter-spacing: 2px; margin-top: 5px;">Your Music . Your Way .</p>
                    </div>
                    <h3 style="color: #ffffff;">Welcome to the flow, {username}!</h3>
                    <p style="color: #a1a1aa; font-size: 13px; line-height: 1.6;">
                        Your Magical Flow account has been officially created and verified. You are now ready to compose, mix, and collaborate using our next-generation AI studio tools.
                    </p>
                    <div style="margin-top: 25px; padding-top: 15px; border-top: 1px solid rgba(147, 51, 234, 0.3); text-align: center;">
                        <p style="color: #71717a; font-size: 10px;">© 2026 Magical Flow Studio. All rights reserved.</p>
                    </div>
                </div>
                """
                send_official_email(email, "Welcome to Magical Flow - Your Studio Access is Ready", welcome_html)
                
                session['new_user_name'] = username
                return redirect(url_for('account_created'))
            except sqlite3.IntegrityError:
                error = "Username or Email already exists."
    return render_template('Register.html', error=error)

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
            
            # Send 2FA Code to Gmail Inbox
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
            
    return render_template('IdentityCheck.html', email=email, prototype_code="[Check your Gmail Inbox]", error=error)

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
                <p style="color: #a1a1aa; font-size: 11px;">If you didn't request this, you can safely ignore this email.</p>
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
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

app.add_url_rule('/google-login', endpoint='google_auth', view_func=google_login)

@app.route('/google/callback')
def google_callback():
    try:
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
        return redirect(url_for('signin', msg="Google authentication failed."))

    return redirect(url_for('signin'))

# ==================== ARTIST SUPPORT & AI CHAT API ====================
@app.route('/artist-support')
def artist_support():
    return render_template('ArtistSupport.html')

@app.route('/api/support-chat', methods=['POST'])
def support_chat():
    data = request.get_json() or {}
    query = data.get('query', '').strip().lower()
    
    if any(k in query for k in ['mix', 'master', 'eq', 'frequencies', 'volume', 'audio', 'sound']):
        reply = "Mixing & Mastering: Balance your multi-track stems in Pro Studio. Use high-pass filters on vocals/synths to clear mud, apply compression for dynamic control, and engage our 'Dragon Fire' master limiter for loudness."
    elif any(k in query for k in ['song', 'write', 'lyrics', 'melody', 'chord', 'compose', 'prompt']):
        reply = "Songwriting & AI Prompts: Craft rich prompts by combining style, key, tempo, and mood. For example: 'Cinematic electronic synthwave in D minor, 128 BPM, featuring driving basslines and atmospheric pads'."
    elif any(k in query for k in ['2fa', 'code', 'verification', 'email', 'login', 'signin', 'sign in']):
        reply = "Sign In & 2FA Security: When you sign in, a 6-digit verification code is sent to your email inbox. Check your inbox to complete your login."
    elif any(k in query for k in ['password', 'reset', 'forgot', 'strength', 'weak', 'secure']):
        reply = "Account & Passwords: Use the 'Forgot Password' link on the Sign In page to receive a recovery code. When creating a password, aim for the green 'Excellent' level by using uppercase letters, numbers, and symbols."
    elif any(k in query for k in ['export', 'download', 'wav', 'mp3', 'stems', 'output']):
        reply = "Exporting Tracks: You can export your completed compositions in high-fidelity 24-bit WAV or compressed MP3 format directly from the Studio Output or Pro Output pages."
    elif any(k in query for k in ['mode', 'moonlight', 'ancient', 'dragon', 'beginner', 'pro']):
        reply = "Studio Modes: Magical Flow offers Moonlight (clarity), Ancient Music (wisdom), and Dragon Fire (power) modes. Switch between Beginner for instant AI results and Pro Studio for full 8-track DAW control."
    elif any(k in query for k in ['hello', 'hi', 'hey', 'maya', 'help']):
        reply = "Hello! I'm Maya, your AI studio assistant. I'm ready to help you with anything in Magical Flow—from generating AI beats and mixing tracks to troubleshooting login issues. What are we working on today?"
    else:
        reply = f"I've got you covered regarding '{query}'. Whether you need help adjusting audio effects, structuring chord progressions, or managing your account settings, I'm here to ensure your session flows smoothly!"
        
    return jsonify({'reply': reply})

# ==================== NAVIGATION PLACEHOLDERS ====================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/select-mode')
def select_mode(): return render_template('Home.html')
@app.route('/beginner-mode')
def beginner_mode(): return render_template('Home.html')
@app.route('/beginner-output')
def beginner_output(): return render_template('Home.html')
@app.route('/pro-studio-mode')
def pro_studio_mode(): return render_template('Home.html')
@app.route('/studio-output')
def studio_output(): return render_template('Home.html')
@app.route('/my-music')
def my_music(): return render_template('Home.html')
@app.route('/account')
def account(): return render_template('Home.html')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
