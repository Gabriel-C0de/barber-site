from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'barber2024')

ADMIN_USER = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASS = os.getenv('ADMIN_PASS', 'admin123')

HORARIOS = [
    '08:00', '08:30', '09:00', '09:30',
    '10:00', '10:30', '11:00', '11:30',
    '13:00', '13:30', '14:00', '14:30',
    '15:00', '15:30', '16:00', '16:30',
    '17:00', '17:30'
]

def conectar():
    return sqlite3.connect('database.db')

def criar_banco():
    conn = conectar()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS agendamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            data TEXT,
            hora TEXT,
            user TEXT
        )
    ''')
    conn.commit()
    conn.close()

def horarios_disponiveis(data):
    conn = conectar()
    c = conn.cursor()
    c.execute('SELECT hora FROM agendamentos WHERE data = ?', (data,))
    ocupados = [row[0] for row in c.fetchall()]
    conn.close()
    return [h for h in HORARIOS if h not in ocupados]

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = request.form['username'].strip()
        senha = request.form['password']
        senha2 = request.form['password2']
        if not user or not senha:
            return render_template('register.html', erro='Preencha todos os campos.')
        if senha != senha2:
            return render_template('register.html', erro='As senhas não coincidem.')
        if len(senha) < 4:
            return render_template('register.html', erro='Senha deve ter pelo menos 4 caracteres.')
        conn = conectar()
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE username = ?', (user,))
        if c.fetchone():
            conn.close()
            return render_template('register.html', erro='Usuário já existe.')
        c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (user, senha))
        conn.commit()
        conn.close()
        return redirect('/login')
    return render_template('register.html', erro=None)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username'].strip()
        senha = request.form['password']
        if user == ADMIN_USER and senha == ADMIN_PASS:
            session['user'] = user
            session['admin'] = True
            return redirect('/dashboard')
        conn = conectar()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username = ? AND password = ?', (user, senha))
        usuario = c.fetchone()
        conn.close()
        if usuario:
            session['user'] = user
            session['admin'] = False
            return redirect('/meus')
        return render_template('login.html', erro='Usuário ou senha incorretos.')
    return render_template('login.html', erro=None)

@app.route('/dashboard')
def dashboard():
    if not session.get('admin'):
        return redirect('/login')
    conn = conectar()
    c = conn.cursor()
    c.execute('SELECT * FROM agendamentos ORDER BY data ASC, hora ASC')
    agendamentos = c.fetchall()
    conn.close()
    return render_template('dashboard.html', agendamentos=agendamentos, hoje=date.today().isoformat())

@app.route('/meus')
def meus():
    if 'user' not in session or session.get('admin'):
        return redirect('/login')
    data_selecionada = request.args.get('data', '')
    horarios = []
    if data_selecionada:
        horarios = horarios_disponiveis(data_selecionada)
    conn = conectar()
    c = conn.cursor()
    c.execute('SELECT * FROM agendamentos WHERE user = ? ORDER BY data ASC, hora ASC', (session['user'],))
    meus_ags = c.fetchall()
    conn.close()
    return render_template(
        'meus.html',
        agendamentos=meus_ags,
        horarios=horarios,
        data_selecionada=data_selecionada,
        hoje=date.today().isoformat()
    )

@app.route('/agendar', methods=['POST'])
def agendar():
    if 'user' not in session:
        return redirect('/login')
    nome = request.form['nome'].strip()
    data = request.form['data']
    hora = request.form['hora']
    destino = '/dashboard' if session.get('admin') else '/meus'
    if nome and data and hora:
        if hora in horarios_disponiveis(data):
            conn = conectar()
            c = conn.cursor()
            c.execute(
                'INSERT INTO agendamentos (nome, data, hora, user) VALUES (?, ?, ?, ?)',
                (nome, data, hora, session['user'])
            )
            conn.commit()
            conn.close()
    return redirect(destino)

@app.route('/excluir/<int:id>')
def excluir(id):
    if 'user' not in session:
        return redirect('/login')
    conn = conectar()
    c = conn.cursor()
    c.execute('SELECT user FROM agendamentos WHERE id = ?', (id,))
    ag = c.fetchone()
    if ag and (session.get('admin') or ag[0] == session['user']):
        c.execute('DELETE FROM agendamentos WHERE id = ?', (id,))
        conn.commit()
    conn.close()
    destino = '/dashboard' if session.get('admin') else '/meus'
    return redirect(destino)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    criar_banco()
    app.run(debug=True)