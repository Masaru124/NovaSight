import sqlite3

conn = sqlite3.connect('emotions.db')
c = conn.cursor()
c.execute('ALTER TABLE emotions ADD COLUMN user_id INTEGER')
conn.commit()
conn.close()
print("Added user_id column to emotions table")
