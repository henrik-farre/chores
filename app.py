from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from datetime import date, datetime
from functools import wraps
from utils.helpers import get_weekdays_of_week, get_week_number_from_date
from utils.db import get_db, init_db
import locale
import hashlib
import logging


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = 'Peen8ra$ ZePair7'
    app.config['DATABASE'] = 'chores.db'

    locale.setlocale(locale.LC_TIME, 'da_DK.UTF-8')

    app.logger.setLevel(logging.INFO)

    init_db(app)

    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session:
                return redirect(url_for('login'))

            return f(*args, **kwargs)
        return decorated_function

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        error = None

        if request.method == 'POST':
            conn = get_db()
            cursor = conn.cursor()

            username = request.form['username']
            password_clear = request.form['password']

            hashed_password = hashlib.md5(password_clear.encode()).hexdigest()

            cursor.execute("SELECT * FROM users WHERE name = ? AND password = ? LIMIT 1", (username, hashed_password))
            user = cursor.fetchone()

            if not user:
                error = 'Forkert brugernavn eller kodeord, prøv igen'
            else:
                session['username'] = user['name']
                session['user_id'] = user['id']
                session['is_admin'] = user['is_admin']
                return redirect(url_for('day_view'))

        return render_template('login.html', error=error)

    @app.route('/logout')
    def logout():
        session.pop('username', None)
        return redirect(url_for('login'))

    @app.route('/')
    def index():
        return redirect(url_for('day_view'))

    @app.route('/day', defaults={'selected_date': None})
    @app.route('/day/<string:selected_date>')
    @login_required
    def day_view(selected_date):
        conn = get_db()
        cursor = conn.cursor()

        if selected_date is None:
            selected_date = date.today()
        else:
            selected_date = datetime.strptime(selected_date, "%Y-%m-%d")

        cursor.execute("SELECT * FROM chores")
        chores = cursor.fetchall()

        cursor.execute('''
            SELECT
                cc.id, c.name, cc.price, u.name AS user_name, u.id AS user_id
            FROM
                completed_chores AS cc
            INNER JOIN chores AS c ON cc.chore_id = c.id
            INNER JOIN users AS u ON cc.user_id = u.id WHERE cc.date = ?
            ''', (selected_date.strftime("%Y-%m-%d"),))

        completed_chores = cursor.fetchall()

        week_number = get_week_number_from_date(selected_date)

        cursor.execute('''
            SELECT
                id
            FROM
                paid_weeks
            WHERE
                year = ? AND week = ?
            LIMIT 1
        ''', (selected_date.year, week_number))

        paid_week = cursor.fetchone()

        return render_template('day.html', chores=chores, current_date=selected_date, completed_chores=completed_chores, week_number=week_number, paid_week=paid_week)

    @app.route('/week', defaults={'week_number': None})
    @app.route('/week/<int:week_number>')
    @login_required
    def week_view(week_number):
        conn = get_db()

        # Get the current week number if not provided in the URL
        if week_number is None:
            now = datetime.now()
            week_number = now.isocalendar()[1]

        year = date.today().year

        weekdays = get_weekdays_of_week(year, week_number)
        start_date = weekdays[0]
        end_date = weekdays[6]

        # Get the chores completed by users for each day in the selected week
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                cc.date,
                cc.price,
                c.name AS chore_name,
                u.name AS user_name
            FROM
                completed_chores AS cc
            INNER JOIN chores AS c ON cc.chore_id = c.id
            INNER JOIN users AS u ON cc.user_id = u.id
            WHERE
                cc.date BETWEEN ? AND ?
            ORDER BY
                cc.timestamp ASC
        ''', (start_date, end_date))

        completed_chores = cursor.fetchall()

        weekdays_with_chores = {}
        for weekday in weekdays:
            index = weekday.strftime('%Y-%m-%d')
            weekdays_with_chores[index] = {
                'datetime': weekday,
                'chores': []
            }

        totals = {}
        bonus = {}

        for row in completed_chores:
            day = row['date']
            user_name = row['user_name']

            if user_name not in totals:
                totals[user_name] = 0

            totals[user_name] = totals[user_name] + row['price']
            bonus[user_name] = False

            weekdays_with_chores[day]['chores'].append({
                'chore_name': row['chore_name'],
                'user_name': row['user_name'],
                'price': row['price']
            })

        for weekday in weekdays:
            index = weekday.strftime('%Y-%m-%d')

            if not weekdays_with_chores[index]['chores']:
                app.logger.info('Nobody did anything on %s', weekday)
                for user_name in bonus:
                    bonus[user_name] = False
                break

            chores = weekdays_with_chores[index]['chores']

            for user_name in bonus:
                buildup_bonus = False
                for chore in chores:
                    if chore.get("user_name") == user_name:
                        buildup_bonus = True

                if buildup_bonus:
                    app.logger.info('%s build up bonus %s', user_name, weekday)
                    bonus[user_name] = True
                else:
                    app.logger.info('%s missed bonus, and is removed!', user_name)
                    del bonus[user_name]
                    break

        cursor.execute('''
            SELECT
                id
            FROM
                paid_weeks
            WHERE
                year = ? AND week = ?
            LIMIT 1
        ''', (year, week_number))

        paid_week = cursor.fetchone()

        return render_template('week.html', week_number=week_number, weekdays_with_chores=weekdays_with_chores, totals=totals, bonus=bonus, paid_week=paid_week)

    @app.route('/week/paid/<int:week_number>', methods=['POST'])
    def mark_week_as_paid(week_number):
        conn = get_db()
        cursor = conn.cursor()

        year = datetime.now().year

        cursor.execute('''
            INSERT INTO paid_weeks (year, week)
            VALUES (?, ?)
        ''', (year, week_number))

        conn.commit()
        conn.close()
        return jsonify({'message': 'Week marked as paid'})

    @app.route('/chore/complete', methods=['POST'])
    @login_required
    def chore_complete():
        conn = get_db()
        cursor = conn.cursor()

        chore_id = request.form.get('chore_id')
        current_date = request.form.get('current_date')

        user_id = session['user_id']

        res = cursor.execute("SELECT price, bonus_price, bonus_price_trigger FROM chores WHERE id = ?", (chore_id,))
        chore = res.fetchone()

        price = chore['price']

        if chore['bonus_price_trigger']:
            current_time = datetime.now().time()
            target_time = datetime.strptime(chore[2], "%H:%M").time()

            if target_time > current_time:
                price = price + chore[1]

        cursor.execute("INSERT INTO completed_chores (chore_id, user_id, date, price) VALUES (?, ?, ?, ?)", (chore_id, user_id, current_date, price))
        conn.commit()

        return redirect(url_for('day_view', selected_date=current_date))

    @app.route('/chore/complete/<int:chore_id>', methods=['DELETE'])
    @login_required
    def chore_delete(chore_id):
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM completed_chores WHERE id = ?", (chore_id,))
        conn.commit()

        return jsonify({'message': 'Chore completed successfully'})

    @app.route('/admin', methods=['GET', 'POST'])
    @login_required
    def admin():
        if 'is_admin' not in session:
            return redirect(url_for('login'))

        if session['is_admin'] != 1:
            return redirect(url_for('login'))

        conn = get_db()
        cursor = conn.cursor()

        if request.method == 'POST':
            if 'add_user' in request.form:
                username = request.form['username']
                password_clear = request.form['password']

                hashed_password = hashlib.md5(password_clear.encode()).hexdigest()

                if username:
                    cursor.execute('INSERT INTO users (name, password) VALUES (?, ?)', (username, hashed_password))
                    conn.commit()

            elif 'delete_user' in request.form:
                user_id = request.form['user_id']
                if user_id:

                    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
                    conn.commit()

            elif 'add_chore' in request.form:
                chore_name = request.form['chore_name']
                chore_price = request.form['chore_price']
                chore_bonus_price = request.form['chore_bonus_price']
                chore_bonus_price_trigger = request.form['chore_bonus_price_trigger']
                chore_type = request.form['chore_type']
                chore_limit = request.form['chore_limit']

                if chore_name and chore_price and chore_type:
                    cursor.execute('''
                        INSERT INTO chores (name, price, bonus_price, bonus_price_trigger, interval, work_limit)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (chore_name, chore_price, chore_bonus_price, chore_bonus_price_trigger, chore_type, chore_limit))
                    conn.commit()

            elif 'delete_chore' in request.form:
                chore_id = request.form['chore_id']
                if chore_id:

                    cursor.execute('DELETE FROM chores WHERE id = ?', (chore_id,))
                    conn.commit()

            return redirect(url_for('admin'))

        else:
            cursor.execute("SELECT * FROM users")
            users = cursor.fetchall()

            cursor.execute("SELECT * FROM chores")
            chores = cursor.fetchall()

            return render_template('admin.html', users=users, chores=chores)

    return app
