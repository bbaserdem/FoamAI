import sqlite3

# Connect to the database (this will create 'tasks.db' if it doesn't exist)
conn = sqlite3.connect('tasks.db')
cursor = conn.cursor()

# Create the tasks table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        status TEXT,
        message TEXT,
        file_path TEXT
    )
''')

conn.commit()
conn.close()

print("Database 'tasks.db' and table 'tasks' created successfully.")
