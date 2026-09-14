from flask import Flask, render_template, request, jsonify
import sqlite3

app = Flask(__name__, template_folder='.')

DAYS = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']


def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn


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
            option_id INTEGER NOT NULL,
            FOREIGN KEY(option_id) REFERENCES meal_options(id)
        )
    ''')
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
        option_ids = data.get('option_ids') or []

        if not day:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Hari wajib dipilih!'}), 400

        if not isinstance(option_ids, list):
            conn.close()
            return jsonify({'status': 'error', 'message': 'Pilihan menu harus berupa daftar!'}), 400

        cleaned_ids = []
        for option_id in option_ids:
            try:
                cleaned_ids.append(int(option_id))
            except (TypeError, ValueError):
                continue

        conn.execute('DELETE FROM daily_plan WHERE day = ?', (day,))
        for option_id in cleaned_ids:
            conn.execute('INSERT INTO daily_plan (day, option_id) VALUES (?, ?)', (day, option_id))

        conn.commit()
        plan_rows = conn.execute('''
            SELECT dp.id, dp.day, mo.id AS option_id, mo.name, mo.calories, mo.category
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
        if not day:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Hari wajib dipilih!'}), 400

        conn.execute('DELETE FROM daily_plan WHERE day = ?', (day,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': f'Jadwal {day} berhasil dihapus!'})

    day = request.args.get('day', '').strip()
    if day:
        plan_rows = conn.execute('''
            SELECT dp.id, dp.day, mo.id AS option_id, mo.name, mo.calories, mo.category
            FROM daily_plan dp
            JOIN meal_options mo ON mo.id = dp.option_id
            WHERE dp.day = ?
            ORDER BY mo.name
        ''', (day,)).fetchall()
    else:
        plan_rows = conn.execute('''
            SELECT dp.id, dp.day, mo.id AS option_id, mo.name, mo.calories, mo.category
            FROM daily_plan dp
            JOIN meal_options mo ON mo.id = dp.option_id
            ORDER BY dp.day, mo.name
        ''').fetchall()

    conn.close()
    return jsonify([dict(row) for row in plan_rows])


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