import os
import csv
import io
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'bigdata_sariaya_secret_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Models ---
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'admin' or 'editor'

class Device(db.Model):
    __tablename__ = 'devices'
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(100), unique=True, nullable=False)
    serial_number = db.Column(db.String(100), unique=True, nullable=False)
    sim_number = db.Column(db.String(100), nullable=True, default='N/A')
    network = db.Column(db.String(20), nullable=True, default='N/A')
    status = db.Column(db.String(20), nullable=False, default='ONHAND')
    store_code_name = db.Column(db.String(200), nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    date_deployed = db.Column(db.Date, nullable=True)
    pullout_date = db.Column(db.Date, nullable=True)
    remarks = db.Column(db.String(50), nullable=True)
    person_in_charge = db.Column(db.String(100), nullable=True)

    @property
    def duration_days(self):
        if self.date_deployed:
            end_date = self.pullout_date if (self.status == 'ONHAND' and self.pullout_date) else datetime.now().date()
            return (end_date - self.date_deployed).days
        return 0

class DeviceHistory(db.Model):
    __tablename__ = 'device_history'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    store_code_name = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Database Initialization ---
def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            hashed_pw = generate_password_hash('admin123', method='pbkdf2:sha256')
            admin_user = User(username='admin', password=hashed_pw, role='admin')
            db.session.add(admin_user)
            db.session.commit()

# --- Routes ---



@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        new_username = request.form.get('username').strip()
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')

        # 1. Verify current password
        if not check_password_hash(current_user.password, current_password):
            flash('Incorrect current password.', 'danger')
            return redirect(url_for('profile'))

        # 2. Update username (if changed and not already taken)
        if new_username != current_user.username:
            existing_user = User.query.filter_by(username=new_username).first()
            if existing_user:
                flash('Username is already taken. Please choose another.', 'warning')
                return redirect(url_for('profile'))
            current_user.username = new_username

        # 3. Update password (if a new one was provided)
        if new_password:
            current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')

        db.session.commit()
        flash('Account credentials updated successfully!', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html')






@app.route('/')
@login_required
def dashboard():
    devices = Device.query.all()
    
    # Analytics Calculation
    total_devices = len(devices)
    status_counts = {'ONHAND': 0, 'DEPLOYED': 0, 'TRANSFER': 0, 'MISSING': 0}
    network_counts = {'SMART': 0, 'DITO': 0, 'GLOBE': 0}
    
    for dev in devices:
        if dev.status in status_counts:
            status_counts[dev.status] += 1
        if dev.network in network_counts:
            network_counts[dev.network] += 1

    return render_template('dashboard.html', 
                           total=total_devices, 
                           status_counts=status_counts, 
                           network_counts=network_counts)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/inventory')
@login_required
def inventory():
    devices = Device.query.all()
    
    # Status Counts for the summary cards
    counts = {
        'DEPLOYED': Device.query.filter_by(status='DEPLOYED').count(),
        'ONHAND': Device.query.filter_by(status='ONHAND').count(),
        'TRANSFER': Device.query.filter_by(status='TRANSFER').count(),
        'MISSING': Device.query.filter_by(status='MISSING').count(),
        'TOTAL': len(devices)
    }
    
    return render_template('inventory.html', devices=devices, counts=counts)

@app.route('/device/add', methods=['GET', 'POST'])
@login_required
def add_device():
    if current_user.role != 'admin':
        flash('Access Denied: Only Admins can encode new devices.', 'danger')
        return redirect(url_for('inventory'))
    
    if request.method == 'POST':
        date_dep = datetime.strptime(request.form['date_deployed'], '%Y-%m-%d').date() if request.form['date_deployed'] else None
        
        device = Device(
            account_number=request.form['account_number'],
            serial_number=request.form['serial_number'],
            sim_number=request.form['sim_number'],
            network=request.form['network'],
            status=request.form['status'],
            store_code_name=request.form['store_code_name'],
            latitude=float(request.form['latitude']) if request.form['latitude'] else None,
            longitude=float(request.form['longitude']) if request.form['longitude'] else None,
            date_deployed=date_dep,
            remarks=request.form['remarks'],
            person_in_charge=request.form['person_in_charge']
        )
        db.session.add(device)
        db.session.commit()

        # Log history if deployed
        if device.latitude and device.longitude and device.store_code_name:
            history = DeviceHistory(device_id=device.id, latitude=device.latitude, longitude=device.longitude, store_code_name=device.store_code_name)
            db.session.add(history)
            db.session.commit()

        flash('Device added successfully!', 'success')
        return redirect(url_for('inventory'))
    
    return render_template('edit_device.html', device=None)

@app.route('/device/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_device(id):
    device = Device.query.get_or_404(id)
    if request.method == 'POST':
        new_status = request.form['status']
        
        # Handle Pullout Check
        if device.status == 'DEPLOYED' and new_status == 'ONHAND':
            pullout_str = request.form.get('pullout_date')
            if not pullout_str:
                flash('Pullout Date is required when changing status from DEPLOYED to ONHAND.', 'warning')
                return render_template('edit_device.html', device=device, require_pullout=True)
            device.pullout_date = datetime.strptime(pullout_str, '%Y-%m-%d').date()

        # Update Editable Fields
        device.status = new_status
        device.store_code_name = request.form['store_code_name']
        device.latitude = float(request.form['latitude']) if request.form['latitude'] else None
        device.longitude = float(request.form['longitude']) if request.form['longitude'] else None
        device.date_deployed = datetime.strptime(request.form['date_deployed'], '%Y-%m-%d').date() if request.form['date_deployed'] else None
        device.remarks = request.form['remarks']
        device.person_in_charge = request.form['person_in_charge']

        # ADMIN ONLY FIELDS
        if current_user.role == 'admin':
            device.account_number = request.form['account_number']
            device.serial_number = request.form['serial_number']
            device.sim_number = request.form['sim_number']
            device.network = request.form['network']

        # Track history update if deployed
        if device.status == 'DEPLOYED' and device.latitude and device.longitude:
            last_hist = DeviceHistory.query.filter_by(device_id=device.id).order_by(DeviceHistory.timestamp.desc()).first()
            if not last_hist or (last_hist.latitude != device.latitude or last_hist.longitude != device.longitude):
                new_hist = DeviceHistory(device_id=device.id, latitude=device.latitude, longitude=device.longitude, store_code_name=device.store_code_name)
                db.session.add(new_hist)

        db.session.commit()
        flash('Device info updated successfully!', 'success')
        return redirect(url_for('inventory'))

    return render_template('edit_device.html', device=device)

@app.route('/device/delete/<int:id>')
@login_required
def delete_device(id):
    if current_user.role != 'admin':
        flash('Access Denied: Only Admins can delete entries.', 'danger')
        return redirect(url_for('inventory'))
    device = Device.query.get_or_404(id)
    db.session.delete(device)
    db.session.commit()
    flash('Device deleted successfully.', 'info')
    return redirect(url_for('inventory'))

@app.route('/users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if current_user.role != 'admin':
        flash('Access Denied: Admin Panel access required.', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'warning')
        else:
            hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
            new_user = User(username=username, password=hashed_pw, role=role)
            db.session.add(new_user)
            db.session.commit()
            flash('New user account created!', 'success')
            
    users = User.query.all()
    return render_template('users.html', users=users)

@app.route('/api/history/<string:serial_number>')
@login_required
def get_device_history(serial_number):
    device = Device.query.filter_by(serial_number=serial_number).first_or_404()
    history = DeviceHistory.query.filter_by(device_id=device.id).order_by(DeviceHistory.timestamp.desc()).limit(3).all()
    
    events = [{
        'store': h.store_code_name,
        'lat': h.latitude,
        'lng': h.longitude,
        'timestamp': h.timestamp.strftime('%Y-%m-%d %H:%M')
    } for h in history]
    
    return jsonify({'serial': device.serial_number, 'history': events})

@app.route('/history_map/<string:serial_number>')
@login_required
def history_map(serial_number):
    return render_template('history.html', serial_number=serial_number)

@app.route('/export/csv')
@login_required
def export_csv():
    if current_user.role != 'admin':
        flash('Access Denied.', 'danger')
        return redirect(url_for('inventory'))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Account No', 'Serial No', 'SIM No', 'Network', 'Status', 'Store Name', 'Lat', 'Long', 'Date Deployed', 'Pullout Date', 'Remarks', 'Duration (Days)', 'Person in Charge'])
    
    devices = Device.query.all()
    for d in devices:
        writer.writerow([
            d.account_number, d.serial_number, d.sim_number, d.network, d.status,
            d.store_code_name, d.latitude, d.longitude, d.date_deployed, d.pullout_date,
            d.remarks, d.duration_days, d.person_in_charge
        ])
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=bigdata_dc_sariaya_inventory.csv"}
    )

@app.route('/import/csv', methods=['POST'])
@login_required
def import_csv():
    if current_user.role != 'admin':
        flash('Access Denied.', 'danger')
        return redirect(url_for('inventory'))

    file = request.files.get('csv_file')
    if not file or not file.filename.endswith('.csv'):
        flash('Please upload a valid CSV file.', 'warning')
        return redirect(url_for('inventory'))

    try:
        stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        imported_count = 0
        skipped_count = 0
        errors = []

        def get_field_val(row_dict, possible_headers):
            clean_dict = {
                ''.join(e for e in str(k).lower() if e.isalnum()): str(v).strip() 
                for k, v in row_dict.items() if k
            }
            for candidate in possible_headers:
                clean_candidate = ''.join(e for e in candidate.lower() if e.isalnum())
                if clean_candidate in clean_dict:
                    val = clean_dict[clean_candidate]
                    return val if val.lower() != 'nan' else None
            return None

        for row_num, row in enumerate(csv_reader, start=2):
            try:
                # Required identifiers
                account_no = get_field_val(row, ['Account Number', 'Account No', 'ACCOUNT NUMBER'])
                serial_no = get_field_val(row, ['Serial Number', 'Serial No', 'SERIAL NUMBER'])
                
                # Optional fields with fallback defaults for missing entries
                sim_no = get_field_val(row, ['SIM Number', 'SIM No', 'SIM NUMBER']) or 'N/A'
                network = get_field_val(row, ['Network', 'NETWORK']) or 'N/A'
                status = get_field_val(row, ['Status', 'STATUS']) or 'MISSING'

                store_name = get_field_val(row, ['LOCATION / STORE CODE', 'Store Code/Name', 'Store Name', 'Store'])
                date_dep_str = get_field_val(row, ['Date Deployed', 'DATE DEPLOYED'])
                remarks = get_field_val(row, ['Remarks', 'REMARKS'])
                person_in_charge = get_field_val(row, ['Person in Charge', 'PERSON IN CHARGE'])

                # Parse coordinates safely
                lat, lng = None, None
                combined_coords = get_field_val(row, ['lat,long', 'lat/long', 'coordinates'])
                
                if combined_coords and ',' in combined_coords:
                    parts = combined_coords.split(',')
                    try:
                        lat = float(parts[0].strip())
                        lng = float(parts[1].strip())
                    except ValueError:
                        pass
                else:
                    lat_str = get_field_val(row, ['Lat', 'Latitude', 'LATITUDE'])
                    lng_str = get_field_val(row, ['Long', 'Longitude', 'LONGITUDE'])
                    lat = float(lat_str) if lat_str else None
                    lng = float(lng_str) if lng_str else None

                # Only require Account Number & Serial Number
                if not account_no or not serial_no:
                    missing = []
                    if not account_no: missing.append("ACCOUNT NUMBER")
                    if not serial_no: missing.append("SERIAL NUMBER")
                    errors.append(f"Row {row_num}: Missing required identifier ({', '.join(missing)})")
                    skipped_count += 1
                    continue

                network = network.upper()
                status = status.upper()

                # Parse dates flexibly
                date_dep = None
                if date_dep_str:
                    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y', '%Y/%m/%d'):
                        try:
                            date_dep = datetime.strptime(date_dep_str, fmt).date()
                            break
                        except ValueError:
                            pass

                # Avoid duplicate entry errors
                existing = Device.query.filter(
                    (Device.account_number == account_no) | (Device.serial_number == serial_no)
                ).first()

                if existing:
                    errors.append(f"Row {row_num}: Duplicate Account '{account_no}' or Serial '{serial_no}'.")
                    skipped_count += 1
                    continue

                dev = Device(
                    account_number=account_no,
                    serial_number=serial_no,
                    sim_number=sim_no,
                    network=network,
                    status=status,
                    store_code_name=store_name,
                    latitude=lat,
                    longitude=lng,
                    date_deployed=date_dep,
                    remarks=remarks,
                    person_in_charge=person_in_charge
                )
                db.session.add(dev)
                imported_count += 1

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                skipped_count += 1

        db.session.commit()

        if imported_count > 0:
            flash(f'Successfully imported {imported_count} device(s)!', 'success')
        if skipped_count > 0:
            error_msg = f'Skipped {skipped_count} row(s): ' + ' | '.join(errors[:5])
            flash(error_msg, 'warning')

    except Exception as e:
        flash(f'Error reading CSV file: {str(e)}', 'danger')

    return redirect(url_for('inventory'))

if __name__ == '__main__':
    init_db()
    # 0.0.0.0 binds to all available network adapters
    app.run(host='0.0.0.0', port=5050, debug=True)