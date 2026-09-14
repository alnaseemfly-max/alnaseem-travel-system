import os
import tempfile
from werkzeug.security import generate_password_hash

os.environ['SECRET_KEY'] = 'test-secret'
import app

app.DB = os.path.join(tempfile.mkdtemp(), 'test.db')
app.init_db()
client = app.app.test_client()
checks = []
checks.append(('login page', client.get('/login').status_code == 200))
checks.append(('protected redirect', client.get('/').status_code in (301, 302)))
with app.db() as conn:
    conn.execute('INSERT INTO users(username,password_hash) VALUES (?,?)', ('admin', generate_password_hash('StrongPass123!', method='scrypt')))
    conn.commit()
r = client.post('/login', data={'username': 'admin', 'password': 'StrongPass123!'}, follow_redirects=True)
checks.append(('login success', r.status_code == 200 and 'لوحة التحكم' in r.get_data(as_text=True)))
r = client.get('/change-password')
checks.append(('password page', r.status_code == 200 and 'تغيير كلمة المرور' in r.get_data(as_text=True)))
r = client.post('/change-password', data={'old_password': 'StrongPass123!', 'new_password': 'NewStrong456!', 'confirm_password': 'NewStrong456!'}, follow_redirects=True)
checks.append(('password change', r.status_code == 200 and 'لوحة التحكم' in r.get_data(as_text=True)))
for name, ok in checks:
    print(f'{name}: {"PASS" if ok else "FAIL"}')
assert all(ok for _, ok in checks)
