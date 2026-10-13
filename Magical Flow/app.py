from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = 'magical_flow_super_secret_key'
DB_NAME = 'MagicalFlow.db'

# --- Email Configuration (SMTP with Terminal fallback) ---
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
    session['user'] = "Google User"
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Placeholder routes for navigation links
@app.route('/select-mode')
def select_mode(): 
    return render_template('Home.html')

@app.route('/beginner-mode')
def beginner_mode(): 
    return render_template('Home.html')

@app.route('/beginner-output')
def beginner_output(): 
    return render_template('Home.html')

@app.route('/pro-studio-mode')
def pro_studio_mode(): 
    return render_template('Home.html')

@app.route('/studio-output')
def studio_output(): 
    return render_template('Home.html')

@app.route('/my-music')
def my_music(): 
    return render_template('Home.html')

@app.route('/account')
def account(): 
    return render_template('Home.html')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
    