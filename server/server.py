from flask import Flask, request, jsonify
import pymysql
import hashlib

app = Flask(__name__)

# 数据库连接配置
db_config = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'passwd': '430538',
    'database': 'theundergraduator',
    'charset': 'utf8'
}

def get_db_connection():
    return pymysql.connect(**db_config)

def md5_hash(password):
    """使用MD5算法对密码进行加密"""
    return hashlib.md5(password.encode()).hexdigest()

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    password = data.get('password')
    protectpass = data.get('protectpass')
    retpassword = data.get('retpassword')

    if not name or not password or not protectpass or not retpassword:
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('select count(*) from users where username=%s', name)
    result = cursor.fetchone()
    count = result[0]

    if count > 0:
        return jsonify({'status': 'error', 'message': 'Username already exists'}), 400

    try:
        hashed_password = md5_hash(password)  # 对密码进行MD5加密
        sql = 'INSERT INTO `users` (`username`, `password`, `security_question`, `security_answer`) VALUES (%s, %s, %s, %s)'
        values = (name, hashed_password, protectpass, retpassword)
        cursor.execute(sql, values)
        conn.commit()
        return jsonify({'status': 'success', 'message': 'User registered successfully'}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        sql = 'SELECT password FROM users WHERE username=%s'
        cursor.execute(sql, (username,))
        result = cursor.fetchone()

        if result is None:
            return jsonify({'status': 'error', 'message': 'Username does not exist'}), 400

        stored_password = result[0]
        hashed_password = md5_hash(password)  # 对输入的密码进行MD5加密

        if stored_password != hashed_password:
            return jsonify({'status': 'error', 'message': 'Incorrect password'}), 400

        return jsonify({'status': 'success', 'message': 'Login successful'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    protectpass = data.get('protectpass')

    if not username or not password or not protectpass:
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        sql = 'SELECT security_answer FROM users WHERE username=%s'
        cursor.execute(sql, (username,))
        result = cursor.fetchone()

        if result is None:
            return jsonify({'status': 'error', 'message': 'Username does not exist'}), 400

        stored_protectpass = result[0]

        if stored_protectpass != protectpass:
            return jsonify({'status': 'error', 'message': 'Incorrect security answer'}), 400

        hashed_password = md5_hash(password)  # 对新密码进行MD5加密
        sql_update_password = 'UPDATE users SET password=%s WHERE username=%s'
        cursor.execute(sql_update_password, (hashed_password, username))
        conn.commit()

        return jsonify({'status': 'success', 'message': 'Password reset successful'}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)