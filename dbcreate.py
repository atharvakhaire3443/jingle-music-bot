import sqlite3
conn = sqlite3.connect('jingle.db')
cursor = conn.cursor()
cursor.execute(f"create table servers(name varchar(100) PRIMARY KEY,channel_id BIGINT)")

cursor.execute(f'create table global_queue(instance_id varchar(100) primary key,song_name varchar(200),server_name varchar(100),queue_position INTEGER)')

cursor.execute('create table global_playlist(instance_id varchar(100) primary key, song_name varchar(200), server_name varchar(100))')

conn.commit()
cursor.close()
