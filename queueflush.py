import sqlite3
conn = sqlite3.connect('jingle.db')
cursor = conn.cursor()
cursor.execute('delete from global_queue')
conn.commit()
conn.close()
