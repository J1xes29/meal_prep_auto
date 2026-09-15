import os
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Flask, render_template, request, jsonify
import json
import sqlite3

app = Flask(__name__, template_folder='.')
app.config['JSON_SORT_KEYS'] = False

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


def normalize_day_name(day_value):
    day = (day_value or '').strip()
    if not day:
        return ''

    mapping = {
        'Monday': 'Senin',
        'Tuesday': 'Selasa',
        'Wednesday': 'Rabu',
        'Thursday': 'Kamis',
        'Friday': 'Jumat',
        'Saturday': 'Sabtu',
        'Sunday': 'Minggu',
        'Senin': 'Senin',
        'Selasa': 'Selasa',
        'Rabu': 'Rabu',
        'Kamis': 'Kamis',
        'Jumat': 'Jumat',
        'Sabtu': 'Sabtu',
        'Minggu': 'Minggu'
    }
    return mapping.get(day, day)


def get_plan_snapshot(conn, date_value='', day_value=''):
    date_value = normalize_date(date_value)
    normalized_day = normalize_day_name(day_value)
    query = '''
        SELECT mo.name, mo.calories, mo.protein
        FROM daily_plan dp
        JOIN meal_options mo ON mo.id = dp.option_id
        WHERE 1 = 1
    '''
    params = []

    if date_value:
        query += ' AND dp.date = ? '
        params.append(date_value)
    elif normalized_day:
        query += ' AND dp.day = ? '
        params.append(normalized_day)
    else:
        return {'menu_names': '', 'total_calories': 0, 'total_protein': 0, 'item_count': 0}

    rows = conn.execute(query, tuple(params)).fetchall()
    menu_names = ' | '.join(row['name'] for row in rows)
    total_calories = sum(int(row['calories'] or 0) for row in rows)
    total_protein = sum(int(row['protein'] or 0) for row in rows)
    return {
        'menu_names': menu_names,
        'total_calories': total_calories,
        'total_protein': total_protein,
        'item_count': len(rows)
    }


def record_plan_history(conn, action, date_value='', day_value='', option_ids=None):
    normalized_date = normalize_date(date_value)
    normalized_day = normalize_day_name(day_value)
    if normalized_date and not normalized_day:
        normalized_day = normalize_day_name(day_from_date(normalized_date))
    if not normalized_date and not normalized_day:
        return

    snapshot = get_plan_snapshot(conn, normalized_date, normalized_day)
    created_at = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    details = {
        'action': action,
        'option_ids': list(option_ids or []),
        'item_count': snapshot['item_count'],
        'menu_names': snapshot['menu_names']
    }
    details_json = json.dumps(details, ensure_ascii=False)
    conn.execute('''
        INSERT INTO plan_history (date, day, action, menu_names, total_calories, total_protein, item_count, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        normalized_date,
        normalized_day,
        action,
        snapshot['menu_names'],
        snapshot['total_calories'],
        snapshot['total_protein'],
        snapshot['item_count'],
        details_json,
        created_at
    ))


def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS meal_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            calories INTEGER NOT NULL,
            protein INTEGER NOT NULL DEFAULT 0,
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
            protein INTEGER NOT NULL DEFAULT 0,
            category TEXT NOT NULL DEFAULT 'Umum',
            portion TEXT NOT NULL DEFAULT '1 porsi'
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS plan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT DEFAULT '',
            day TEXT DEFAULT '',
            action TEXT NOT NULL,
            menu_names TEXT DEFAULT '',
            total_calories INTEGER DEFAULT 0,
            total_protein INTEGER DEFAULT 0,
            item_count INTEGER DEFAULT 0,
            details TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    columns = [row['name'] for row in conn.execute('PRAGMA table_info(daily_plan)').fetchall()]
    if 'date' not in columns:
        conn.execute('ALTER TABLE daily_plan ADD COLUMN date TEXT DEFAULT ""')

    meal_columns = [row['name'] for row in conn.execute('PRAGMA table_info(meal_options)').fetchall()]
    if 'protein' not in meal_columns:
        conn.execute('ALTER TABLE meal_options ADD COLUMN protein INTEGER NOT NULL DEFAULT 0')

    food_columns = [row['name'] for row in conn.execute('PRAGMA table_info(food_reference)').fetchall()]
    if 'protein' not in food_columns:
        conn.execute('ALTER TABLE food_reference ADD COLUMN protein INTEGER NOT NULL DEFAULT 0')
    if 'calories_per_100g' not in food_columns:
        conn.execute('ALTER TABLE food_reference ADD COLUMN calories_per_100g REAL NOT NULL DEFAULT 0')
    if 'protein_per_100g' not in food_columns:
        conn.execute('ALTER TABLE food_reference ADD COLUMN protein_per_100g REAL NOT NULL DEFAULT 0')

    conn.execute('''
        UPDATE food_reference
        SET calories_per_100g = calories
        WHERE calories_per_100g = 0 AND calories > 0
    ''')
    conn.execute('''
        UPDATE food_reference
        SET protein_per_100g = protein
        WHERE protein_per_100g = 0 AND protein > 0
    ''')
    conn.execute("UPDATE food_reference SET portion = '100 g' WHERE portion != '100 g'")

    existing = conn.execute('SELECT COUNT(*) AS total FROM food_reference').fetchone()['total']
    if existing == 0:
        sample_foods = [
            ('Ayam Goreng', 250, 30, 250, 30, 'Protein', '100 g'),
            ('Ayam Bakar', 220, 28, 220, 28, 'Protein', '100 g'),
            ('Dada Ayam', 165, 31, 165, 31, 'Protein', '100 g'),
            ('Nasi Putih', 200, 4, 200, 4, 'Karbohidrat', '100 g'),
            ('Nasi Uduk', 420, 12, 420, 12, 'Karbohidrat', '100 g'),
            ('Kentang Rebus', 130, 3, 130, 3, 'Karbohidrat', '100 g'),
            ('Tempe Goreng', 190, 18, 190, 18, 'Protein', '100 g'),
            ('Tahu', 80, 8, 80, 8, 'Protein', '100 g'),
            ('Sayur Bayam', 40, 3, 40, 3, 'Sayur', '100 g'),
            ('Brokoli Rebus', 55, 4, 55, 4, 'Sayur', '100 g'),
            ('Alpukat', 160, 2, 160, 2, 'Sayur', '100 g'),
            ('Buah Pisang', 105, 1, 105, 1, 'Buah', '100 g'),
            ('Apel', 95, 0, 95, 0, 'Buah', '100 g'),
            ('Telur Rebus', 78, 6, 78, 6, 'Protein', '100 g'),
            ('Telur Orak-Arik', 120, 8, 120, 8, 'Protein', '100 g'),
            ('Minyak Goreng', 120, 0, 120, 0, 'Lainnya', '100 g'),
            ('Mie Goreng', 330, 10, 330, 10, 'Karbohidrat', '100 g'),
            ('Oatmeal', 150, 5, 150, 5, 'Karbohidrat', '100 g'),
            ('Greek Yogurt', 130, 17, 130, 17, 'Protein', '100 g'),
            ('Smoothie Pisang', 220, 4, 220, 4, 'Minuman', '100 g'),
        ]
        conn.executemany(
            '''INSERT INTO food_reference
               (name, calories, protein, calories_per_100g, protein_per_100g, category, portion)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            sample_foods
        )

    conn.commit()
    conn.close()


