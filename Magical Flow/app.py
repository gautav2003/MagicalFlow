from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = 'magical_flow_super_secret_key'
DB_NAME = 'MagicalFlow.db'

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "your_email@gmail.com"
SENDER_PASSWORD = "your_app_password"

def send_email(recipient_email, subject_text, body_text):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient_email
        msg['Subject'] = subject_text
        msg.attach(MIMEText(body_text, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
        server.quit()
        print(f"[*] Email sent successfully to {recipient_email}")
    except Exception as e:
        print(f"[!] SMTP Notice: {e}")
        print(f"==========================================")
        print(f" [{subject_text.upper()} FOR {recipient_email}]: Check console for prototype code")
        print(f"==========================================")

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

@app.route('/')
def home():
    return render_template('Home.html')

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
                session['new_user_name'] = username
                return redirect(url_for('account_created'))
            except sqlite3.IntegrityError:
                error = "Username or Email already exists."
    return render_template('Register.html', error=error)

@app.route('/account-created')
def account_created():
    username = session.get('new_user_name', 'Artist')
    return render_template('AccountCreated.html', username=username)

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
            send_email(user[2], "Magical Flow - Identity Check Code", f"Your verification code is: {code}")
            return redirect(url_for('identity_check'))
        else:
            error = "Invalid username/email or password."
    return render_template('Signin.html', error=error, message=message)

@app.route('/identity-check', methods=['GET', 'POST'])
def identity_check():
    error = None
    email = session.get('pending_email', 'user@gmail.com')
    prototype_code = session.get('auth_code', '482731')
    
    if request.method == 'POST':
        user_code = request.form.get('code')
        if user_code == prototype_code:
            session['user'] = session.get('pending_username')
            return redirect(url_for('home'))
        else:
            error = "Invalid verification code."
            
    return render_template('IdentityCheck.html', email=email, prototype_code=prototype_code, error=error)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        if user:
            recovery_code = str(random.randint(100000, 999999))
            session['recovery_email'] = email
            session['recovery_code'] = recovery_code
            send_email(email, "Magical Flow - Password Recovery Code", f"Your recovery code is: {recovery_code}")
            return redirect(url_for('account_recovery'))
        else:
            error = "No account found with that email address."
    return render_template('ForgotPassword.html', error=error)

@app.route('/account-recovery', methods=['GET', 'POST'])
def account_recovery():
    error = None
    email = session.get('recovery_email', 'Gautavsharma11@gmail.com')
    prototype_code = session.get('recovery_code', '409809')
    
    if request.method == 'POST':
        input_code = request.form.get('recovery_code')
        new_password = request.form.get('new_password')
        
        if input_code == prototype_code:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password = ? WHERE email = ?", (new_password, email))
            conn.commit()
            conn.close()
            return redirect(url_for('signin', msg='Password updated. Sign in with your new password.'))
        else:
            error = "Invalid recovery code."
            
    return render_template('AccountRecovery.html', email=email, prototype_code=prototype_code, error=error)

@app.route('/google-auth')
def google_auth():
    session['user'] = "Gautav Sharma (Google)"
    session['new_user_name'] = "Gautav Sharma (Google)"
    return redirect(url_for('account_created'))

@app.route('/google-login')
def google_login():
    session['pending_email'] = "gautavsharma11@gmail.com"
    session['pending_username'] = "Gautav Sharma (Google)"
    code = str(random.randint(100000, 999999))
    session['auth_code'] = code
    send_email("gautavsharma11@gmail.com", "Magical Flow - Google Sign In Verification", f"Your verification code is: {code}")
    return redirect(url_for('identity_check'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

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
        reply = "Sign In & 2FA Security: When you sign in, a 6-digit verification code is sent to your email. If testing locally without an active SMTP server, check your VS Code terminal console for the prototype code to complete your login."
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

# Navigation Placeholders
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
    