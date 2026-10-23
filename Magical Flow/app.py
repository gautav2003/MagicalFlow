from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from functools import wraps
import base64
import json
import os
from pathlib import Path
import sqlite3
import random
import smtplib
import ssl
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load environment variables from the hidden .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = 'magical_flow_super_secret_production_key'
DB_NAME = 'MagicalFlow.db'
GENERATED_AUDIO_DIR = Path(app.instance_path) / 'generated_audio'
GEMINI_INTERACTIONS_URL = 'https://generativelanguage.googleapis.com/v1beta/interactions'
GEMINI_MUSIC_MODEL = os.getenv('GEMINI_MUSIC_MODEL') or 'lyria-3.5'


class MusicGenerationError(Exception):
    """Raised when the configured music-generation provider cannot return a song."""


def generate_music(prompt):
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise MusicGenerationError(
            'Music generation is not configured yet. Add GEMINI_API_KEY to your local .env file.'
        )

    payload = json.dumps({
        'model': GEMINI_MUSIC_MODEL,
        'input': prompt,
    }).encode('utf-8')
    api_request = Request(
        GEMINI_INTERACTIONS_URL,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'x-goog-api-key': api_key,
        },
        method='POST',
    )

    try:
        with urlopen(api_request, timeout=300) as response:
            result = json.loads(response.read())
    except HTTPError as error:
        app.logger.error('Gemini music generation returned HTTP %s.', error.code)
        raise MusicGenerationError(
            'The music provider could not generate this song. Check model access, quota, and billing.'
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        app.logger.error('Gemini music generation request failed: %s', error)
        raise MusicGenerationError(
            'Could not reach the music provider. Please try again.'
        ) from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        app.logger.error('Gemini returned an unreadable music-generation response.')
        raise MusicGenerationError(
            'The music provider returned an unreadable response. Please try again.'
        ) from error

    if not isinstance(result, dict):
        raise MusicGenerationError('The music provider returned an unreadable response. Please try again.')
    output_audio = result.get('output_audio')
    audio_data = output_audio.get('data') if isinstance(output_audio, dict) else None
    if not audio_data:
        app.logger.error('Gemini music generation response did not contain audio.')
        raise MusicGenerationError(
            'The music provider returned no audio for this request. Please try again.'
        )
    if not isinstance(audio_data, str):
        raise MusicGenerationError('The music provider returned invalid audio. Please try again.')
    try:
        audio_bytes = base64.b64decode(audio_data, validate=True)
    except (ValueError, TypeError) as error:
        app.logger.error('Gemini returned invalid encoded audio.')
        raise MusicGenerationError(
            'The music provider returned invalid audio. Please try again.'
        ) from error
    if not audio_bytes:
        raise MusicGenerationError('The music provider returned an empty audio file.')

    GENERATED_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    audio_id = uuid.uuid4().hex
    audio_path = GENERATED_AUDIO_DIR / f'{audio_id}.mp3'
    try:
        audio_path.write_bytes(audio_bytes)
    except OSError as error:
        app.logger.error('Unable to save generated music: %s', error)
        raise MusicGenerationError('The generated song could not be saved on this server.') from error
    lyrics = result.get('output_text', '')
    return audio_id, lyrics if isinstance(lyrics, str) else ''

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
    
    selected_genre = session.get('active_vocal_genre', 'Bollywood')

    # 1. GENERATE SPECIFIC VOCAL STYLE (e.g., "magical", "male", "female", "romantic")
    if any(k in query_lower for k in ['magical', 'romantic', 'classical', 'energetic', 'male', 'female']):
        vibe = "Magical & Ethereal" if "magical" in query_lower else "Expressive & Soulful"
        gender = "Female Vocalist" if "female" in query_lower else ("Male Vocalist" if "male" in query_lower else "Dual Male/Female Duet")
        
        reply = (
            f"✨ **Maya's AI {selected_genre} Vocal Generator** ✨<br><br>"
            f"🎉 **Generated Vocal Profile:** {selected_genre} {gender} ({vibe})<br><br>"
            "🔹 **Tone & Texture:** Silky smooth classical runs, lush ambient hall reverb, subtle tape warmth, and expressive dynamic pitch bends.<br>"
            "🔹 **Recommended Scale:** C# Minor / D Phrygian Dominant (for rich Eastern modal color).<br>"
            "🔹 **FX Chain Preset:** High-pass filter @ 100Hz -> Optical Compressor -> Shimmer Reverb (2.8s decay) -> Analog Delay (1/8th note triplet sync).<br><br>"
            "🎧 **Studio Preview Action:** Your custom vocal track has been synthesized and synced to your current BPM! Would you like to load this directly into **Pro Studio Mode** track 1?"
        )

    # 2. INTERACTIVE GENRE CHOICE (e.g., "bollywood", "punjabi", "hollywood", "pop")
    elif any(g in query_lower for g in ['bollywood', 'punjabi', 'hollywood', 'kpop', 'k-pop', 'classical']):
        matched_genre = "Bollywood" if "bollywood" in query_lower else "Custom Genre"
        session['active_vocal_genre'] = matched_genre
        
        reply = (
            f"🎻 **Maya's AI Vocal Customizer ({matched_genre})** 🎻<br><br>"
            f"Great choice! I am ready to generate custom **{matched_genre}** vocals for your music.<br><br>"
            "To build the perfect vocal for your track, please tell me:<br>"
            "1. Would you like a **Male**, **Female**, or **Duet** voice?<br>"
            "2. How should the vocal sound like? (e.g., **Magical**, **Romantic**, **Classical**, or **Energetic**)?<br><br>"
            "*(Simply type your preference below, e.g., 'Female and magical'!)*"
        )

    # 3. GENERAL VOCAL QUERY
    elif any(k in query_lower for k in ['vocal', 'singing', 'singer', 'signing', 'voice', 'acapella', 'vocals']):
        reply = (
            "🎤 **Maya's AI Vocal & Singer Selection Studio** 🎤<br><br>"
            "I can generate and process custom vocals for any style of music! Which genre are you working on?<br><br>"
            "• **Bollywood** (e.g., Magical, Romantic, Sufi Classical)<br>"
            "• **Punjabi Folk / Bhangra**<br>"
            "• **Pop & Cyberpunk Synthwave**<br>"
            "• **Hip-Hop / Melodic Trap**<br>"
            "• **R&B & Soul**<br><br>"
            "👉 *Type your genre (for example: 'Bollywood') to customize your singer!*"
        )

    # 4. WRITE A SONG INTENT
    elif any(k in query_lower for k in ['write a song', 'lyrics', 'compose a track', 'write lyrics', 'make a song about']):
        reply = (
            "🎵 **Maya's Custom AI Songwriting Studio** 🎵<br><br>"
            "Here is a custom song concept crafted just for your request:<br><br>"
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

    # 5. SONG SUGGESTIONS & IDEAS INTENT
    elif any(k in query_lower for k in ['suggest', 'what song', 'idea', 'inspiration', 'what should i create', 'recommend']):
        reply = (
            "✨ **Maya's Top Song Recommendations for Today** ✨<br><br>"
            "Choose one of these unique directions to start your next session in Magical Flow:<br><br>"
            "1. **Bollywood Fusion (105 BPM - C# Minor):** Warm acoustic sitar chords, punchy dholak groove, and sweeping magical vocal runs.<br><br>"
            "2. **Cyberpunk Synthwave (125 BPM - A Minor):** Heavy distorted bass, punchy 808 drums, and arpeggiated lead synths.<br><br>"
            "3. **Lo-Fi Chill Hop (85 BPM - C Major):** Dusty vinyl crackle, warm rhodes piano chords, and smooth saxophone.<br><br>"
            "Which of these vibes would you like to build first?"
        )

    # 6. MIXING & MASTERING HELP INTENT
    elif any(k in query_lower for k in ['mix', 'master', 'eq', 'frequencies', 'volume', 'compression', 'balance']):
        reply = (
            "🎛️ **Maya's Pro Mixing & Mastering Guide** 🎛️<br><br>"
            "Follow these 4 professional steps to make your tracks sound radio-ready:<br><br>"
            "1. **Gain Staging:** Ensure individual track faders sit around -12dB to -18dB for headroom.<br><br>"
            "2. **EQ & Filtering:** High-pass filter vocals/synths (80Hz–100Hz) to keep kick/bass clean.<br><br>"
            "3. **Compression:** Apply gentle compression on vocals and drums to glue dynamics.<br><br>"
            "4. **The Master Limiter:** Engage our **'Dragon Fire' master limiter** on output for maximum loudness without clipping!"
        )

    # 7. HOW TO MAKE MUSIC / WORKFLOW INTENT
    elif any(k in query_lower for k in ['how to make music', 'how do i start', 'start making music', 'workflow', 'beginner guide']):
        reply = (
            "🎹 **Step-by-Step Music Production Guide in Magical Flow** 🎹<br><br>"
            "Here is how you can go from zero to a finished track in minutes:<br><br>"
            "• **Step 1:** Select your mode from Home screen (Beginner Mode or Pro Studio Mode).<br><br>"
            "• **Step 2:** Choose your Key and Tempo (e.g., 120 BPM in G Major).<br><br>"
            "• **Step 3:** Lay down your core stems—drums, bassline, and chords.<br><br>"
            "• **Step 4:** Mix your levels, add effects, and export your track in high-fidelity WAV format!"
        )

    # 8. ACCOUNT / 2FA / PASSWORD HELP
    elif any(k in query_lower for k in ['2fa', 'code', 'verification', 'email', 'login', 'signin', 'password', 'reset', 'forgot']):
        reply = (
            "🔒 **Security & Account Support** 🔒<br><br>"
            "• **Sign In & 2FA:** A 6-digit verification code is sent to your Gmail inbox (or displayed in your VS Code terminal as a backup).<br><br>"
            "• **Password Recovery:** Click 'Forgot Password' on the Sign In page to receive a recovery code."
        )

    # 9. GREETINGS
    elif any(k in query_lower for k in ['hello', 'hi', 'hey', 'maya', 'help']):
        reply = (
            "👋 Hello! I'm **Maya**, your personal AI studio assistant in Magical Flow.<br><br>"
            "I can generate custom vocals (Bollywood, Pop, R&B, Punjabi, etc.), write lyrics, recommend song concepts, and help you mix your tracks. What are we creating today?"
        )

    # 10. DEFAULT CATCH-ALL
    else:
        reply = (
            f"🎵 I hear you loud and clear regarding '{query}'.<br><br>"
            "Whether you need magical Bollywood vocals, custom song lyrics, chord suggestions, or mixing advice, I'm here to help. Tell me what genre or vibe you're aiming for, and let's create it!"
        )

    return jsonify({'reply': reply})

# ==================== NAVIGATION & STUDIO MODES ====================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('signin'))

@app.route('/select-mode')
@login_required
def select_mode():
    username = session.get('user', 'Artist')
    return render_template('SelectMode.html', username=username)

@app.route('/beginner-mode', methods=['GET', 'POST'])
@login_required
def beginner_mode():
    if request.method == 'POST':
        prompt = request.form.get('prompt', '').strip()
        genre = request.form.get('genre', '')
        mood = request.form.get('mood', '')
        allowed_genres = {
            'Lo-Fi', 'Hip-Hop', 'Jazz', 'Electronic', 'Western Pop', 'Folk',
            'R&B', 'Classical', 'Punjabi Pop', 'Bhangra', 'Bollywood Romance',
        }
        genre_directions = {
            'Lo-Fi': 'A relaxed, dusty hip-hop groove with warm keys and soft drums.',
            'Hip-Hop': 'A Western hip-hop production with a steady kick and snare, deep bass, and a memorable original instrumental hook.',
            'Jazz': 'A warm small-combo jazz arrangement with expressive harmony and a relaxed rhythmic feel.',
            'Electronic': 'A modern electronic production with layered synthesizers and a clear rhythmic build.',
            'Western Pop': 'A polished Western pop production with a clear verse and chorus, memorable original hook, lively drums, and layered harmony.',
            'Folk': 'An acoustic folk arrangement with organic strumming, gentle percussion, and an intimate melody.',
            'R&B': 'A smooth contemporary R&B production with warm chords, a relaxed groove, and expressive original melody.',
            'Classical': 'A cinematic orchestral arrangement with a developing melody and dynamic instrumental sections.',
            'Punjabi Pop': 'A contemporary Punjabi pop production with original Punjabi folk-inspired rhythm, dhol accents, bass, and melodic instrumentation.',
            'Bhangra': 'An upbeat Punjabi Bhangra song with an energetic dhol groove, tumbi-inspired melodic flourishes, handclaps, and a celebratory original chorus.',
            'Bollywood Romance': 'A romantic Hindi film-song arrangement inspired by broad 1990s Bollywood production traits: expressive strings, flute-like melodic fills, hand percussion, lush harmony, and a memorable original chorus.',
        }
        allowed_moods = {'Chill', 'Energetic', 'Dark', 'Happy', 'Sad', 'Romantic', 'Focused'}
        allowed_instruments = {
            'Piano', 'Guitar', 'Bass', 'Drums', 'Synth', 'Strings',
            'Brass', 'Pad', 'Arp', 'Vocals',
        }
        try:
            bpm = int(request.form.get('bpm', '90'))
            duration = int(request.form.get('duration', '2'))
        except ValueError:
            bpm, duration = 0, 0
        instruments = request.form.getlist('instruments')
        instruments = [instrument for instrument in instruments if instrument in allowed_instruments]
        vocals = 'Generated vocals' if 'Vocals' in instruments else 'Instrumental'
        composition = {
            'prompt': prompt,
            'genre': genre,
            'mood': mood,
            'tempo': f'{bpm} BPM',
            'duration': duration,
            'instruments': instruments,
            'vocals': vocals,
        }
        if not prompt or len(prompt) > 500:
            composition['generation_error'] = 'Enter a song description of 1 to 500 characters.'
        elif genre not in allowed_genres or mood not in allowed_moods:
            composition['generation_error'] = 'Choose a valid genre and mood before generating.'
        elif not 60 <= bpm <= 180 or not 1 <= duration <= 3:
            composition['generation_error'] = 'Choose a tempo from 60 to 180 BPM and a song length from 1 to 3 minutes.'
        else:
            selected_instruments = ', '.join(instruments) if instruments else 'a suitable original arrangement'
            genre_direction = genre_directions[genre]
            vocal_direction = (
                'Include original, newly written sung lyrics appropriate to the selected genre and language requested in the description. '
                if vocals == 'Generated vocals' else 'Instrumental only; no sung vocals or lyrics. '
            )
            generation_prompt = (
                f"Create a complete, original {genre} song. {genre_direction} "
                f"The mood is {mood}; make it approximately {duration} minutes long at {bpm} BPM. "
                f"Use {selected_instruments}. "
                f"{vocal_direction}"
                f"Follow this creative description: {prompt}. "
                "Use an original melody, lyrics, and arrangement; do not imitate or reproduce any existing song or artist."
            )
            try:
                audio_id, lyrics = generate_music(generation_prompt)
                composition['audio_id'] = audio_id
                composition['lyrics'] = lyrics
                composition['generation_error'] = ''
            except MusicGenerationError as error:
                composition['generation_error'] = str(error)
        session['composition_data'] = composition
        return redirect(url_for('beginner_output'))
    return render_template('Beginnermode.html')

@app.route('/beginner-output')
@login_required
def beginner_output():
    composition = session.get('composition_data', {
        'prompt': 'A magical melody under the stars',
        'genre': 'Bollywood Romantic',
        'mood': 'Magical & Dreamy',
        'tempo': '120 BPM',
        'vocals': 'Instrumental',
        'generation_error': 'Describe a song in Beginner Mode to generate your first track.',
    })
    if not composition.get('audio_id') and not composition.get('generation_error'):
        composition['generation_error'] = 'No generated song is available yet. Create a song in Beginner Mode to get started.'
    return render_template('BeginnerGeneration.html', composition=composition)

@app.route('/generated-audio/<audio_id>')
@login_required
def generated_audio(audio_id):
    composition = session.get('composition_data', {})
    if audio_id != composition.get('audio_id'):
        return 'Audio not found.', 404
    return send_from_directory(
        str(GENERATED_AUDIO_DIR),
        f'{audio_id}.mp3',
        mimetype='audio/mpeg',
        as_attachment=request.args.get('download') == '1',
        download_name='magical-flow-song.mp3',
    )

@app.route('/pro-studio-mode')
@login_required
def pro_studio_mode():
    return render_template('prostudiomode.html')

@app.route('/pro-studio-output')
@login_required
def studio_output():
    return render_template('prostudiooutput.html')

@app.route('/my-music')
@login_required
def my_music():
    return render_template('mymusic.html')

@app.route('/account')
@login_required
def account():
    return render_template('account.html')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
