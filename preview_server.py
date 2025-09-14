#!/usr/bin/env python3
"""
Minimal preview server for testing template customizations
"""
from flask import Flask, render_template, url_for, send_from_directory
import configparser
import datetime
import os
from timezone_utils import convert_to_local, format_timestamp, time_ago

app = Flask(__name__, static_folder='www')

# Load config
config = configparser.ConfigParser()
config.read("config.ini")

# Mock data for preview
mock_data = {
    'active_nodes': [{'id': 1}, {'id': 2}, {'id': 3}],  # 3 fake nodes
    'timestamp': datetime.datetime.now(),
    'auth': False,
    'success_message': None,
    'error_message': None,
    'format_timestamp': format_timestamp,
    'convert_to_local': convert_to_local,
    'time_ago': time_ago,
    'url_for': url_for,
    'current_time': datetime.datetime.now()
}

# Add datetime and current time to Jinja2 globals
app.jinja_env.globals.update(
    datetime=datetime,
    current_time=datetime.datetime.now()
)

@app.route('/')
@app.route('/index.html')
def index():
    return render_template('index.html.j2', 
                         config=config, 
                         this_page='index',
                         **mock_data)

@app.route('/layout_preview')
def layout_preview():
    """Preview the layout with navigation"""
    return render_template('layout.html.j2', 
                         config=config,
                         this_page='preview',
                         **mock_data)

@app.route('/login')
@app.route('/login.html')
def login():
    """Login page preview"""
    return render_template('login.html.j2', 
                         config=config,
                         this_page='login',
                         **mock_data)

@app.route('/register')
@app.route('/register.html')
def register():
    """Mock register route"""
    return "Register page (not implemented in preview)"

@app.route('/forgot-password')
def forgot_password():
    """Mock forgot password route"""
    return "Forgot Password page (not implemented in preview)"

@app.route('/logout')
def logout():
    """Mock logout route"""
    return "Logout page (not implemented in preview)"

@app.route('/mynodes')
def mynodes():
    """Mock mynodes route"""
    return "My Nodes page (not implemented in preview)"

# Static file routes
@app.route('/css/<path:filename>')
def css_files(filename):
    return send_from_directory('www/css', filename)

@app.route('/js/<path:filename>')
def js_files(filename):
    return send_from_directory('www/js', filename)

@app.route('/images/<path:filename>')
def image_files(filename):
    return send_from_directory('www/images', filename)

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html.j2', 
                         config=config,
                         **mock_data), 404

if __name__ == '__main__':
    print("\n" + "="*60)
    print("MESHINFO-LITE TEMPLATE PREVIEW SERVER")
    print("="*60)
    print(f"Mesh Name: {config.get('mesh', 'name')}")
    print(f"Region: {config.get('mesh', 'region')}")
    print(f"Short Name: {config.get('mesh', 'short_name')}")
    print("="*60)
    print("\nStarting preview server...")
    print("Visit http://localhost:5000 to preview the customized templates")
    print("Press Ctrl+C to stop the server\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)