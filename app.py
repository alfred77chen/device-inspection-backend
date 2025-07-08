import os
import jwt
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = Flask(__name__)
CORS(app, supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# 配置
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL').replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 定义模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    full_name = db.Column(db.String(120))
    role = db.Column(db.String(50))
    is_admin = db.Column(db.Boolean, default=False)
    device_id = db.Column(db.String(36))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    client = db.Column(db.String(255))
    contact_person = db.Column(db.String(255))
    contact_phone = db.Column(db.String(50))
    start_date = db.Column(db.DateTime)
    frequency = db.Column(db.String(50))
    next_inspection = db.Column(db.DateTime)
    last_inspection = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(100))
    model = db.Column(db.String(100))
    serial = db.Column(db.String(100))
    location = db.Column(db.Text)
    service_content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Engineer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(50))
    position = db.Column(db.String(50), default='工程师')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Inspection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='inProgress')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Repair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'))
    engineer_id = db.Column(db.Integer, db.ForeignKey('engineer.id'))
    title = db.Column(db.String(255))
    description = db.Column(db.Text)
    priority = db.Column(db.String(50))
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# 初始化数据库
def initialize_database():
    with app.app_context():
        db.create_all()
        if not User.query.first():
            admin = User(
                username="admin",
                password="ht886631",
                full_name="系统管理员",
                role="admin",
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("创建默认用户: admin/ht886631")

initialize_database()

# JWT辅助函数
def generate_token(user_id):
    return jwt.encode({
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }, app.config['SECRET_KEY'])

def verify_token(token):
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        return User.query.get(payload['user_id'])
    except:
        return None

# 用户认证
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    
    if user and user.password == data['password']:
        # 更新设备ID
        if 'device_id' in data:
            user.device_id = data['device_id']
            db.session.commit()
        
        token = generate_token(user.id)
        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'full_name': user.full_name,
                'role': user.role,
                'is_admin': user.is_admin,
                'avatar': user.full_name[0] if user.full_name else 'U'
            }
        })
    return jsonify({'success': False, 'message': '用户名或密码错误'}), 401

# 用户管理
@app.route('/api/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'full_name': u.full_name,
        'role': u.role,
        'is_admin': u.is_admin
    } for u in users])

@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.get_json()
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'success': False, 'message': '用户名已存在'}), 400
    
    new_user = User(
        username=data['username'],
        password=data['password'],
        full_name=data['full_name'],
        role=data['role'],
        is_admin=data.get('is_admin', False)
    )
    db.session.add(new_user)
    db.session.commit()
    
    # 广播用户更新
    socketio.emit('user_update', {
        'type': 'created',
        'user_id': new_user.id,
        'username': new_user.username
    })
    
    return jsonify({'success': True, 'user_id': new_user.id})

# 项目管理
@app.route('/api/projects', methods=['GET'])
def get_projects():
    projects = Project.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'client': p.client,
        'status': p.status,
        'next_inspection': p.next_inspection.isoformat() if p.next_inspection else None,
        'last_inspection': p.last_inspection.isoformat() if p.last_inspection else None
    } for p in projects])

@app.route('/api/projects', methods=['POST'])
def create_project():
    data = request.get_json()
    if Project.query.filter_by(name=data['name']).first():
        return jsonify({'success': False, 'message': '项目名称已存在'}), 400
    
    # 处理日期
    start_date = datetime.fromisoformat(data['start_date']) if 'start_date' in data else datetime.utcnow()
    next_inspection = datetime.fromisoformat(data['next_inspection']) if 'next_inspection' in data else None
    
    new_project = Project(
        name=data['name'],
        client=data['client'],
        contact_person=data.get('contact_person', ''),
        contact_phone=data.get('contact_phone', ''),
        start_date=start_date,
        frequency=data.get('frequency', 'monthly'),
        next_inspection=next_inspection,
        status='active'
    )
    db.session.add(new_project)
    db.session.commit()
    
    # 添加设备
    for device in data.get('devices', []):
        new_device = Device(
            project_id=new_project.id,
            name=device['name'],
            type=device['type'],
            model=device.get('model'),
            serial=device.get('serial'),
            location=device.get('location'),
            service_content=device.get('service_content')
        )
        db.session.add(new_device)
    
    # 添加工程师
    for engineer in data.get('engineers', []):
        new_engineer = Engineer(
            project_id=new_project.id,
            name=engineer['name'],
            phone=engineer['phone'],
            position=engineer.get('position', '工程师')
        )
        db.session.add(new_engineer)
    
    db.session.commit()
    
    # 广播项目创建
    socketio.emit('project_update', {
        'type': 'created',
        'project_id': new_project.id,
        'name': new_project.name
    })
    
    return jsonify({'success': True, 'project_id': new_project.id})

