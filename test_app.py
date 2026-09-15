import os
import json
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
            "protein": 38,
            "category": "Protein"
        }
        create_response = self.app.post('/api/options', json=option_payload)
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.get_json()['option']['protein'], 38)

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
        self.assertTrue(any(item.get('total_protein', 0) >= 0 for item in history_data))
        self.assertTrue(any(item.get('details') for item in history_data))
        if history_data:
            parsed_details = json.loads(history_data[0]['details'])
            self.assertIn('action', parsed_details)

        history_id = history_data[0]['id']
        delete_response = self.app.delete(f'/api/history/{history_id}')
        self.assertEqual(delete_response.status_code, 200)
        remaining_history = self.app.get('/api/history?limit=10').get_json()
        self.assertFalse(any(item.get('id') == history_id for item in remaining_history))

        missing_delete = self.app.delete(f'/api/history/{history_id}')
        self.assertEqual(missing_delete.status_code, 404)

    def test_summary_uses_dates_for_daily_totals(self):
        option_payload = {
            "name": "Nasi Uduk",
            "calories": 420,
            "protein": 12,
            "category": "Karbohidrat"
        }
        create_response = self.app.post('/api/options', json=option_payload)
        self.assertEqual(create_response.status_code, 201)

        first_plan = self.app.post('/api/daily-plan', json={
            "day": "Senin",
            "date": "2026-09-14",
            "option_ids": [1]
        })
        self.assertEqual(first_plan.status_code, 201)

        second_plan = self.app.post('/api/daily-plan', json={
            "day": "Selasa",
            "date": "2026-09-15",
            "option_ids": [1]
        })
        self.assertEqual(second_plan.status_code, 201)

        summary_response = self.app.get('/api/summary')
        self.assertEqual(summary_response.status_code, 200)
        daily_totals = summary_response.get_json()['daily_totals']
        self.assertIn('2026-09-14', [item['day'] for item in daily_totals])
        self.assertIn('2026-09-15', [item['day'] for item in daily_totals])

    def test_health_endpoint_works(self):
        response = self.app.get('/api/health')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'ok')
        self.assertIn('service', data)

    def test_can_search_food_calorie_reference(self):
        response = self.app.get('/api/food-reference?query=ayam')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(len(data) >= 1)
        self.assertTrue(any(item.get('name', '').lower().find('ayam') >= 0 for item in data))

    def test_can_filter_food_reference_by_category(self):
        response = self.app.get('/api/food-reference?category=Protein')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(len(data) >= 1)
        self.assertTrue(all(item.get('category') == 'Protein' for item in data))

    def test_food_reference_calculates_calories_and_protein_by_grams(self):
        response = self.app.get('/api/food-reference?query=Dada%20Ayam&grams=250')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['grams'], 250.0)
        self.assertEqual(data[0]['calories_per_100g'], 165.0)
        self.assertEqual(data[0]['protein_per_100g'], 31.0)
        self.assertEqual(data[0]['calories'], 412.5)
        self.assertEqual(data[0]['protein'], 77.5)

    def test_food_reference_rejects_invalid_gram_inputs(self):
        for grams in ('abc', '0', '-10', '100001'):
            response = self.app.get(f'/api/food-reference?query=ayam&grams={grams}')
            self.assertEqual(response.status_code, 400, grams)

    def test_food_reference_supports_fractional_grams(self):
        response = self.app.get('/api/food-reference?query=Dada%20Ayam&grams=12.5')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()[0]
        self.assertEqual(data['calories'], 20.6)
        self.assertEqual(data['protein'], 3.9)

    def test_can_update_daily_plan_for_specific_date(self):
        option_payload = {
            "name": "Nasi Uduk",
            "calories": 420,
            "category": "Karbohidrat"
        }
        create_response = self.app.post('/api/options', json=option_payload)
        self.assertEqual(create_response.status_code, 201)

        first_id = create_response.get_json()['option']['id']

        second_payload = {
            "name": "Telur Rebus",
            "calories": 78,
            "protein": 6,
            "category": "Protein"
        }
        second_response = self.app.post('/api/options', json=second_payload)
        self.assertEqual(second_response.status_code, 201)
        second_id = second_response.get_json()['option']['id']

        initial = self.app.post('/api/daily-plan', json={
            "day": "Rabu",
            "date": "2026-09-16",
            "option_ids": [first_id]
        })
        self.assertEqual(initial.status_code, 201)

        update = self.app.put('/api/daily-plan', json={
            "day": "Rabu",
            "date": "2026-09-16",
            "option_ids": [second_id]
        })
        self.assertEqual(update.status_code, 200)

        get_response = self.app.get('/api/daily-plan?date=2026-09-16')
        self.assertEqual(get_response.status_code, 200)
        data = get_response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['option_id'], second_id)


if __name__ == '__main__':
    unittest.main()
