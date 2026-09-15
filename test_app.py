import os
import tempfile
import unittest

import app as app_module

fd, db_path = tempfile.mkstemp(suffix='.db')
os.close(fd)
app_module.DATABASE_PATH = db_path
app_module.init_db()


class MealPlannerTests(unittest.TestCase):
    def setUp(self):
        for table_name in ('daily_plan', 'meal_options'):
            conn = app_module.get_db_connection()
            conn.execute(f'DELETE FROM {table_name}')
            conn.commit()
            conn.close()

        self.app = app_module.app.test_client()
        self.app.testing = True

    def test_can_add_menu_option_and_get_daily_plan(self):
        option_payload = {
            "name": "Dada Ayam & Brokoli",
            "calories": 460,
            "category": "Protein"
        }
        create_response = self.app.post('/api/options', json=option_payload)
        self.assertEqual(create_response.status_code, 201)

        plan_response = self.app.post('/api/daily-plan', json={
            "day": "Senin",
            "option_ids": [1]
        })
        self.assertEqual(plan_response.status_code, 201)

        get_response = self.app.get('/api/daily-plan?day=Senin')
        self.assertEqual(get_response.status_code, 200)
        data = get_response.get_json()
        self.assertTrue(len(data) >= 1)
        self.assertEqual(data[0]["day"], "Senin")

    def test_can_store_and_fetch_daily_history_by_date(self):
        option_payload = {
            "name": "Nasi Uduk",
            "calories": 420,
            "category": "Karbohidrat"
        }
        create_response = self.app.post('/api/options', json=option_payload)
        self.assertEqual(create_response.status_code, 201)

        plan_response = self.app.post('/api/daily-plan', json={
            "day": "Selasa",
            "date": "2026-09-15",
            "option_ids": [1]
        })
        self.assertEqual(plan_response.status_code, 201)

        history_response = self.app.get('/api/history?limit=10')
        self.assertEqual(history_response.status_code, 200)
        history_data = history_response.get_json()
        self.assertTrue(any(item.get('date') == '2026-09-15' for item in history_data))

    def test_can_search_food_calorie_reference(self):
        response = self.app.get('/api/food-reference?query=ayam')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(len(data) >= 1)
        self.assertTrue(any(item.get('name', '').lower().find('ayam') >= 0 for item in data))


if __name__ == '__main__':
    unittest.main()
