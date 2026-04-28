import os
import json
import sqlite3
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or "super_secret_barber_key_2024"

DB_PATH = "database.db"

PROFISSIONAIS = ["Carlos", "Marcos", "João"]
HORARIOS = ["09:00", "10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00", "18:00"]

def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def criar_banco():
    conn = conectar()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS agendamentos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  nome TEXT,
                  data TEXT,
                  hora TEXT,
                  profissional TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS datas_bloqueadas
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  data TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS horarios_bloqueados
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  data TEXT,
                  hora TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS profissionais_bloqueados
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  profissional TEXT UNIQUE)''')
    conn.commit()
    conn.close()

def get_horarios_disponiveis(data, profissional):
    conn = conectar()
    c = conn.cursor()
    c.execute('SELECT hora FROM agendamentos WHERE data=? AND profissional=?', (data, profissional))
    agendados = [r['hora'] for r in c.fetchall()]
    c.execute('SELECT hora FROM horarios_bloqueados WHERE data=?', (data,))
    bloqueados = [r['hora'] for r in c.fetchall()]
    conn.close()
    ocupados = set(agendados + bloqueados)
    return [h for h in HORARIOS if h not in ocupados]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = request.form.get('username', '').strip()
        senha = request.form.get('password', '')
        senha2 = request.form.get('password2', '')
        if not user or not senha:
            return render_template('register.html', erro='Preencha todos os campos.')
        if senha != senha2:
            return render_template('register.html', erro='As senhas não coincidem.')
        if len(senha) < 4:
            return render_template('register.html', erro='Senha deve ter pelo menos 4 caracteres.')
        conn = conectar()
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE username=?', (user,))
        if c.fetchone():
            conn.close()
            return render_template('register.html', erro='Usuário já existe.')
        c.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                  (user, generate_password_hash(senha)))
        conn.commit()
        conn.close()
        return redirect(url_for('login'))
    return render_template('register.html', erro=None)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username', '').strip()
        senha = request.form.get('password', '')
        if user == os.getenv("ADMIN_USER") and senha == os.getenv("ADMIN_PASSWORD"):
            session['user'] = user
            session['admin'] = True
            return redirect(url_for('admin'))
        conn = conectar()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username=?', (user,))
        usuario = c.fetchone()
        conn.close()
        if usuario and check_password_hash(usuario['password'], senha):
            session['user'] = user
            session['admin'] = False
            return redirect(url_for('dashboard'))
        return render_template('login.html', erro='Usuário ou senha incorretos.')
    return render_template('login.html', erro=None)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session or session.get('admin'):
        return redirect(url_for('login'))
    conn = conectar()
    c = conn.cursor()
    c.execute('SELECT * FROM agendamentos WHERE nome=? ORDER BY data ASC, hora ASC',
              (session['user'],))
    meus_agendamentos = [dict(r) for r in c.fetchall()]
    c.execute('SELECT data FROM datas_bloqueadas')
    datas_bloqueadas = [r['data'] for r in c.fetchall()]
    c.execute('SELECT profissional FROM profissionais_bloqueados')
    profs_bloqueados = [r['profissional'] for r in c.fetchall()]
    profissionais_ativos = [p for p in PROFISSIONAIS if p not in profs_bloqueados]
    conn.close()
    datas_bloqueadas_json = json.dumps(datas_bloqueadas)
    return render_template('dashboard.html',
                           agendamentos=meus_agendamentos,
                           profissionais=profissionais_ativos,
                           datas_bloqueadas_json=datas_bloqueadas_json,
                           horarios=HORARIOS)

@app.route('/api/horarios')
def api_horarios():
    if 'user' not in session:
        return jsonify({'erro': 'nao autorizado'}), 401
    data = request.args.get('data', '')
    profissional = request.args.get('profissional', '')
    if not data or not profissional:
        return jsonify([])
    return jsonify(get_horarios_disponiveis(data, profissional))

@app.route('/agendar', methods=['POST'])
def agendar():
    if 'user' not in session:
        return redirect(url_for('login'))
    data = request.form.get('data')
    hora = request.form.get('hora')
    profissional = request.form.get('profissional')
    if not data or not hora or not profissional:
        return redirect(url_for('dashboard'))
    if hora not in get_horarios_disponiveis(data, profissional):
        return redirect(url_for('dashboard'))
    conn = conectar()
    c = conn.cursor()
    c.execute('INSERT INTO agendamentos (nome, data, hora, profissional) VALUES (?, ?, ?, ?)',
              (session['user'], data, hora, profissional))
    conn.commit()
    conn.close()
    destino = url_for('admin') if session.get('admin') else url_for('dashboard')
    return redirect(destino)

@app.route('/cancelar/<int:id>', methods=['POST'])
def cancelar(id):
    if 'user' not in session:
        return redirect(url_for('login'))
    conn = conectar()
    c = conn.cursor()
    if session.get('admin'):
        c.execute('DELETE FROM agendamentos WHERE id=?', (id,))
    else:
        c.execute('DELETE FROM agendamentos WHERE id=? AND nome=?', (id, session['user']))
    conn.commit()
    conn.close()
    destino = url_for('admin') if session.get('admin') else url_for('dashboard')
    return redirect(destino)

@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect(url_for('login'))
    conn = conectar()
    c = conn.cursor()
    c.execute('SELECT * FROM agendamentos ORDER BY data ASC, hora ASC')
    agendamentos = [dict(r) for r in c.fetchall()]
    c.execute('SELECT * FROM datas_bloqueadas ORDER BY data ASC')
    datas_bloqueadas = [dict(r) for r in c.fetchall()]
    c.execute('SELECT * FROM horarios_bloqueados ORDER BY data ASC, hora ASC')
    horarios_bloqueados = [dict(r) for r in c.fetchall()]
    c.execute('SELECT * FROM profissionais_bloqueados')
    profs_bloqueados = [dict(r) for r in c.fetchall()]
    conn.close()
    return render_template('admin.html',
                           agendamentos=agendamentos,
                           datas_bloqueadas=datas_bloqueadas,
                           horarios_bloqueados=horarios_bloqueados,
                           profs_bloqueados=profs_bloqueados,
                           profissionais=PROFISSIONAIS,
                           horarios=HORARIOS)

@app.route('/bloquear_data', methods=['POST'])
def bloquear_data():
    if not session.get('admin'):
        return redirect(url_for('login'))
    data = request.form.get('data')
    if data:
        conn = conectar()
        c = conn.cursor()
        try:
            c.execute('INSERT INTO datas_bloqueadas (data) VALUES (?)', (data,))
            conn.commit()
        except:
            pass
        conn.close()
    return redirect(url_for('admin'))

@app.route('/desbloquear_data/<int:id>')
def desbloquear_data(id):
    if not session.get('admin'):
        return redirect(url_for('login'))
    conn = conectar()
    c = conn.cursor()
    c.execute('DELETE FROM datas_bloqueadas WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/bloquear_horario', methods=['POST'])
def bloquear_horario():
    if not session.get('admin'):
        return redirect(url_for('login'))
    data = request.form.get('data')
    hora = request.form.get('hora')
    if data and hora:
        conn = conectar()
        c = conn.cursor()
        c.execute('SELECT id FROM horarios_bloqueados WHERE data=? AND hora=?', (data, hora))
        if not c.fetchone():
            c.execute('INSERT INTO horarios_bloqueados (data, hora) VALUES (?, ?)', (data, hora))
            conn.commit()
        conn.close()
    return redirect(url_for('admin'))

@app.route('/desbloquear_horario/<int:id>')
def desbloquear_horario(id):
    if not session.get('admin'):
        return redirect(url_for('login'))
    conn = conectar()
    c = conn.cursor()
    c.execute('DELETE FROM horarios_bloqueados WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/bloquear_profissional', methods=['POST'])
def bloquear_profissional():
    if not session.get('admin'):
        return redirect(url_for('login'))
    profissional = request.form.get('profissional')
    if profissional:
        conn = conectar()
        c = conn.cursor()
        try:
            c.execute('INSERT INTO profissionais_bloqueados (profissional) VALUES (?)', (profissional,))
            conn.commit()
        except:
            pass
        conn.close()
    return redirect(url_for('admin'))

@app.route('/desbloquear_profissional/<int:id>')
def desbloquear_profissional(id):
    if not session.get('admin'):
        return redirect(url_for('login'))
    conn = conectar()
    c = conn.cursor()
    c.execute('DELETE FROM profissionais_bloqueados WHERE id=?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    criar_banco()
    app.run(debug=True, port=5000)