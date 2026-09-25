import sqlite3

conn = sqlite3.connect("data/historical_aws.db")
c = conn.cursor()
c.execute("""
    UPDATE aws_observations 
    SET latitude = 26.1175, longitude = 92.0835 
    WHERE station_id = '55D20BC6' OR (latitude = 0.0 AND longitude = 0.0)
""")
conn.commit()
print("Updated rows:", c.rowcount)

rows = c.execute("""
    SELECT DISTINCT station_id, station_name, latitude, longitude 
    FROM aws_observations 
    WHERE latitude < 6 OR latitude > 38 OR longitude < 65 OR longitude > 98.5
""").fetchall()
print("Remaining outside India:", len(rows))
if rows:
    for r in rows:
        print(r)
conn.close()
