"""Clear fictional demo claims and uploaded receipts. Preserve demo user accounts."""
from app import connect,UPLOADS,init_database
init_database()
with connect() as cx:
    cx.execute('DELETE FROM events')
    cx.execute('DELETE FROM claims')
    cx.execute('DELETE FROM sessions')
    cx.execute("DELETE FROM sqlite_sequence WHERE name IN ('claims','events')")
    cx.commit()
for f in UPLOADS.iterdir():
    if f.is_file():f.unlink()
print('Demo claims and receipts cleared. All fictional demo accounts remain available.')
