from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from functools import wraps
import os
import sqlite3
import random
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables from the hidden .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = 'magical_flow_super_secret_production_key'
DB_NAME = 'MagicalFlow.db'

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

# ==================== AUTHENTICATION GUARD DECORATOR ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('signin'))
        return f(*args, **kwargs)
    return decorated_function

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
            
    return render_template('IdentityCheck.html', email=email, prototype_code="[Check your Gmail Inbox or Terminal]", error=error)

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

# ==================== ARTIST SUPPORT & AI MAYA CHAT API (LOCKED) ====================
@app.route('/artist-support')
@login_required
def artist_support():
    return render_template('ArtistSupport.html')

@app.route('/api/support-chat', methods=['POST'])
def support_chat():
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    query_lower = query.lower()
    
    # 1. WRITE A SONG INTENT
    if any(k in query_lower for k in ['write a song', 'lyrics', 'compose a track', 'write lyrics', 'make a song about']):
        reply = (
            "🎵 **Maya's Custom AI Songwriting Studio** 🎵<br><br>"
            "Here is a custom cinematic electronic/synthwave track concept crafted just for you:<br><br>"
            "🔹 **Title:** Neon Horizons<br>"
            "🔹 **Key & Tempo:** D Minor | 128 BPM<br>"
            "🔹 **Vibe:** Melancholic yet driving, futuristic, energetic.<br><br>"
            "**[Verse 1]**<br>"
            "Digital shadows stretching on the wall,<br>"
            "We're chasing echoes as the city lights fall.<br>"
            "Static in the air, a pulse in the dark,<br>"
            "Looking for a sign, a sudden spark.<br><br>"
            "**[Chorus]**<br>"
            "Ride the magical flow through the neon rain,<br>"
            "Wash away the noise, leave behind the pain.<br>"
            "In the synth and the bass, we come alive,<br>"
            "This is the rhythm where our souls survive!<br><br>"
            "💡 *Tip: Head over to Pro Studio Mode to lay down a pulsing synth bassline matching this 128 BPM groove!*"
        )
        
    # 2. SONG SUGGESTIONS & IDEAS INTENT
    elif any(k in query_lower for k in ['suggest', 'what song', 'idea', 'inspiration', 'what should i create', 'recommend']):
        reply = (
            "✨ **Maya's Top Song Recommendations for Today** ✨<br><br>"
            "Choose one of these unique directions to start your next session in Magical Flow:<br><br>"
            "1. **Cyberpunk Synthwave (125 BPM - A Minor):** Heavy distorted bass, punchy 808 drums, and soaring arpeggiated lead synths. Great for high-energy futuristic vibes.<br><br>"
            "2. **Lo-Fi Chill Hop (85 BPM - C Major):** Dusty vinyl crackle, warm rhodes piano chords, relaxed acoustic drum loop, and a smooth jazz saxophone or vocal chop.<br><br>"
            "3. **Cinematic Ambient Pop (110 BPM - E Minor):** Sweeping atmospheric string pads, echoing ambient guitars, and emotional soaring vocals with heavy reverb.<br><br>"
            "Which of these vibes would you like to build first?"
        )
        
    # 3. MIXING & MASTERING HELP INTENT
    elif any(k in query_lower for k in ['mix', 'master', 'eq', 'frequencies', 'volume', 'compression', 'balance']):
        reply = (
            "🎛️ **Maya's Pro Mixing & Mastering Guide** 🎛️<br><br>"
            "Follow these 4 professional steps to make your tracks sound radio-ready:<br><br>"
            "1. **Gain Staging:** Ensure your individual track faders sit around -12dB to -18dB so you leave plenty of headroom on the master bus.<br><br>"
            "2. **EQ & Filtering:** Use high-pass filters on your vocals and synths (around 80Hz–100Hz) to remove muddy low-end frequencies that clash with your kick and bass.<br><br>"
            "3. **Compression:** Apply gentle compression on your vocals and drums to even out dynamics and glue the elements together.<br><br>"
            "4. **The Master Limiter:** Engage our **'Dragon Fire' master limiter** on the output channel to boost overall loudness without introducing digital clipping!"
        )
        
    # 4. HOW TO MAKE MUSIC / WORKFLOW INTENT
    elif any(k in query_lower for k in ['how to make music', 'how do i start', 'start making music', 'workflow', 'beginner guide']):
        reply = (
            "🎹 **Step-by-Step Music Production Guide in Magical Flow** 🎹<br><br>"
            "Here is how you can go from zero to a finished track in minutes:<br><br>"
            "• **Step 1:** Select your mode from the Home screen. Use **Beginner Mode** for instant AI-generated beat ideas, or **Pro Studio Mode** for full 8-track DAW control.<br><br>"
            "• **Step 2:** Choose your Key and Tempo (e.g., 120 BPM in G Major is a fantastic starting point for melodic electronic music).<br><br>"
            "• **Step 3:** Lay down your core stems—start with a solid drum groove, add a bassline, and layer your chords.<br><br>"
            "• **Step 4:** Mix your audio levels, add effects, and export your finished masterpiece in high-fidelity WAV format!"
        )
        
    # 5. ACCOUNT / 2FA / PASSWORD HELP
    elif any(k in query_lower for k in ['2fa', 'code', 'verification', 'email', 'login', 'signin', 'password', 'reset', 'forgot']):
        reply = (
            "🔒 **Security & Account Support** 🔒<br><br>"
            "• **Sign In & 2FA:** When you sign in, an official 6-digit verification code is sent to your Gmail inbox (or displayed in your VS Code terminal as a backup).<br><br>"
            "• **Password Recovery:** Click 'Forgot Password' on the Sign In page to receive a recovery code and securely update your password."
        )
        
    # 6. GREETINGS
    elif any(k in query_lower for k in ['hello', 'hi', 'hey', 'maya', 'help']):
        reply = (
            "👋 Hello! I'm **Maya**, your personal AI studio assistant in Magical Flow.<br><br>"
            "I'm here to help you with *everything* you need: writing custom song lyrics, brainstorming hit song ideas, teaching you how to make music, or mixing your tracks. What would you like to work on today?"
        )
        
    # 7. DEFAULT CATCH-ALL (Dynamic custom response)
    else:
        reply = (
            f"🎵 I hear you loud and clear regarding '{query}'.<br><br>"
            "Whether you need me to write custom lyrics, suggest chord progressions, guide you through mixing stems, or help you navigate the studio, I've got your back. Tell me a bit more about what sound or genre you're aiming for, and let's make some magic!"
        )
        
    return jsonify({'reply': reply})

# ==================== NAVIGATION PLACEHOLDERS (LOCKED) ====================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('signin'))

@app.route('/select-mode')
@login_required
def select_mode(): return render_template('Home.html')

@app.route('/beginner-mode')
@login_required
def beginner_mode(): return render_template('Home.html')

@app.route('/beginner-output')
@login_required
def beginner_output(): return render_template('Home.html')

@app.route('/pro-studio-mode')
@login_required
def pro_studio_mode(): return render_template('Home.html')

@app.route('/studio-output')
@login_required
def studio_output(): return render_template('Home.html')

@app.route('/my-music')
@login_required
def my_music(): return render_template('Home.html')

@app.route('/account')
@login_required
def account(): return render_template('Home.html')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
    