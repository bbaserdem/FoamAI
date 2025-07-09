import sqlite3
from datetime import datetime

# Connect to the database (this will create 'tasks.db' if it doesn't exist)
conn = sqlite3.connect('tasks.db')
cursor = conn.cursor()

# Create the tasks table with enhanced schema for pvserver tracking
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        status TEXT,
        message TEXT,
        file_path TEXT,
        case_path TEXT,
        pvserver_port INTEGER,
        pvserver_pid INTEGER,
        pvserver_status TEXT,
        pvserver_started_at TIMESTAMP,
        pvserver_last_activity TIMESTAMP,
        pvserver_error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# Check if we need to add new columns to existing table
try:
    # Try to add new columns (will fail silently if they already exist)
    cursor.execute('ALTER TABLE tasks ADD COLUMN case_path TEXT')
    print("Added case_path column")
except sqlite3.OperationalError:
    pass  # Column already exists

try:
    cursor.execute('ALTER TABLE tasks ADD COLUMN pvserver_port INTEGER')
    print("Added pvserver_port column")
except sqlite3.OperationalError:
    pass

try:
    cursor.execute('ALTER TABLE tasks ADD COLUMN pvserver_pid INTEGER')
    print("Added pvserver_pid column")
except sqlite3.OperationalError:
    pass

try:
    cursor.execute('ALTER TABLE tasks ADD COLUMN pvserver_status TEXT')
    print("Added pvserver_status column")
except sqlite3.OperationalError:
    pass

try:
    cursor.execute('ALTER TABLE tasks ADD COLUMN pvserver_started_at TIMESTAMP')
    print("Added pvserver_started_at column")
except sqlite3.OperationalError:
    pass

try:
    cursor.execute('ALTER TABLE tasks ADD COLUMN pvserver_last_activity TIMESTAMP')
    print("Added pvserver_last_activity column")
except sqlite3.OperationalError:
    pass

try:
    cursor.execute('ALTER TABLE tasks ADD COLUMN pvserver_error_message TEXT')
    print("Added pvserver_error_message column")
except sqlite3.OperationalError:
    pass

try:
    cursor.execute('ALTER TABLE tasks ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    print("Added created_at column")
except sqlite3.OperationalError:
    pass

conn.commit()
conn.close()

print("Database 'tasks.db' and table 'tasks' created/updated successfully with pvserver tracking.")
