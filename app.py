import os
from datetime import datetime

from flask import Flask, render_template, request, jsonify
import sqlite3

app = Flask(__name__, template_folder='.')

DATABASE_PATH = os.environ.get('MEAL_DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db'))
DAYS = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_date(date_value):
    if not date_value: 
        return ''

    value = str(date_value).strip()
    if not value:
        return ''

    try:
        datetime.strptime(value, '%Y-%m-%d')
        return value
    except ValueError:
        return ''


def day_from_date(date_value):
    normalized = normalize_date(date_value)
    if not normalized:
        return ''

    try:
        return datetime.strptime(normalized, '%Y-%m-%d').strftime('%A')
    except ValueError:
        return ''


def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS meal_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            calories INTEGER NOT NULL,
            category TEXT NOT NULL DEFAULT 'Umum'
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS daily_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            date TEXT DEFAULT '',
            option_id INTEGER NOT NULL,
            FOREIGN KEY(option_id) REFERENCES meal_options(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS food_reference (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            calories INTEGER NOT NULL,
            category TEXT NOT NULL DEFAULT 'Umum',
            portion TEXT NOT NULL DEFAULT '1 porsi'
        )
    ''')

    columns = [row['name'] for row in conn.execute('PRAGMA table_info(daily_plan)').fetchall()]
    if 'date' not in columns:
        conn.execute('ALTER TABLE daily_plan ADD COLUMN date TEXT DEFAULT ""')

    existing = conn.execute('SELECT COUNT(*) AS total FROM food_reference').fetchone()['total']
    if existing == 0:
        sample_foods = [
            ('Ayam Goreng', 250, 'Protein', '1 porsi'),
            ('Ayam Bakar', 220, 'Protein', '1 porsi'),
            ('Dada Ayam', 165, 'Protein', '100 g'),
            ('Nasi Putih', 200, 'Karbohidrat', '1 piring'),
            ('Nasi Uduk', 420, 'Karbohidrat', '1 porsi'),
            ('Kentang Rebus', 130, 'Karbohidrat', '150 g'),
            ('Tempe Goreng', 190, 'Protein', '1 potong'),
            ('Tahu', 80, 'Protein', '1 potong'),
            ('Sayur Bayam', 40, 'Sayur', '1 porsi'),
            ('Brokoli Rebus', 55, 'Sayur', '1 porsi'),
            ('Alpukat', 160, 'Sayur', '1 buah'),
            ('Buah Pisang', 105, 'Buah', '1 buah'),
            ('Apel', 95, 'Buah', '1 buah'),
            ('Telur Rebus', 78, 'Protein', '1 butir'),
            ('Telur Orak-Arik', 120, 'Protein', '1 porsi'),
            ('Minyak Goreng', 120, 'Lainnya', '1 sdm'),
            ('Mie Goreng', 330, 'Karbohidrat', '1 porsi'),
            ('Oatmeal', 150, 'Karbohidrat', '1 mangkuk'),
            ('Greek Yogurt', 130, 'Protein', '1 cup'),
            ('Smoothie Pisang', 220, 'Minuman', '1 gelas'),
        ]
        conn.executemany(
            'INSERT INTO food_reference (name, calories, category, portion) VALUES (?, ?, ?, ?)',
            sample_foods
        )

    conn.commit()
    conn.close()


init_db()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/options', methods=['GET', 'POST'])
def manage_options():
    conn = get_db_connection()

    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        category = (data.get('category') or 'Umum').strip() or 'Umum'
        calories = data.get('calories')

        if not name or calories is None:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Nama menu dan kalori wajib diisi!'}), 400

        try:
            calories = int(calories)
        except (TypeError, ValueError):
            conn.close()
            return jsonify({'status': 'error', 'message': 'Kalori harus berupa angka!'}), 400

        cursor = conn.execute(
            'INSERT INTO meal_options (name, calories, category) VALUES (?, ?, ?)',
            (name, calories, category)
        )
        conn.commit()
        option = conn.execute('SELECT * FROM meal_options WHERE id = ?', (cursor.lastrowid,)).fetchone()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Menu berhasil ditambahkan!', 'option': dict(option)}), 201

    category_filter = request.args.get('category', '').strip()
    if category_filter:
        options = conn.execute('SELECT * FROM meal_options WHERE category = ? ORDER BY name', (category_filter,)).fetchall()
    else:
        options = conn.execute('SELECT * FROM meal_options ORDER BY category, name').fetchall()
    conn.close()
    return jsonify([dict(option) for option in options])


@app.route('/api/options/<int:option_id>', methods=['DELETE'])
def delete_option(option_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM daily_plan WHERE option_id = ?', (option_id,))
    conn.execute('DELETE FROM meal_options WHERE id = ?', (option_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': 'Menu berhasil dihapus!'})


@app.route('/api/daily-plan', methods=['GET', 'POST', 'DELETE'])
def manage_daily_plan():
    conn = get_db_connection()

    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        day = (data.get('day') or '').strip()
        date = normalize_date(data.get('date'))
        option_ids = data.get('option_ids') or []

        if not day and not date:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Hari atau tanggal wajib dipilih!'}), 400

        if not isinstance(option_ids, list):
            conn.close()
            return jsonify({'status': 'error', 'message': 'Pilihan menu harus berupa daftar!'}), 400

        if date and not day:
            day = day_from_date(date)
            if day == 'Monday':
                day = 'Senin'
            elif day == 'Tuesday':
                day = 'Selasa'
            elif day == 'Wednesday':
                day = 'Rabu'
            elif day == 'Thursday':
                day = 'Kamis'
            elif day == 'Friday':
                day = 'Jumat'
            elif day == 'Saturday':
                day = 'Sabtu'
            elif day == 'Sunday':
                day = 'Minggu'

        cleaned_ids = []
        for option_id in option_ids:
            try:
                cleaned_ids.append(int(option_id))
            except (TypeError, ValueError):
                continue

        if date:
            conn.execute('DELETE FROM daily_plan WHERE date = ?', (date,))
        elif day:
            conn.execute('DELETE FROM daily_plan WHERE day = ?', (day,))

        for option_id in cleaned_ids:
            conn.execute(
                'INSERT INTO daily_plan (day, date, option_id) VALUES (?, ?, ?)',
                (day or '', date or '', option_id)
            )

        conn.commit()
        query = '''
            SELECT dp.id, dp.day, dp.date, mo.id AS option_id, mo.name, mo.calories, mo.category
            FROM daily_plan dp
            JOIN meal_options mo ON mo.id = dp.option_id
            WHERE dp.date = ? OR dp.day = ?
            ORDER BY mo.name
        '''
        plan_rows = conn.execute(query, (date or '', day or '')).fetchall() if date else conn.execute('''
            SELECT dp.id, dp.day, dp.date, mo.id AS option_id, mo.name, mo.calories, mo.category
            FROM daily_plan dp
            JOIN meal_options mo ON mo.id = dp.option_id
            WHERE dp.day = ?
            ORDER BY mo.name
        ''', (day,)).fetchall()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Jadwal harian berhasil disimpan!', 'items': [dict(row) for row in plan_rows]}), 201

    if request.method == 'DELETE':
        data = request.get_json(silent=True) or {}
        day = (data.get('day') or '').strip()
        date = normalize_date(data.get('date'))
        if not day and not date:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Hari atau tanggal wajib dipilih!'}), 400

        if date:
            conn.execute('DELETE FROM daily_plan WHERE date = ?', (date,))
        else:
            conn.execute('DELETE FROM daily_plan WHERE day = ?', (day,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': f'Jadwal {date or day} berhasil dihapus!'})

    date = normalize_date(request.args.get('date', '').strip())
    day = request.args.get('day', '').strip()

    if date:
        plan_rows = conn.execute('''
            SELECT dp.id, dp.day, dp.date, mo.id AS option_id, mo.name, mo.calories, mo.category
            FROM daily_plan dp
            JOIN meal_options mo ON mo.id = dp.option_id
            WHERE dp.date = ?
            ORDER BY mo.name
        ''', (date,)).fetchall()
    elif day:
        plan_rows = conn.execute('''
            SELECT dp.id, dp.day, dp.date, mo.id AS option_id, mo.name, mo.calories, mo.category
            FROM daily_plan dp
            JOIN meal_options mo ON mo.id = dp.option_id
            WHERE dp.day = ?
            ORDER BY mo.name
        ''', (day,)).fetchall()
    else:
        plan_rows = conn.execute('''
            SELECT dp.id, dp.day, dp.date, mo.id AS option_id, mo.name, mo.calories, mo.category
            FROM daily_plan dp
            JOIN meal_options mo ON mo.id = dp.option_id
            ORDER BY dp.date DESC, dp.day, mo.name
        ''').fetchall()

    conn.close()
    return jsonify([dict(row) for row in plan_rows])


@app.route('/api/history')
def get_history():
    conn = get_db_connection()
    limit_value = request.args.get('limit', '10', type=int)
    history_rows = conn.execute('''
        SELECT
            dp.date,
            dp.day,
            GROUP_CONCAT(mo.name, ' | ') AS menu_names,
            SUM(mo.calories) AS total_calories,
            COUNT(mo.id) AS item_count
        FROM daily_plan dp
        JOIN meal_options mo ON mo.id = dp.option_id
        WHERE dp.date != ''
        GROUP BY dp.date, dp.day
        ORDER BY dp.date DESC, dp.day
        LIMIT ?
    ''', (limit_value,)).fetchall()
    conn.close()
    return jsonify([
        {
            'date': row['date'],
            'day': row['day'],
            'menu_names': row['menu_names'],
            'total_calories': int(row['total_calories'] or 0),
            'item_count': int(row['item_count'] or 0)
        }
        for row in history_rows
    ])


@app.route('/api/food-reference')
def get_food_reference():
    conn = get_db_connection()
    query = (request.args.get('query') or '').strip()

    if query:
        rows = conn.execute('''
            SELECT id, name, calories, category, portion
            FROM food_reference
            WHERE LOWER(name) LIKE ? OR LOWER(category) LIKE ?
            ORDER BY CASE
                WHEN LOWER(name) LIKE ? THEN 0
                ELSE 1
            END, name
            LIMIT 10
        ''', (f'%{query.lower()}%', f'%{query.lower()}%', f'{query.lower()}%')).fetchall()
    else:
        rows = conn.execute('SELECT id, name, calories, category, portion FROM food_reference ORDER BY name LIMIT 10').fetchall()

    conn.close()
    return jsonify([
        {
            'id': row['id'],
            'name': row['name'],
            'calories': row['calories'],
            'category': row['category'],
            'portion': row['portion']
        }
        for row in rows
    ])


@app.route('/api/summary')
def get_summary():
    conn = get_db_connection()
    menu_count = conn.execute('SELECT COUNT(*) AS total FROM meal_options').fetchone()['total']
    daily_totals = []
    weekly_total = 0

    for day in DAYS:
        rows = conn.execute('''
            SELECT SUM(mo.calories) AS total_calories, COUNT(*) AS count
            FROM daily_plan dp
            JOIN meal_options mo ON mo.id = dp.option_id
            WHERE dp.day = ?
        ''', (day,)).fetchone()
        total_calories = rows['total_calories'] or 0
        count = rows['count'] or 0
        daily_totals.append({'day': day, 'total_calories': int(total_calories), 'count': int(count)})
        weekly_total += int(total_calories)

    categories = conn.execute('SELECT category, COUNT(*) AS count FROM meal_options GROUP BY category ORDER BY category').fetchall()
    conn.close()
    return jsonify({
        'menu_count': menu_count,
        'weekly_total': weekly_total,
        'categories': [dict(row) for row in categories],
        'daily_totals': daily_totals
    })


if __name__ == '__main__':
    app.run(debug=True)