import unittest

import app as app_module


class MealPlannerTests(unittest.TestCase):
    def setUp(self):
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


if __name__ == '__main__':
    unittest.main()
