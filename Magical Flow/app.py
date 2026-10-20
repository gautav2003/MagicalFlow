import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, session, request, flash
from authlib.integrations.flask_client import OAuth

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "magical_flow_default_secret_key")

# --------------------------------------------------------------------
# 1. AUTHENTICATION DECORATOR (Strict Route Protection)
# --------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            flash("Please sign in or register to access Magical Flow.", "warning")
            return redirect(url_for('signin'))
        return f(*args, **kwargs)
    return decorated_function


# --------------------------------------------------------------------
# 2. GOOGLE OAUTH CONFIGURATION
# --------------------------------------------------------------------
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

@app.route('/login/google')
def google_login():
    # Automatically generates http://127.0.0.1:5000/authorize/google
    redirect_uri = url_for('google_authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize/google')
def google_authorize():
    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo')
        if user_info:
            session['user_email'] = user_info['email']
            session['user_name'] = user_info.get('name')
            flash("Successfully signed in with Google!", "success")
            return redirect(url_for('select_mode'))
    except Exception as e:
        print(f"Google Auth Error: {e}")
        flash("Google login failed. Please try again.", "error")
    return redirect(url_for('signin'))


# --------------------------------------------------------------------
# 3. GMAIL SMTP HELPER FUNCTION
# --------------------------------------------------------------------
def send_email(recipient_email, subject, html_content):
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 465))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    msg = MIMEMultipart()
    msg['From'] = smtp_from
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_content, 'html'))

    try:
        if smtp_port == 465 or os.getenv("SMTP_USE_SSL") == "true":
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        return True
    except Exception as e:
        print(f"SMTP Error: {e}")
        # Terminal fallback print so local testing doesn't break if firewall blocks ports
        print(f"\n--- [FALLBACK EMAIL] To: {recipient_email} | Subject: {subject} ---\n{html_content}\n----------------------------------------------------\n")
        return False


# --------------------------------------------------------------------
# 4. APPLICATION ROUTES
# --------------------------------------------------------------------

@app.route('/')
def root():
    if 'user_email' in session:
        return redirect(url_for('home'))
    return redirect(url_for('signin'))

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        session['user_email'] = email
        flash("Signed in successfully!", "success")
        return redirect(url_for('select_mode'))
    return render_template('SignIn.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        session['user_email'] = email
        session['user_name'] = name
        send_email(email, "Welcome to Magical Flow!", "<h2>Welcome!</h2><p>Your Magical Flow account has been successfully created.</p>")
        return redirect(url_for('account_created'))
    return render_template('Register.html')

@app.route('/account-created')
@login_required
def account_created():
    return render_template('AccountCreated.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        email = request.form.get('email')
        send_email(email, "Password Reset Code - Magical Flow", "<h3>Password Recovery</h3><p>Use your 2FA terminal recovery code to reset your credentials.</p>")
        flash("Password reset instructions sent to your email.", "info")
        return redirect(url_for('signin'))
    return render_template('ResetPassword.html')

@app.route('/home')
@login_required
def home():
    return render_template('Home.html')

@app.route('/select-mode')
@login_required
def select_mode():
    return render_template('SelectMode.html')

@app.route('/beginner-mode')
@login_required
def beginner_mode():
    return render_template('BeginnerMode.html')

@app.route('/pro-studio-mode')
@login_required
def pro_studio_mode():
    return render_template('ProStudioMode.html')

@app.route('/beginner-output', methods=['GET', 'POST'])
@login_required
def beginner_output():
    if request.method == 'POST':
        prompt = request.form.get('prompt')
        genre = request.form.get('genre')
        mood = request.form.get('mood')
        tempo = request.form.get('tempo')
        vocals = request.form.get('vocals')
    return render_template('BeginnerOutput.html')

@app.route('/studio-output')
@login_required
def studio_output():
    return render_template('StudioOutput.html')

@app.route('/my-music')
@login_required
def my_music():
    return render_template('MyMusic.html')

@app.route('/account')
@login_required
def account():
    return render_template('Account.html')

@app.route('/artist-support')
@login_required
def artist_support():
    return render_template('ArtistSupport.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for('signin'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)), debug=True)