# 设备管理
@app.route('/api/devices', methods=['GET'])
def get_devices():
    project_id = request.args.get('project_id')
    devices = Device.query.filter_by(project_id=project_id).all()
    return jsonify([{
        'id': d.id,
        'name': d.name,
        'type': d.type,
        'model': d.model,
        'location': d.location
    } for d in devices])

# 工程师管理
@app.route('/api/engineers', methods=['GET'])
def get_engineers():
    project_id = request.args.get('project_id')
    engineers = Engineer.query.filter_by(project_id=project_id).all()
    return jsonify([{
        'id': e.id,
        'name': e.name,
        'phone': e.phone,
        'position': e.position
    } for e in engineers])

# 巡检管理
@app.route('/api/inspections', methods=['POST'])
def create_inspection():
    data = request.get_json()
    new_inspection = Inspection(
        project_id=data['project_id'],
        status='inProgress'
    )
    db.session.add(new_inspection)
    db.session.commit()
    
    # 更新项目最后巡检时间
    project = Project.query.get(data['project_id'])
    project.last_inspection = datetime.utcnow()
    db.session.commit()
    
    # 广播巡检创建
    socketio.emit('inspection_update', {
        'type': 'created',
        'inspection_id': new_inspection.id,
        'project_id': data['project_id']
    })
    
    return jsonify({'success': True, 'inspection_id': new_inspection.id})

# 维修工单
@app.route('/api/repairs', methods=['GET'])
def get_repairs():
    repairs = Repair.query.all()
    return jsonify([{
        'id': r.id,
        'title': r.title,
        'project_id': r.project_id,
        'device_id': r.device_id,
        'priority': r.priority,
        'status': r.status,
        'created_at': r.created_at.isoformat()
    } for r in repairs])

@app.route('/api/repairs', methods=['POST'])
def create_repair():
    data = request.get_json()
    new_repair = Repair(
        project_id=data['project_id'],
        device_id=data['device_id'],
        title=data['title'],
        description=data['description'],
        priority=data['priority'],
        status='pending'
    )
    db.session.add(new_repair)
    db.session.commit()
    
    # 广播维修工单创建
    socketio.emit('repair_update', {
        'type': 'created',
        'repair_id': new_repair.id,
        'project_id': data['project_id']
    })
    
    return jsonify({'success': True, 'repair_id': new_repair.id})

@app.route('/api/repairs/<int:repair_id>', methods=['PUT'])
def update_repair(repair_id):
    data = request.get_json()
    repair = Repair.query.get(repair_id)
    if not repair:
        return jsonify({'success': False, 'message': '维修工单不存在'}), 404
    
    repair.status = data.get('status', repair.status)
    repair.engineer_id = data.get('engineer_id', repair.engineer_id)
    repair.updated_at = datetime.utcnow()
    db.session.commit()
    
    # 广播维修工单更新
    socketio.emit('repair_update', {
        'type': 'updated',
        'repair_id': repair.id,
        'status': repair.status
    })
    
    return jsonify({'success': True})

# WebSocket 实时通信
@socketio.on('connect')
def handle_connect():
    print('客户端已连接:', request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    print('客户端已断开:', request.sid)

# 提供前端文件
FRONTEND_PATH = os.path.join(os.path.dirname(__file__), 'dist')
os.makedirs(FRONTEND_PATH, exist_ok=True)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path != "" and os.path.exists(os.path.join(FRONTEND_PATH, path)):
        return send_from_directory(FRONTEND_PATH, path)
    else:
        return send_from_directory(FRONTEND_PATH, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