init_db()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/health')
def health_check():
    conn = get_db_connection()
    try:
        db_status = conn.execute('SELECT 1').fetchone()
    finally:
        conn.close()

    return jsonify({
        'status': 'ok',
        'service': 'meal-prep-auto',
        'database': 'connected' if db_status else 'unreachable',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })


@app.route('/api/options', methods=['GET', 'POST'])
def manage_options():
    conn = get_db_connection()

    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        category = (data.get('category') or 'Umum').strip() or 'Umum'
        calories = data.get('calories')
        protein = data.get('protein', 0)

        if not name or calories is None:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Nama menu dan kalori wajib diisi!'}), 400

        try:
            calories = int(calories)
            protein = int(protein)
        except (TypeError, ValueError):
            conn.close()
            return jsonify({'status': 'error', 'message': 'Kalori dan protein harus berupa angka!'}), 400

        existing = conn.execute(
            'SELECT id FROM meal_options WHERE LOWER(name) = LOWER(?)',
            (name,)
        ).fetchone()
        if existing:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Menu dengan nama yang sama sudah ada.'}), 409

        cursor = conn.execute(
            'INSERT INTO meal_options (name, calories, protein, category) VALUES (?, ?, ?, ?)',
            (name, calories, protein, category)
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


@app.route('/api/daily-plan', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_daily_plan():
    conn = get_db_connection()

    def save_plan(day_value, date_value, option_ids):
        normalized_day = normalize_day_name(day_value)
        normalized_date = normalize_date(date_value)

        if normalized_date and not normalized_day:
            normalized_day = normalize_day_name(day_from_date(normalized_date))
        elif not normalized_date and not normalized_day:
            raise ValueError('Hari atau tanggal wajib dipilih!')

        if not isinstance(option_ids, list):
            raise ValueError('Pilihan menu harus berupa daftar!')

        cleaned_ids = []
        for option_id in option_ids:
            try:
                cleaned_ids.append(int(option_id))
            except (TypeError, ValueError):
                continue

        if normalized_date:
            conn.execute('DELETE FROM daily_plan WHERE date = ?', (normalized_date,))
        elif normalized_day:
            conn.execute('DELETE FROM daily_plan WHERE day = ?', (normalized_day,))

        for option_id in cleaned_ids:
            conn.execute(
                'INSERT INTO daily_plan (day, date, option_id) VALUES (?, ?, ?)',
                (normalized_day or '', normalized_date or '', option_id)
            )

        if normalized_date:
            query = '''
                SELECT dp.id, dp.day, dp.date, mo.id AS option_id, mo.name, mo.calories, mo.category
                FROM daily_plan dp
                JOIN meal_options mo ON mo.id = dp.option_id
                WHERE dp.date = ?
                ORDER BY mo.name
            '''
            rows = conn.execute(query, (normalized_date,)).fetchall()
            record_plan_history(conn, 'updated', normalized_date, normalized_day, cleaned_ids)
            return rows

        rows = conn.execute('''
            SELECT dp.id, dp.day, dp.date, mo.id AS option_id, mo.name, mo.calories, mo.category
            FROM daily_plan dp
            JOIN meal_options mo ON mo.id = dp.option_id
            WHERE dp.day = ?
            ORDER BY mo.name
        ''', (normalized_day,)).fetchall()
        record_plan_history(conn, 'updated', normalized_date, normalized_day, cleaned_ids)
        return rows

    if request.method in ('POST', 'PUT'):
        data = request.get_json(silent=True) or {}
        day = (data.get('day') or '').strip()
        date = normalize_date(data.get('date'))
        option_ids = data.get('option_ids') or []

        try:
            plan_rows = save_plan(day, date, option_ids)
            conn.commit()
            conn.close()
            return jsonify({'status': 'success', 'message': 'Jadwal harian berhasil disimpan!', 'items': [dict(row) for row in plan_rows]}), (201 if request.method == 'POST' else 200)
        except ValueError as exc:
            conn.close()
            return jsonify({'status': 'error', 'message': str(exc)}), 400

    if request.method == 'DELETE':
        data = request.get_json(silent=True) or {}
        day = (data.get('day') or '').strip()
        date = normalize_date(data.get('date'))
        if not date:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Tanggal wajib dipilih!'}), 400

        snapshot = get_plan_snapshot(conn, date, day)
        conn.execute('DELETE FROM daily_plan WHERE date = ?', (date,))
        record_plan_history(conn, 'deleted', date, day, [])
        conn.commit()
        conn.close()
        return jsonify({
            'status': 'success',
            'message': f'Jadwal {date or normalize_day_name(day)} berhasil dihapus!',
            'history': snapshot
        })

    date = normalize_date(request.args.get('date', '').strip())
    day = normalize_day_name(request.args.get('day', '').strip())

    if date:
        plan_rows = conn.execute('''
            SELECT dp.id, dp.day, dp.date, mo.id AS option_id, mo.name, mo.calories, mo.protein, mo.category
            FROM daily_plan dp
            JOIN meal_options mo ON mo.id = dp.option_id
            WHERE dp.date = ?
            ORDER BY mo.name
        ''', (date,)).fetchall()
    elif day:
        plan_rows = conn.execute('''
            SELECT dp.id, dp.day, dp.date, mo.id AS option_id, mo.name, mo.calories, mo.protein, mo.category
            FROM daily_plan dp
            JOIN meal_options mo ON mo.id = dp.option_id
            WHERE dp.day = ?
            ORDER BY mo.name
        ''', (day,)).fetchall()
    else:
        plan_rows = conn.execute('''
            SELECT dp.id, dp.day, dp.date, mo.id AS option_id, mo.name, mo.calories, mo.protein, mo.category
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
            ph.id,
            ph.date,
            ph.day,
            ph.action,
            ph.menu_names,
            ph.total_calories,
            ph.total_protein,
            ph.item_count,
            ph.created_at,
            ph.details
        FROM plan_history ph
        ORDER BY ph.created_at DESC, ph.id DESC
        LIMIT ?
    ''', (limit_value,)).fetchall()
    conn.close()
    return jsonify([
        {
            'id': row['id'],
            'date': row['date'],
            'day': row['day'],
            'action': row['action'],
            'menu_names': row['menu_names'],
            'total_calories': int(row['total_calories'] or 0),
            'total_protein': int(row['total_protein'] or 0),
            'item_count': int(row['item_count'] or 0),
            'created_at': row['created_at'],
            'details': row['details']
        }
        for row in history_rows
    ])


@app.route('/api/history/<int:history_id>', methods=['DELETE'])
def delete_history(history_id):
    conn = get_db_connection()
    cursor = conn.execute('DELETE FROM plan_history WHERE id = ?', (history_id,))
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        return jsonify({'status': 'error', 'message': 'Riwayat tidak ditemukan.'}), 404

    return jsonify({'status': 'success', 'message': 'Riwayat berhasil dihapus.'})


@app.route('/api/food-reference')
def get_food_reference():
    conn = get_db_connection()
    query = (request.args.get('query') or '').strip()
    category = (request.args.get('category') or '').strip()
    grams_raw = request.args.get('grams')
    grams = None

    if grams_raw is not None and str(grams_raw).strip():
        try:
            grams = Decimal(str(grams_raw).strip())
        except InvalidOperation:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Gramasi harus berupa angka.'}), 400
        if not grams.is_finite() or grams <= 0 or grams > 100000:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Gramasi harus lebih dari 0 dan maksimal 100000 gram.'}), 400

    if query or category:
        sql = '''
            SELECT id, name, calories, protein, calories_per_100g, protein_per_100g, category, portion
            FROM food_reference
            WHERE 1 = 1
        '''
        params = []
        if query:
            sql += ' AND (LOWER(name) LIKE ? OR LOWER(category) LIKE ?) '
            params.extend([f'%{query.lower()}%', f'%{query.lower()}%'])
        if category:
            sql += ' AND LOWER(category) = LOWER(?) '
            params.append(category)
        sql += ' ORDER BY CASE WHEN LOWER(name) LIKE ? THEN 0 ELSE 1 END, name LIMIT 10 '
        if query:
            params.append(f'{query.lower()}%')
        else:
            params.append('%')
        rows = conn.execute(sql, tuple(params)).fetchall()
    else:
        rows = conn.execute('''
            SELECT id, name, calories, protein, calories_per_100g, protein_per_100g, category, portion
            FROM food_reference ORDER BY name LIMIT 10
        ''').fetchall()

    conn.close()
    response = []
    for row in rows:
        calories_per_100g = Decimal(str(row['calories_per_100g'] or row['calories'] or 0))
        protein_per_100g = Decimal(str(row['protein_per_100g'] or row['protein'] or 0))
        multiplier = (grams / Decimal('100')) if grams is not None else Decimal('1')
        calculated_calories = (calories_per_100g * multiplier).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
        calculated_protein = (protein_per_100g * multiplier).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
        response.append({
            'id': row['id'],
            'name': row['name'],
            'calories': float(calculated_calories),
            'protein': float(calculated_protein),
            'calories_per_100g': float(calories_per_100g),
            'protein_per_100g': float(protein_per_100g),
            'grams': float(grams) if grams is not None else None,
            'category': row['category'],
            'portion': '100 g'
        })
    return jsonify(response)


@app.route('/api/summary')
def get_summary():
    conn = get_db_connection()
    menu_count = conn.execute('SELECT COUNT(*) AS total FROM meal_options').fetchone()['total']
    date_rows = conn.execute('''
        SELECT dp.date,
               SUM(mo.calories) AS total_calories,
               SUM(mo.protein) AS total_protein,
               COUNT(mo.id) AS count
        FROM daily_plan dp
        JOIN meal_options mo ON mo.id = dp.option_id
        WHERE dp.date != ''
        GROUP BY dp.date
        ORDER BY dp.date ASC
    ''').fetchall()

    if date_rows:
        daily_totals = [
            {
                'day': row['date'],
                'total_calories': int(row['total_calories'] or 0),
                'total_protein': int(row['total_protein'] or 0),
                'count': int(row['count'] or 0)
            }
            for row in date_rows
        ]
    else:
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        daily_totals = []

        for offset in range(7):
            date_value = (week_start + timedelta(days=offset)).strftime('%Y-%m-%d')
            rows = conn.execute('''
                SELECT SUM(mo.calories) AS total_calories, SUM(mo.protein) AS total_protein, COUNT(*) AS count
                FROM daily_plan dp
                JOIN meal_options mo ON mo.id = dp.option_id
                WHERE dp.date = ?
            ''', (date_value,)).fetchone()
            total_calories = rows['total_calories'] or 0
            total_protein = rows['total_protein'] or 0
            count = rows['count'] or 0
            daily_totals.append({
                'day': date_value,
                'total_calories': int(total_calories),
                'total_protein': int(total_protein),
                'count': int(count)
            })

    weekly_total = sum(int(item['total_calories']) for item in daily_totals)
    weekly_protein = sum(int(item['total_protein']) for item in daily_totals)

    categories = conn.execute('SELECT category, COUNT(*) AS count FROM meal_options GROUP BY category ORDER BY category').fetchall()
    conn.close()
    return jsonify({
        'menu_count': menu_count,
        'weekly_total': weekly_total,
        'weekly_protein': weekly_protein,
        'categories': [dict(row) for row in categories],
        'daily_totals': daily_totals
    })


@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/api/'):
        return jsonify({'status': 'error', 'message': 'Endpoint tidak ditemukan.'}), 404
    return error


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)